from datetime import datetime
from app.extensions import db


class Stock(db.Model):
    """Stock model - represents a stock/ETF."""
    __tablename__ = 'stocks'

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False, unique=True)
    name = db.Column(db.String(200), nullable=False)
    isin = db.Column(db.String(12), unique=True, nullable=True)
    sector_id = db.Column(db.Integer, db.ForeignKey('sectors.id'), nullable=True)
    exchange = db.Column(db.String(10), nullable=True)  # NSE, BSE
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    trades = db.relationship('Trade', backref='stock', lazy='dynamic',
                             cascade='all, delete-orphan')
    allocations = db.relationship('Allocation', backref='stock', lazy='dynamic',
                                  cascade='all, delete-orphan')
    realized_pnls = db.relationship('RealizedPnL', backref='stock', lazy='dynamic',
                                    cascade='all, delete-orphan')
    corporate_actions = db.relationship('CorporateAction', backref='stock', lazy='dynamic',
                                        cascade='all, delete-orphan')
    price_cache = db.relationship('PriceCache', backref='stock', uselist=False,
                                  cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Stock {self.symbol}>'

    def to_dict(self, include_price=False):
        data = {
            'id': self.id,
            'symbol': self.symbol,
            'name': self.name,
            'isin': self.isin,
            'sector_id': self.sector_id,
            'sector_name': self.sector.name if self.sector else None,
            'exchange': self.exchange,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_price and self.price_cache:
            data['current_price'] = float(self.price_cache.current_price) if self.price_cache.current_price else None
            data['change_percent'] = float(self.price_cache.change_percent) if self.price_cache.change_percent else None
            data['last_updated'] = self.price_cache.last_updated.isoformat() if self.price_cache.last_updated else None
        return data

    @classmethod
    def get_or_create(cls, symbol, name=None, isin=None):
        """Get existing stock or create a new one."""
        stock = cls.query.filter_by(symbol=symbol).first()
        if not stock:
            stock = cls(
                symbol=symbol,
                name=name or symbol,
                isin=isin
            )
            db.session.add(stock)
            db.session.flush()
        return stock
