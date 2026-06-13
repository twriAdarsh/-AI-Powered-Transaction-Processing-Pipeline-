"""
App-wide constants. Keeping these in one place makes them easy to tweak.
"""

# ============= Status Values =============
JOB_STATUS_PENDING = "pending"
JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"

TRANSACTION_STATUS_SUCCESS = "SUCCESS"
TRANSACTION_STATUS_FAILED = "FAILED"
TRANSACTION_STATUS_PENDING = "PENDING"

# ============= Risk Levels =============
RISK_LEVEL_LOW = "low"
RISK_LEVEL_MEDIUM = "medium"
RISK_LEVEL_HIGH = "high"

# ============= Categories =============
VALID_CATEGORIES = {
    "Food",
    "Shopping",
    "Travel",
    "Transport",
    "Utilities",
    "Cash Withdrawal",
    "Entertainment",
    "Other",
    "Uncategorised"
}

DEFAULT_CATEGORY = "Uncategorised"

# ============= Currencies =============
VALID_CURRENCIES = {"INR", "USD"}

# ============= Domestic Merchants =============
# These merchants are India-specific and should only have INR transactions
DOMESTIC_ONLY_MERCHANTS = {
    "swiggy",
    "zomato",
    "ola",
    "irctc",
    "flipkart",
    "amazon",
    "bookmyshow",
    "jio recharge",
    "hdfc atm"
}

# ============= Anomaly Detection =============
OUTLIER_MULTIPLIER = 3  # Flag if amount > median * 3
ANOMALY_REASON_OUTLIER = "Statistical outlier (3x+ median)"
ANOMALY_REASON_CURRENCY_MISMATCH = "Currency mismatch with domestic merchant"

# LLM retry config — 3 attempts, doubling the wait each time: 1s, 2s, 4s
LLM_RETRY_MAX_ATTEMPTS = 3
LLM_RETRY_BACKOFF_FACTOR = 2
LLM_INITIAL_BACKOFF_SECONDS = 1

# ============= CSV Configuration =============
REQUIRED_CSV_COLUMNS = {
    "txn_id",
    "date",
    "merchant",
    "amount",
    "currency",
    "status",
    "category",
    "account_id",
    "notes"
}

# ============= Date Formats =============
DATE_FORMATS = [
    "%d-%m-%Y",    # DD-MM-YYYY
    "%Y/%m/%d",    # YYYY/MM/DD
    "%Y-%m-%d",    # YYYY-MM-DD (already ISO 8601)
]

ISO_DATE_FORMAT = "%Y-%m-%d"

# How many merchants to send per Gemini API call
# 15 is a good balance between cost efficiency and staying under token limits
LLM_BATCH_SIZE = 15
BATCH_SIZE_LLM = LLM_BATCH_SIZE  # alias — used in process_job.py
