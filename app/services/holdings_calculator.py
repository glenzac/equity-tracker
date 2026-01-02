"""
Holdings Calculator - Calculate current holdings from trades.

Provides:
1. Current holdings per stock/account
2. FIFO-based buy lots for each holding
3. Unrealized P&L calculations
4. Holdings aggregation by owner/goal/sector
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from collections import defaultdict
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Trade, Stock, Account, Allocation, PriceCache, Sector, CorporateAction
from app.services.fifo_engine import FIFOEngine, BuyLot
from app.services.corporate_actions import CorporateActionService

logger = logging.getLogger(__name__)


@dataclass
class Holding:
    """Represents a stock holding with calculated metrics."""
    stock_id: int
    account_id: int
    symbol: str
    stock_name: str
    isin: Optional[str]
    sector_id: Optional[int]
    sector_name: Optional[str]
    exchange: Optional[str]
    quantity: int
    avg_buy_price: Decimal
    total_buy_value: Decimal
    current_price: Optional[Decimal]
    current_value: Optional[Decimal]
    unrealized_pnl: Optional[Decimal]
    unrealized_pnl_percent: Optional[Decimal]
    day_change_percent: Optional[Decimal]
    buy_lots: List[Dict[str, Any]] = field(default_factory=list)
    allocations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'stock_id': self.stock_id,
            'account_id': self.account_id,
            'symbol': self.symbol,
            'stock_name': self.stock_name,
            'isin': self.isin,
            'sector_id': self.sector_id,
            'sector_name': self.sector_name,
            'exchange': self.exchange,
            'quantity': self.quantity,
            'avg_buy_price': round(float(self.avg_buy_price), 4) if self.avg_buy_price else None,
            'total_buy_value': round(float(self.total_buy_value), 2) if self.total_buy_value else None,
            'current_price': round(float(self.current_price), 2) if self.current_price else None,
            'current_value': round(float(self.current_value), 2) if self.current_value else None,
            'unrealized_pnl': round(float(self.unrealized_pnl), 2) if self.unrealized_pnl else None,
            'unrealized_pnl_percent': round(float(self.unrealized_pnl_percent), 2) if self.unrealized_pnl_percent else None,
            'day_change_percent': round(float(self.day_change_percent), 2) if self.day_change_percent else None,
            'buy_lots': self.buy_lots,
            'allocations': self.allocations
        }


class HoldingsCalculator:
    """
    Calculate holdings from trades using FIFO.

    Usage:
        calculator = HoldingsCalculator()
        holdings = calculator.get_holdings(account_id=1)
        summary = calculator.get_summary(account_id=1)
    """

    def __init__(self):
        self._fifo_engines: Dict[tuple, FIFOEngine] = {}

    def _get_fifo_engine(self, stock_id: int, account_id: int) -> FIFOEngine:
        """Get or create FIFO engine for a stock/account combination."""
        key = (stock_id, account_id)
        if key not in self._fifo_engines:
            engine = FIFOEngine()

            # Load trades
            trades = Trade.query.filter_by(
                stock_id=stock_id,
                account_id=account_id
            ).order_by(
                Trade.trade_datetime.asc().nullsfirst(),
                Trade.trade_date.asc()
            ).all()

            # Check for existing corporate actions or detect new ones
            splits = CorporateAction.query.filter_by(
                stock_id=stock_id,
                action_type='split'
            ).all()

            # If no splits found, try to detect from trade patterns
            if not splits:
                detected = CorporateActionService.detect_and_save_splits(stock_id, account_id)
                if detected:
                    splits = [detected]

            # Determine split date if we have splits
            split_info = None
            if splits:
                # Use the most recent split
                split = max(splits, key=lambda s: s.record_date or date.min)
                split_ratio = split.ratio_to / split.ratio_from
                split_info = {
                    'ratio': split_ratio,
                    'record_date': split.record_date,
                    'old_price': split.old_price,
                    'new_price': split.new_price
                }

            for trade in trades:
                quantity = trade.quantity
                price = trade.price

                # Apply split adjustment for pre-split buys
                if split_info and trade.trade_type == 'buy':
                    # Detect if this is a pre-split trade by comparing price
                    if split_info['old_price'] and split_info['new_price']:
                        # If trade price is close to old (pre-split) price, adjust it
                        new_price_float = float(split_info['new_price'])
                        price_ratio = float(trade.price) / new_price_float if new_price_float > 0 else 0
                        if price_ratio > split_info['ratio'] * 0.8:
                            # This is a pre-split trade, adjust quantity and price
                            quantity = int(trade.quantity * split_info['ratio'])
                            price = Decimal(str(float(trade.price) / split_info['ratio']))

                if trade.trade_type == 'buy':
                    engine.process_buy(
                        trade_date=trade.trade_date,
                        quantity=quantity,
                        price=price,
                        trade_id=trade.trade_id,
                        trade_datetime=trade.trade_datetime,
                        order_id=trade.order_id
                    )
                else:
                    try:
                        engine.process_sell(
                            trade_date=trade.trade_date,
                            quantity=trade.quantity,  # Sells are always in post-split quantities
                            price=trade.price,
                            trade_id=trade.trade_id,
                            trade_datetime=trade.trade_datetime
                        )
                    except ValueError:
                        # Data issue - sell exceeds holdings
                        pass

            self._fifo_engines[key] = engine

        return self._fifo_engines[key]

    def get_holding(self, stock_id: int, account_id: int,
                    include_lots: bool = True,
                    include_allocations: bool = True) -> Optional[Holding]:
        """Get holding for a specific stock/account."""
        engine = self._get_fifo_engine(stock_id, account_id)
        quantity = engine.get_available_quantity()

        if quantity == 0:
            return None

        # Eager load related objects to avoid N+1 queries
        stock = Stock.query.options(
            joinedload(Stock.sector),
            joinedload(Stock.price_cache)
        ).get(stock_id)
        account = Account.query.get(account_id)

        if not stock or not account:
            return None

        avg_price = engine.calculate_average_price()
        total_buy_value = Decimal(quantity) * avg_price if avg_price else Decimal('0')

        # Get current price
        current_price = None
        day_change = None
        if stock.price_cache:
            current_price = stock.price_cache.current_price
            day_change = stock.price_cache.change_percent

        current_value = None
        unrealized_pnl = None
        unrealized_pnl_percent = None

        if current_price:
            current_value = Decimal(quantity) * current_price
            unrealized_pnl = current_value - total_buy_value
            if total_buy_value > 0:
                unrealized_pnl_percent = (unrealized_pnl / total_buy_value) * 100

        holding = Holding(
            stock_id=stock_id,
            account_id=account_id,
            symbol=stock.symbol,
            stock_name=stock.name,
            isin=stock.isin,
            sector_id=stock.sector_id,
            sector_name=stock.sector.name if stock.sector else None,
            exchange=stock.exchange,
            quantity=quantity,
            avg_buy_price=avg_price or Decimal('0'),
            total_buy_value=total_buy_value,
            current_price=current_price,
            current_value=current_value,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_percent=unrealized_pnl_percent,
            day_change_percent=day_change
        )

        if include_lots:
            holding.buy_lots = engine.get_current_holdings()

        if include_allocations:
            allocations = Allocation.query.filter_by(
                stock_id=stock_id,
                account_id=account_id
            ).all()
            holding.allocations = [a.to_dict() for a in allocations]

        return holding

    def get_holdings(self, account_id: Optional[int] = None,
                     owner_id: Optional[int] = None,
                     goal_id: Optional[int] = None,
                     sector_id: Optional[int] = None,
                     include_lots: bool = False,
                     include_allocations: bool = True) -> List[Holding]:
        """
        Get all holdings with optional filters.

        Args:
            account_id: Filter by account
            owner_id: Filter by owner (via allocations)
            goal_id: Filter by goal (via allocations)
            sector_id: Filter by sector
            include_lots: Include FIFO buy lots
            include_allocations: Include allocation details

        Returns:
            List of Holding objects
        """
        # Get distinct stock/account combinations with trades
        query = db.session.query(
            Trade.stock_id,
            Trade.account_id
        ).distinct()

        if account_id:
            query = query.filter(Trade.account_id == account_id)

        stock_accounts = query.all()

        holdings = []
        for stock_id, acc_id in stock_accounts:
            holding = self.get_holding(
                stock_id=stock_id,
                account_id=acc_id,
                include_lots=include_lots,
                include_allocations=include_allocations
            )

            if holding and holding.quantity > 0:
                # Apply filters
                if sector_id and holding.sector_id != sector_id:
                    continue

                if owner_id or goal_id:
                    # Check allocations
                    alloc_query = Allocation.query.filter_by(
                        stock_id=stock_id,
                        account_id=acc_id
                    )
                    if owner_id:
                        alloc_query = alloc_query.filter_by(owner_id=owner_id)
                    if goal_id:
                        alloc_query = alloc_query.filter_by(goal_id=goal_id)

                    if alloc_query.count() == 0:
                        continue

                holdings.append(holding)

        # Sort by current value (descending)
        holdings.sort(
            key=lambda h: h.current_value or h.total_buy_value or 0,
            reverse=True
        )

        return holdings

    def get_summary(self, account_id: Optional[int] = None,
                    owner_id: Optional[int] = None,
                    goal_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get portfolio summary with totals.

        Returns:
            Dictionary with total values, P&L, etc.
        """
        holdings = self.get_holdings(
            account_id=account_id,
            owner_id=owner_id,
            goal_id=goal_id,
            include_lots=False,
            include_allocations=False
        )

        total_buy_value = Decimal('0')
        total_current_value = Decimal('0')
        total_unrealized_pnl = Decimal('0')
        holdings_with_price = 0

        for h in holdings:
            total_buy_value += h.total_buy_value or Decimal('0')
            if h.current_value:
                total_current_value += h.current_value
                holdings_with_price += 1
            if h.unrealized_pnl:
                total_unrealized_pnl += h.unrealized_pnl

        pnl_percent = None
        if total_buy_value > 0:
            pnl_percent = (total_unrealized_pnl / total_buy_value) * 100

        return {
            'total_holdings': len(holdings),
            'holdings_with_price': holdings_with_price,
            'total_buy_value': float(total_buy_value),
            'total_current_value': float(total_current_value),
            'total_unrealized_pnl': float(total_unrealized_pnl),
            'total_unrealized_pnl_percent': float(pnl_percent) if pnl_percent else None
        }

    def get_sector_allocation(self, account_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get holdings grouped by sector."""
        holdings = self.get_holdings(account_id=account_id, include_lots=False)

        sector_totals = defaultdict(lambda: {'value': Decimal('0'), 'count': 0})

        for h in holdings:
            sector_name = h.sector_name or 'Others'
            value = h.current_value or h.total_buy_value or Decimal('0')
            sector_totals[sector_name]['value'] += value
            sector_totals[sector_name]['count'] += 1

        total_value = sum(s['value'] for s in sector_totals.values())

        result = []
        for sector_name, data in sorted(sector_totals.items(), key=lambda x: -x[1]['value']):
            pct = (data['value'] / total_value * 100) if total_value > 0 else 0
            result.append({
                'sector': sector_name,
                'value': float(data['value']),
                'count': data['count'],
                'percentage': float(pct)
            })

        return result

    def get_owner_allocation(self, account_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get holdings grouped by owner."""
        query = db.session.query(
            Allocation.owner_id,
            db.func.sum(Allocation.quantity * Allocation.buy_price).label('buy_value')
        ).group_by(Allocation.owner_id)

        if account_id:
            query = query.filter(Allocation.account_id == account_id)

        results = query.all()

        from app.models import Owner
        total_value = sum(r.buy_value or 0 for r in results)

        allocations = []
        for r in results:
            owner = Owner.query.get(r.owner_id)
            if owner:
                pct = (r.buy_value / total_value * 100) if total_value > 0 else 0
                allocations.append({
                    'owner_id': owner.id,
                    'owner_name': owner.name,
                    'value': float(r.buy_value or 0),
                    'percentage': float(pct)
                })

        return sorted(allocations, key=lambda x: -x['value'])

    def get_goal_allocation(self, account_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get holdings grouped by goal."""
        query = db.session.query(
            Allocation.goal_id,
            db.func.sum(Allocation.quantity * Allocation.buy_price).label('buy_value')
        ).group_by(Allocation.goal_id)

        if account_id:
            query = query.filter(Allocation.account_id == account_id)

        results = query.all()

        from app.models import Goal
        total_value = sum(r.buy_value or 0 for r in results)

        allocations = []
        for r in results:
            goal = Goal.query.get(r.goal_id)
            if goal:
                pct = (r.buy_value / total_value * 100) if total_value > 0 else 0
                allocations.append({
                    'goal_id': goal.id,
                    'goal_name': goal.name,
                    'target_amount': float(goal.target_amount) if goal.target_amount else None,
                    'value': float(r.buy_value or 0),
                    'percentage': float(pct)
                })

        return sorted(allocations, key=lambda x: -x['value'])
