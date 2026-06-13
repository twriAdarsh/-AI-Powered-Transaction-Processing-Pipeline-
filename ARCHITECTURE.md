# AI-Powered Transaction Processing Pipeline - System Architecture

## 1. SYSTEM ARCHITECTURE OVERVIEW

### High-Level Architecture Diagram
```
┌─────────────────┐
│   User/Client   │
└────────┬────────┘
         │
         │ HTTP
         ▼
┌──────────────────────────────┐
│     FastAPI Backend          │
│  ┌─────────────────────────┐ │
│  │ POST   /jobs/upload     │ │  File validation
│  │ GET    /jobs/{id}/status│ │  Job polling
│  │ GET    /jobs/{id}/results│ │  Result retrieval
│  │ GET    /jobs            │ │  Job listing
│  └─────────────────────────┘ │
└──────────┬───────────────────┘
           │
      ┌────┼────┐
      │    │    │
      ▼    ▼    ▼
┌──────────────────────────────────────┐
│  PostgreSQL Database                 │
│  ├─ Job (status, metadata)          │
│  ├─ Transaction (cleaned data)       │
│  └─ JobSummary (results)             │
└──────────────────────────────────────┘
      │    │    │
      ▼    │    ▼
┌──────────────────────────────────────┐
│     Redis Job Queue                  │
│     (Celery Message Broker)          │
└──────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────┐
│  Celery Worker Process               │
│                                      │
│  Step 1: Data Cleaning               │
│  ├─ Normalize dates (ISO 8601)      │
│  ├─ Strip currency symbols          │
│  ├─ Uppercase status values         │
│  ├─ Fill missing categories         │
│  └─ Remove duplicate rows           │
│                                      │
│  Step 2: Anomaly Detection           │
│  ├─ Statistical outliers (3x median)│
│  └─ Currency/merchant mismatches    │
│                                      │
│  Step 3: LLM Classification (Batch)  │
│  ├─ Categorize missing categories   │
│  └─ Retry logic (3x exponential)    │
│                                      │
│  Step 4: LLM Narrative Summary       │
│  ├─ Generate risk assessment        │
│  └─ Create spending narrative       │
│                                      │
└──────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────┐
│     Gemini 1.5 Flash LLM API         │
│  (Classification & Summarization)    │
└──────────────────────────────────────┘
```

---

## 2. FOLDER STRUCTURE

```
devops_intern/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app initialization
│   ├── config.py                        # Configuration management
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py                    # All API endpoints
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py                  # SQLAlchemy models
│   │   └── schemas.py                   # Pydantic schemas
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── csv_processor.py             # CSV reading & validation
│   │   ├── data_cleaner.py              # Data cleaning logic
│   │   ├── anomaly_detector.py          # Anomaly detection
│   │   ├── llm_service.py               # Gemini API integration
│   │   └── db_service.py                # Database operations
│   │
│   ├── tasks/
│   │   ├── __init__.py
│   │   └── process_job.py               # Celery task definition
│   │
│   └── utils/
│       ├── __init__.py
│       ├── constants.py                 # Constants & enums
│       └── helpers.py                   # Utility functions
│
├── tests/
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_cleaner.py
│   └── test_anomaly.py
│
├── Dockerfile                           # FastAPI container
├── Dockerfile.worker                    # Celery worker container
├── docker-compose.yml                   # Orchestration
├── requirements.txt                     # Python dependencies
├── .env.example                         # Environment template
├── README.md                            # Documentation
├── ARCHITECTURE.md                      # This file
└── DIAGRAM.md                           # draw.io diagram spec
```

---

## 3. DATABASE SCHEMA

### Job Table
```sql
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, processing, completed, failed
    row_count_raw INTEGER,
    row_count_clean INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);
```

