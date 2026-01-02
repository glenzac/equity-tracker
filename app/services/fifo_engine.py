"""
FIFO Engine - Manages First-In-First-Out matching of trades

Key responsibilities:
1. Maintain buy lot queue per stock/account
2. Match sells to oldest buys first
3. Calculate holding period for each matched lot
4. Determine tax term (STCG/LTCG)
"""
from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple, Deque
from copy import deepcopy


@dataclass
class BuyLot:
    """Represents a buy lot in the FIFO queue."""
    trade_date: date
    trade_datetime: Optional[datetime]
    quantity: int
    price: Decimal
    remaining_qty: int
    trade_id: str
    order_id: Optional[str] = None

    def __post_init__(self):
        if self.remaining_qty is None:
            self.remaining_qty = self.quantity

    @property
    def value(self) -> Decimal:
        """Total value of remaining units."""
        return self.remaining_qty * self.price

    def to_dict(self) -> Dict[str, Any]:
        return {
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'trade_datetime': self.trade_datetime.isoformat() if self.trade_datetime else None,
            'quantity': self.quantity,
            'price': float(self.price),
            'remaining_qty': self.remaining_qty,
            'trade_id': self.trade_id,
            'value': float(self.value)
        }


@dataclass
class MatchedLot:
    """Represents a matched sell-to-buy lot."""
    entry_date: date
    exit_date: date
    quantity: int
    buy_price: Decimal
    sell_price: Decimal
    buy_value: Decimal
    sell_value: Decimal
    profit: Decimal
    holding_days: int
    tax_term: str  # 'STCG' or 'LTCG'
    buy_trade_id: str
    sell_trade_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'entry_date': self.entry_date.isoformat() if self.entry_date else None,
            'exit_date': self.exit_date.isoformat() if self.exit_date else None,
            'quantity': self.quantity,
            'buy_price': float(self.buy_price),
            'sell_price': float(self.sell_price),
            'buy_value': float(self.buy_value),
            'sell_value': float(self.sell_value),
            'profit': float(self.profit),
            'holding_days': self.holding_days,
            'tax_term': self.tax_term,
            'buy_trade_id': self.buy_trade_id,
            'sell_trade_id': self.sell_trade_id
        }


