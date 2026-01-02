from datetime import datetime
from app.extensions import db


class Account(db.Model):
    """Account model - represents a trading account with a broker."""
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True)
    broker_id = db.Column(db.Integer, db.ForeignKey('brokers.id'), nullable=False)
    account_number = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Unique constraint on broker + account number
    __table_args__ = (
        db.UniqueConstraint('broker_id', 'account_number', name='uq_broker_account'),
    )

    # Relationships
    trades = db.relationship('Trade', backref='account', lazy='dynamic',
                             cascade='all, delete-orphan')
    allocations = db.relationship('Allocation', backref='account', lazy='dynamic',
                                  cascade='all, delete-orphan')
    realized_pnls = db.relationship('RealizedPnL', backref='account', lazy='dynamic',
                                    cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Account {self.account_number}>'

    def to_dict(self):
        return {
            'id': self.id,
            'broker_id': self.broker_id,
            'broker_name': self.broker.name if self.broker else None,
            'account_number': self.account_number,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
