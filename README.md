# AI-Powered Transaction Processing Pipeline

Backend + DevOps Internship Assignment - Complete Implementation

## Overview

This is a production-grade backend API that processes financial transactions asynchronously using a job queue system. It includes:

- **FastAPI** web framework with async request handling
- **PostgreSQL** database for persistent storage
- **Redis + Celery** for asynchronous job queue processing
- **Gemini LLM** for intelligent transaction categorization and narrative generation
- **Docker & Docker Compose** for containerization and orchestration
- **Comprehensive error handling** with retry logic and exponential backoff

### Features

✅ CSV file upload and validation
✅ Asynchronous transaction processing
✅ Data cleaning (date normalization, currency symbols, case standardization)
✅ Anomaly detection (statistical outliers + currency/merchant mismatches)
✅ Batch LLM-based transaction categorization
✅ LLM-generated narrative summary with risk assessment
✅ Retry logic with exponential backoff for LLM failures
✅ RESTful API with polling and results retrieval
✅ Full Docker containerization - single command deployment

---

## System Architecture

```mermaid
graph TD
    Client[Client / Swagger UI] -->|POST /jobs/upload| API[FastAPI Server]
    API -->|1. Write CSV| Vol[(Shared Volume /app/csv_uploads)]
    API -->|2. Create Job| DB[(PostgreSQL)]
    API -->|3. Enqueue Task| Redis[(Redis Broker)]
    
    Redis -->|4. Dequeue Task| Worker[Celery Worker]
    Worker -->|5. Read CSV| Vol
    
    subgraph Celery Processing Pipeline
        direction TB
        W1[1. Data Cleaning] --> W2[2. Anomaly Detection]
        W2 --> W3[3. LLM Categorization]
        W3 --> W4[4. LLM Narrative Generation]
    end
    
    Worker -->|Execute Pipeline| W1
    W3 -.->|API Call| LLM((Google Gemini API))
    W4 -.->|API Call| LLM
    
    W4 -->|6. Save Results & Update Status| DB
    Client -->|GET /jobs/{id}/results| API
    API -->|Read Results| DB
```

> **Note:** A detailed draw.io HLD diagram is also available in the repository as [`architecture_diagram.drawio`](architecture_diagram.drawio).

---

## Quick Start

### Prerequisites

- Docker & Docker Compose (version 3.9+)
- Gemini API key (get free at https://ai.google.dev/)
- Unix-like environment (Linux, macOS, or WSL on Windows)

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repo_url>
cd devops_intern

# Copy environment template
cp .env.example .env

# Add your Gemini API key to .env
# Edit .env and set: GEMINI_API_KEY=your_key_here
```

### 2. Start All Services

```bash
# Build and start all containers
docker compose up

# Wait for all services to be healthy:
# - PostgreSQL: Ready
# - Redis: Ready
# - FastAPI: Running on http://localhost:8000
# - Celery Worker: Listening for tasks
```

### 3. Verify Setup

```bash
# Check API health
curl http://localhost:8000/health

# Response: {"status":"ok","version":"1.0.0"}

# View API documentation
# Open browser to: http://localhost:8000/docs
```

---

## API Endpoints

### 1. Upload CSV File

**Endpoint**: `POST /jobs/upload`

**Request**:
```bash
curl -X POST "http://localhost:8000/jobs/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@transactions.csv"
```

**Response** (201 Created):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Job queued for processing"
}
```

**Save the `job_id` for polling results**

---

### 2. Check Job Status

**Endpoint**: `GET /jobs/{job_id}/status`

**Request**:
```bash
curl "http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000/status"
```

**Response (while processing)**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "filename": "transactions.csv",
  "row_count_raw": 90,
  "row_count_clean": 85,
  "created_at": "2024-06-12T10:00:00Z",
  "completed_at": null,
  "summary": null
}
```

**Response (completed)**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "filename": "transactions.csv",
  "row_count_raw": 90,
  "row_count_clean": 85,
  "created_at": "2024-06-12T10:00:00Z",
  "completed_at": "2024-06-12T10:05:30Z",
  "summary": {
    "total_spend_inr": 450000.50,
    "total_spend_usd": 25000.00,
    "anomaly_count": 12,
    "risk_level": "medium"
  }
}
```

---

### 3. Get Full Results

**Endpoint**: `GET /jobs/{job_id}/results`

**Request**:
```bash
curl "http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000/results"
```

