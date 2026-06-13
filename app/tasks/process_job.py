"""
Celery task that runs the full transaction processing pipeline.
This is the main worker — it gets triggered after a CSV upload.
"""
import logging
from typing import Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session
from celery import Celery, Task
from celery.exceptions import SoftTimeLimitExceeded

from app.config import get_settings
from app.models.database import Base
from app.services.csv_processor import CSVProcessor
from app.services.data_cleaner import DataCleaner
from app.services.anomaly_detector import AnomalyDetector
from app.services.llm_service import LLMService
from app.services.db_service import DBService
from app.utils.constants import (
    JOB_STATUS_PROCESSING,
    JOB_STATUS_FAILED,
    BATCH_SIZE_LLM,
    DEFAULT_CATEGORY,
)

logger = logging.getLogger(__name__)

# One Celery app shared between the API (to enqueue tasks)
# and the worker (to consume them)
settings = get_settings()
celery_app = Celery(
    "transaction_processor",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,       # hard kill after 30 min
    task_soft_time_limit=25 * 60,  # soft warning at 25 min (gives time to clean up)
)


@celery_app.task(bind=True, name="tasks.process_job")
def process_job(self, job_id: str) -> Dict[str, Any]:
    """
    Main task: Process uploaded CSV file through entire pipeline
    
    Args:
        job_id: UUID of the job to process
        
    Returns:
        Dict with processing result
    """
    logger.info(f"Starting job processing for {job_id}")
    
    try:
        # Import here to avoid circular imports
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        # Create database session
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        # Step 1: Get job and validate
        job_uuid = UUID(job_id)
        job = DBService.get_job(db, job_uuid)
        
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        logger.info(f"Processing job {job_id}: {job.filename}")
        
        # Update status to processing
        DBService.update_job_status(db, job_uuid, JOB_STATUS_PROCESSING)
        
        # Step 2: Read CSV from file (stored in job metadata)
        # In a real scenario, you'd read from S3 or filesystem
        # For now, we'll use the filename as a key to retrieve from DB
        csv_content = _get_csv_content(db, job_id)
        
        # Step 3: Validate CSV
        CSVProcessor.validate_csv(csv_content)
        
        # Step 2: Read and parse the CSV rows
        raw_rows, raw_count = CSVProcessor.read_csv(csv_content)
        job.row_count_raw = raw_count
        db.commit()
        
        logger.info(f"Read {raw_count} rows from {job.filename}")
        
        # Step 5: Remove duplicates
        unique_rows = CSVProcessor.remove_duplicates(raw_rows)
        logger.info(f"After deduplication: {len(unique_rows)} rows")
        
        # Step 6: Clean data
        cleaned_transactions, clean_errors = DataCleaner.clean_batch(unique_rows)
        
        if clean_errors:
            logger.warning(f"Cleaning errors: {clean_errors}")
        
        logger.info(f"Cleaned {len(cleaned_transactions)} transactions")
        
        # Step 5: Flag outliers and currency mismatches
        AnomalyDetector.detect_anomalies(cleaned_transactions)
        anomaly_count = sum(1 for t in cleaned_transactions if t.get("is_anomaly"))
        logger.info(f"Detected {anomaly_count} anomalies")
        
        # Step 6: Persist cleaned transactions
        DBService.save_transactions(db, job_uuid, cleaned_transactions)
        
        # Figure out which merchants still need a category from the LLM
        merchants_to_categorize = list(set(
            txn["merchant"]
            for txn in cleaned_transactions
            if txn.get("category") == DEFAULT_CATEGORY
        ))
        
        logger.info(f"Found {len(merchants_to_categorize)} merchants to categorize")
        
        # Step 10: Call LLM for categorization in batches
        if merchants_to_categorize:
            llm_service = LLMService()
            
            for i in range(0, len(merchants_to_categorize), BATCH_SIZE_LLM):
                batch = merchants_to_categorize[i:i + BATCH_SIZE_LLM]
                logger.info(f"Categorizing batch {i // BATCH_SIZE_LLM + 1}")
                
                categorizations = llm_service.categorize_batch(batch)
                
                # Update transactions with LLM categories
                for txn in cleaned_transactions:
                    if txn["merchant"] in categorizations:
                        txn["llm_category"] = categorizations[txn["merchant"]]
                
                DBService.update_transaction_categories(db, job_uuid, categorizations)
        
        # Step 11: Generate summary statistics
        total_inr, total_usd = DBService.get_total_spend(db, job_uuid)
        category_breakdown = DBService.get_category_breakdown(db, job_uuid)
        top_merchants = DBService.get_top_merchants(db, job_uuid, limit=3)
        
        logger.info(
            f"Summary: INR={total_inr:.2f}, USD={total_usd:.2f}, "
            f"Anomalies={anomaly_count}, Categories={len(category_breakdown)}"
        )
        
        # Step 12: Generate narrative summary with LLM
        llm_service = LLMService()
        summary_data = llm_service.generate_summary(
            total_spend_inr=total_inr,
            total_spend_usd=total_usd,
            top_merchants=top_merchants,
            anomaly_count=anomaly_count,
            category_breakdown=category_breakdown,
        )
        
        # Step 13: Save summary to DB
        DBService.save_job_summary(
            db,
            job_uuid,
            total_spend_inr=total_inr,
            total_spend_usd=total_usd,
            top_merchants=top_merchants,
            anomaly_count=anomaly_count,
            narrative=summary_data.get("narrative", ""),
            risk_level=summary_data.get("risk_level", "medium"),
        )
        
        # Step 14: Finalize job
        DBService.finalize_job(db, job_uuid, len(cleaned_transactions))
        
        logger.info(f"Job {job_id} completed successfully")
        
        db.close()
        
        return {
            "status": "success",
            "job_id": job_id,
            "rows_processed": len(cleaned_transactions),
            "anomalies_detected": anomaly_count,
        }
        
    except SoftTimeLimitExceeded:
        logger.error(f"Job {job_id} exceeded time limit")
        try:
            db = _get_db_session()
            DBService.update_job_status(
                db,
                UUID(job_id),
                JOB_STATUS_FAILED,
                "Job execution exceeded maximum time limit",
            )
            db.close()
        except Exception as e:
            logger.error(f"Failed to update job status: {str(e)}")
        raise
        
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {str(e)}", exc_info=True)
        
        try:
            db = _get_db_session()
            DBService.update_job_status(
                db,
                UUID(job_id),
                JOB_STATUS_FAILED,
                f"Error: {str(e)}",
            )
            db.close()
        except Exception as db_error:
            logger.error(f"Failed to update job status: {str(db_error)}")
        
        raise


def _get_db_session():
    """Create a new database session"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _get_csv_content(db: Session, job_id: str) -> str:
    """
    Retrieve CSV content from temporary storage
    In production, this would read from S3 or persistent storage
    """
    # Import here to avoid circular imports
    from app.api.routes import get_csv_content_for_job
    
    return get_csv_content_for_job(job_id)
