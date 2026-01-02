"""
Allocations Routes - Manage unit-level allocations to owners and goals.
"""
import logging
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Allocation, Stock, Account, Owner, Goal
from app.services.allocation_manager import (
    AllocationManager,
    AllocationError,
    InsufficientUnitsError,
    InvalidOwnerError,
    InvalidGoalError
)
from app.utils.validation import (
    ValidationError,
    validate_integer,
    validate_positive_integer
)

logger = logging.getLogger(__name__)

allocations_bp = Blueprint('allocations', __name__)


@allocations_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    """Handle validation errors."""
    return jsonify({
        'status': 'error',
        'message': error.message,
        'field': error.field
    }), 400


@allocations_bp.route('/stocks/<int:stock_id>/allocations', methods=['GET'])
def get_stock_allocations(stock_id: int):
    """
    Get all allocations for a stock.

    Query parameters:
    - account: Account ID (required if multiple accounts)
    """
    account_id = request.args.get('account', type=int)

    if not account_id:
        # Get first account with this stock
        from app.models import Trade
        trade = Trade.query.filter_by(stock_id=stock_id).first()
        if trade:
            account_id = trade.account_id
        else:
            return jsonify({
                'status': 'error',
                'message': 'No trades found for this stock'
            }), 404

    manager = AllocationManager(stock_id=stock_id, account_id=account_id)

    allocations = manager.get_allocations()
    total_holdings = manager.get_total_holdings()
    allocated_units = manager.get_allocated_units()
    available_units = manager.get_available_units()

    stock = Stock.query.get(stock_id)

    return jsonify({
        'status': 'success',
        'data': {
            'stock': stock.to_dict() if stock else None,
            'account_id': account_id,
            'total_holdings': total_holdings,
            'allocated_units': allocated_units,
            'available_units': available_units,
            'allocations': [a.to_dict() for a in allocations],
            'count': len(allocations)
        }
    })


@allocations_bp.route('/stocks/<int:stock_id>/allocations', methods=['POST'])
def create_allocation(stock_id: int):
    """
    Create a new allocation for a stock.

    JSON body:
    - account_id: Account ID (required)
    - owner_id: Owner ID (required)
    - goal_id: Goal ID (required)
    - quantity: Number of units to allocate (required)
    """
    data = request.get_json() or {}

    # Validate inputs with proper bounds
    account_id = validate_integer(data.get('account_id'), 'Account ID', min_value=1)
    owner_id = validate_integer(data.get('owner_id'), 'Owner ID', min_value=1)
    goal_id = validate_integer(data.get('goal_id'), 'Goal ID', min_value=1)
    quantity = validate_positive_integer(data.get('quantity'), 'Quantity')

    try:
        manager = AllocationManager(
            stock_id=stock_id,
            account_id=account_id
        )

        allocation = manager.create_allocation(
            owner_id=owner_id,
            goal_id=goal_id,
            quantity=quantity
        )

        logger.info(f"Created allocation: {quantity} units of stock {stock_id} to owner {owner_id}")

        return jsonify({
            'status': 'success',
            'data': allocation.to_dict()
        }), 201

    except InsufficientUnitsError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except InvalidOwnerError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 404
    except InvalidGoalError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 404
    except AllocationError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@allocations_bp.route('/allocations/<int:allocation_id>', methods=['GET'])
def get_allocation(allocation_id: int):
    """Get a specific allocation."""
    allocation = Allocation.query.get_or_404(allocation_id)

    return jsonify({
        'status': 'success',
        'data': allocation.to_dict()
    })


@allocations_bp.route('/allocations/<int:allocation_id>', methods=['PUT'])
def update_allocation(allocation_id: int):
    """
    Update an existing allocation.

    JSON body:
    - owner_id: New owner ID (optional)
    - goal_id: New goal ID (optional)
    - quantity: New quantity (optional)

    Note: Buy price remains fixed even when owner/goal changes.
    """
    allocation = Allocation.query.get_or_404(allocation_id)
    data = request.get_json()

    if not data:
        return jsonify({
            'status': 'error',
            'message': 'Request body is required'
        }), 400

    try:
        manager = AllocationManager(
            stock_id=allocation.stock_id,
            account_id=allocation.account_id
        )

        updated = manager.update_allocation(
            allocation_id=allocation_id,
            new_owner_id=data.get('owner_id'),
            new_goal_id=data.get('goal_id'),
            new_quantity=data.get('quantity')
        )

        return jsonify({
            'status': 'success',
            'data': updated.to_dict()
        })

    except InsufficientUnitsError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except InvalidOwnerError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 404
    except InvalidGoalError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 404
    except AllocationError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@allocations_bp.route('/allocations/<int:allocation_id>', methods=['DELETE'])
