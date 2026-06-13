"""
Pydantic schemas for request/response validation
Defines data models for API contracts
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


# ============= Job Schemas =============

class JobUploadResponse(BaseModel):
    """Response for POST /jobs/upload"""
    job_id: UUID
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Response for GET /jobs/{job_id}/status"""
    job_id: UUID
    status: str
    filename: str
    row_count_raw: Optional[int]
    row_count_clean: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]
    summary: Optional[Dict[str, Any]] = None


class JobListItem(BaseModel):
    """Single job in job list"""
    job_id: UUID = Field(alias="id")
    filename: str
    status: str
    row_count_raw: Optional[int]
    row_count_clean: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Response for GET /jobs"""
    jobs: List[JobListItem]
    total: int


# ============= Transaction Schemas =============

class TransactionInDB(BaseModel):
    """Transaction model for results output"""
    txn_id: Optional[str]
    date: Optional[str]
    merchant: Optional[str]
    amount: Optional[float]
    currency: Optional[str]
    status: Optional[str]
    category: Optional[str]
    account_id: Optional[str]
    is_anomaly: bool
    anomaly_reason: Optional[str]
    llm_category: Optional[str]


class AnomalyFlagged(BaseModel):
    """Anomaly item in results"""
    txn_id: Optional[str]
    merchant: Optional[str]
    amount: Optional[float]
    currency: Optional[str]
    reason: Optional[str]


class MerchantStats(BaseModel):
    """Top merchant info"""
    merchant: str
    total: float


class JobResultsSummary(BaseModel):
    """Summary section of job results"""
    total_spend_inr: Optional[float]
    total_spend_usd: Optional[float]
    top_merchants: List[MerchantStats]
    anomaly_count: int
    narrative: str
    risk_level: str


class JobResultsResponse(BaseModel):
    """Response for GET /jobs/{job_id}/results"""
    job_id: UUID
    status: str
    transactions: List[TransactionInDB]
    flagged_anomalies: List[AnomalyFlagged]
    category_breakdown: Dict[str, float]
    summary: JobResultsSummary


class ErrorResponse(BaseModel):
    """Error response"""
    detail: str


# ============= Internal Schemas =============

class CleanedTransaction(BaseModel):
    """Internal representation after cleaning"""
    txn_id: Optional[str]
    date: str  # ISO 8601
    merchant: str
    amount: float
    currency: str  # INR or USD
    status: str  # SUCCESS, FAILED, PENDING
    category: str  # Never empty after cleaning
    account_id: str
    original_notes: Optional[str]
    
    class Config:
        from_attributes = True
