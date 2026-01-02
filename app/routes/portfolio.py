"""
Portfolio Routes - Holdings, stocks, and portfolio management.
"""
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Stock, Trade, Account, RealizedPnL
from app.services.holdings_calculator import HoldingsCalculator
from app.services.price_fetcher import PriceFetcher

portfolio_bp = Blueprint('portfolio', __name__)


@portfolio_bp.route('/holdings', methods=['GET'])
def get_holdings():
    """
    Get all current holdings.

    Query parameters:
    - account: Filter by account ID
    - owner: Filter by owner ID
    - goal: Filter by goal ID
    - sector: Filter by sector ID
    - include_lots: Include FIFO buy lots (default: false)
    """
    account_id = request.args.get('account', type=int)
    owner_id = request.args.get('owner', type=int)
    goal_id = request.args.get('goal', type=int)
    sector_id = request.args.get('sector', type=int)
    include_lots = request.args.get('include_lots', 'false').lower() == 'true'

    calculator = HoldingsCalculator()

    holdings = calculator.get_holdings(
        account_id=account_id,
        owner_id=owner_id,
        goal_id=goal_id,
        sector_id=sector_id,
        include_lots=include_lots
    )

    summary = calculator.get_summary(
        account_id=account_id,
        owner_id=owner_id,
        goal_id=goal_id
    )

    return jsonify({
        'status': 'success',
        'data': {
            'holdings': [h.to_dict() for h in holdings],
            'summary': summary
        }
    })


@portfolio_bp.route('/holdings/<int:stock_id>', methods=['GET'])
def get_holding_detail(stock_id: int):
    """
    Get detailed holding for a specific stock.

    URL parameters:
    - stock_id: Stock ID

    Query parameters:
    - account: Account ID (required if multiple accounts)
    """
    account_id = request.args.get('account', type=int)

    if not account_id:
        # Get first account with this stock
        trade = Trade.query.filter_by(stock_id=stock_id).first()
        if trade:
            account_id = trade.account_id

    if not account_id:
        return jsonify({
            'status': 'error',
            'message': 'Account ID required'
        }), 400

    calculator = HoldingsCalculator()
    holding = calculator.get_holding(
        stock_id=stock_id,
        account_id=account_id,
        include_lots=True,
        include_allocations=True
    )

    if not holding:
        return jsonify({
            'status': 'error',
            'message': 'Holding not found'
        }), 404

    return jsonify({
        'status': 'success',
        'data': holding.to_dict()
    })


@portfolio_bp.route('/summary', methods=['GET'])
def get_portfolio_summary():
    """
    Get portfolio summary with totals.

    Query parameters:
    - account: Filter by account ID
    - owner: Filter by owner ID
    - goal: Filter by goal ID
    """
    account_id = request.args.get('account', type=int)
    owner_id = request.args.get('owner', type=int)
    goal_id = request.args.get('goal', type=int)

    calculator = HoldingsCalculator()

    summary = calculator.get_summary(
        account_id=account_id,
        owner_id=owner_id,
        goal_id=goal_id
    )

    return jsonify({
        'status': 'success',
        'data': summary
    })


@portfolio_bp.route('/sector-allocation', methods=['GET'])
def get_sector_allocation():
    """Get holdings grouped by sector."""
    account_id = request.args.get('account', type=int)

    calculator = HoldingsCalculator()
    allocation = calculator.get_sector_allocation(account_id=account_id)

    return jsonify({
        'status': 'success',
        'data': {
            'allocations': allocation
        }
    })


@portfolio_bp.route('/owner-allocation', methods=['GET'])
def get_owner_allocation():
    """Get holdings grouped by owner."""
    account_id = request.args.get('account', type=int)

    calculator = HoldingsCalculator()
    allocation = calculator.get_owner_allocation(account_id=account_id)

    return jsonify({
        'status': 'success',
        'data': {
            'allocations': allocation
        }
    })


@portfolio_bp.route('/goal-allocation', methods=['GET'])
def get_goal_allocation():
    """Get holdings grouped by goal."""
    account_id = request.args.get('account', type=int)

    calculator = HoldingsCalculator()
    allocation = calculator.get_goal_allocation(account_id=account_id)

    return jsonify({
        'status': 'success',
        'data': {
            'allocations': allocation
        }
    })


@portfolio_bp.route('/prices/refresh', methods=['POST'])
def refresh_prices():
    """
    Refresh all stock prices.

    Query parameters:
    - force: Force refresh even if cache is valid (default: false)
    """
    force = request.args.get('force', 'false').lower() == 'true'

    fetcher = PriceFetcher()
    result = fetcher.refresh_all_prices(force=force)

    return jsonify({
        'status': 'success',
        'data': result
    })


@portfolio_bp.route('/prices/<int:stock_id>', methods=['GET'])
def get_stock_price(stock_id: int):
    """Get price for a specific stock."""
    stock = Stock.query.get_or_404(stock_id)

    fetcher = PriceFetcher()
    price_data = fetcher.refresh_stock_price(stock)

    if price_data:
        return jsonify({
            'status': 'success',
            'data': price_data
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Could not fetch price'
        }), 404


@portfolio_bp.route('/stocks', methods=['GET'])
def get_stocks():
    """
    Get all stocks.

    Query parameters:
    - has_holdings: Only stocks with current holdings (default: false)
    - sector: Filter by sector ID
    """
    has_holdings = request.args.get('has_holdings', 'false').lower() == 'true'
    sector_id = request.args.get('sector', type=int)

    query = Stock.query

    if sector_id:
        query = query.filter_by(sector_id=sector_id)

    if has_holdings:
        # Get stocks that have trades
        query = query.join(Trade).distinct()

    stocks = query.order_by(Stock.symbol).all()

    return jsonify({
        'status': 'success',
        'data': {
            'stocks': [s.to_dict(include_price=True) for s in stocks],
            'count': len(stocks)
        }
    })


