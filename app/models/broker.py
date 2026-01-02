from datetime import datetime
from app.extensions import db


class Broker(db.Model):
    """Broker model - represents a stock broker (e.g., Zerodha, Groww)."""
    __tablename__ = 'brokers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    accounts = db.relationship('Account', backref='broker', lazy='dynamic',
                               cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Broker {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'account_count': self.accounts.count()
        }
