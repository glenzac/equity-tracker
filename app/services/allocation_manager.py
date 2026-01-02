"""
Allocation Manager - Handles unit-level allocation to owners/goals.

Key rules:
1. Each allocation has a fixed buy price (locked at creation)
2. Total allocated units cannot exceed current holdings
3. Unallocated units go to #DEFAULT owner and #UNASSIGNED goal
4. When selling (FIFO), oldest allocations are affected first
"""
from datetime import date
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple

from app.extensions import db
from app.models import Allocation, Stock, Account, Owner, Goal, Trade
from app.services.fifo_engine import FIFOEngine


class AllocationError(Exception):
    """Base class for allocation errors."""
    pass


class InsufficientUnitsError(AllocationError):
    """Not enough units available for allocation."""
    pass


class InvalidOwnerError(AllocationError):
    """Owner does not exist."""
    pass


class InvalidGoalError(AllocationError):
    """Goal does not exist."""
    pass


class AllocationManager:
    """
    Manage unit-level allocation to owners and goals.

    Usage:
        manager = AllocationManager(stock_id=1, account_id=1)
        available = manager.get_available_units()
        allocation = manager.create_allocation(owner_id=2, goal_id=3, quantity=50)
    """

    def __init__(self, stock_id: int, account_id: int):
        self.stock_id = stock_id
        self.account_id = account_id
        self._fifo_engine: Optional[FIFOEngine] = None

    def _get_fifo_engine(self) -> FIFOEngine:
        """Get FIFO engine for this stock/account."""
        if self._fifo_engine is None:
            self._fifo_engine = FIFOEngine()

            trades = Trade.query.filter_by(
                stock_id=self.stock_id,
                account_id=self.account_id
            ).order_by(
                Trade.trade_datetime.asc().nullsfirst(),
                Trade.trade_date.asc()
            ).all()

            for trade in trades:
                if trade.trade_type == 'buy':
                    self._fifo_engine.process_buy(
                        trade_date=trade.trade_date,
                        quantity=trade.quantity,
                        price=trade.price,
                        trade_id=trade.trade_id,
                        trade_datetime=trade.trade_datetime
                    )
                else:
                    try:
                        self._fifo_engine.process_sell(
                            trade_date=trade.trade_date,
                            quantity=trade.quantity,
                            price=trade.price,
                            trade_id=trade.trade_id,
                            trade_datetime=trade.trade_datetime
                        )
                    except ValueError:
                        pass

        return self._fifo_engine

    def get_total_holdings(self) -> int:
        """Get total current holdings from FIFO."""
        return self._get_fifo_engine().get_available_quantity()

    def get_allocated_units(self) -> int:
        """Get total units already allocated."""
        result = db.session.query(
            db.func.sum(Allocation.quantity)
        ).filter_by(
            stock_id=self.stock_id,
            account_id=self.account_id
        ).scalar()
        return result or 0

    def get_available_units(self) -> int:
        """Get units available for allocation."""
        total = self.get_total_holdings()
        allocated = self.get_allocated_units()
        return max(0, total - allocated)

    def get_fifo_buy_lots(self) -> List[Dict[str, Any]]:
        """Get current buy lots in FIFO order."""
        return self._get_fifo_engine().get_current_holdings()

    def get_weighted_average_price(self, quantity: int) -> Tuple[Decimal, date]:
        """
        Calculate weighted average price for allocating a given quantity.

        Uses FIFO - takes from oldest available lots first.

        Returns:
            Tuple of (weighted_avg_price, earliest_buy_date)
        """
        lots = self._get_fifo_engine().get_current_holdings_as_lots()

        # Get already allocated quantity per lot (simplified - we assume allocations map to oldest lots)
        allocated = self.get_allocated_units()

        total_value = Decimal('0')
        total_qty = 0
        earliest_date = None
        remaining_to_allocate = quantity
        lots_to_skip = allocated

        for lot in lots:
            available_in_lot = lot.remaining_qty

            # Skip already allocated portions
            if lots_to_skip > 0:
                skip_from_lot = min(lots_to_skip, available_in_lot)
                available_in_lot -= skip_from_lot
                lots_to_skip -= skip_from_lot

            if available_in_lot <= 0:
                continue

            take_qty = min(remaining_to_allocate, available_in_lot)
            total_value += take_qty * lot.price
            total_qty += take_qty

            if earliest_date is None:
                earliest_date = lot.trade_date

            remaining_to_allocate -= take_qty
            if remaining_to_allocate <= 0:
                break

        if total_qty == 0:
            raise InsufficientUnitsError("No units available for allocation")

        avg_price = total_value / total_qty
        return avg_price, earliest_date

    def create_allocation(self, owner_id: int, goal_id: int,
                          quantity: int) -> Allocation:
        """
        Create new allocation from available units.

        Buy price is determined by FIFO (oldest available lots first).

        Args:
            owner_id: Owner ID
            goal_id: Goal ID
            quantity: Number of units to allocate

        Returns:
            Created Allocation object

        Raises:
            InsufficientUnitsError: Not enough units available
            InvalidOwnerError: Owner not found
            InvalidGoalError: Goal not found
        """
        # Validate owner
        owner = Owner.query.get(owner_id)
        if not owner:
            raise InvalidOwnerError(f"Owner with ID {owner_id} not found")

        # Validate goal
        goal = Goal.query.get(goal_id)
        if not goal:
            raise InvalidGoalError(f"Goal with ID {goal_id} not found")

        # Check available units
        available = self.get_available_units()
        if quantity > available:
            raise InsufficientUnitsError(
                f"Requested {quantity} units but only {available} available"
            )

        # Calculate buy price from FIFO lots
        avg_price, buy_date = self.get_weighted_average_price(quantity)

        # Create allocation
        allocation = Allocation(
            stock_id=self.stock_id,
            account_id=self.account_id,
            owner_id=owner_id,
            goal_id=goal_id,
            quantity=quantity,
            buy_price=avg_price,
            buy_date=buy_date
        )
        db.session.add(allocation)
        db.session.commit()

        return allocation

    def update_allocation(self, allocation_id: int,
                          new_quantity: Optional[int] = None,
                          new_owner_id: Optional[int] = None,
                          new_goal_id: Optional[int] = None) -> Allocation:
        """
        Update existing allocation.

        Note: Buy price remains fixed even when owner/goal changes.

        Args:
            allocation_id: Allocation ID
            new_quantity: New quantity (optional)
            new_owner_id: New owner ID (optional)
            new_goal_id: New goal ID (optional)

        Returns:
            Updated Allocation object
        """
        allocation = Allocation.query.get(allocation_id)
        if not allocation:
            raise AllocationError(f"Allocation {allocation_id} not found")

        if allocation.stock_id != self.stock_id or allocation.account_id != self.account_id:
            raise AllocationError("Allocation does not belong to this stock/account")

        # Update owner
        if new_owner_id is not None:
            owner = Owner.query.get(new_owner_id)
            if not owner:
                raise InvalidOwnerError(f"Owner with ID {new_owner_id} not found")
            allocation.owner_id = new_owner_id

        # Update goal
        if new_goal_id is not None:
            goal = Goal.query.get(new_goal_id)
            if not goal:
                raise InvalidGoalError(f"Goal with ID {new_goal_id} not found")
            allocation.goal_id = new_goal_id

        # Update quantity
        if new_quantity is not None:
            if new_quantity <= 0:
                raise AllocationError("Quantity must be positive")

            # Check if we have enough units
            current_allocated = self.get_allocated_units()
            available = self.get_total_holdings() - current_allocated + allocation.quantity

            if new_quantity > available:
                raise InsufficientUnitsError(
                    f"Requested {new_quantity} units but only {available} available"
                )

            allocation.quantity = new_quantity

        db.session.commit()
        return allocation

    def delete_allocation(self, allocation_id: int) -> bool:
        """
        Delete allocation. Units return to available pool.

        Args:
            allocation_id: Allocation ID

        Returns:
            True if deleted
        """
        allocation = Allocation.query.get(allocation_id)
        if not allocation:
            raise AllocationError(f"Allocation {allocation_id} not found")

        if allocation.stock_id != self.stock_id or allocation.account_id != self.account_id:
            raise AllocationError("Allocation does not belong to this stock/account")

        db.session.delete(allocation)
        db.session.commit()
        return True

    def get_allocations(self) -> List[Allocation]:
        """Get all allocations for this stock/account."""
        return Allocation.query.filter_by(
            stock_id=self.stock_id,
            account_id=self.account_id
        ).order_by(Allocation.buy_date).all()

    def get_allocations_by_owner(self, owner_id: int) -> List[Allocation]:
        """Get allocations for a specific owner."""
        return Allocation.query.filter_by(
            stock_id=self.stock_id,
            account_id=self.account_id,
            owner_id=owner_id
        ).all()

    def get_allocations_by_goal(self, goal_id: int) -> List[Allocation]:
        """Get allocations for a specific goal."""
        return Allocation.query.filter_by(
            stock_id=self.stock_id,
            account_id=self.account_id,
            goal_id=goal_id
        ).all()

    def reallocate_to_default(self, quantity: int) -> Allocation:
        """
        Create allocation to default owner/goal.

        Useful for unallocated units.
        """
        default_owner = Owner.get_default()
        default_goal = Goal.get_default()

        if not default_owner or not default_goal:
            raise AllocationError("Default owner or goal not found")

        return self.create_allocation(
            owner_id=default_owner.id,
            goal_id=default_goal.id,
            quantity=quantity
        )

    def sync_with_holdings(self) -> Dict[str, int]:
        """
        Sync allocations with actual holdings.

        If holdings decreased (due to sales), reduce allocations from oldest first.
        If holdings increased (new buys), do nothing (user must allocate manually).

        Returns:
            Dictionary with sync results
        """
        total_holdings = self.get_total_holdings()
        total_allocated = self.get_allocated_units()

        if total_allocated <= total_holdings:
            return {'adjusted': 0, 'deleted': 0}

        # Need to reduce allocations
        excess = total_allocated - total_holdings
        adjusted = 0
        deleted = 0

        # Get allocations ordered by buy_date (oldest first - FIFO)
        allocations = self.get_allocations()

        for alloc in allocations:
            if excess <= 0:
                break

            if alloc.quantity <= excess:
                # Delete entire allocation
                excess -= alloc.quantity
                db.session.delete(alloc)
                deleted += 1
            else:
                # Reduce allocation
                alloc.quantity -= excess
                adjusted += 1
                excess = 0

        db.session.commit()

        return {'adjusted': adjusted, 'deleted': deleted}