@portfolio_bp.route('/stocks/<int:stock_id>', methods=['GET'])
def get_stock_detail(stock_id: int):
    """Get detailed information for a stock."""
    stock = Stock.query.get_or_404(stock_id)

    return jsonify({
        'status': 'success',
        'data': stock.to_dict(include_price=True)
    })


@portfolio_bp.route('/stocks/<int:stock_id>', methods=['PUT'])
def update_stock(stock_id: int):
    """
    Update stock details.

    JSON body:
    - name: Stock name
    - sector_id: Sector ID
    - exchange: Exchange (NSE or BSE)
    """
    stock = Stock.query.get_or_404(stock_id)
    data = request.get_json()

    if 'name' in data:
        stock.name = data['name']
    if 'sector_id' in data:
        stock.sector_id = data['sector_id']
    if 'exchange' in data:
        stock.exchange = data['exchange']

    db.session.commit()

    return jsonify({
        'status': 'success',
        'data': stock.to_dict(include_price=True)
    })


@portfolio_bp.route('/stocks/<int:stock_id>/trades', methods=['GET'])
def get_stock_trades(stock_id: int):
    """Get all trades for a stock."""
    account_id = request.args.get('account', type=int)

    query = Trade.query.filter_by(stock_id=stock_id)
    if account_id:
        query = query.filter_by(account_id=account_id)

    trades = query.order_by(Trade.trade_datetime.desc(), Trade.trade_date.desc()).all()

    return jsonify({
        'status': 'success',
        'data': {
            'trades': [t.to_dict() for t in trades],
            'count': len(trades)
        }
    })


@portfolio_bp.route('/trades', methods=['GET'])
def get_trades():
    """
    Get all trades.

    Query parameters:
    - account: Filter by account ID
    - stock: Filter by stock ID
    - type: Filter by trade type (buy/sell)
    - from_date: Filter from date (YYYY-MM-DD)
    - to_date: Filter to date (YYYY-MM-DD)
    - limit: Limit results (default: 100)
    """
    account_id = request.args.get('account', type=int)
    stock_id = request.args.get('stock', type=int)
    trade_type = request.args.get('type')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    limit = request.args.get('limit', 100, type=int)

    query = Trade.query

    if account_id:
        query = query.filter_by(account_id=account_id)
    if stock_id:
        query = query.filter_by(stock_id=stock_id)
    if trade_type:
        query = query.filter_by(trade_type=trade_type)
    if from_date:
        query = query.filter(Trade.trade_date >= from_date)
    if to_date:
        query = query.filter(Trade.trade_date <= to_date)

    trades = query.order_by(
        Trade.trade_datetime.desc().nullslast(),
        Trade.trade_date.desc()
    ).limit(limit).all()

    return jsonify({
        'status': 'success',
        'data': {
            'trades': [t.to_dict() for t in trades],
            'count': len(trades)
        }
    })


@portfolio_bp.route('/pnl/realized', methods=['GET'])
def get_realized_pnl():
    """
    Get realized P&L.

    Query parameters:
    - fy: Filter by financial year
    - account: Filter by account ID
    - stock: Filter by stock ID
    - tax_term: Filter by tax term (STCG/LTCG)
    """
    financial_year = request.args.get('fy')
    account_id = request.args.get('account', type=int)
    stock_id = request.args.get('stock', type=int)
    tax_term = request.args.get('tax_term')

    query = RealizedPnL.query

    if financial_year:
        query = query.filter_by(financial_year=financial_year)
    if account_id:
        query = query.filter_by(account_id=account_id)
    if stock_id:
        query = query.filter_by(stock_id=stock_id)
    if tax_term:
        query = query.filter_by(tax_term=tax_term)

    entries = query.order_by(RealizedPnL.exit_date.desc()).all()

    # Calculate summary
    stcg_total = sum(e.profit for e in entries if e.tax_term == 'STCG')
    ltcg_total = sum(e.profit for e in entries if e.tax_term == 'LTCG')
    total = sum(e.profit for e in entries)

    return jsonify({
        'status': 'success',
        'data': {
            'entries': [e.to_dict() for e in entries],
            'count': len(entries),
            'summary': {
                'stcg_total': float(stcg_total),
                'ltcg_total': float(ltcg_total),
                'total': float(total)
            }
        }
    })


@portfolio_bp.route('/pnl/summary', methods=['GET'])
def get_pnl_summary():
    """Get P&L summary by financial year."""
    account_id = request.args.get('account', type=int)

    results = RealizedPnL.get_summary_by_fy(account_id=account_id)

    summary = {}
    for fy, tax_term, total_profit, trade_count in results:
        if fy not in summary:
            summary[fy] = {'financial_year': fy, 'stcg': 0, 'ltcg': 0, 'total': 0, 'trades': 0}
        if tax_term == 'STCG':
            summary[fy]['stcg'] = float(total_profit or 0)
        else:
            summary[fy]['ltcg'] = float(total_profit or 0)
        summary[fy]['total'] = summary[fy]['stcg'] + summary[fy]['ltcg']
        summary[fy]['trades'] += trade_count

    return jsonify({
        'status': 'success',
        'data': {
            'summary': list(summary.values())
        }
    })