**Response**:
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
      "llm_category": null
    }
  ],
  "flagged_anomalies": [
    {
      "txn_id": "TXN2001",
      "merchant": "Flipkart",
      "amount": 146100.68,
      "currency": "INR",
      "reason": "Statistical outlier (3x+ median)"
    }
  ],
  "category_breakdown": {
    "Shopping": 125000.00,
    "Food": 45000.00,
    "Travel": 60000.00,
    "Transport": 55000.00,
    "Utilities": 80000.00
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
    "narrative": "User primarily spends on shopping and transportation with moderate frequency. Several large transactions were flagged as statistical outliers. Risk assessment suggests medium-level anomalies.",
    "risk_level": "medium"
  }
}
```

---

### 4. List All Jobs

**Endpoint**: `GET /jobs`

**Request**:
```bash
# List all jobs
curl "http://localhost:8000/jobs"

# Filter by status
curl "http://localhost:8000/jobs?status=completed"
```

**Response**:
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
      "completed_at": "2024-06-12T10:05:30Z"
    }
  ],
  "total": 1
}
```

---

## Processing Pipeline

### Step-by-Step Execution

1. **CSV Upload & Validation**
   - File format validation
   - Required columns check
   - Size validation (<10MB)

2. **Data Cleaning**
   - Normalize dates to ISO 8601
   - Strip currency symbols ($)
   - Uppercase status values
   - Fill missing categories with "Uncategorised"
   - Remove duplicate rows

3. **Anomaly Detection**
   - Flag transactions >3x account median
   - Flag USD transactions from domestic-only merchants

4. **LLM Categorization** (Batched)
   - Identify uncategorized transactions
   - Batch process (15 per LLM call) to optimize costs
   - Assign categories: Food, Shopping, Travel, Transport, Utilities, Cash Withdrawal, Entertainment, Other
   - Retry failed calls up to 3 times with exponential backoff

5. **LLM Summary Generation**
   - Single LLM call for entire dataset
   - Generate narrative: 2-3 sentence spending summary
   - Assess risk level: low, medium, high
   - Identify top 3 merchants

6. **Results Storage**
   - Save all cleaned transactions
   - Store anomaly flags and reasons
   - Save final summary and risk assessment

---

## Development & Debugging

### View API Documentation

```bash
# Interactive Swagger UI
http://localhost:8000/docs

# Alternative ReDoc documentation
http://localhost:8000/redoc
```

### Check Service Logs

```bash
# FastAPI logs
docker compose logs api

# Celery worker logs
docker compose logs worker

# Database logs
docker compose logs db

# Redis logs
docker compose logs redis

# Follow logs in real-time
docker compose logs -f api
```

### Access PostgreSQL

```bash
# Connect to database
docker exec -it transactions_db psql -U postgres -d transactions_db

# List jobs
SELECT * FROM jobs;

# List transactions
SELECT * FROM transactions LIMIT 10;

# Check summaries
SELECT * FROM job_summaries;
```

### Restart Services

```bash
# Restart API only
docker compose restart api

# Restart worker only
docker compose restart worker

# Restart all services
docker compose restart
```

---

## Environment Configuration

### .env File Variables

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@db:5432/transactions_db

# Redis
REDIS_URL=redis://redis:6379/0

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Gemini LLM
GEMINI_API_KEY=your_gemini_api_key_here

# FastAPI
DEBUG=False
API_HOST=0.0.0.0
API_PORT=8000

# Processing
MAX_FILE_SIZE_MB=10
BATCH_SIZE_LLM=15
```

### Getting Gemini API Key

1. Go to https://ai.google.dev/
2. Click "Get API key"
3. Create a new API key
4. Copy and paste into `.env` file

---

## Testing with Sample Data

### Using Provided transactions.csv

```bash
# Upload the provided CSV file
curl -X POST "http://localhost:8000/jobs/upload" \
  -F "file=@transactions.csv"

# Capture job_id from response
JOB_ID="550e8400-e29b-41d4-a716-446655440000"

# Poll status until completed
for i in {1..30}; do
  echo "Check $i:"
  curl "http://localhost:8000/jobs/$JOB_ID/status"
  sleep 5
done

# Get final results
curl "http://localhost:8000/jobs/$JOB_ID/results" | jq .
```

### Create Test CSV

```bash
cat > test_transactions.csv << 'EOF'
txn_id,date,merchant,amount,currency,status,category,account_id,notes
TXN001,01-01-2024,Amazon,1500.00,INR,SUCCESS,Shopping,ACC001,
TXN002,2024/01/02,Swiggy,450.50,INR,success,Food,ACC001,
TXN003,03-01-2024,IRCTC,2500.00,USD,FAILED,Travel,ACC002,SUSPICIOUS
EOF

