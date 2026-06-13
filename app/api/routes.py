"""
API route definitions.
All job-related endpoints live here — upload, status, results, and listing.
"""
import logging
import os
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models.schemas import (
    JobUploadResponse,
    JobStatusResponse,
    JobListResponse,
    JobListItem,
    JobResultsResponse,
    TransactionInDB,
    AnomalyFlagged,
    JobResultsSummary,
    MerchantStats,
    ErrorResponse,
)
from app.services.csv_processor import CSVProcessor
from app.services.db_service import DBService
from app.tasks.process_job import celery_app
from app.utils.constants import JOB_STATUS_COMPLETED

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

settings = get_settings()

# CSVs are saved to disk so the Celery worker (a separate container)
# can read them. Both containers mount the project at /app,
# so this path works for both.
CSV_UPLOAD_DIR = "/app/csv_uploads"
os.makedirs(CSV_UPLOAD_DIR, exist_ok=True)


def get_db() -> Session:
    """Get database session dependency"""
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/upload", response_model=JobUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> JobUploadResponse:
    """
    Upload a CSV file for processing
    
    Args:
        file: CSV file to upload
        db: Database session
        
    Returns:
        JobUploadResponse with job_id and status
        
    Raises:
        HTTPException: If validation fails
    """
    logger.info(f"Received upload request for file: {file.filename}")
    
    # Validate file type
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV file")
    
    # Check file size
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    
    if file_size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds {settings.MAX_FILE_SIZE_MB}MB limit",
        )
    
    # Decode and validate CSV
    try:
        csv_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")
    
    try:
        CSVProcessor.validate_csv(csv_content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Create the job entry, save the CSV file, and queue the processing task
    try:
        job = DBService.create_job(db, file.filename)
        
        # Write CSV to shared disk so the worker can pick it up
        csv_path = os.path.join(CSV_UPLOAD_DIR, f"{job.id}.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(csv_content)
        
        logger.info(f"CSV saved to {csv_path}")
        
        # Hand off to Celery — the API returns immediately after this
        task = celery_app.send_task(
            "tasks.process_job",
            args=[str(job.id)],
        )
        
        logger.info(f"Job {job.id} enqueued with task {task.id}")
        
        return JobUploadResponse(
            job_id=job.id,
            status="pending",
            message="Job queued for processing",
        )
        
    except Exception as e:
        logger.error(f"Error creating job: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create job")


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    """
    Get job status and summary
    
    Args:
        job_id: Job ID
        db: Database session
        
    Returns:
        JobStatusResponse with current status and optional summary
        
    Raises:
        HTTPException: If job not found
    """
    job = DBService.get_job(db, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    response = JobStatusResponse(
        job_id=job.id,
        status=job.status,
        filename=job.filename,
        row_count_raw=job.row_count_raw,
        row_count_clean=job.row_count_clean,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )
    
    # Include summary if completed
    if job.status == JOB_STATUS_COMPLETED:
        summary = DBService.get_job_summary(db, job_id)
        if summary:
            response.summary = {
                "total_spend_inr": summary.total_spend_inr,
                "total_spend_usd": summary.total_spend_usd,
                "anomaly_count": summary.anomaly_count,
                "risk_level": summary.risk_level,
            }
    
    return response


@router.get("/{job_id}/results", response_model=JobResultsResponse)
async def get_job_results(
    job_id: UUID,
    db: Session = Depends(get_db),
) -> JobResultsResponse:
    """
    Get full job results with transactions and analysis
    
    Args:
        job_id: Job ID
        db: Database session
        
    Returns:
        JobResultsResponse with all transaction details
        
    Raises:
        HTTPException: If job not found or not completed
    """
    job = DBService.get_job(db, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JOB_STATUS_COMPLETED:
        raise HTTPException(
            status_code=202,
            detail=f"Job is still {job.status}. Check status endpoint later.",
        )
    
    # Get transactions
    transactions = DBService.get_transactions(db, job_id)
    transaction_list = [
        TransactionInDB(
            txn_id=t.txn_id,
            date=t.date,
            merchant=t.merchant,
            amount=t.amount,
            currency=t.currency,
            status=t.status,
            category=t.category or t.llm_category,
            account_id=t.account_id,
            is_anomaly=t.is_anomaly,
            anomaly_reason=t.anomaly_reason,
            llm_category=t.llm_category,
        )
        for t in transactions
    ]
    
    # Get flagged anomalies
    flagged_anomalies = [
        AnomalyFlagged(
            txn_id=t.txn_id,
            merchant=t.merchant,
            amount=t.amount,
            currency=t.currency,
            reason=t.anomaly_reason,
        )
        for t in transactions
        if t.is_anomaly
    ]
    
    # Get category breakdown
    category_breakdown = DBService.get_category_breakdown(db, job_id)
    
    # Get summary
    summary_data = DBService.get_job_summary(db, job_id)
    
    if not summary_data:
        raise HTTPException(status_code=500, detail="Summary data not found")
    
    top_merchants = [
        MerchantStats(merchant=m["merchant"], total=m["total"])
        for m in summary_data.top_merchants
    ]
    
    summary = JobResultsSummary(
        total_spend_inr=summary_data.total_spend_inr,
        total_spend_usd=summary_data.total_spend_usd,
        top_merchants=top_merchants,
        anomaly_count=summary_data.anomaly_count,
        narrative=summary_data.narrative,
        risk_level=summary_data.risk_level,
    )
    
    return JobResultsResponse(
        job_id=job.id,
        status=job.status,
        transactions=transaction_list,
        flagged_anomalies=flagged_anomalies,
        category_breakdown=category_breakdown,
        summary=summary,
    )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
) -> JobListResponse:
    """
    List all jobs with optional status filtering
    
    Args:
        status: Optional status filter (pending, processing, completed, failed)
        db: Database session
        
    Returns:
        JobListResponse with list of jobs
    """
    jobs = DBService.get_all_jobs(db, status=status)
    
    job_items = [
        JobListItem(
            id=j.id,
            filename=j.filename,
            status=j.status,
            row_count_raw=j.row_count_raw,
            row_count_clean=j.row_count_clean,
            created_at=j.created_at,
            completed_at=j.completed_at,
        )
        for j in jobs
    ]
    
    return JobListResponse(jobs=job_items, total=len(job_items))


def get_csv_content_for_job(job_id: str) -> str:
    """Read the uploaded CSV for a job from the shared volume."""
    csv_path = os.path.join(CSV_UPLOAD_DIR, f"{job_id}.csv")
    if not os.path.exists(csv_path):
        raise ValueError(f"CSV not found for job {job_id} — expected at {csv_path}")
    with open(csv_path, "r", encoding="utf-8") as f:
        return f.read()
