from datetime import datetime, time
from app.extensions import db


class PriceCache(db.Model):
    """PriceCache model - caches current stock prices."""
    __tablename__ = 'price_cache'

    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False, unique=True)
    current_price = db.Column(db.Numeric(15, 4), nullable=True)
    change_percent = db.Column(db.Numeric(8, 4), nullable=True)
    day_high = db.Column(db.Numeric(15, 4), nullable=True)
    day_low = db.Column(db.Numeric(15, 4), nullable=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    # Market hours (India)
    MARKET_OPEN = time(9, 15)
    MARKET_CLOSE = time(15, 30)
    CACHE_DURATION_MARKET = 300  # 5 minutes
    CACHE_DURATION_CLOSED = 3600  # 1 hour

    def __repr__(self):
        return f'<PriceCache {self.stock.symbol if self.stock else "?"} @ {self.current_price}>'

    def to_dict(self):
        return {
            'id': self.id,
            'stock_id': self.stock_id,
            'symbol': self.stock.symbol if self.stock else None,
            'current_price': float(self.current_price) if self.current_price else None,
            'change_percent': float(self.change_percent) if self.change_percent else None,
            'day_high': float(self.day_high) if self.day_high else None,
            'day_low': float(self.day_low) if self.day_low else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }

    def is_stale(self):
        """Check if the cached price is stale and needs refresh."""
        if not self.last_updated:
            return True

        now = datetime.now()
        age_seconds = (now - self.last_updated).total_seconds()

        if self.is_market_open():
            return age_seconds > self.CACHE_DURATION_MARKET
        else:
            return age_seconds > self.CACHE_DURATION_CLOSED

    @classmethod
    def is_market_open(cls):
        """Check if Indian stock market is currently open."""
        now = datetime.now()

        # Check if weekend (Saturday=5, Sunday=6)
        if now.weekday() >= 5:
            return False

        current_time = now.time()
        return cls.MARKET_OPEN <= current_time <= cls.MARKET_CLOSE

    def update_price(self, current_price, change_percent=None, day_high=None, day_low=None):
        """Update cached price data."""
        self.current_price = current_price
        self.change_percent = change_percent
        self.day_high = day_high
        self.day_low = day_low
        self.last_updated = datetime.utcnow()

    @classmethod
    def get_or_create(cls, stock_id):
        """Get existing cache entry or create a new one."""
        cache = cls.query.filter_by(stock_id=stock_id).first()
        if not cache:
            cache = cls(stock_id=stock_id)
            db.session.add(cache)
            db.session.flush()
        return cache

    @classmethod
    def get_stale_entries(cls):
        """Get all cache entries that need refreshing."""
        entries = cls.query.all()
        return [e for e in entries if e.is_stale()]
