from datetime import datetime
from decimal import Decimal
from app.extensions import db


class Goal(db.Model):
    """Goal model - represents an investment goal."""
    __tablename__ = 'goals'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    target_amount = db.Column(db.Numeric(15, 2), nullable=True)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    allocations = db.relationship('Allocation', backref='goal', lazy='dynamic')

    def __repr__(self):
        return f'<Goal {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'target_amount': float(self.target_amount) if self.target_amount else None,
            'is_default': self.is_default,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'allocation_count': self.allocations.count()
        }

    @classmethod
    def get_default(cls):
        """Get the default goal (#UNASSIGNED)."""
        return cls.query.filter_by(is_default=True).first()

    def get_current_value(self):
        """Calculate current value of all allocations for this goal."""
        total = Decimal('0')
        for allocation in self.allocations:
            if allocation.stock.price_cache:
                current_price = allocation.stock.price_cache.current_price or 0
                total += allocation.quantity * current_price
        return total

    def get_progress_percent(self):
        """Calculate progress towards target amount."""
        if not self.target_amount or self.target_amount == 0:
            return None
        current = self.get_current_value()
        return float(current / self.target_amount * 100)
