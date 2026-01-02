"""
Zerodha Tradebook Parser

File format:
- Excel file (.xlsx)
- Header row typically at row 14 (may vary)
- Columns: Symbol, ISIN, Trade Date, Exchange, Segment, Series,
           Trade Type, Auction, Quantity, Price, Trade ID, Order ID,
           Order Execution Time
- Client ID at row 6
"""
from typing import List, Dict, Any, Optional
from datetime import date, datetime
from decimal import Decimal
import pandas as pd

from app.services.parsers.base_parser import (
    BaseParser, ParserError, MissingColumnError, DataValidationError
)


class ZerodhaTradeBookParser(BaseParser):
    """Parser for Zerodha Tradebook Excel files."""

    EXPECTED_COLUMNS = [
        'Symbol', 'ISIN', 'Trade Date', 'Exchange', 'Segment',
        'Series', 'Trade Type', 'Auction', 'Quantity', 'Price',
        'Trade ID', 'Order ID', 'Order Execution Time'
    ]

    REQUIRED_COLUMNS = ['Symbol', 'ISIN', 'Trade Date', 'Trade Type', 'Quantity', 'Price', 'Trade ID']

    def __init__(self, file_path: str):
        super().__init__(file_path)
        self._account_info: Optional[Dict[str, str]] = None
        self._header_row: Optional[int] = None

    def get_account_info(self) -> Dict[str, str]:
        """Extract account information from the file."""
        if self._account_info is not None:
            return self._account_info

        df = self.read_excel(header=None, nrows=15)
        self._account_info = {}

        # Look for Client ID (typically at row 6)
        for i in range(min(15, len(df))):
            row = df.iloc[i]
            for j, val in enumerate(row):
                if pd.notna(val) and str(val).strip() == 'Client ID':
                    # Next column should have the value
                    if j + 1 < len(row) and pd.notna(row.iloc[j + 1]):
                        self._account_info['client_id'] = str(row.iloc[j + 1]).strip()
                        break

        # Look for date range in the file
        for i in range(min(15, len(df))):
            row = df.iloc[i]
            for val in row:
                if pd.notna(val):
                    val_str = str(val)
                    if 'Tradebook for Equity from' in val_str:
                        # Extract date range
                        self._account_info['date_range'] = val_str
                        break

        return self._account_info

    def _find_header_row(self) -> int:
        """Find the row containing column headers."""
        if self._header_row is not None:
            return self._header_row

        df = self.read_excel(header=None, nrows=30)

        for i in range(len(df)):
            row_values = [str(v).strip() for v in df.iloc[i].values if pd.notna(v)]
            if 'Symbol' in row_values and 'Trade Date' in row_values:
                self._header_row = i
                return i

        raise MissingColumnError("Could not find header row with 'Symbol' and 'Trade Date' columns")

    def parse(self) -> List[Dict[str, Any]]:
        """
        Parse tradebook and return list of trade dictionaries.

        Each trade: {
            'symbol': str,
            'isin': str,
            'trade_date': date,
            'trade_datetime': datetime,
            'exchange': str,
            'segment': str,
            'series': str,
            'trade_type': str,  # 'buy' or 'sell'
            'auction': bool,
            'quantity': int,
            'price': Decimal,
            'trade_id': str,
            'order_id': str
        }
        """
        header_row = self._find_header_row()
        df = self.read_excel(header=header_row)

        # Clean column names
        df.columns = [str(col).strip() for col in df.columns]

        # Drop the unnamed first column if present
        if df.columns[0].startswith('Unnamed'):
            df = df.drop(df.columns[0], axis=1)

        # Verify required columns exist
        missing_cols = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            raise MissingColumnError(f"Missing required columns: {missing_cols}")

        trades = []

        for idx, row in df.iterrows():
            # Skip rows with missing essential data
            if pd.isna(row.get('Symbol')) or pd.isna(row.get('Trade ID')):
                continue

            try:
                trade = self._parse_row(row, idx + header_row + 2)  # +2 for 1-based and header
                if trade:
                    trades.append(trade)
            except Exception as e:
                self.add_error(idx + header_row + 2, str(e), row.to_dict())

        return trades

    def _parse_row(self, row: pd.Series, row_num: int) -> Optional[Dict[str, Any]]:
        """Parse a single row into a trade dictionary."""
        symbol = self.clean_string(row.get('Symbol'))
        if not symbol:
            return None

        isin = self.clean_string(row.get('ISIN'))
        trade_date = self.parse_date(row.get('Trade Date'))
        trade_datetime = self.parse_datetime(row.get('Order Execution Time'))

        if not trade_date:
            self.add_error(row_num, f"Invalid trade date for {symbol}")
            return None

        # If we have execution time, combine with trade date for precise ordering
        if trade_datetime and trade_datetime.date() != trade_date:
            # Use the datetime's date if they differ
            trade_date = trade_datetime.date()

        trade_type = self.clean_string(row.get('Trade Type'))
        if trade_type:
            trade_type = trade_type.lower()
            if trade_type not in ('buy', 'sell'):
                self.add_error(row_num, f"Invalid trade type: {trade_type}")
                return None
        else:
            self.add_error(row_num, "Missing trade type")
            return None

        quantity = self.parse_int(row.get('Quantity'))
        if not quantity or quantity <= 0:
            self.add_error(row_num, f"Invalid quantity: {row.get('Quantity')}")
            return None

        price = self.parse_decimal(row.get('Price'))
        if not price or price <= 0:
            self.add_error(row_num, f"Invalid price: {row.get('Price')}")
            return None

        trade_id = self.clean_string(row.get('Trade ID'))
        if not trade_id:
            self.add_error(row_num, "Missing trade ID")
            return None

        # Parse auction field
        auction_val = row.get('Auction')
        auction = False
        if pd.notna(auction_val):
            auction = str(auction_val).strip().lower() in ('true', 'yes', '1')

        return {
            'symbol': symbol,
            'isin': isin,
            'trade_date': trade_date,
            'trade_datetime': trade_datetime,
            'exchange': self.clean_string(row.get('Exchange')),
            'segment': self.clean_string(row.get('Segment')),
            'series': self.clean_string(row.get('Series')),
            'trade_type': trade_type,
            'auction': auction,
            'quantity': quantity,
            'price': price,
            'trade_id': trade_id,
            'order_id': self.clean_string(row.get('Order ID'))
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics from the parsed data."""
        trades = self.parse()

        if not trades:
            return {'total_trades': 0}

        buy_trades = [t for t in trades if t['trade_type'] == 'buy']
        sell_trades = [t for t in trades if t['trade_type'] == 'sell']

        symbols = set(t['symbol'] for t in trades)

        return {
            'total_trades': len(trades),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'unique_symbols': len(symbols),
            'symbols': sorted(symbols),
            'date_range': {
                'start': min(t['trade_date'] for t in trades),
                'end': max(t['trade_date'] for t in trades)
            },
            'total_buy_value': sum(t['quantity'] * t['price'] for t in buy_trades),
            'total_sell_value': sum(t['quantity'] * t['price'] for t in sell_trades),
            'errors': len(self.errors),
            'warnings': len(self.warnings)
        }
