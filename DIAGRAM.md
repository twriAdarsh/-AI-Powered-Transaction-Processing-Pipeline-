# System Architecture Diagram - Draw.io Specification

## For Visual Creation in draw.io

### How to Create the Diagram

1. Go to https://draw.io
2. Create a new diagram
3. Use the following components to recreate this architecture
4. Save and export as SVG/PNG

---

## High-Level Components

### Layer 1: Client/User
```
┌─────────────────────┐
│   User/Client       │
│  (CSV Upload Tool)  │
└──────────┬──────────┘
           │ HTTP/REST
           ▼
```

### Layer 2: API Server
```
┌─────────────────────────────────────┐
│     FastAPI Web Server              │
│  (Uvicorn, Port 8000)               │
│                                     │
│  POST   /jobs/upload ───────────┐   │
│  GET    /jobs/{id}/status       │   │
│  GET    /jobs/{id}/results      │   │
│  GET    /jobs                   │   │
└─────────────────────────────────┘
          │ TCP
          ├─────────────────┬──────────────────┐
          ▼                 ▼                  ▼
```

### Layer 3: Persistent Storage
```
┌──────────────────────┐      ┌──────────────────┐
│  PostgreSQL 16       │      │  Redis 7         │
│  (Port 5432)         │      │  (Port 6379)     │
│                      │      │                  │
│  Tables:             │      │  Message Queue   │
│  - jobs              │      │  - Task Queue    │
│  - transactions      │      │  - Cache         │
│  - job_summaries     │      │                  │
└──────────────────────┘      └──────────────────┘
          ▲                            ▲
          │                            │
          └────────────┬───────────────┘
                       │
```

### Layer 4: Message Queue (Async Processing)
```
┌─────────────────────────────────────┐
│  Celery Task Queue (Redis-backed)   │
│                                     │
│  Queue: process_job                 │
│  Status: pending → processing →     │
│          completed/failed           │
└─────────────────────────────────────┘
          ▲                │
          │                │ Enqueue
          │                │
```

### Layer 5: Background Workers
```
┌──────────────────────────────────────┐
│  Celery Worker Process               │
│  (Concurrency: 2)                    │
│                                      │
│  ┌────────────────────────────────┐  │
│  │ Step 1: Data Cleaning          │  │
│  │ - Normalize dates (ISO 8601)   │  │
│  │ - Strip currency symbols ($)   │  │
│  │ - Uppercase status values      │  │
│  │ - Fill missing categories      │  │
│  │ - Remove duplicates            │  │
│  └────────────────────────────────┘  │
│           ▼                           │
│  ┌────────────────────────────────┐  │
│  │ Step 2: Anomaly Detection      │  │
│  │ - Statistical outliers (3x)    │  │
│  │ - Currency/Merchant mismatch   │  │
│  └────────────────────────────────┘  │
│           ▼                           │
│  ┌────────────────────────────────┐  │
│  │ Step 3: LLM Categorization     │  │
│  │ (Batched, 15 per call)         │  │
│  │ - Call Gemini API              │  │
│  │ - Retry 3x with backoff        │  │
│  │ - Save categories              │  │
│  └────────────────────────────────┘  │
│           ▼                           │
│  ┌────────────────────────────────┐  │
│  │ Step 4: LLM Summary            │  │
│  │ - Generate narrative           │  │
│  │ - Calculate risk level         │  │
│  │ - Top merchants                │  │
│  └────────────────────────────────┘  │
│           ▼                           │
│  ┌────────────────────────────────┐  │
│  │ Step 5: Save Results           │  │
│  │ - Update job status            │  │
│  │ - Mark as completed            │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
          │
          ▼
    PostgreSQL (Write)
```

### Layer 6: External Services
```
┌──────────────────────────────────┐
│  Google Gemini 1.5 Flash API     │
│  (LLM for Classification)        │
│                                  │
│  - Categorization calls          │
│  - Narrative generation          │
│  - Retry logic (3x, backoff)     │
│  - Exponential backoff strategy  │
└──────────────────────────────────┘
```

---

## Data Flow Diagram

### Request → Response Flow

```
1. User uploads transactions.csv
   └─→ POST /jobs/upload
       └─→ API validates CSV format
           └─→ Creates Job record (status: pending)
               └─→ Stores CSV content in memory
                   └─→ Enqueues celery task
                       └─→ Returns job_id
                           └─→ 201 Created Response

2. User polls job status
   └─→ GET /jobs/{job_id}/status
       └─→ API queries database
           └─→ Returns current status & summary
               └─→ 200 OK Response

3. User retrieves results (after completed)
   └─→ GET /jobs/{job_id}/results
       └─→ API fetches all data from DB
           ├─→ Cleaned transactions
           ├─→ Flagged anomalies
           ├─→ Category breakdown
           └─→ Final summary
               └─→ 200 OK Response

4. Celery Worker processes job
   └─→ Dequeues from Redis
       └─→ Reads CSV content
           └─→ Validates & cleans data
               └─→ Detects anomalies
                   └─→ Calls Gemini API (batched)
                       └─→ Saves to PostgreSQL
                           └─→ Generates summary
                               └─→ Updates job status
                                   └─→ Completed
```

---

## Container Architecture (Docker Compose)