### Transaction Table
```sql
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    txn_id VARCHAR(50),
    date DATE,
    merchant VARCHAR(255),
    amount DECIMAL(15, 2),
    currency VARCHAR(3),
    status VARCHAR(20),  -- SUCCESS, FAILED, PENDING
    category VARCHAR(50),
    account_id VARCHAR(50),
    is_anomaly BOOLEAN DEFAULT FALSE,
    anomaly_reason VARCHAR(255),
    llm_category VARCHAR(50),  -- Result from LLM
    llm_raw_response TEXT,
    llm_failed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### JobSummary Table
```sql
CREATE TABLE job_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
    total_spend_inr DECIMAL(15, 2),
    total_spend_usd DECIMAL(15, 2),
    top_merchants JSONB,  -- JSON: [{"merchant": "...", "total": ...}, ...]
    anomaly_count INTEGER,
    narrative TEXT,  -- 2-3 sentence summary
    risk_level VARCHAR(20),  -- low, medium, high
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Indexes
```sql
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at);
CREATE INDEX idx_transactions_job_id ON transactions(job_id);
CREATE INDEX idx_transactions_account_id ON transactions(account_id);
CREATE INDEX idx_transactions_is_anomaly ON transactions(is_anomaly);
```

---

## 4. API DESIGN

### Endpoint 1: POST /jobs/upload
**Purpose**: Accept CSV file, validate, create Job record, enqueue processing

**Request**:
```http
POST /jobs/upload HTTP/1.1
Content-Type: multipart/form-data

file: <binary CSV file>
```

**Response** (201 Created):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Job queued for processing"
}
```

**Validations**:
- File must be CSV
- Must have required columns
- Max file size: 10MB
- Return 400 if validation fails

---

### Endpoint 2: GET /jobs/{job_id}/status
**Purpose**: Poll job status and high-level summary

**Request**:
```http
GET /jobs/550e8400-e29b-41d4-a716-446655440000/status HTTP/1.1
```

**Response** (200 OK):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",  // or: completed, failed
  "filename": "transactions.csv",
  "row_count_raw": 90,
  "row_count_clean": 85,
  "created_at": "2024-06-12T10:00:00Z",
  "completed_at": null,
  "summary": {
    "total_spend_inr": 450000.50,
    "total_spend_usd": 25000.00,
    "anomaly_count": 12,
    "risk_level": "medium"
  }
}
```

**Error Response** (404):
```json
{
  "detail": "Job not found"
}
```

---

### Endpoint 3: GET /jobs/{job_id}/results
**Purpose**: Full structured output (only available when completed)

**Request**:
```http
GET /jobs/550e8400-e29b-41d4-a716-446655440000/results HTTP/1.1
```

