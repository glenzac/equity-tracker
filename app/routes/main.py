from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def dashboard():
    """Main dashboard page."""
    return render_template('dashboard.html')


@main_bp.route('/portfolio')
def portfolio():
    """Portfolio view page."""
    return render_template('portfolio/index.html')


@main_bp.route('/portfolio/<int:stock_id>')
def stock_detail(stock_id: int):
    """Stock detail page with allocations."""
    return render_template('portfolio/detail.html', stock_id=stock_id)


@main_bp.route('/trades')
def trades():
    """Trades management page."""
    return render_template('trades/index.html')


@main_bp.route('/allocations')
def allocations():
    """Allocations management page."""
    return render_template('allocations/index.html')


@main_bp.route('/import')
def import_data():
    """Data import page."""
    return render_template('import/index.html')


@main_bp.route('/reports')
def reports():
    """Reports and analytics page."""
    return render_template('reports/index.html')


@main_bp.route('/settings')
def settings():
    """Settings page."""
    return render_template('settings/index.html')
