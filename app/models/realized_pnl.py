from datetime import datetime
from app.extensions import db


class RealizedPnL(db.Model):
    """RealizedPnL model - represents realized profit/loss from Tax P&L import."""
    __tablename__ = 'realized_pnl'

    id = db.Column(db.Integer, primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    entry_date = db.Column(db.Date, nullable=False)
    exit_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    buy_value = db.Column(db.Numeric(15, 2), nullable=False)
    sell_value = db.Column(db.Numeric(15, 2), nullable=False)
    profit = db.Column(db.Numeric(15, 2), nullable=False)
    holding_days = db.Column(db.Integer, nullable=False)
    tax_term = db.Column(db.String(4), nullable=False)  # 'STCG' or 'LTCG'
    financial_year = db.Column(db.String(9), nullable=False)  # e.g., '2024-2025'
    source = db.Column(db.String(20), default='imported')  # 'imported' or 'calculated'
    brokerage = db.Column(db.Numeric(10, 4), default=0)
    stt = db.Column(db.Numeric(10, 4), default=0)
    other_charges = db.Column(db.Numeric(10, 4), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("tax_term IN ('STCG', 'LTCG')", name='ck_tax_term'),
        db.CheckConstraint("source IN ('imported', 'calculated')", name='ck_source'),
        db.Index('idx_realized_pnl_fy', 'financial_year'),
        db.Index('idx_realized_pnl_account', 'account_id'),
        db.Index('idx_realized_pnl_stock', 'stock_id'),
        db.Index('idx_realized_pnl_exit_date', 'exit_date'),
    )

    def __repr__(self):
        return f'<RealizedPnL {self.stock.symbol if self.stock else "?"} {self.profit}>'

    def to_dict(self):
        return {
            'id': self.id,
            'stock_id': self.stock_id,
            'symbol': self.stock.symbol if self.stock else None,
            'stock_name': self.stock.name if self.stock else None,
            'account_id': self.account_id,
            'account_number': self.account.account_number if self.account else None,
            'entry_date': self.entry_date.isoformat() if self.entry_date else None,
            'exit_date': self.exit_date.isoformat() if self.exit_date else None,
            'quantity': self.quantity,
            'buy_value': round(float(self.buy_value), 2) if self.buy_value else None,
            'sell_value': round(float(self.sell_value), 2) if self.sell_value else None,
            'profit': round(float(self.profit), 2) if self.profit else None,
            'holding_days': self.holding_days,
            'tax_term': self.tax_term,
            'financial_year': self.financial_year,
            'source': self.source,
            'brokerage': round(float(self.brokerage), 4) if self.brokerage else 0,
            'stt': round(float(self.stt), 4) if self.stt else 0,
            'other_charges': round(float(self.other_charges), 4) if self.other_charges else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    @staticmethod
    def get_financial_year(date):
        """
        Get Indian financial year for a given date.
        FY runs from April 1 to March 31.
        """
        if date.month >= 4:  # April onwards
            return f"{date.year}-{date.year + 1}"
        else:  # January to March
            return f"{date.year - 1}-{date.year}"

    @classmethod
    def get_by_financial_year(cls, financial_year, account_id=None):
        """Get all realized P&L for a financial year."""
        query = cls.query.filter_by(financial_year=financial_year)
        if account_id:
            query = query.filter_by(account_id=account_id)
        return query.order_by(cls.exit_date).all()

    @classmethod
    def get_summary_by_fy(cls, account_id=None):
        """Get aggregated P&L summary by financial year and tax term."""
        from sqlalchemy import func

        query = db.session.query(
            cls.financial_year,
            cls.tax_term,
            func.sum(cls.profit).label('total_profit'),
            func.count(cls.id).label('trade_count')
        ).group_by(cls.financial_year, cls.tax_term)

        if account_id:
            query = query.filter_by(account_id=account_id)

        return query.order_by(cls.financial_year).all()