**Response** (200 OK):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "transactions": [
    {
      "txn_id": "TXN1065",
      "date": "2024-09-04",
      "merchant": "Flipkart",
      "amount": 10882.55,
      "currency": "INR",
      "status": "SUCCESS",
      "category": "Shopping",
      "account_id": "ACC003",
      "is_anomaly": false,
      "anomaly_reason": null,
      "llm_category": "Shopping"
    }
    // ... more transactions
  ],
  "flagged_anomalies": [
    {
      "txn_id": "TXN2001",
      "merchant": "Flipkart",
      "amount": 146100.68,
      "currency": "INR",
      "reason": "Statistical outlier (3x+ median)"
    }
    // ... more anomalies
  ],
  "category_breakdown": {
    "Shopping": 125000.00,
    "Food": 45000.00,
    "Travel": 60000.00,
    "Transport": 55000.00,
    "Utilities": 80000.00,
    "Entertainment": 25000.00,
    "Cash Withdrawal": 35000.00,
    "Other": 10000.00
  },
  "summary": {
    "total_spend_inr": 450000.00,
    "total_spend_usd": 25000.00,
    "top_merchants": [
      {"merchant": "Flipkart", "total": 85000.00},
      {"merchant": "Ola", "total": 75000.00},
      {"merchant": "IRCTC", "total": 65000.00}
    ],
    "anomaly_count": 12,
    "narrative": "The user's spending is primarily concentrated in shopping and transportation. Several large transactions were flagged as statistical outliers exceeding 3x the account median. Overall spending shows moderate risk with some suspicious high-value transactions.",
    "risk_level": "medium"
  }
}
```

**Error Response** (202 Accepted - Still Processing):
```json
{
  "detail": "Job is still processing. Check status endpoint later."
}
```

---

### Endpoint 4: GET /jobs
**Purpose**: List all jobs with optional filtering

**Request**:
```http
GET /jobs HTTP/1.1
GET /jobs?status=completed HTTP/1.1
```

**Response** (200 OK):
```json
{
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "transactions.csv",
      "status": "completed",
      "row_count_raw": 90,
      "row_count_clean": 85,
      "created_at": "2024-06-12T10:00:00Z",
      "completed_at": "2024-06-12T10:15:30Z"
    }
    // ... more jobs
  ],
  "total": 5
}
```

---

## 5. DATA CLEANING LOGIC

### Step 1: Date Normalization
- Input: Mixed formats (DD-MM-YYYY, YYYY/MM/DD)
- Output: ISO 8601 (YYYY-MM-DD)
- Logic: Detect format, parse, re-format

### Step 2: Amount Cleaning
- Remove $ prefix if present
- Convert to float
- Validate it's numeric

### Step 3: Status Normalization
- Uppercase: "success" → "SUCCESS", "failed" → "FAILED", "pending" → "PENDING"
- Validate against allowed values

### Step 4: Category Filling
- If empty: Set to "Uncategorised"
- Later: Call LLM for categorization

### Step 5: Duplicate Removal
- Group by all columns except internal IDs
- Keep first occurrence
- Track row count before/after

---

## 6. ANOMALY DETECTION

### Rule 1: Statistical Outliers
- For each account_id, calculate median transaction amount
- Flag if: `amount > (median * 3)`
- Reason: "Statistical outlier (3x+ median)"

### Rule 2: Currency/Merchant Mismatch
- Domestic brands (hardcoded list):
  - Swiggy, Zomato, Ola, IRCTC, Flipkart, Amazon, BookMyShow, MakeMyTrip (INR-only), Jio Recharge, HDFC ATM
- Flag if: currency == "USD" AND merchant in domestic_list
- Reason: "Currency mismatch with domestic merchant"

---

## 7. LLM INTEGRATION

### Service 1: Batched Categorization
**Input**: List of transaction texts (merchant names)
**Output**: Assigned categories

**Batch Strategy**:
- Group uncategorized transactions into batches of 10-20
- Single LLM call per batch with structured prompt
- Categories: Food, Shopping, Travel, Transport, Utilities, Cash Withdrawal, Entertainment, Other

**Retry Logic**:
- Max retries: 3
- Backoff: 1s, 2s, 4s (exponential)
- If all fail: Mark transaction with `llm_failed = True`

### Service 2: Narrative Summary
**Input**: All cleaned transactions, anomalies, category breakdown
**Output**: JSON with narrative, risk level, top merchants

**Prompt Structure**:
```
Analyze this transaction data:
- Total transactions: X
- Total spend INR: Y
- Total spend USD: Z
- Flagged anomalies: N
- Top categories: [...]

Provide:
1. 2-3 sentence spending narrative
2. Risk assessment (low/medium/high)
3. Top 3 merchants by spend
4. Key observations