def delete_allocation(allocation_id: int):
    """
    Delete an allocation.

    Units return to the available pool.
    """
    allocation = Allocation.query.get_or_404(allocation_id)

    try:
        manager = AllocationManager(
            stock_id=allocation.stock_id,
            account_id=allocation.account_id
        )

        manager.delete_allocation(allocation_id)

        return jsonify({
            'status': 'success',
            'message': 'Allocation deleted'
        })

    except AllocationError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@allocations_bp.route('/stocks/<int:stock_id>/allocations/sync', methods=['POST'])
def sync_allocations(stock_id: int):
    """
    Sync allocations with actual holdings.

    If holdings decreased (due to sales), reduces allocations from oldest first.

    Query parameters:
    - account: Account ID (required)
    """
    account_id = request.args.get('account', type=int)

    if not account_id:
        return jsonify({
            'status': 'error',
            'message': 'Account ID is required'
        }), 400

    try:
        manager = AllocationManager(stock_id=stock_id, account_id=account_id)
        result = manager.sync_with_holdings()

        return jsonify({
            'status': 'success',
            'data': {
                'adjusted': result['adjusted'],
                'deleted': result['deleted'],
                'total_holdings': manager.get_total_holdings(),
                'allocated_units': manager.get_allocated_units()
            }
        })

    except AllocationError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@allocations_bp.route('/stocks/<int:stock_id>/allocations/default', methods=['POST'])
def allocate_to_default(stock_id: int):
    """
    Allocate available units to default owner/goal.

    Query parameters:
    - account: Account ID (required)

    JSON body:
    - quantity: Number of units (optional, defaults to all available)
    """
    account_id = request.args.get('account', type=int)

    if not account_id:
        return jsonify({
            'status': 'error',
            'message': 'Account ID is required'
        }), 400

    data = request.get_json() or {}

    try:
        manager = AllocationManager(stock_id=stock_id, account_id=account_id)

        quantity = data.get('quantity')
        if quantity is None:
            quantity = manager.get_available_units()

        if quantity <= 0:
            return jsonify({
                'status': 'error',
                'message': 'No units available for allocation'
            }), 400

        allocation = manager.reallocate_to_default(quantity)

        return jsonify({
            'status': 'success',
            'data': allocation.to_dict()
        }), 201

    except AllocationError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@allocations_bp.route('/stocks/<int:stock_id>/lots', methods=['GET'])
def get_buy_lots(stock_id: int):
    """
    Get FIFO buy lots for a stock.

    Query parameters:
    - account: Account ID (required)
    """
    account_id = request.args.get('account', type=int)

    if not account_id:
        return jsonify({
            'status': 'error',
            'message': 'Account ID is required'
        }), 400

    manager = AllocationManager(stock_id=stock_id, account_id=account_id)
    lots = manager.get_fifo_buy_lots()

    stock = Stock.query.get(stock_id)

    return jsonify({
        'status': 'success',
        'data': {
            'stock': stock.to_dict() if stock else None,
            'account_id': account_id,
            'total_holdings': manager.get_total_holdings(),
            'lots': lots,
            'count': len(lots)
        }
    })


@allocations_bp.route('/allocations', methods=['GET'])
def list_all_allocations():
    """
    Get all allocations with optional filters.

    Query parameters:
    - account: Filter by account ID
    - owner: Filter by owner ID
    - goal: Filter by goal ID
    - stock: Filter by stock ID
    """
    account_id = request.args.get('account', type=int)
    owner_id = request.args.get('owner', type=int)
    goal_id = request.args.get('goal', type=int)
    stock_id = request.args.get('stock', type=int)

    query = Allocation.query

    if account_id:
        query = query.filter_by(account_id=account_id)
    if owner_id:
        query = query.filter_by(owner_id=owner_id)
    if goal_id:
        query = query.filter_by(goal_id=goal_id)
    if stock_id:
        query = query.filter_by(stock_id=stock_id)

    allocations = query.order_by(Allocation.buy_date).all()

    # Calculate totals
    total_value = sum(a.quantity * a.buy_price for a in allocations)

    return jsonify({
        'status': 'success',
        'data': {
            'allocations': [a.to_dict() for a in allocations],
            'count': len(allocations),
            'total_value': float(total_value)
        }
    })
