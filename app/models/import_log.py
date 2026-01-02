from datetime import datetime
from app.extensions import db


class ImportLog(db.Model):
    """ImportLog model - tracks file import history."""
    __tablename__ = 'import_logs'

    id = db.Column(db.Integer, primary_key=True)
    file_type = db.Column(db.String(20), nullable=False)  # tradebook, taxpnl
    file_name = db.Column(db.String(255), nullable=False)
    broker_id = db.Column(db.Integer, db.ForeignKey('brokers.id'), nullable=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)
    financial_year = db.Column(db.String(9), nullable=True)  # e.g., '2024-2025'
    records_imported = db.Column(db.Integer, default=0)
    records_skipped = db.Column(db.Integer, default=0)
    discrepancies_found = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='pending')  # pending, success, partial, failed
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    broker = db.relationship('Broker', backref='import_logs')
    account = db.relationship('Account', backref='import_logs')

    __table_args__ = (
        db.CheckConstraint(
            "file_type IN ('tradebook', 'taxpnl')",
            name='ck_file_type'
        ),
        db.CheckConstraint(
            "status IN ('pending', 'success', 'partial', 'failed')",
            name='ck_status'
        ),
    )

    def __repr__(self):
        return f'<ImportLog {self.file_type} {self.file_name} - {self.status}>'

    def to_dict(self):
        return {
            'id': self.id,
            'file_type': self.file_type,
            'file_name': self.file_name,
            'broker_id': self.broker_id,
            'broker_name': self.broker.name if self.broker else None,
            'account_id': self.account_id,
            'account_number': self.account.account_number if self.account else None,
            'financial_year': self.financial_year,
            'records_imported': self.records_imported,
            'records_skipped': self.records_skipped,
            'discrepancies_found': self.discrepancies_found,
            'status': self.status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def mark_success(self, records_imported, records_skipped=0):
        """Mark import as successful."""
        self.status = 'success'
        self.records_imported = records_imported
        self.records_skipped = records_skipped

    def mark_partial(self, records_imported, records_skipped, discrepancies):
        """Mark import as partial success."""
        self.status = 'partial'
        self.records_imported = records_imported
        self.records_skipped = records_skipped
        self.discrepancies_found = discrepancies

    def mark_failed(self, error_message):
        """Mark import as failed."""
        self.status = 'failed'
        self.error_message = error_message

    @classmethod
    def get_recent(cls, limit=10):
        """Get most recent import logs."""
        return cls.query.order_by(cls.created_at.desc()).limit(limit).all()
