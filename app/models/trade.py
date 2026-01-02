from datetime import datetime
from app.extensions import db


class Trade(db.Model):
    """Trade model - represents a buy/sell transaction from tradebook."""
    __tablename__ = 'trades'

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    trade_type = db.Column(db.String(4), nullable=False)  # 'buy' or 'sell'
    trade_date = db.Column(db.Date, nullable=False)
    trade_datetime = db.Column(db.DateTime, nullable=True)  # For precise FIFO ordering
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric(15, 4), nullable=False)
    exchange = db.Column(db.String(10), nullable=True)  # NSE, BSE
    order_id = db.Column(db.String(50), nullable=True)
    trade_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Unique constraint: account + trade_id
    __table_args__ = (
        db.UniqueConstraint('account_id', 'trade_id', name='uq_account_trade'),
        db.CheckConstraint("trade_type IN ('buy', 'sell')", name='ck_trade_type'),
        db.CheckConstraint('quantity > 0', name='ck_quantity_positive'),
        db.CheckConstraint('price > 0', name='ck_price_positive'),
        db.Index('idx_trades_fifo', 'stock_id', 'account_id', 'trade_type', 'trade_datetime'),
    )

    def __repr__(self):
        return f'<Trade {self.trade_type} {self.quantity} {self.stock.symbol if self.stock else "?"} @ {self.price}>'

    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'account_number': self.account.account_number if self.account else None,
            'stock_id': self.stock_id,
            'symbol': self.stock.symbol if self.stock else None,
            'trade_type': self.trade_type,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'trade_datetime': self.trade_datetime.isoformat() if self.trade_datetime else None,
            'quantity': self.quantity,
            'price': float(self.price) if self.price else None,
            'value': float(self.price * self.quantity) if self.price else None,
            'exchange': self.exchange,
            'order_id': self.order_id,
            'trade_id': self.trade_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    @property
    def value(self):
        """Calculate trade value."""
        return self.quantity * self.price

    @classmethod
    def get_by_trade_id(cls, account_id, trade_id):
        """Get trade by account and trade_id."""
        return cls.query.filter_by(account_id=account_id, trade_id=trade_id).first()

    @classmethod
    def exists(cls, account_id, trade_id):
        """Check if trade already exists."""
        return cls.query.filter_by(account_id=account_id, trade_id=trade_id).count() > 0
