"""
Database Service
Handles all database operations using SQLAlchemy
"""
import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from collections import defaultdict

from app.models.database import Job, Transaction, JobSummary
from app.utils.constants import JOB_STATUS_PENDING, JOB_STATUS_COMPLETED, JOB_STATUS_FAILED

logger = logging.getLogger(__name__)


class DBService:
    """Database operations service"""
    
    @staticmethod
    def create_job(db: Session, filename: str) -> Job:
        """
        Create a new job record
        
        Args:
            db: Database session
            filename: Name of uploaded file
            
        Returns:
            Created Job object
        """
        job = Job(
            filename=filename,
            status=JOB_STATUS_PENDING,
            row_count_raw=0,
            row_count_clean=0,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        logger.info(f"Created job {job.id} for file {filename}")
        return job
    
    @staticmethod
    def get_job(db: Session, job_id: UUID) -> Optional[Job]:
        """Get job by ID"""
        return db.query(Job).filter(Job.id == job_id).first()
    
    @staticmethod
    def update_job_status(db: Session, job_id: UUID, status: str, error_msg: str = None) -> None:
        """
        Update job status
        
        Args:
            db: Database session
            job_id: Job ID
            status: New status
            error_msg: Optional error message
        """
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = status
            if error_msg:
                job.error_message = error_msg
            db.commit()
            logger.info(f"Updated job {job_id} status to {status}")
    
    @staticmethod
    def save_transactions(
        db: Session, job_id: UUID, transactions: List[Dict[str, Any]]
    ) -> int:
        """
        Save cleaned transactions to database
        
        Args:
            db: Database session
            job_id: Job ID
            transactions: List of cleaned transaction dicts
            
        Returns:
            Number of transactions saved
        """
        count = 0
        for txn in transactions:
            db_txn = Transaction(
                job_id=job_id,
                txn_id=txn.get("txn_id"),
                date=txn.get("date"),
                merchant=txn.get("merchant"),
                amount=txn.get("amount"),
                currency=txn.get("currency"),
                status=txn.get("status"),
                category=txn.get("category"),
                account_id=txn.get("account_id"),
                is_anomaly=txn.get("is_anomaly", False),
                anomaly_reason=txn.get("anomaly_reason"),
            )
            db.add(db_txn)
            count += 1
        
        db.commit()
        logger.info(f"Saved {count} transactions for job {job_id}")
        return count
    
    @staticmethod
    def get_transactions(db: Session, job_id: UUID) -> List[Transaction]:
        """Get all transactions for a job"""
        return db.query(Transaction).filter(Transaction.job_id == job_id).all()
    
    @staticmethod
    def update_transaction_categories(
        db: Session, job_id: UUID, categorizations: Dict[str, str]
    ) -> None:
        """
        Update transactions with LLM categories
        
        Args:
            db: Database session
            job_id: Job ID
            categorizations: Dict mapping merchant to category
        """
        transactions = db.query(Transaction).filter(
            Transaction.job_id == job_id,
            Transaction.category == "Uncategorised"
        ).all()
        
        updated = 0
        for txn in transactions:
            if txn.merchant in categorizations:
                txn.llm_category = categorizations[txn.merchant]
                updated += 1
        
        if updated > 0:
            db.commit()
            logger.info(f"Updated {updated} transaction categories for job {job_id}")
    
    @staticmethod
    def save_job_summary(
        db: Session,
        job_id: UUID,
        total_spend_inr: float,
        total_spend_usd: float,
        top_merchants: List[Dict[str, Any]],
        anomaly_count: int,
        narrative: str,
        risk_level: str,
    ) -> JobSummary:
        """
        Save job summary
        
        Args:
            db: Database session
            job_id: Job ID
            total_spend_inr: Total INR spend
            total_spend_usd: Total USD spend
            top_merchants: List of top merchants
            anomaly_count: Number of anomalies
            narrative: Summary narrative
            risk_level: Risk assessment
            
        Returns:
            Created JobSummary
        """
        summary = JobSummary(
            job_id=job_id,
            total_spend_inr=total_spend_inr,
            total_spend_usd=total_spend_usd,
            top_merchants=top_merchants,
            anomaly_count=anomaly_count,
            narrative=narrative,
            risk_level=risk_level,
        )
        db.add(summary)
        db.commit()
        db.refresh(summary)
        logger.info(f"Saved summary for job {job_id}")
        return summary
    
    @staticmethod
    def get_job_summary(db: Session, job_id: UUID) -> Optional[JobSummary]:
        """Get summary for a job"""
        return db.query(JobSummary).filter(JobSummary.job_id == job_id).first()
    
    @staticmethod
    def get_all_jobs(db: Session, status: Optional[str] = None) -> List[Job]:
        """Get all jobs with optional status filter"""
        query = db.query(Job)
        if status:
            query = query.filter(Job.status == status)
        return query.order_by(Job.created_at.desc()).all()
    
    @staticmethod
    def finalize_job(
        db: Session,
        job_id: UUID,
        clean_count: int,
    ) -> None:
        """
        Finalize job by updating counts and status
        
        Args:
            db: Database session
            job_id: Job ID
            clean_count: Final clean row count
        """
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.row_count_clean = clean_count
            job.status = JOB_STATUS_COMPLETED
            from datetime import datetime
            job.completed_at = datetime.utcnow()
            db.commit()
            logger.info(f"Finalized job {job_id}")
    
    @staticmethod
    def get_category_breakdown(db: Session, job_id: UUID) -> Dict[str, float]:
        """
        Calculate spending by category
        
        Args:
            db: Database session
            job_id: Job ID
            
        Returns:
            Dict mapping category to total spend
        """
        transactions = db.query(Transaction).filter(
            Transaction.job_id == job_id,
            Transaction.status == "SUCCESS"
        ).all()
        
        breakdown = defaultdict(float)
        for txn in transactions:
            category = txn.category or "Other"
            breakdown[category] += txn.amount or 0
        
        return dict(breakdown)
    
    @staticmethod
    def get_top_merchants(db: Session, job_id: UUID, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Get top merchants by spending
        
        Args:
            db: Database session
            job_id: Job ID
            limit: Number of top merchants
            
        Returns:
            List of dicts with merchant and total
        """
        transactions = db.query(Transaction).filter(
            Transaction.job_id == job_id,
            Transaction.status == "SUCCESS"
        ).all()
        
        merchant_totals = defaultdict(float)
        for txn in transactions:
            merchant = txn.merchant or "Unknown"
            merchant_totals[merchant] += txn.amount or 0
        
        # Sort by total descending
        sorted_merchants = sorted(
            merchant_totals.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        return [
            {"merchant": merchant, "total": total}
            for merchant, total in sorted_merchants
        ]
    
    @staticmethod
    def get_anomaly_count(db: Session, job_id: UUID) -> int:
        """Get count of flagged anomalies"""
        return db.query(Transaction).filter(
            Transaction.job_id == job_id,
            Transaction.is_anomaly == True
        ).count()
    
    @staticmethod
    def get_total_spend(db: Session, job_id: UUID) -> tuple[float, float]:
        """
        Get total spend by currency
        
        Args:
            db: Database session
            job_id: Job ID
            
        Returns:
            Tuple of (total_inr, total_usd)
        """
        transactions = db.query(Transaction).filter(
            Transaction.job_id == job_id,
            Transaction.status == "SUCCESS"
        ).all()
        
        total_inr = 0.0
        total_usd = 0.0
        
        for txn in transactions:
            amount = txn.amount or 0
            if txn.currency == "INR":
                total_inr += amount
            elif txn.currency == "USD":
                total_usd += amount
        
        return total_inr, total_usd
