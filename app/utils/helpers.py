"""
Helper utility functions
"""
from datetime import datetime
from app.utils.constants import (
    DATE_FORMATS,
    ISO_DATE_FORMAT,
    TRANSACTION_STATUS_SUCCESS,
    TRANSACTION_STATUS_FAILED,
    TRANSACTION_STATUS_PENDING,
)


def parse_date(date_str: str) -> str:
    """
    Parse mixed date formats and return ISO 8601 format (YYYY-MM-DD)
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        ISO 8601 formatted date string
        
    Raises:
        ValueError: If date cannot be parsed
    """
    if not date_str or not isinstance(date_str, str):
        raise ValueError(f"Invalid date: {date_str}")
    
    date_str = date_str.strip()
    
    for date_format in DATE_FORMATS:
        try:
            parsed_date = datetime.strptime(date_str, date_format)
            return parsed_date.strftime(ISO_DATE_FORMAT)
        except ValueError:
            continue
    
    raise ValueError(f"Could not parse date: {date_str}")


def clean_amount(amount_str: str) -> float:
    """
    Clean amount by removing currency symbols and converting to float
    
    Args:
        amount_str: Amount string (may have $ prefix)
        
    Returns:
        Float amount
        
    Raises:
        ValueError: If amount cannot be converted
    """
    if not amount_str or not isinstance(amount_str, (str, int, float)):
        raise ValueError(f"Invalid amount: {amount_str}")
    
    # Convert to string if needed
    amount_str = str(amount_str).strip()
    
    # Remove currency symbols
    amount_str = amount_str.replace("$", "").strip()
    
    try:
        return float(amount_str)
    except ValueError:
        raise ValueError(f"Could not parse amount: {amount_str}")


def normalize_status(status: str) -> str:
    """
    Normalize status to uppercase
    
    Args:
        status: Status string
        
    Returns:
        Uppercase status
        
    Raises:
        ValueError: If status is invalid
    """
    if not status or not isinstance(status, str):
        raise ValueError(f"Invalid status: {status}")
    
    normalized = status.strip().upper()
    
    valid_statuses = {
        TRANSACTION_STATUS_SUCCESS,
        TRANSACTION_STATUS_FAILED,
        TRANSACTION_STATUS_PENDING,
    }
    
    if normalized not in valid_statuses:
        raise ValueError(f"Invalid status value: {normalized}")
    
    return normalized


def normalize_currency(currency: str) -> str:
    """
    Normalize currency to uppercase
    
    Args:
        currency: Currency string
        
    Returns:
        Uppercase currency
        
    Raises:
        ValueError: If currency is invalid
    """
    if not currency or not isinstance(currency, str):
        raise ValueError(f"Invalid currency: {currency}")
    
    normalized = currency.strip().upper()
    
    if normalized not in {"INR", "USD"}:
        raise ValueError(f"Invalid currency: {normalized}")
    
    return normalized


def clean_merchant_name(merchant: str) -> str:
    """
    Clean merchant name by trimming whitespace
    
    Args:
        merchant: Merchant name
        
    Returns:
        Cleaned merchant name
    """
    if not merchant:
        return "Unknown"
    
    return str(merchant).strip()


def is_domestic_only_merchant(merchant: str) -> bool:
    """
    Check if merchant is domestic-only (India-only)
    
    Args:
        merchant: Merchant name
        
    Returns:
        True if merchant is domestic-only
    """
    from app.utils.constants import DOMESTIC_ONLY_MERCHANTS
    
    if not merchant:
        return False
    
    return merchant.strip().lower() in DOMESTIC_ONLY_MERCHANTS


def calculate_median(amounts: list) -> float:
    """
    Calculate median of amounts
    
    Args:
        amounts: List of numeric amounts
        
    Returns:
        Median value
    """
    if not amounts:
        return 0
    
    sorted_amounts = sorted(amounts)
    n = len(sorted_amounts)
    
    if n % 2 == 0:
        return (sorted_amounts[n // 2 - 1] + sorted_amounts[n // 2]) / 2
    else:
        return sorted_amounts[n // 2]
