"""
Zerodha Tax P&L Parser

File format:
- Excel file (.xlsx)
- Multiple sections: Equity-Intraday, Equity-Short Term, Equity-Long Term,
                     Equity-Buyback, Non Equity, Mutual Funds, F&O, etc.
- Each section has its own header row
- Client info at rows 6-8 (Client ID, Client Name, PAN)
- Capital gains summary at rows 14-18

Key columns:
- Symbol, ISIN, Entry Date, Exit Date, Quantity,
- Buy Value, Sell Value, Profit, Period of Holding,
- Fair Market Value, Taxable Profit, Turnover,
- Brokerage, Exchange Transaction Charges, IPFT, SEBI Charges,
- CGST, SGST, IGST, Stamp Duty, STT
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import date
from decimal import Decimal
import pandas as pd

from app.services.parsers.base_parser import (
    BaseParser, ParserError, MissingColumnError, DataValidationError
)


class ZerodhaTaxPnLParser(BaseParser):
    """Parser for Zerodha Tax P&L Excel files."""

    # Sections we care about for equity
    EQUITY_SECTIONS = [
        'Equity - Intraday',
        'Equity - Short Term',
        'Equity - Long Term',
        'Equity - Buyback',
    ]

    EXPECTED_COLUMNS = [
        'Symbol', 'ISIN', 'Entry Date', 'Exit Date', 'Quantity',
        'Buy Value', 'Sell Value', 'Profit', 'Period of Holding'
    ]

    CHARGE_COLUMNS = [
        'Brokerage', 'Exchange Transaction Charges', 'IPFT', 'SEBI Charges',
        'CGST', 'SGST', 'IGST', 'Stamp Duty', 'STT'
    ]

    def __init__(self, file_path: str):
        super().__init__(file_path)
        self._account_info: Optional[Dict[str, str]] = None
        self._sections: Optional[Dict[str, Tuple[int, int]]] = None
        self._capital_gains_summary: Optional[Dict[str, Decimal]] = None

    def get_account_info(self) -> Dict[str, str]:
        """Extract account information from the file."""
        if self._account_info is not None:
            return self._account_info

        df = self.read_excel(header=None, nrows=15)
        self._account_info = {}

        # Look for Client ID, Client Name, PAN (typically rows 6-8)
        fields_to_find = ['Client ID', 'Client Name', 'PAN']

        for i in range(min(15, len(df))):
            row = df.iloc[i]
            for j, val in enumerate(row):
                if pd.notna(val):
                    val_str = str(val).strip()
                    if val_str in fields_to_find:
                        # Next column should have the value
                        if j + 1 < len(row) and pd.notna(row.iloc[j + 1]):
                            key = val_str.lower().replace(' ', '_')
                            self._account_info[key] = str(row.iloc[j + 1]).strip()

        # Look for date range
        for i in range(min(15, len(df))):
            row = df.iloc[i]
            for val in row:
                if pd.notna(val):
                    val_str = str(val)
                    if 'Tradewise Exits from' in val_str:
                        self._account_info['date_range'] = val_str
                        break

        return self._account_info

    def get_capital_gains_summary(self) -> Dict[str, Decimal]:
        """Extract capital gains summary from the file header."""
        if self._capital_gains_summary is not None:
            return self._capital_gains_summary

        df = self.read_excel(header=None, nrows=25)
        self._capital_gains_summary = {}

        # Look for capital gains breakdown (typically rows 14-18)
        summary_fields = [
            'STCG before July 23, 2024',
            'STCG after July 23, 2024',
            'LTCG before July 23, 2024',
            'LTCG after July 23, 2024',
        ]

        for i in range(len(df)):
            row = df.iloc[i]
            for j, val in enumerate(row):
                if pd.notna(val):
                    val_str = str(val).strip()
                    for field in summary_fields:
                        if field in val_str or val_str == field:
                            # Next column should have the value
                            if j + 1 < len(row) and pd.notna(row.iloc[j + 1]):
                                key = val_str.lower().replace(' ', '_').replace(',', '')
                                value = self.parse_decimal(row.iloc[j + 1])
                                if value is not None:
                                    self._capital_gains_summary[key] = value

        return self._capital_gains_summary

    def _find_sections(self) -> Dict[str, Tuple[int, int]]:
        """Find start and end rows for each section."""
        if self._sections is not None:
            return self._sections

        df = self.read_excel(header=None)
        self._sections = {}

        section_starts = []

        # Find all section headers
        for i in range(len(df)):
            row = df.iloc[i]
            for val in row:
                if pd.notna(val):
                    val_str = str(val).strip()
                    for section in self.EQUITY_SECTIONS:
                        if val_str == section:
                            section_starts.append((section, i))
                            break

        # Also look for Non Equity section as a boundary
        for i in range(len(df)):
            row = df.iloc[i]
            for val in row:
                if pd.notna(val):
                    val_str = str(val).strip()
                    if val_str == 'Non Equity':
                        section_starts.append(('Non Equity', i))
                        break

        # Sort by row number
        section_starts.sort(key=lambda x: x[1])

        # Determine section boundaries
        for idx, (section_name, start_row) in enumerate(section_starts):
            if section_name == 'Non Equity':
                continue  # We don't parse this section, just use as boundary

            # Find end row (next section start or end of file)
            if idx + 1 < len(section_starts):
                end_row = section_starts[idx + 1][1] - 1
            else:
                end_row = len(df) - 1

            self._sections[section_name] = (start_row, end_row)

        return self._sections

    def _parse_section(self, section_name: str, start_row: int, end_row: int) -> List[Dict[str, Any]]:
        """Parse a single section of the Tax P&L."""
        # Read the section
        df = self.read_excel(header=None, skiprows=start_row, nrows=end_row - start_row + 1)

        if len(df) < 3:  # Need at least header row + 1 data row
            return []

        # Find header row within section (typically 2 rows after section title)
        header_row_idx = None
        for i in range(min(5, len(df))):
            row_values = [str(v).strip() for v in df.iloc[i].values if pd.notna(v)]
            if 'Symbol' in row_values and 'Entry Date' in row_values:
                header_row_idx = i
                break

        if header_row_idx is None:
            self.add_warning(start_row, f"Could not find header row in section {section_name}")
            return []

        # Re-read with proper header
        df = self.read_excel(header=start_row + header_row_idx)

        # Clean column names
        df.columns = [str(col).strip() for col in df.columns]

        # Drop unnamed first column if present
        if df.columns[0].startswith('Unnamed'):
            df = df.drop(df.columns[0], axis=1)

        # Limit to section rows
        section_rows = end_row - (start_row + header_row_idx + 1)
        if section_rows > 0:
            df = df.head(section_rows)

        entries = []

        for idx, row in df.iterrows():
            # Skip rows with missing essential data
            if pd.isna(row.get('Symbol')) or pd.isna(row.get('Exit Date')):
                continue

            # Skip summary rows
            symbol = self.clean_string(row.get('Symbol'))
            if not symbol or symbol.lower() in ('total', 'grand total', 'sub total'):
                continue

            try:
                entry = self._parse_pnl_row(row, section_name, start_row + header_row_idx + idx + 2)
                if entry:
                    entries.append(entry)
            except Exception as e:
                self.add_error(start_row + header_row_idx + idx + 2, str(e))

        return entries

    def _parse_pnl_row(self, row: pd.Series, section_name: str, row_num: int) -> Optional[Dict[str, Any]]:
        """Parse a single row into a P&L entry dictionary."""
        symbol = self.clean_string(row.get('Symbol'))
        if not symbol:
            return None

        isin = self.clean_string(row.get('ISIN'))
        entry_date = self.parse_date(row.get('Entry Date'))
        exit_date = self.parse_date(row.get('Exit Date'))

        if not entry_date or not exit_date:
            self.add_error(row_num, f"Invalid dates for {symbol}")
            return None

        quantity = self.parse_int(row.get('Quantity'))
        if not quantity or quantity <= 0:
            self.add_error(row_num, f"Invalid quantity: {row.get('Quantity')}")
            return None

        buy_value = self.parse_decimal(row.get('Buy Value'))
        sell_value = self.parse_decimal(row.get('Sell Value'))
        profit = self.parse_decimal(row.get('Profit'))

        if buy_value is None or sell_value is None:
            self.add_error(row_num, f"Invalid buy/sell values for {symbol}")
            return None

        # Calculate profit if not provided
        if profit is None:
            profit = sell_value - buy_value

        # Parse holding period
        holding_days = self.parse_int(row.get('Period of Holding'))
        if holding_days is None:
            # Calculate from dates
            holding_days = (exit_date - entry_date).days

        # Determine tax term based on section and holding period
        if 'Long Term' in section_name:
            tax_term = 'LTCG'
        elif 'Short Term' in section_name or 'Intraday' in section_name:
            tax_term = 'STCG'
        else:
            # Determine from holding period
            tax_term = 'LTCG' if holding_days > 365 else 'STCG'

        # Parse charges
        brokerage = self.parse_decimal(row.get('Brokerage')) or Decimal('0')
        stt = self.parse_decimal(row.get('STT')) or Decimal('0')

        # Calculate other charges
        other_charges = Decimal('0')
        for col in ['Exchange Transaction Charges', 'IPFT', 'SEBI Charges',
                    'CGST', 'SGST', 'IGST', 'Stamp Duty']:
            val = self.parse_decimal(row.get(col))
            if val:
                other_charges += val

        return {
            'symbol': symbol,
            'isin': isin,
            'entry_date': entry_date,
            'exit_date': exit_date,
            'quantity': quantity,
            'buy_value': buy_value,
            'sell_value': sell_value,
            'profit': profit,
            'holding_days': holding_days,
            'tax_term': tax_term,
            'section': section_name,
            'financial_year': self.get_financial_year(exit_date),
            'brokerage': brokerage,
            'stt': stt,
            'other_charges': other_charges
        }

    def parse(self) -> List[Dict[str, Any]]:
        """
        Parse entire Tax P&L and return list of entries.

        Each entry: {
            'symbol': str,
            'isin': str,
            'entry_date': date,
            'exit_date': date,
            'quantity': int,
            'buy_value': Decimal,
            'sell_value': Decimal,
            'profit': Decimal,
            'holding_days': int,
            'tax_term': str,  # 'STCG' or 'LTCG'
            'section': str,
            'financial_year': str,
            'brokerage': Decimal,
            'stt': Decimal,
            'other_charges': Decimal
        }
        """
        sections = self._find_sections()
        all_entries = []

        for section_name, (start_row, end_row) in sections.items():
            entries = self._parse_section(section_name, start_row, end_row)
            all_entries.extend(entries)

        # Sort by exit date
        all_entries.sort(key=lambda x: x['exit_date'])

        return all_entries

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics from the parsed data."""
        entries = self.parse()

        if not entries:
            return {
                'total_entries': 0,
                'capital_gains': self.get_capital_gains_summary()
            }

        stcg_entries = [e for e in entries if e['tax_term'] == 'STCG']
        ltcg_entries = [e for e in entries if e['tax_term'] == 'LTCG']

        symbols = set(e['symbol'] for e in entries)
        financial_years = set(e['financial_year'] for e in entries)

        return {
            'total_entries': len(entries),
            'stcg_entries': len(stcg_entries),
            'ltcg_entries': len(ltcg_entries),
            'unique_symbols': len(symbols),
            'symbols': sorted(symbols),
            'financial_years': sorted(financial_years),
            'date_range': {
                'start': min(e['exit_date'] for e in entries),
                'end': max(e['exit_date'] for e in entries)
            },
            'total_stcg_profit': sum(e['profit'] for e in stcg_entries),
            'total_ltcg_profit': sum(e['profit'] for e in ltcg_entries),
            'total_profit': sum(e['profit'] for e in entries),
            'capital_gains': self.get_capital_gains_summary(),
            'errors': len(self.errors),
            'warnings': len(self.warnings)
        }