class FIFOEngine:
    """
    FIFO Engine for a single stock/account combination.

    Usage:
        engine = FIFOEngine()
        engine.process_buy(date(2024, 1, 1), 100, Decimal('50.00'), 'T001')
        engine.process_buy(date(2024, 2, 1), 50, Decimal('55.00'), 'T002')
        matched = engine.process_sell(date(2024, 3, 1), 80, Decimal('60.00'), 'T003')
        holdings = engine.get_current_holdings()
    """

    def __init__(self):
        self.buy_lots: Deque[BuyLot] = deque()
        self.matched_lots: List[MatchedLot] = []
        self._total_bought = 0
        self._total_sold = 0

    def process_buy(self, trade_date: date, quantity: int, price: Decimal,
                    trade_id: str, trade_datetime: Optional[datetime] = None,
                    order_id: Optional[str] = None) -> BuyLot:
        """
        Add a buy lot to the queue.

        Returns the created BuyLot.
        """
        lot = BuyLot(
            trade_date=trade_date,
            trade_datetime=trade_datetime,
            quantity=quantity,
            price=price,
            remaining_qty=quantity,
            trade_id=trade_id,
            order_id=order_id
        )
        self.buy_lots.append(lot)
        self._total_bought += quantity
        return lot

    def process_sell(self, trade_date: date, quantity: int, price: Decimal,
                     trade_id: str, trade_datetime: Optional[datetime] = None) -> List[MatchedLot]:
        """
        Match sell against oldest buy lots (FIFO).

        Returns list of matched lots with P&L calculations.

        Raises:
            ValueError: If sell quantity exceeds available holdings.
        """
        available = self.get_available_quantity()
        if quantity > available:
            raise ValueError(
                f"Sell quantity ({quantity}) exceeds available holdings ({available})"
            )

        matched = []
        remaining_sell = quantity

        while remaining_sell > 0 and self.buy_lots:
            buy_lot = self.buy_lots[0]
            matched_qty = min(remaining_sell, buy_lot.remaining_qty)

            # Calculate P&L
            buy_value = matched_qty * buy_lot.price
            sell_value = matched_qty * price
            profit = sell_value - buy_value
            holding_days = (trade_date - buy_lot.trade_date).days
            tax_term = 'LTCG' if holding_days > 365 else 'STCG'

            matched_lot = MatchedLot(
                entry_date=buy_lot.trade_date,
                exit_date=trade_date,
                quantity=matched_qty,
                buy_price=buy_lot.price,
                sell_price=price,
                buy_value=buy_value,
                sell_value=sell_value,
                profit=profit,
                holding_days=holding_days,
                tax_term=tax_term,
                buy_trade_id=buy_lot.trade_id,
                sell_trade_id=trade_id
            )
            matched.append(matched_lot)
            self.matched_lots.append(matched_lot)

            # Update quantities
            buy_lot.remaining_qty -= matched_qty
            remaining_sell -= matched_qty

            # Remove exhausted lot
            if buy_lot.remaining_qty == 0:
                self.buy_lots.popleft()

        self._total_sold += quantity
        return matched

    def get_available_quantity(self) -> int:
        """Get total available quantity (sum of remaining in buy lots)."""
        return sum(lot.remaining_qty for lot in self.buy_lots)

    def get_current_holdings(self) -> List[Dict[str, Any]]:
        """Return remaining buy lots as current holdings."""
        return [lot.to_dict() for lot in self.buy_lots if lot.remaining_qty > 0]

    def get_current_holdings_as_lots(self) -> List[BuyLot]:
        """Return remaining buy lots as BuyLot objects."""
        return [lot for lot in self.buy_lots if lot.remaining_qty > 0]

    def calculate_average_price(self) -> Optional[Decimal]:
        """Calculate weighted average buy price of remaining holdings."""
        total_qty = Decimal('0')
        total_value = Decimal('0')

        for lot in self.buy_lots:
            if lot.remaining_qty > 0:
                total_qty += lot.remaining_qty
                total_value += lot.remaining_qty * lot.price

        if total_qty == 0:
            return None

        return total_value / total_qty

    def get_realized_pnl(self) -> List[Dict[str, Any]]:
        """Get all matched lots as realized P&L entries."""
        return [lot.to_dict() for lot in self.matched_lots]

    def get_unrealized_pnl(self, current_price: Decimal) -> Dict[str, Any]:
        """Calculate unrealized P&L at a given current price."""
        total_qty = 0
        total_buy_value = Decimal('0')

        for lot in self.buy_lots:
            if lot.remaining_qty > 0:
                total_qty += lot.remaining_qty
                total_buy_value += lot.remaining_qty * lot.price

        if total_qty == 0:
            return {
                'quantity': 0,
                'buy_value': 0,
                'current_value': 0,
                'unrealized_pnl': 0,
                'unrealized_pnl_percent': 0
            }

        current_value = total_qty * current_price
        unrealized_pnl = current_value - total_buy_value
        pnl_percent = (unrealized_pnl / total_buy_value * 100) if total_buy_value else Decimal('0')

        return {
            'quantity': total_qty,
            'buy_value': float(total_buy_value),
            'current_value': float(current_value),
            'unrealized_pnl': float(unrealized_pnl),
            'unrealized_pnl_percent': float(pnl_percent)
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of the FIFO engine state."""
        avg_price = self.calculate_average_price()
        return {
            'total_bought': self._total_bought,
            'total_sold': self._total_sold,
            'available_quantity': self.get_available_quantity(),
            'average_buy_price': float(avg_price) if avg_price else None,
            'num_buy_lots': len([l for l in self.buy_lots if l.remaining_qty > 0]),
            'num_matched_lots': len(self.matched_lots),
            'total_realized_pnl': float(sum(m.profit for m in self.matched_lots))
        }

    @classmethod
    def from_trades(cls, trades: List[Dict[str, Any]]) -> 'FIFOEngine':
        """
        Create a FIFO engine from a list of trades.

        Trades should be sorted by trade_datetime or trade_date.
        Each trade dict should have: trade_type, trade_date, quantity, price, trade_id
        """
        engine = cls()

        # Sort trades by datetime for proper FIFO ordering
        sorted_trades = sorted(
            trades,
            key=lambda t: t.get('trade_datetime') or datetime.combine(t['trade_date'], datetime.min.time())
        )

        for trade in sorted_trades:
            if trade['trade_type'] == 'buy':
                engine.process_buy(
                    trade_date=trade['trade_date'],
                    quantity=trade['quantity'],
                    price=Decimal(str(trade['price'])),
                    trade_id=trade['trade_id'],
                    trade_datetime=trade.get('trade_datetime'),
                    order_id=trade.get('order_id')
                )
            elif trade['trade_type'] == 'sell':
                try:
                    engine.process_sell(
                        trade_date=trade['trade_date'],
                        quantity=trade['quantity'],
                        price=Decimal(str(trade['price'])),
                        trade_id=trade['trade_id'],
                        trade_datetime=trade.get('trade_datetime')
                    )
                except ValueError as e:
                    # This might happen if there's a data issue
                    raise ValueError(f"Error processing sell trade {trade['trade_id']}: {e}")

        return engine


def process_trades_fifo(trades: List[Dict[str, Any]]) -> Tuple[List[Dict], List[Dict]]:
    """
    Process a list of trades using FIFO and return realized P&L and remaining holdings.

    Args:
        trades: List of trade dictionaries with keys:
            - trade_type: 'buy' or 'sell'
            - trade_date: date
            - trade_datetime: datetime (optional, for ordering)
            - quantity: int
            - price: Decimal or float
            - trade_id: str

    Returns:
        Tuple of (realized_pnl_entries, remaining_holdings)
    """
    engine = FIFOEngine.from_trades(trades)
    return engine.get_realized_pnl(), engine.get_current_holdings()
