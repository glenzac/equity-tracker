"""
Base Parser - Abstract base class for broker file parsers.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime
from decimal import Decimal
import pandas as pd


class ParserError(Exception):
    """Base exception for parser errors."""
    pass


class FileFormatError(ParserError):
    """Invalid file format."""
    pass


class MissingColumnError(ParserError):
    """Required column missing in file."""
    pass


class DataValidationError(ParserError):
    """Data validation failed."""
    pass


class BaseParser(ABC):
    """Abstract base class for broker file parsers."""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self._df: Optional[pd.DataFrame] = None

        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if self.file_path.suffix.lower() != '.xlsx':
            raise FileFormatError(f"Expected .xlsx file, got: {self.file_path.suffix}")

    @abstractmethod
    def parse(self) -> List[Dict[str, Any]]:
        """Parse the file and return list of records."""
        pass

    @abstractmethod
    def get_account_info(self) -> Dict[str, str]:
        """Extract account information from the file."""
        pass

    def add_error(self, row: int, message: str, data: Any = None):
        """Add an error to the error list."""
        self.errors.append({
            'row': row,
            'message': message,
            'data': data
        })

    def add_warning(self, row: int, message: str, data: Any = None):
        """Add a warning to the warning list."""
        self.warnings.append({
            'row': row,
            'message': message,
            'data': data
        })

    def has_errors(self) -> bool:
        """Check if there were any parsing errors."""
        return len(self.errors) > 0

    def read_excel(self, header: Optional[int] = None, **kwargs) -> pd.DataFrame:
        """Read the Excel file with the given header row."""
        return pd.read_excel(self.file_path, header=header, **kwargs)

    def find_header_row(self, df: pd.DataFrame, required_columns: List[str],
                        max_rows: int = 50) -> int:
        """
        Find the row containing the column headers.

        Args:
            df: DataFrame read without headers
            required_columns: List of column names to look for
            max_rows: Maximum number of rows to search

        Returns:
            Row index containing the headers

        Raises:
            MissingColumnError: If headers not found
        """
        for i in range(min(max_rows, len(df))):
            row_values = [str(v).strip() for v in df.iloc[i].values if pd.notna(v)]
            # Check if this row contains any of the required columns
            matches = sum(1 for col in required_columns if col in row_values)
            if matches >= len(required_columns) // 2:  # At least half the columns match
                return i

        raise MissingColumnError(
            f"Could not find header row with required columns: {required_columns}"
        )

    @staticmethod
    def parse_date(value: Any) -> Optional[date]:
        """Parse a date value from various formats."""
        if pd.isna(value):
            return None

        if isinstance(value, (datetime, pd.Timestamp)):
            return value.date()

        if isinstance(value, date):
            return value

        if isinstance(value, str):
            value = value.strip()
            # Try common date formats
            formats = ['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d']
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue

        return None

    @staticmethod
    def parse_datetime(value: Any) -> Optional[datetime]:
        """Parse a datetime value from various formats."""
        if pd.isna(value):
            return None

        if isinstance(value, datetime):
            return value

        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime()

        if isinstance(value, str):
            value = value.strip()
            # Try common datetime formats
            formats = [
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S',
                '%d-%m-%Y %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%f',
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue

        return None

    @staticmethod
    def parse_decimal(value: Any) -> Optional[Decimal]:
        """Parse a decimal value."""
        if pd.isna(value):
            return None

        if isinstance(value, (int, float)):
            return Decimal(str(value))

        if isinstance(value, str):
            value = value.strip().replace(',', '')
            try:
                return Decimal(value)
            except:
                return None

        return None

    @staticmethod
    def parse_int(value: Any) -> Optional[int]:
        """Parse an integer value."""
        if pd.isna(value):
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, float):
            return int(value)

        if isinstance(value, str):
            value = value.strip().replace(',', '')
            try:
                return int(float(value))
            except:
                return None

        return None

    @staticmethod
    def clean_string(value: Any) -> Optional[str]:
        """Clean and return a string value."""
        if pd.isna(value):
            return None

        return str(value).strip()

    @staticmethod
    def get_financial_year(dt: date) -> str:
        """
        Get Indian financial year for a given date.
        FY runs from April 1 to March 31.
        """
        if dt.month >= 4:  # April onwards
            return f"{dt.year}-{dt.year + 1}"
        else:  # January to March
            return f"{dt.year - 1}-{dt.year}"
