"""
CSV Processing Service
Handles CSV file reading, validation, and parsing
"""
import csv
from typing import List, Dict, Any
from io import StringIO
from app.utils.constants import REQUIRED_CSV_COLUMNS


class CSVProcessor:
    """Processes CSV files and validates format"""
    
    @staticmethod
    def validate_csv(file_content: str) -> bool:
        """
        Validate CSV file has required columns
        
        Args:
            file_content: Raw CSV file content as string
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If validation fails
        """
        try:
            reader = csv.DictReader(StringIO(file_content))
            
            if reader.fieldnames is None:
                raise ValueError("CSV file is empty")
            
            csv_columns = set(reader.fieldnames)
            
            if not REQUIRED_CSV_COLUMNS.issubset(csv_columns):
                missing = REQUIRED_CSV_COLUMNS - csv_columns
                raise ValueError(f"Missing required columns: {missing}")
            
            # Check that file has at least one row
            first_row = next(reader, None)
            if first_row is None:
                raise ValueError("CSV file has no data rows")
            
            return True
            
        except csv.Error as e:
            raise ValueError(f"Invalid CSV format: {str(e)}")
    
    @staticmethod
    def read_csv(file_content: str) -> tuple[List[Dict[str, Any]], int]:
        """
        Read CSV file and return list of rows
        
        Args:
            file_content: Raw CSV file content as string
            
        Returns:
            Tuple of (list of row dicts, raw row count)
            
        Raises:
            ValueError: If reading fails
        """
        try:
            reader = csv.DictReader(StringIO(file_content))
            rows = list(reader)
            row_count = len(rows)
            
            if row_count == 0:
                raise ValueError("CSV file has no data rows")
            
            return rows, row_count
            
        except csv.Error as e:
            raise ValueError(f"Error reading CSV: {str(e)}")
    
    @staticmethod
    def remove_duplicates(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove exact duplicate rows (keeping first occurrence)
        
        Args:
            rows: List of row dictionaries
            
        Returns:
            List with duplicates removed
        """
        seen = set()
        unique_rows = []
        
        for row in rows:
            # Create a hashable tuple of all values
            row_tuple = tuple(sorted((k, str(v).strip() if v else "") for k, v in row.items()))
            
            if row_tuple not in seen:
                seen.add(row_tuple)
                unique_rows.append(row)
        
        return unique_rows
