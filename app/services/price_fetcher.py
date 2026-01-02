"""
Price Fetcher - Fetches current stock prices from yfinance.

Features:
1. Fetch prices for NSE/BSE stocks
2. Batch fetching for multiple symbols
3. Caching with market hours awareness
4. Update price_cache table
"""
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
import logging

try:
    import yfinance as yf
except ImportError:
    yf = None

from app.extensions import db
from app.models import Stock, PriceCache

logger = logging.getLogger(__name__)


class PriceFetcher:
    """
    Fetch current stock prices from Yahoo Finance.

    Usage:
        fetcher = PriceFetcher()
        price = fetcher.fetch_price('TATATECH')
        fetcher.refresh_all_prices()
    """

    # Indian market hours
    MARKET_OPEN = time(9, 15)
    MARKET_CLOSE = time(15, 30)

    # Cache durations in seconds
    CACHE_DURATION_MARKET = 300  # 5 minutes during market hours
    CACHE_DURATION_CLOSED = 3600  # 1 hour when market is closed

    def __init__(self):
        if yf is None:
            logger.warning("yfinance not installed. Price fetching disabled.")

    @classmethod
    def is_market_open(cls) -> bool:
        """Check if Indian stock market is currently open."""
        now = datetime.now()

        # Check if weekend
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False

        current_time = now.time()
        return cls.MARKET_OPEN <= current_time <= cls.MARKET_CLOSE

    def get_yahoo_symbol(self, symbol: str, exchange: str = 'NSE') -> str:
        """
        Convert Indian stock symbol to Yahoo Finance format.

        Args:
            symbol: Stock symbol (e.g., 'TATATECH')
            exchange: Exchange ('NSE' or 'BSE')

        Returns:
            Yahoo Finance symbol (e.g., 'TATATECH.NS')
        """
        suffix = '.NS' if exchange.upper() == 'NSE' else '.BO'
        return f"{symbol}{suffix}"

    def fetch_price(self, symbol: str, exchange: str = 'NSE') -> Optional[Dict[str, Any]]:
        """
        Fetch current price for a single stock.

        Args:
            symbol: Stock symbol
            exchange: Exchange ('NSE' or 'BSE')

        Returns:
            Dictionary with price data or None if failed
        """
        if yf is None:
            return None

        yahoo_symbol = self.get_yahoo_symbol(symbol, exchange)

        try:
            ticker = yf.Ticker(yahoo_symbol)
            info = ticker.info

            if not info or 'currentPrice' not in info:
                # Try fast_info as fallback
                fast_info = ticker.fast_info
                if hasattr(fast_info, 'last_price'):
                    return {
                        'symbol': symbol,
                        'current_price': Decimal(str(fast_info.last_price)),
                        'change_percent': None,
                        'day_high': None,
                        'day_low': None,
                        'last_updated': datetime.utcnow()
                    }
                return None

            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            previous_close = info.get('previousClose') or info.get('regularMarketPreviousClose')

            change_percent = None
            if current_price and previous_close:
                change_percent = ((current_price - previous_close) / previous_close) * 100

            return {
                'symbol': symbol,
                'current_price': Decimal(str(current_price)) if current_price else None,
                'change_percent': Decimal(str(change_percent)) if change_percent else None,
                'day_high': Decimal(str(info.get('dayHigh'))) if info.get('dayHigh') else None,
                'day_low': Decimal(str(info.get('dayLow'))) if info.get('dayLow') else None,
                'last_updated': datetime.utcnow()
            }

        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    def fetch_prices_batch(self, symbols: List[str], exchange: str = 'NSE') -> Dict[str, Dict[str, Any]]:
        """
        Fetch prices for multiple stocks in one call.

        Args:
            symbols: List of stock symbols
            exchange: Exchange

        Returns:
            Dictionary mapping symbol to price data
        """
        if yf is None or not symbols:
            return {}

        yahoo_symbols = [self.get_yahoo_symbol(s, exchange) for s in symbols]

        try:
            # Use yfinance download for batch fetching
            tickers = yf.Tickers(' '.join(yahoo_symbols))

            results = {}
            for i, symbol in enumerate(symbols):
                yahoo_sym = yahoo_symbols[i]
                try:
                    ticker = tickers.tickers.get(yahoo_sym)
                    if ticker:
                        info = ticker.info
                        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
                        previous_close = info.get('previousClose')

                        change_percent = None
                        if current_price and previous_close:
                            change_percent = ((current_price - previous_close) / previous_close) * 100

                        if current_price:
                            results[symbol] = {
                                'symbol': symbol,
                                'current_price': Decimal(str(current_price)),
                                'change_percent': Decimal(str(change_percent)) if change_percent else None,
                                'day_high': Decimal(str(info.get('dayHigh'))) if info.get('dayHigh') else None,
                                'day_low': Decimal(str(info.get('dayLow'))) if info.get('dayLow') else None,
                                'last_updated': datetime.utcnow()
                            }
                except Exception as e:
                    logger.error(f"Error fetching price for {symbol}: {e}")

            return results

        except Exception as e:
            logger.error(f"Error in batch price fetch: {e}")
            return {}

    def update_price_cache(self, stock: Stock, price_data: Dict[str, Any]) -> PriceCache:
        """Update price cache for a stock."""
        cache = PriceCache.get_or_create(stock.id)
        cache.update_price(
            current_price=price_data.get('current_price'),
            change_percent=price_data.get('change_percent'),
            day_high=price_data.get('day_high'),
            day_low=price_data.get('day_low')
        )
        return cache

    def refresh_stock_price(self, stock: Stock, force: bool = False) -> Optional[Dict[str, Any]]:
        """
        Refresh price for a single stock.

        Args:
            stock: Stock model instance
            force: Force refresh even if cache is valid

        Returns:
            Price data dictionary or None
        """
        # Check cache first
        if not force and stock.price_cache and not stock.price_cache.is_stale():
            return stock.price_cache.to_dict()

        # Fetch new price
        price_data = self.fetch_price(stock.symbol)
        if price_data:
            self.update_price_cache(stock, price_data)
            db.session.commit()
            return price_data

        return None

    def get_stock_exchange(self, stock: Stock) -> str:
        """
        Get the exchange for a stock.

        Priority:
        1. Stock's exchange field (user-configured)
        2. Exchange from trades
        3. Default to NSE
        """
        # First check if stock has exchange set
        if stock.exchange:
            return stock.exchange.upper()

        # Fall back to trade exchange
        from app.models import Trade
        trade = Trade.query.filter_by(stock_id=stock.id).first()
        if trade and trade.exchange:
            return trade.exchange.upper()

        return 'NSE'  # Default to NSE

    def refresh_all_prices(self, force: bool = False, batch_size: int = 10) -> Dict[str, Any]:
        """
        Refresh prices for all stocks with holdings.

        Args:
            force: Force refresh even if cache is valid
            batch_size: Number of stocks to fetch per batch

        Returns:
            Summary of refresh results
        """
        from app.models import Trade

        # Get all stocks that have trades
        stocks = db.session.query(Stock).join(Trade).distinct().all()

        if not stocks:
            return {'refreshed': 0, 'failed': 0, 'skipped': 0}

        refreshed = 0
        failed = 0
        skipped = 0

        # Group stocks by exchange for proper fetching
        for stock in stocks:
            if not force and stock.price_cache and not stock.price_cache.is_stale():
                skipped += 1
                continue

            # Get the exchange for this stock
            exchange = self.get_stock_exchange(stock)

            # Fetch price with correct exchange
            price_data = self.fetch_price(stock.symbol, exchange)

            if price_data and price_data.get('current_price'):
                self.update_price_cache(stock, price_data)
                refreshed += 1
            else:
                # Try alternate exchange if primary fails
                alt_exchange = 'BSE' if exchange == 'NSE' else 'NSE'
                price_data = self.fetch_price(stock.symbol, alt_exchange)

                if price_data and price_data.get('current_price'):
                    self.update_price_cache(stock, price_data)
                    refreshed += 1
                else:
                    failed += 1

        db.session.commit()

        return {
            'refreshed': refreshed,
            'failed': failed,
            'skipped': skipped,
            'total': len(stocks)
        }

    def get_cached_price(self, stock_id: int) -> Optional[Dict[str, Any]]:
        """Get cached price for a stock."""
        cache = PriceCache.query.filter_by(stock_id=stock_id).first()
        if cache:
            return cache.to_dict()
        return None
