"""
Data Cleaning Service
Handles data normalization and standardization
"""
from typing import List, Dict, Any
from app.utils.helpers import (
    parse_date,
    clean_amount,
    normalize_status,
    normalize_currency,
    clean_merchant_name,
)
from app.utils.constants import DEFAULT_CATEGORY


class DataCleaner:
    """Cleans and normalizes transaction data"""
    
    @staticmethod
    def clean_transaction(row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean a single transaction row
        
        Args:
            row: Raw transaction row from CSV
            
        Returns:
            Cleaned transaction row
            
        Raises:
            ValueError: If critical field cannot be cleaned
        """
        cleaned = {}
        
        # txn_id - keep as is, but may be empty
        cleaned["txn_id"] = str(row.get("txn_id", "")).strip() or None
        
        # Date - normalize to ISO 8601
        date_str = str(row.get("date", "")).strip()
        try:
            cleaned["date"] = parse_date(date_str)
        except ValueError:
            # If date parsing fails, skip this transaction
            raise ValueError(f"Could not parse date: {date_str}")
        
        # Merchant - clean name
        cleaned["merchant"] = clean_merchant_name(row.get("merchant", ""))
        
        # Amount - clean and convert to float
        amount_str = str(row.get("amount", "")).strip()
        try:
            cleaned["amount"] = clean_amount(amount_str)
        except ValueError:
            raise ValueError(f"Could not parse amount: {amount_str}")
        
        # Currency - normalize to uppercase
        currency_str = str(row.get("currency", "")).strip()
        try:
            cleaned["currency"] = normalize_currency(currency_str)
        except ValueError:
            raise ValueError(f"Invalid currency: {currency_str}")
        
        # Status - normalize to uppercase
        status_str = str(row.get("status", "")).strip()
        try:
            cleaned["status"] = normalize_status(status_str)
        except ValueError:
            raise ValueError(f"Invalid status: {status_str}")
        
        # Category - fill with default if empty
        category = str(row.get("category", "")).strip()
        cleaned["category"] = category if category else DEFAULT_CATEGORY
        
        # Account ID - keep as is
        cleaned["account_id"] = str(row.get("account_id", "")).strip() or "UNKNOWN"
        
        # Notes - keep as is (for reference)
        cleaned["notes"] = str(row.get("notes", "")).strip() or ""
        
        return cleaned
    
    @staticmethod
    def clean_batch(rows: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        Clean a batch of transactions
        
        Args:
            rows: List of raw transaction rows
            
        Returns:
            Tuple of (cleaned rows, list of error messages for skipped rows)
        """
        cleaned_rows = []
        errors = []
        
        for idx, row in enumerate(rows):
            try:
                cleaned = DataCleaner.clean_transaction(row)
                cleaned_rows.append(cleaned)
            except ValueError as e:
                # Skip rows that fail cleaning, but track the error
                txn_id = row.get("txn_id", "unknown")
                errors.append(f"Row {idx}: {txn_id} - {str(e)}")
        
        return cleaned_rows, errors
