"""
Anomaly Detection Service
Detects suspicious transactions
"""
from typing import List, Dict, Any
from collections import defaultdict
from app.utils.constants import (
    OUTLIER_MULTIPLIER,
    ANOMALY_REASON_OUTLIER,
    ANOMALY_REASON_CURRENCY_MISMATCH,
)
from app.utils.helpers import is_domestic_only_merchant, calculate_median


class AnomalyDetector:
    """Detects anomalies in transaction data"""
    
    @staticmethod
    def detect_anomalies(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect anomalies in transactions
        
        Args:
            transactions: List of cleaned transactions
            
        Returns:
            Same transactions with anomaly flags set
        """
        # First, detect statistical outliers
        AnomalyDetector._flag_statistical_outliers(transactions)
        
        # Then, detect currency/merchant mismatches
        AnomalyDetector._flag_currency_mismatches(transactions)
        
        return transactions
    
    @staticmethod
    def _flag_statistical_outliers(transactions: List[Dict[str, Any]]) -> None:
        """
        Flag transactions that are statistical outliers (3x+ median per account)
        Modifies transactions in place
        
        Args:
            transactions: List of transactions
        """
        # Group amounts by account_id
        account_amounts = defaultdict(list)
        
        for txn in transactions:
            account_id = txn.get("account_id")
            amount = txn.get("amount", 0)
            account_amounts[account_id].append(amount)
        
        # Calculate median per account
        account_medians = {}
        for account_id, amounts in account_amounts.items():
            account_medians[account_id] = calculate_median(amounts)
        
        # Flag outliers
        for txn in transactions:
            account_id = txn.get("account_id")
            amount = txn.get("amount", 0)
            median = account_medians.get(account_id, 0)
            
            # Check if amount exceeds 3x median
            if median > 0 and amount > (median * OUTLIER_MULTIPLIER):
                txn["is_anomaly"] = True
                txn["anomaly_reason"] = ANOMALY_REASON_OUTLIER
    
    @staticmethod
    def _flag_currency_mismatches(transactions: List[Dict[str, Any]]) -> None:
        """
        Flag transactions with currency/merchant mismatches
        Modifies transactions in place
        
        Args:
            transactions: List of transactions
        """
        for txn in transactions:
            merchant = txn.get("merchant", "")
            currency = txn.get("currency", "")
            
            # Check if currency is USD but merchant is domestic
            if currency == "USD" and is_domestic_only_merchant(merchant):
                txn["is_anomaly"] = True
                # Only set anomaly_reason if not already flagged
                if not txn.get("anomaly_reason"):
                    txn["anomaly_reason"] = ANOMALY_REASON_CURRENCY_MISMATCH
                else:
                    # Combine reasons if already flagged
                    txn["anomaly_reason"] += f" + {ANOMALY_REASON_CURRENCY_MISMATCH}"
