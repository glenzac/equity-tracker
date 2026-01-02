from datetime import datetime
from app.extensions import db


class Allocation(db.Model):
    """Allocation model - represents unit-level assignment to owner/goal."""
    __tablename__ = 'allocations'

    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('owners.id'), nullable=False)
    goal_id = db.Column(db.Integer, db.ForeignKey('goals.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    buy_price = db.Column(db.Numeric(15, 4), nullable=False)  # Fixed at allocation time
    buy_date = db.Column(db.Date, nullable=False)  # Earliest FIFO lot date
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint('quantity > 0', name='ck_allocation_quantity_positive'),
        db.Index('idx_allocations_stock_account', 'stock_id', 'account_id'),
        db.Index('idx_allocations_owner', 'owner_id'),
        db.Index('idx_allocations_goal', 'goal_id'),
    )

    def __repr__(self):
        return f'<Allocation {self.quantity} {self.stock.symbol if self.stock else "?"} to {self.owner.name if self.owner else "?"}>'

    def to_dict(self, include_current_price=False):
        data = {
            'id': self.id,
            'stock_id': self.stock_id,
            'symbol': self.stock.symbol if self.stock else None,
            'stock_name': self.stock.name if self.stock else None,
            'account_id': self.account_id,
            'account_number': self.account.account_number if self.account else None,
            'owner_id': self.owner_id,
            'owner_name': self.owner.name if self.owner else None,
            'goal_id': self.goal_id,
            'goal_name': self.goal.name if self.goal else None,
            'quantity': self.quantity,
            'buy_price': round(float(self.buy_price), 4) if self.buy_price else None,
            'buy_value': round(float(self.buy_price * self.quantity), 2) if self.buy_price else None,
            'buy_date': self.buy_date.isoformat() if self.buy_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

        if include_current_price and self.stock and self.stock.price_cache:
            current_price = self.stock.price_cache.current_price
            if current_price:
                data['current_price'] = round(float(current_price), 2)
                data['current_value'] = round(float(current_price * self.quantity), 2)
                data['unrealized_pnl'] = round(float((current_price - self.buy_price) * self.quantity), 2)
                if self.buy_price > 0:
                    data['unrealized_pnl_percent'] = round(float(
                        (current_price - self.buy_price) / self.buy_price * 100
                    ), 2)

        return data

    @property
    def buy_value(self):
        """Calculate buy value."""
        return self.quantity * self.buy_price

    def get_unrealized_pnl(self, current_price):
        """Calculate unrealized P&L given current price."""
        return (current_price - self.buy_price) * self.quantity

    def get_holding_days(self, as_of_date=None):
        """Calculate holding days from buy date."""
        if as_of_date is None:
            as_of_date = datetime.now().date()
        return (as_of_date - self.buy_date).days

    def get_tax_term(self, as_of_date=None):
        """Determine tax term (STCG or LTCG) based on holding period."""
        holding_days = self.get_holding_days(as_of_date)
        return 'LTCG' if holding_days > 365 else 'STCG'
