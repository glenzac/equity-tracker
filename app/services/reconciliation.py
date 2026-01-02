"""
Reconciliation Service - Cross-validates Tradebook vs Tax P&L

Detection logic for corporate actions:
1. For each Tax P&L entry, find matching tradebook buy
2. Compare quantities and prices
3. Detect patterns:
   - Stock Split: qty_ratio matches inverse of price_ratio, total value same
   - Bonus: qty increases, total value stays same, price adjusts
   - Missing data: Tax P&L has entries before earliest tradebook
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict


@dataclass
class Discrepancy:
    """Represents a discrepancy between tradebook and Tax P&L."""
    symbol: str
    isin: Optional[str]
    discrepancy_type: str  # 'quantity_mismatch', 'price_mismatch', 'missing_trade', 'corporate_action'
    tradebook_data: Optional[Dict[str, Any]]
    taxpnl_data: Optional[Dict[str, Any]]
    message: str
    detected_action: Optional[Dict[str, Any]] = None  # For corporate actions
    severity: str = 'warning'  # 'info', 'warning', 'error'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'isin': self.isin,
            'discrepancy_type': self.discrepancy_type,
            'tradebook_data': self.tradebook_data,
            'taxpnl_data': self.taxpnl_data,
            'message': self.message,
            'detected_action': self.detected_action,
            'severity': self.severity
        }


@dataclass
class ReconciliationResult:
    """Result of reconciliation between tradebook and Tax P&L."""
    matched: List[Dict[str, Any]] = field(default_factory=list)
    discrepancies: List[Discrepancy] = field(default_factory=list)
    corporate_actions: List[Dict[str, Any]] = field(default_factory=list)
    missing_tradebook_entries: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'matched': self.matched,
            'discrepancies': [d.to_dict() for d in self.discrepancies],
            'corporate_actions': self.corporate_actions,
            'missing_tradebook_entries': self.missing_tradebook_entries,
            'summary': self.summary
        }


class ReconciliationService:
    """
    Service to reconcile tradebook trades with Tax P&L entries.

    Main purposes:
    1. Validate that tradebook and Tax P&L data are consistent
    2. Detect corporate actions (splits, bonuses) from discrepancies
    3. Identify missing tradebook entries
    """

    # Common split ratios to detect
    COMMON_SPLIT_RATIOS = [2, 3, 4, 5, 10, 20, 25, 50, 100]

    # Tolerance for value matching (1%)
    VALUE_TOLERANCE = Decimal('0.01')

    def __init__(self, tradebook_trades: List[Dict[str, Any]],
                 taxpnl_entries: List[Dict[str, Any]]):
        """
        Initialize with parsed tradebook trades and Tax P&L entries.

        Args:
            tradebook_trades: List of trades from ZerodhaTradeBookParser.parse()
            taxpnl_entries: List of entries from ZerodhaTaxPnLParser.parse()
        """
        self.tradebook_trades = tradebook_trades
        self.taxpnl_entries = taxpnl_entries

        # Index trades by symbol and ISIN for faster lookup
        self._trades_by_symbol = defaultdict(list)
        self._trades_by_isin = defaultdict(list)
        self._index_trades()

    def _index_trades(self):
        """Index tradebook trades by symbol and ISIN."""
        for trade in self.tradebook_trades:
            symbol = trade.get('symbol')
            isin = trade.get('isin')
            if symbol:
                self._trades_by_symbol[symbol].append(trade)
            if isin:
                self._trades_by_isin[isin].append(trade)

    def get_trades_for_symbol(self, symbol: str, isin: Optional[str] = None) -> List[Dict]:
        """Get all tradebook trades for a symbol/ISIN."""
        # Try ISIN first as it's more reliable
        if isin and isin in self._trades_by_isin:
            return self._trades_by_isin[isin]
        return self._trades_by_symbol.get(symbol, [])

    def get_buys_before_date(self, symbol: str, isin: Optional[str],
                              before_date: date) -> List[Dict]:
        """Get buy trades for a symbol that occurred before a specific date."""
        trades = self.get_trades_for_symbol(symbol, isin)
        return [
            t for t in trades
            if t['trade_type'] == 'buy' and t['trade_date'] <= before_date
        ]

    def find_matching_buy(self, taxpnl_entry: Dict) -> Optional[Dict]:
        """
        Find the tradebook buy trade that matches a Tax P&L entry.

        Match criteria:
        1. Same ISIN or symbol
        2. Buy date matches entry_date in Tax P&L
        3. Similar quantity and price (allowing for corporate actions)
        """
        symbol = taxpnl_entry['symbol']
        isin = taxpnl_entry.get('isin')
        entry_date = taxpnl_entry['entry_date']
        quantity = taxpnl_entry['quantity']
        buy_value = taxpnl_entry['buy_value']

        trades = self.get_trades_for_symbol(symbol, isin)
        buy_trades = [t for t in trades if t['trade_type'] == 'buy']

        # Look for exact date match first
        for trade in buy_trades:
            if trade['trade_date'] == entry_date:
                # Check if values match (exact or split-adjusted)
                trade_value = trade['quantity'] * trade['price']
                if self._values_match(trade_value, buy_value):
                    return trade

        # Look for close date match (within 1 day for settlement differences)
        for trade in buy_trades:
            date_diff = abs((trade['trade_date'] - entry_date).days)
            if date_diff <= 1:
                trade_value = trade['quantity'] * trade['price']
                if self._values_match(trade_value, buy_value):
                    return trade

        return None

    def _values_match(self, value1: Decimal, value2: Decimal,
                      tolerance: Optional[Decimal] = None) -> bool:
        """Check if two values match within tolerance."""
        if tolerance is None:
            tolerance = self.VALUE_TOLERANCE

        if value1 == 0 and value2 == 0:
            return True
        if value1 == 0 or value2 == 0:
            return False

        diff_ratio = abs(value1 - value2) / max(abs(value1), abs(value2))
        return diff_ratio <= tolerance

    def detect_stock_split(self, tradebook_entry: Dict,
                           taxpnl_entry: Dict) -> Optional[Dict[str, Any]]:
        """
        Detect if discrepancy is due to stock split.

        Example (NESTLEIND 1:10 split):
        - Tradebook: 1 unit @ Rs.25,634 = Rs.25,634
        - Tax P&L: 10 units @ Rs.2,563.4 = Rs.25,634
        - Ratio: 10:1, Values match -> Stock Split
        """
        tb_qty = tradebook_entry['quantity']
        tb_price = tradebook_entry['price']
        tb_value = tb_qty * tb_price

        pnl_qty = taxpnl_entry['quantity']
        pnl_value = taxpnl_entry['buy_value']
        pnl_price = pnl_value / pnl_qty if pnl_qty else Decimal('0')

        # Check if total values match
        if not self._values_match(tb_value, pnl_value, Decimal('0.02')):
            return None  # Values don't match, not a simple split

        # Calculate quantity ratio
        if tb_qty == 0:
            return None

        qty_ratio = pnl_qty / tb_qty

        # Check if it's a clean ratio
        for ratio in self.COMMON_SPLIT_RATIOS:
            if abs(qty_ratio - ratio) < 0.01:
                # Verify price ratio is inverse
                expected_new_price = tb_price / ratio
                if abs(pnl_price - expected_new_price) / tb_price < 0.02:
                    return {
                        'action_type': 'split',
                        'symbol': taxpnl_entry['symbol'],
                        'isin': taxpnl_entry.get('isin'),
                        'ratio_from': 1,
                        'ratio_to': ratio,
                        'old_price': float(tb_price),
                        'new_price': float(pnl_price),
                        'detected_automatically': True,
                        'confidence': 'high' if abs(qty_ratio - ratio) < 0.001 else 'medium'
                    }

        return None

    def detect_bonus_issue(self, tradebook_entry: Dict,
                           taxpnl_entry: Dict) -> Optional[Dict[str, Any]]:
        """
        Detect if discrepancy is due to bonus issue.

        Example (1:1 bonus):
        - Original: 100 units @ Rs.500 = Rs.50,000
        - After bonus: 200 units @ Rs.250 = Rs.50,000 (same total value)

        Note: Bonus shares have zero cost basis, but when sold,
        the Tax P&L may show adjusted cost basis.
        """
        tb_qty = tradebook_entry['quantity']
        tb_price = tradebook_entry['price']
        tb_value = tb_qty * tb_price

        pnl_qty = taxpnl_entry['quantity']
        pnl_value = taxpnl_entry['buy_value']

        # For bonus, total value stays same but quantity increases
        if not self._values_match(tb_value, pnl_value, Decimal('0.02')):
            return None

        if pnl_qty <= tb_qty:
            return None  # Quantity should increase for bonus

        # Calculate bonus ratio
        qty_ratio = pnl_qty / tb_qty

        # Common bonus ratios: 1:1 (2x), 2:1 (1.5x), 1:2 (3x), etc.
        bonus_ratios = [
            (1, 1, 2.0),   # 1:1 bonus = 2x shares
            (1, 2, 1.5),   # 1:2 bonus = 1.5x shares
            (2, 1, 3.0),   # 2:1 bonus = 3x shares
            (3, 1, 4.0),   # 3:1 bonus = 4x shares
        ]

        for bonus_num, bonus_den, expected_ratio in bonus_ratios:
            if abs(qty_ratio - expected_ratio) < 0.01:
                return {
                    'action_type': 'bonus',
                    'symbol': taxpnl_entry['symbol'],
                    'isin': taxpnl_entry.get('isin'),
                    'ratio_from': bonus_den,
                    'ratio_to': bonus_num,
                    'old_price': float(tb_price),
                    'new_price': float(pnl_value / pnl_qty),
                    'detected_automatically': True,
                    'confidence': 'medium'
                }

        return None

    def reconcile(self, financial_year: Optional[str] = None) -> ReconciliationResult:
        """
        Run full reconciliation between tradebook and Tax P&L.

        Args:
            financial_year: Optional filter by financial year (e.g., '2024-2025')

        Returns:
            ReconciliationResult with matched entries, discrepancies, and detected actions.
        """
        result = ReconciliationResult()

        # Filter Tax P&L entries by financial year if specified
        entries = self.taxpnl_entries
        if financial_year:
            entries = [e for e in entries if e.get('financial_year') == financial_year]

        # Get earliest tradebook date
        earliest_tradebook_date = None
        if self.tradebook_trades:
            earliest_tradebook_date = min(t['trade_date'] for t in self.tradebook_trades)

        for entry in entries:
            symbol = entry['symbol']
            isin = entry.get('isin')
            entry_date = entry['entry_date']

            # Check if this entry is before our tradebook data
            if earliest_tradebook_date and entry_date < earliest_tradebook_date:
                result.missing_tradebook_entries.append({
                    'symbol': symbol,
                    'isin': isin,
                    'entry_date': entry_date.isoformat(),
                    'quantity': entry['quantity'],
                    'buy_value': float(entry['buy_value']),
                    'message': f"Entry date {entry_date} is before earliest tradebook date {earliest_tradebook_date}"
                })
                continue

            # Try to find matching buy trade
            matching_trade = self.find_matching_buy(entry)

            if matching_trade:
                # Check for quantity/price discrepancies
                if (matching_trade['quantity'] == entry['quantity'] and
                    self._values_match(
                        matching_trade['quantity'] * matching_trade['price'],
                        entry['buy_value']
                    )):
                    # Perfect match
                    result.matched.append({
                        'symbol': symbol,
                        'isin': isin,
                        'entry_date': entry_date.isoformat(),
                        'tradebook_trade_id': matching_trade['trade_id'],
                        'quantity': entry['quantity'],
                        'buy_value': float(entry['buy_value'])
                    })
                else:
                    # Quantity or price mismatch - check for corporate action
                    split_action = self.detect_stock_split(matching_trade, entry)
                    if split_action:
                        result.corporate_actions.append(split_action)
                        result.discrepancies.append(Discrepancy(
                            symbol=symbol,
                            isin=isin,
                            discrepancy_type='corporate_action',
                            tradebook_data={
                                'trade_id': matching_trade['trade_id'],
                                'quantity': matching_trade['quantity'],
                                'price': float(matching_trade['price']),
                                'date': matching_trade['trade_date'].isoformat()
                            },
                            taxpnl_data={
                                'quantity': entry['quantity'],
                                'buy_value': float(entry['buy_value']),
                                'entry_date': entry_date.isoformat()
                            },
                            message=f"Stock split detected: {split_action['ratio_from']}:{split_action['ratio_to']}",
                            detected_action=split_action,
                            severity='info'
                        ))
                        continue

                    bonus_action = self.detect_bonus_issue(matching_trade, entry)
                    if bonus_action:
                        result.corporate_actions.append(bonus_action)
                        result.discrepancies.append(Discrepancy(
                            symbol=symbol,
                            isin=isin,
                            discrepancy_type='corporate_action',
                            tradebook_data={
                                'trade_id': matching_trade['trade_id'],
                                'quantity': matching_trade['quantity'],
                                'price': float(matching_trade['price']),
                                'date': matching_trade['trade_date'].isoformat()
                            },
                            taxpnl_data={
                                'quantity': entry['quantity'],
                                'buy_value': float(entry['buy_value']),
                                'entry_date': entry_date.isoformat()
                            },
                            message=f"Bonus issue detected: {bonus_action['ratio_to']}:{bonus_action['ratio_from']}",
                            detected_action=bonus_action,
                            severity='info'
                        ))
                        continue

                    # Unknown discrepancy
                    result.discrepancies.append(Discrepancy(
                        symbol=symbol,
                        isin=isin,
                        discrepancy_type='quantity_mismatch' if matching_trade['quantity'] != entry['quantity'] else 'price_mismatch',
                        tradebook_data={
                            'trade_id': matching_trade['trade_id'],
                            'quantity': matching_trade['quantity'],
                            'price': float(matching_trade['price']),
                            'value': float(matching_trade['quantity'] * matching_trade['price']),
                            'date': matching_trade['trade_date'].isoformat()
                        },
                        taxpnl_data={
                            'quantity': entry['quantity'],
                            'buy_value': float(entry['buy_value']),
                            'entry_date': entry_date.isoformat()
                        },
                        message=f"Quantity or price mismatch for {symbol}",
                        severity='warning'
                    ))
            else:
                # No matching trade found
                result.discrepancies.append(Discrepancy(
                    symbol=symbol,
                    isin=isin,
                    discrepancy_type='missing_trade',
                    tradebook_data=None,
                    taxpnl_data={
                        'quantity': entry['quantity'],
                        'buy_value': float(entry['buy_value']),
                        'entry_date': entry_date.isoformat(),
                        'exit_date': entry['exit_date'].isoformat()
                    },
                    message=f"No matching tradebook entry found for {symbol} bought on {entry_date}",
                    severity='warning'
                ))

        # Generate summary
        result.summary = {
            'total_taxpnl_entries': len(entries),
            'matched': len(result.matched),
            'discrepancies': len(result.discrepancies),
            'corporate_actions': len(result.corporate_actions),
            'missing_tradebook_entries': len(result.missing_tradebook_entries),
            'match_rate': len(result.matched) / len(entries) * 100 if entries else 0
        }

        return result
