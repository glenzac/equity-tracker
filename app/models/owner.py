from datetime import datetime
from app.extensions import db


class Owner(db.Model):
    """Owner model - represents a person who owns allocations."""
    __tablename__ = 'owners'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    allocations = db.relationship('Allocation', backref='owner', lazy='dynamic')

    def __repr__(self):
        return f'<Owner {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'is_default': self.is_default,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'allocation_count': self.allocations.count()
        }

    @classmethod
    def get_default(cls):
        """Get the default owner (#DEFAULT)."""
        return cls.query.filter_by(is_default=True).first()
