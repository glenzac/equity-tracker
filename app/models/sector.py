from datetime import datetime
from app.extensions import db


class Sector(db.Model):
    """Sector model - represents an Indian market sector."""
    __tablename__ = 'sectors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    stocks = db.relationship('Stock', backref='sector', lazy='dynamic')

    # Pre-defined Indian market sectors
    INDIAN_SECTORS = [
        'Automobiles',
        'Banks - Private',
        'Banks - Public',
        'Cement',
        'Chemicals',
        'Consumer Durables',
        'Energy - Oil & Gas',
        'Energy - Power',
        'Energy - Renewable',
        'Engineering',
        'ETF - Equity',
        'ETF - Gold',
        'ETF - Debt',
        'FMCG',
        'Healthcare - Hospitals',
        'Healthcare - Pharma',
        'Industrials',
        'Infrastructure',
        'Insurance',
        'IT - Software',
        'IT - Services',
        'Media & Entertainment',
        'Metals & Mining',
        'NBFC',
        'Real Estate',
        'Retail',
        'Telecom',
        'Textiles',
        'Others',
    ]

    def __repr__(self):
        return f'<Sector {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'stock_count': self.stocks.count()
        }

    @classmethod
    def seed_sectors(cls):
        """Seed the database with pre-defined sectors."""
        from app.extensions import db
        for sector_name in cls.INDIAN_SECTORS:
            existing = cls.query.filter_by(name=sector_name).first()
            if not existing:
                sector = cls(name=sector_name)
                db.session.add(sector)
        db.session.commit()
