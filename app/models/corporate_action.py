from datetime import datetime
from app.extensions import db


class CorporateAction(db.Model):
    """CorporateAction model - represents stock splits, bonuses, mergers, etc."""
    __tablename__ = 'corporate_actions'

    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    action_type = db.Column(db.String(20), nullable=False)  # split, bonus, merger, demerger
    record_date = db.Column(db.Date, nullable=True)
    ratio_from = db.Column(db.Integer, nullable=False, default=1)  # e.g., 1
    ratio_to = db.Column(db.Integer, nullable=False, default=1)  # e.g., 10 (for 1:10 split)
    old_price = db.Column(db.Numeric(15, 4), nullable=True)
    new_price = db.Column(db.Numeric(15, 4), nullable=True)
    detected_automatically = db.Column(db.Boolean, default=True)
    applied = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint(
            "action_type IN ('split', 'bonus', 'merger', 'demerger')",
            name='ck_action_type'
        ),
    )

    def __repr__(self):
        return f'<CorporateAction {self.action_type} {self.ratio_from}:{self.ratio_to} {self.stock.symbol if self.stock else "?"}>'

    def to_dict(self):
        return {
            'id': self.id,
            'stock_id': self.stock_id,
            'symbol': self.stock.symbol if self.stock else None,
            'stock_name': self.stock.name if self.stock else None,
            'action_type': self.action_type,
            'record_date': self.record_date.isoformat() if self.record_date else None,
            'ratio_from': self.ratio_from,
            'ratio_to': self.ratio_to,
            'ratio_display': f'{self.ratio_from}:{self.ratio_to}',
            'old_price': float(self.old_price) if self.old_price else None,
            'new_price': float(self.new_price) if self.new_price else None,
            'detected_automatically': self.detected_automatically,
            'applied': self.applied,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def get_quantity_multiplier(self):
        """Get the quantity multiplier for this action."""
        if self.action_type == 'split':
            return self.ratio_to / self.ratio_from
        elif self.action_type == 'bonus':
            return (self.ratio_from + self.ratio_to) / self.ratio_from
        return 1

    def get_price_divisor(self):
        """Get the price divisor for this action."""
        return self.get_quantity_multiplier()

    @classmethod
    def get_pending(cls, stock_id=None):
        """Get all pending (not applied) corporate actions."""
        query = cls.query.filter_by(applied=False)
        if stock_id:
            query = query.filter_by(stock_id=stock_id)
        return query.order_by(cls.record_date).all()