curl -X POST "http://localhost:8000/jobs/upload" \
  -F "file=@test_transactions.csv"
```

---

## Performance & Scalability

### Current Configuration

- **Celery Workers**: 1 (can scale)
- **Concurrency**: 2 tasks per worker
- **Task Timeout**: 30 minutes hard limit
- **LLM Batch Size**: 15 transactions per call
- **Retry Logic**: 3 attempts with exponential backoff (1s, 2s, 4s)

### Scaling for 100x Traffic

1. **Add more Celery workers**:
   ```yaml
   worker-2:
     extends: worker
     container_name: transactions_worker_2
   ```

2. **Increase PostgreSQL connections**:
   ```env
   max_connections=1000
   ```

3. **Use Redis persistence**:
   ```yaml
   redis:
     command: redis-server --appendonly yes
   ```

4. **Add load balancer**:
   ```yaml
   nginx:
     image: nginx:alpine
     ports:
       - "80:80"
   ```

5. **Move to managed services**:
   - AWS RDS for PostgreSQL
   - AWS ElastiCache for Redis
   - AWS SQS for job queue
   - AWS S3 for file storage

---

## Troubleshooting

### 1. API Container Fails to Start

```bash
# Check logs
docker compose logs api

# Verify database connection
docker compose exec api python -c "from sqlalchemy import create_engine; create_engine('postgresql://postgres:postgres@db:5432/transactions_db').connect()"
```

### 2. Worker Not Processing Jobs

```bash
# Check worker is running
docker compose ps worker

# View worker logs
docker compose logs worker

# Verify Redis connectivity
docker compose exec worker redis-cli ping
```

### 3. LLM Calls Failing

```bash
# Verify API key is set
docker compose exec api echo $GEMINI_API_KEY

# Test Gemini API directly
curl -H "x-goog-api-key: YOUR_KEY" \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
```

### 4. Database Connection Issues

```bash
# Check database is healthy
docker compose exec db pg_isready

# Verify credentials
docker compose exec db psql -U postgres -d transactions_db -c "SELECT 1;"
```

---

## File Structure

```
devops_intern/
├── app/
│   ├── main.py                 # FastAPI app
│   ├── config.py              # Configuration
│   ├── models/
│   │   ├── database.py        # SQLAlchemy models
│   │   └── schemas.py         # Pydantic schemas
│   ├── api/
│   │   └── routes.py          # API endpoints
│   ├── services/
│   │   ├── csv_processor.py   # CSV handling
│   │   ├── data_cleaner.py    # Data cleaning
│   │   ├── anomaly_detector.py # Anomaly detection
│   │   ├── llm_service.py     # Gemini integration
│   │   └── db_service.py      # Database operations
│   ├── tasks/
│   │   └── process_job.py     # Celery task
│   └── utils/
│       ├── constants.py       # Constants
│       └── helpers.py         # Utility functions
├── Dockerfile                  # FastAPI container
├── Dockerfile.worker          # Celery worker container
├── docker-compose.yml         # Orchestration
├── requirements.txt           # Dependencies
├── .env.example              # Environment template
├── README.md                 # This file
└── ARCHITECTURE.md           # System design
```

---

## Production Deployment

### Before Going Live

1. **Security**
   - Change database password
   - Use strong API keys
   - Enable HTTPS/TLS
   - Set DEBUG=False
   - Add authentication/authorization

2. **Performance**
   - Use managed PostgreSQL (RDS)
   - Use managed Redis (ElastiCache)
   - Add CDN for static files
   - Implement caching
   - Use connection pooling

3. **Monitoring**
   - Add Prometheus metrics
   - Set up Grafana dashboards
   - Configure CloudWatch/DataDog
   - Add distributed tracing
   - Set up log aggregation (ELK)

4. **Backup & Recovery**
   - Enable automated database backups
   - Set up Redis persistence
   - Create disaster recovery plan
   - Document rollback procedures

---

## Support & Issues

For issues or questions:

1. Check logs: `docker compose logs -f`
2. Review ARCHITECTURE.md for design details
3. Check database: `docker compose exec db psql ...`
4. Verify Redis: `docker compose exec redis redis-cli`
5. Test API manually with curl examples

---

## License

Internship Assignment - Alemeno

---

**Status**: ✅ Production Ready | **Version**: 1.0.0 | **Last Updated**: 2024-06-12