```
Host Machine
│
├─ Bridge Network: app_network
│
├─ Container: transactions_db
│   └─ PostgreSQL:16-alpine
│      ├─ Port: 5432
│      └─ Volume: postgres_data
│
├─ Container: transactions_redis
│   └─ Redis:7-alpine
│      └─ Port: 6379
│
├─ Container: transactions_api
│   └─ FastAPI (Uvicorn)
│      ├─ Port: 8000
│      ├─ Depends: db, redis
│      └─ Volume: .:/app
│
└─ Container: transactions_worker
    └─ Celery Worker
       ├─ Depends: db, redis
       └─ Volume: .:/app
```

---

## Sequence Diagram (Upload & Processing)

```
User          API              Database    Redis Queue      Worker
│             │                   │            │              │
├──Upload CSV─▶│                  │            │              │
│             │─Validate CSV─────▶│            │              │
│             │◀─Response─────────│            │              │
│             │                   │            │              │
│             │─Create Job────────▶│           │              │
│             │◀─Job ID──────────│            │              │
│             │                   │            │              │
│             │─Enqueue Task─────────────────▶│              │
│             │◀─Task Queued───────────────────│              │
│             │                   │            │              │
│             │◀─Return Job ID────────────────│              │
│◀─201 Created─┤                  │            │              │
│             │                   │            │              │
│             │                   │            │◀─Dequeue────│
│             │                   │            │  Task      │
│             │                   │            │              │
│             │                   │            │          Process
│             │                   │            │          (Clean,
│             │                   │            │           Detect,
│             │                   │            │           LLM)
│             │                   │            │              │
│             │                   │◀───────────────Save────────┤
│             │                   │   Transactions            │
│             │                   │            │              │
│             │                   │◀───────────────Update Status
│             │                   │            │              │
│Check Status─▶│◀─Query Status────│            │              │
│◀─Status OK──┤                  │            │              │
│             │                   │            │              │
│Check Results─▶│◀─Query Results──│            │              │
│◀─Full Data──┤                  │            │              │
```

---

## Error Handling Flow

```
Worker Processing
│
├─ CSV Validation Error
│  └─→ Return 400 Bad Request (API)
│      └─→ Job status: failed
│
├─ Data Cleaning Error
│  └─→ Skip row, log error
│      └─→ Continue with valid rows
│
├─ LLM API Call Fails
│  └─→ Retry 1 (wait 1s)
│      └─→ Retry 2 (wait 2s)
│          └─→ Retry 3 (wait 4s)
│              └─→ Mark as llm_failed
│                  └─→ Continue job
│
└─ Job Processing Timeout
   └─→ Hard limit: 30 minutes
       └─→ Soft limit: 25 minutes
           └─→ Job status: failed
```

---

## Components Summary

| Component | Technology | Role | Scaling |
|-----------|-----------|------|---------|
| API | FastAPI + Uvicorn | HTTP Server | Horizontal (Load Balancer) |
| Database | PostgreSQL 16 | Persistence | Vertical (RDS) |
| Message Queue | Redis + Celery | Job Queue | Vertical (ElastiCache) |
| Worker | Celery | Processing | Horizontal (Multiple Workers) |
| LLM | Gemini 1.5 Flash | Intelligence | Rate Limiting |
| Container Orch | Docker Compose | Local Dev | Kubernetes (Prod) |

---

## Key Design Patterns

1. **Async Job Queue**
   - Decouples upload from processing
   - Long-running tasks don't block API
   - Enables horizontal scaling

2. **Retry with Exponential Backoff**
   - Handles transient LLM API failures
   - 3 attempts: 1s, 2s, 4s delays
   - Graceful degradation

3. **Batch Processing**
   - 15 transactions per LLM call
   - Reduces API costs
   - Single summary call for all data

4. **Event-Driven Architecture**
   - CSV upload → Task enqueued
   - Task processed → Database updated
   - Status polling for visibility

5. **Transaction Isolation**
   - Each job is independent
   - No shared state between jobs
   - Supports concurrent processing

---

## Monitoring Points

```
API Metrics
├─ Request rate (req/s)
├─ Response time (ms)
├─ Error rate (%)
└─ Concurrent requests

Database Metrics
├─ Connection pool usage
├─ Query latency
├─ Transaction throughput
└─ Disk usage

Redis Metrics
├─ Key count
├─ Memory usage
├─ Queue depth
└─ Commands/sec

Worker Metrics
├─ Task count (active)
├─ Task success rate
├─ Task failure rate
├─ Processing time (avg)
└─ LLM API latency

LLM Service Metrics
├─ API calls/sec
├─ Retry rate
├─ Success rate
└─ Cost (tokens)
```

---

## Next Steps for Diagram Creation

1. **Open draw.io**: https://draw.io
2. **Import this structure** or manually recreate using:
   - Rectangle boxes for services
   - Arrows for data flow
   - Color coding (blue=storage, green=processing, orange=external)
3. **Add labels** for each component
4. **Export** as SVG/PNG for submission

---

## Alternative: Direct Link Format

For detailed draw.io diagram creation, visit:
- Template: https://draw.io (Use "UML" or "Network" templates)
- Base containers from library: "Gcp" or "AWS" icons
- Customize colors and labels as shown above