Format as JSON.
```

---

## 8. CELERY TASK FLOW

### Task: process_job
```
1. Fetch Job from DB (job_id)
2. Fetch raw CSV from file storage (or DB)
3. Update Job status → "processing"
4. Call data_cleaner.clean() → cleaned_data
5. Save cleaned transactions to DB
6. Call anomaly_detector.detect() → anomalies
7. Update transaction records with is_anomaly flag
8. Call llm_service.categorize_batch() → categories
9. Update transaction records with llm_category
10. Call llm_service.generate_summary() → summary
11. Save JobSummary to DB
12. Update Job status → "completed"
13. On error: Update status → "failed", log error_message
```

---

## 9. IMPLEMENTATION ROADMAP

### Phase 1: Foundation (Day 1)
- [ ] Set up FastAPI project structure
- [ ] Configure PostgreSQL with SQLAlchemy
- [ ] Set up Redis & Celery
- [ ] Create database models & schemas
- [ ] Implement Pydantic validators

### Phase 2: API Layer (Day 1)
- [ ] Implement POST /jobs/upload endpoint
- [ ] Implement GET /jobs/{job_id}/status endpoint
- [ ] Implement GET /jobs/{job_id}/results endpoint
- [ ] Implement GET /jobs endpoint with filtering
- [ ] Add error handling & validation

### Phase 3: Data Processing (Day 2)
- [ ] Implement CSV cleaning pipeline
- [ ] Implement anomaly detection logic
- [ ] Implement database save operations
- [ ] Create unit tests for cleaner & detector

### Phase 4: LLM Integration (Day 2)
- [ ] Set up Gemini API client
- [ ] Implement batched categorization
- [ ] Implement narrative summary generation
- [ ] Implement retry logic with backoff
- [ ] Handle LLM failures gracefully

### Phase 5: Celery Worker (Day 2)
- [ ] Create Celery app configuration
- [ ] Implement process_job task
- [ ] Integrate all sub-services
- [ ] Test end-to-end processing

### Phase 6: Containerization (Day 3)
- [ ] Create Dockerfile for FastAPI
- [ ] Create Dockerfile for Celery worker
- [ ] Create docker-compose.yml
- [ ] Test: docker compose up

### Phase 7: Documentation (Day 3)
- [ ] Write README.md
- [ ] Create curl examples
- [ ] Create architecture diagram specification
- [ ] Prepare video content outline

---

## 10. TECHNOLOGY DECISIONS

### Why FastAPI?
- Automatic OpenAPI documentation
- Built-in request validation (Pydantic)
- Async support for high concurrency
- Modern Python async/await syntax
- Fast performance

### Why Celery + Redis?
- Industry standard for job queues
- Reliable task delivery
- Retry logic built-in
- Horizontal scaling capability
- Redis for speed & simplicity

### Why PostgreSQL?
- JSONB support for flexible summaries
- Strong ACID guarantees
- Perfect for relational data (Job → Transactions)
- UUID support (no auto-increment bottleneck)

### Why Gemini 1.5 Flash?
- Free tier available
- Fast inference
- Good for categorization tasks
- Batch processing friendly

---

## 11. ERROR HANDLING STRATEGY

### At API Layer
- 400: Invalid CSV format, missing columns
- 404: Job not found
- 409: Job already processing (race condition)
- 422: Validation error (Pydantic)
- 500: Internal server error

### At Celery Layer
- Retry failed LLM calls (3x with backoff)
- Log detailed error messages
- Mark job as failed with reason
- Preserve partial results where possible

### At Database Layer
- Connection pooling to handle disconnects
- Transactional integrity for Job updates
- Soft deletes for audit trail (optional)

---

## 12. SCALABILITY CONSIDERATIONS

### Current Bottlenecks (for 100x scale)
1. **PostgreSQL Connection Pool** → Increase max connections
2. **Celery Worker Throughput** → Add more workers
3. **LLM API Rate Limits** → Queue batches, add request throttling
4. **Memory Usage** → Stream CSV instead of loading entirely
5. **File Storage** → Use S3 instead of local filesystem

### Production Improvements
1. **Multi-worker Celery setup** with load balancing
2. **PostgreSQL replication** for read scaling
3. **Redis persistence** (AOF or RDB)
4. **Horizontal scaling** with Docker Swarm/Kubernetes
5. **Caching layer** for frequently accessed jobs
6. **Monitoring** with Prometheus/Grafana
7. **Logging** with ELK stack

---

## Architecture Approved? ✓

This architecture is **production-ready** for the internship assignment. It demonstrates:
- ✓ Separation of concerns (models, services, tasks)
- ✓ Asynchronous job processing
- ✓ Robust error handling
- ✓ Scalable design
- ✓ Complete containerization
- ✓ Clear data flow

**Proceed to Phase 1 implementation.**
