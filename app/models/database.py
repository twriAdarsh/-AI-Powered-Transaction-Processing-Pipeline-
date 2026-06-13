"""
SQLAlchemy ORM Models
Defines all database tables: Job, Transaction, JobSummary
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

Base = declarative_base()


class Job(Base):
    """Represents an uploaded job for processing transactions"""
    __tablename__ = "jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, processing, completed, failed
    row_count_raw = Column(Integer)
    row_count_clean = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="job", cascade="all, delete-orphan")
    summary = relationship("JobSummary", back_populates="job", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Job {self.id}: {self.filename} ({self.status})>"


class Transaction(Base):
    """Represents a single transaction from the CSV"""
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    txn_id = Column(String(50))
    date = Column(String(20))  # ISO 8601 format after cleaning
    merchant = Column(String(255))
    amount = Column(Float)
    currency = Column(String(3))  # INR, USD
    status = Column(String(20))  # SUCCESS, FAILED, PENDING
    category = Column(String(50))
    account_id = Column(String(50))
    
    # Anomaly detection
    is_anomaly = Column(Boolean, default=False)
    anomaly_reason = Column(String(255))
    
    # LLM results
    llm_category = Column(String(50))  # Result from LLM if original was empty
    llm_raw_response = Column(Text)  # Raw response from LLM for debugging
    llm_failed = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction {self.txn_id}: {self.merchant} {self.amount} {self.currency}>"


class JobSummary(Base):
    """Stores the final summary for a completed job"""
    __tablename__ = "job_summaries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), unique=True, nullable=False)
    
    total_spend_inr = Column(Float)
    total_spend_usd = Column(Float)
    top_merchants = Column(JSON)  # List of dicts: [{"merchant": "...", "total": ...}, ...]
    anomaly_count = Column(Integer)
    narrative = Column(Text)  # 2-3 sentence summary
    risk_level = Column(String(20))  # low, medium, high
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="summary")
    
    def __repr__(self):
        return f"<JobSummary {self.job_id}: {self.risk_level}>"
