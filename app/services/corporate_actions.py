"""
Corporate Action Service - Detect and apply stock splits and bonuses.

Detection approaches:
1. Price pattern detection: When consecutive trades show significant price ratio changes
2. Tax P&L reconciliation: Compare tradebook quantities with Tax P&L post-split quantities
3. Manual entry: Allow users to add known corporate actions

Application:
- Adjust pre-split buy lot quantities and prices
- Maintain audit trail of applied adjustments
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from app.extensions import db
from app.models import Trade, Stock, CorporateAction


# Common split ratios to detect
COMMON_SPLIT_RATIOS = [2, 3, 4, 5, 10, 20, 25, 50, 100]

# Price ratio thresholds for split detection (min, max) for each split ratio
# Widened thresholds to account for market price fluctuations between split date and next trade
SPLIT_DETECTION_THRESHOLDS = {
    2: (1.7, 2.4),
    3: (2.5, 3.6),
    4: (3.4, 4.8),
    5: (4.2, 6.0),
    10: (8.5, 12.0),
    20: (17.0, 24.0),
    25: (21.0, 30.0),
    50: (42.0, 60.0),
    100: (85.0, 120.0),
}


class CorporateActionService:
    """Service to detect and apply corporate actions."""

    @staticmethod
    def detect_split_from_prices(stock_id: int, account_id: int) -> Optional[Dict[str, Any]]:
        """
        Detect stock split from price pattern in trades.

        Looks for a significant price drop between consecutive buy trades
        that suggests a stock split occurred.

        Returns:
            Dictionary with split details if detected, None otherwise
        """
        # Get buy trades ordered by date
        buy_trades = Trade.query.filter_by(
            stock_id=stock_id,
            account_id=account_id,
            trade_type='buy'
        ).order_by(Trade.trade_date, Trade.trade_datetime).all()

        if len(buy_trades) < 2:
            return None

        # Look for price drops that indicate splits
        for i in range(1, len(buy_trades)):
            prev_trade = buy_trades[i - 1]
            curr_trade = buy_trades[i]

            if curr_trade.price <= 0:
                continue

            price_ratio = float(prev_trade.price) / float(curr_trade.price)

            # Check if ratio matches a common split ratio
            for split_ratio, (min_ratio, max_ratio) in SPLIT_DETECTION_THRESHOLDS.items():
                if min_ratio <= price_ratio <= max_ratio:
                    # Found a potential split
                    # Estimate split date as between the two trades
                    split_date = curr_trade.trade_date

                    return {
                        'stock_id': stock_id,
                        'action_type': 'split',
                        'ratio_from': 1,
                        'ratio_to': split_ratio,
                        'old_price': float(prev_trade.price),
                        'new_price': float(curr_trade.price),
                        'detected_date': split_date,
                        'pre_split_trade_id': prev_trade.trade_id,
                        'post_split_trade_id': curr_trade.trade_id,
                        'confidence': 'high' if abs(price_ratio - split_ratio) < 0.5 else 'medium'
                    }

        return None

    @staticmethod
    def detect_split_from_sell_mismatch(stock_id: int, account_id: int) -> Optional[Dict[str, Any]]:
        """
        Detect stock split when sell quantity exceeds calculated holdings.

        If FIFO calculation shows negative holdings, it's likely due to an
        undetected stock split.
        """
        from app.services.fifo_engine import FIFOEngine

        trades = Trade.query.filter_by(
            stock_id=stock_id,
            account_id=account_id
        ).order_by(Trade.trade_date, Trade.trade_datetime).all()

        # Calculate raw holdings
        total_buy = sum(t.quantity for t in trades if t.trade_type == 'buy')
        total_sell = sum(t.quantity for t in trades if t.trade_type == 'sell')

        if total_sell <= total_buy:
            return None  # No mismatch

        # There's a mismatch - try to find split ratio
        sell_to_buy_ratio = total_sell / total_buy if total_buy > 0 else 0

        # Check common split ratios
        for split_ratio in COMMON_SPLIT_RATIOS:
            expected_holdings_after_split = total_buy * split_ratio
            if abs(expected_holdings_after_split - total_sell) <= total_sell * 0.1:  # 10% tolerance
                # Found matching ratio
                # Find the likely split point (where price dropped significantly)
                buy_trades = [t for t in trades if t.trade_type == 'buy']

                split_date = None
                old_price = None
                new_price = None

                for i in range(1, len(buy_trades)):
                    prev = buy_trades[i - 1]
                    curr = buy_trades[i]
                    ratio = float(prev.price) / float(curr.price) if curr.price > 0 else 0
                    if 0.8 * split_ratio <= ratio <= 1.2 * split_ratio:
                        split_date = curr.trade_date
                        old_price = float(prev.price)
                        new_price = float(curr.price)
                        break

                return {
                    'stock_id': stock_id,
                    'action_type': 'split',
                    'ratio_from': 1,
                    'ratio_to': split_ratio,
                    'old_price': old_price,
                    'new_price': new_price,
                    'detected_date': split_date,
                    'total_buy': total_buy,
                    'total_sell': total_sell,
                    'confidence': 'medium'
                }

        return None

    @staticmethod
    def save_corporate_action(action_data: Dict[str, Any]) -> CorporateAction:
        """Save detected corporate action to database."""
        stock_id = action_data['stock_id']
        action_type = action_data['action_type']
        ratio_from = action_data['ratio_from']
        ratio_to = action_data['ratio_to']

        # Check if already exists
        existing = CorporateAction.query.filter_by(
            stock_id=stock_id,
            action_type=action_type,
            ratio_from=ratio_from,
            ratio_to=ratio_to
        ).first()

        if existing:
            return existing

        ca = CorporateAction(
            stock_id=stock_id,
            action_type=action_type,
            record_date=action_data.get('detected_date'),
            ratio_from=ratio_from,
            ratio_to=ratio_to,
            old_price=action_data.get('old_price'),
            new_price=action_data.get('new_price'),
            detected_automatically=True,
            applied=False
        )
        db.session.add(ca)
        db.session.commit()

        return ca

    @staticmethod
    def get_applicable_splits(stock_id: int, before_date: date) -> List[CorporateAction]:
        """
        Get all stock splits that apply to holdings bought before a given date.

        Args:
            stock_id: Stock ID
            before_date: Get splits that occurred after holdings were bought

        Returns:
            List of CorporateAction objects
        """
        return CorporateAction.query.filter(
            CorporateAction.stock_id == stock_id,
            CorporateAction.action_type == 'split',
            CorporateAction.record_date <= datetime.now().date()
        ).order_by(CorporateAction.record_date).all()

    @staticmethod
    def adjust_quantity_for_splits(original_qty: int, original_price: Decimal,
                                   buy_date: date, splits: List[CorporateAction]
                                   ) -> Tuple[int, Decimal]:
        """
        Adjust quantity and price for stock splits that occurred after purchase.

        Args:
            original_qty: Original quantity bought
            original_price: Original buy price
            buy_date: Date of purchase
            splits: List of splits to apply

        Returns:
            Tuple of (adjusted_quantity, adjusted_price)
        """
        adjusted_qty = original_qty
        adjusted_price = original_price

        for split in splits:
            if split.record_date and buy_date < split.record_date:
                # Apply this split
                split_ratio = split.ratio_to / split.ratio_from
                adjusted_qty = int(adjusted_qty * split_ratio)
                adjusted_price = adjusted_price / Decimal(str(split_ratio))

        return adjusted_qty, adjusted_price

    @staticmethod
    def detect_and_save_splits(stock_id: int, account_id: int) -> Optional[CorporateAction]:
        """
        Detect splits using multiple methods and save if found.

        Returns:
            CorporateAction if detected and saved, None otherwise
        """
        # Try price pattern detection first
        split_data = CorporateActionService.detect_split_from_prices(stock_id, account_id)

        # If not found, try sell mismatch detection
        if not split_data:
            split_data = CorporateActionService.detect_split_from_sell_mismatch(stock_id, account_id)

        if split_data:
            return CorporateActionService.save_corporate_action(split_data)

        return None
