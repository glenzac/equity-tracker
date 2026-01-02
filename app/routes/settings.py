"""
Settings Routes - Manage brokers, accounts, owners, goals, sectors.
"""
import logging
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Broker, Account, Owner, Goal, Sector
from app.utils.validation import (
    ValidationError,
    validate_string,
    validate_integer,
    validate_positive_decimal
)

logger = logging.getLogger(__name__)

settings_bp = Blueprint('settings', __name__)


@settings_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    """Handle validation errors."""
    return jsonify({
        'status': 'error',
        'message': error.message,
        'field': error.field
    }), 400


# ============ BROKERS ============

@settings_bp.route('/brokers', methods=['GET'])
def get_brokers():
    """Get all brokers."""
    brokers = Broker.query.order_by(Broker.name).all()
    return jsonify({
        'status': 'success',
        'data': {
            'brokers': [b.to_dict() for b in brokers],
            'count': len(brokers)
        }
    })


@settings_bp.route('/brokers', methods=['POST'])
def create_broker():
    """
    Create a new broker.

    JSON body:
    - name: Broker name (required)
    """
    data = request.get_json() or {}

    name = validate_string(data.get('name'), 'Broker name', max_length=100)

    # Check for duplicate
    existing = Broker.query.filter_by(name=name).first()
    if existing:
        return jsonify({
            'status': 'error',
            'message': f'Broker "{name}" already exists'
        }), 400

    broker = Broker(name=name)
    db.session.add(broker)
    db.session.commit()

    logger.info(f"Created broker: {name}")

    return jsonify({
        'status': 'success',
        'data': broker.to_dict()
    }), 201


@settings_bp.route('/brokers/<int:broker_id>', methods=['PUT'])
def update_broker(broker_id: int):
    """
    Update a broker.

    JSON body:
    - name: Broker name
    """
    broker = Broker.query.get_or_404(broker_id)
    data = request.get_json()

    if 'name' in data:
        name = data['name'].strip()
        existing = Broker.query.filter(Broker.name == name, Broker.id != broker_id).first()
        if existing:
            return jsonify({
                'status': 'error',
                'message': f'Broker "{name}" already exists'
            }), 400
        broker.name = name

    db.session.commit()

    return jsonify({
        'status': 'success',
        'data': broker.to_dict()
    })


@settings_bp.route('/brokers/<int:broker_id>', methods=['DELETE'])
def delete_broker(broker_id: int):
    """Delete a broker."""
    broker = Broker.query.get_or_404(broker_id)

    if broker.accounts.count() > 0:
        return jsonify({
            'status': 'error',
            'message': 'Cannot delete broker with existing accounts'
        }), 400

    db.session.delete(broker)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': f'Broker "{broker.name}" deleted'
    })


# ============ ACCOUNTS ============

@settings_bp.route('/accounts', methods=['GET'])
def get_accounts():
    """Get all accounts."""
    broker_id = request.args.get('broker', type=int)

    query = Account.query
    if broker_id:
        query = query.filter_by(broker_id=broker_id)

    accounts = query.order_by(Account.account_number).all()

    return jsonify({
        'status': 'success',
        'data': {
            'accounts': [a.to_dict() for a in accounts],
            'count': len(accounts)
        }
    })


@settings_bp.route('/accounts', methods=['POST'])
def create_account():
    """
    Create a new account.

    JSON body:
    - broker_id: Broker ID (required)
    - account_number: Account number (required)
    """
    data = request.get_json() or {}

    broker_id = validate_integer(data.get('broker_id'), 'Broker ID', min_value=1)
    account_number = validate_string(data.get('account_number'), 'Account number', max_length=50)

    broker = Broker.query.get(broker_id)
    if not broker:
        return jsonify({
            'status': 'error',
            'message': 'Broker not found'
        }), 404

    # Check for duplicate
    existing = Account.query.filter_by(
        broker_id=broker_id,
        account_number=account_number
    ).first()
    if existing:
        return jsonify({
            'status': 'error',
            'message': f'Account "{account_number}" already exists for this broker'
        }), 400

    account = Account(broker_id=broker_id, account_number=account_number)
    db.session.add(account)
    db.session.commit()

    logger.info(f"Created account: {account_number} for broker {broker.name}")

    return jsonify({
        'status': 'success',
        'data': account.to_dict()
    }), 201


@settings_bp.route('/accounts/<int:account_id>', methods=['PUT'])
def update_account(account_id: int):
    """
    Update an account.

    JSON body:
    - account_number: Account number
    - name: Account name (optional display name)
    """
    account = Account.query.get_or_404(account_id)
    data = request.get_json()

    if 'account_number' in data:
        account_number = data['account_number'].strip()
        existing = Account.query.filter(
            Account.account_number == account_number,
            Account.broker_id == account.broker_id,
            Account.id != account_id
        ).first()
        if existing:
            return jsonify({
                'status': 'error',
                'message': f'Account "{account_number}" already exists for this broker'
            }), 400
        account.account_number = account_number

    if 'name' in data:
        account.name = data['name'].strip() if data['name'] else None

    db.session.commit()

    return jsonify({
        'status': 'success',
        'data': account.to_dict()
    })


@settings_bp.route('/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id: int):
    """Delete an account."""
    account = Account.query.get_or_404(account_id)

    if account.trades.count() > 0:
        return jsonify({
            'status': 'error',
            'message': 'Cannot delete account with existing trades'
        }), 400

    db.session.delete(account)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': f'Account "{account.account_number}" deleted'
    })


# ============ OWNERS ============

@settings_bp.route('/owners', methods=['GET'])
def get_owners():
    """Get all owners."""
    owners = Owner.query.order_by(Owner.is_default.desc(), Owner.name).all()
    return jsonify({
        'status': 'success',
        'data': {
            'owners': [o.to_dict() for o in owners],
            'count': len(owners)
        }
    })


@settings_bp.route('/owners', methods=['POST'])
def create_owner():
    """
    Create a new owner.

    JSON body:
    - name: Owner name (required)
    """
    data = request.get_json() or {}

    name = validate_string(data.get('name'), 'Owner name', max_length=100)

    # Check for duplicate
    existing = Owner.query.filter_by(name=name).first()
    if existing:
        return jsonify({
            'status': 'error',
            'message': f'Owner "{name}" already exists'
        }), 400

    owner = Owner(name=name, is_default=False)
    db.session.add(owner)
    db.session.commit()

    logger.info(f"Created owner: {name}")

    return jsonify({
        'status': 'success',
        'data': owner.to_dict()
    }), 201


@settings_bp.route('/owners/<int:owner_id>', methods=['PUT'])
def update_owner(owner_id: int):
    """
    Update an owner.

    JSON body:
    - name: Owner name
    """
    owner = Owner.query.get_or_404(owner_id)

    if owner.is_default:
        return jsonify({
            'status': 'error',
            'message': 'Cannot modify default owner'
        }), 400

    data = request.get_json()

    if 'name' in data:
        name = data['name'].strip()
        existing = Owner.query.filter(Owner.name == name, Owner.id != owner_id).first()
        if existing:
            return jsonify({
                'status': 'error',
                'message': f'Owner "{name}" already exists'
            }), 400
        owner.name = name

    db.session.commit()

    return jsonify({
        'status': 'success',
        'data': owner.to_dict()
    })


@settings_bp.route('/owners/<int:owner_id>', methods=['DELETE'])
def delete_owner(owner_id: int):
    """Delete an owner."""
    owner = Owner.query.get_or_404(owner_id)

    if owner.is_default:
        return jsonify({
            'status': 'error',
            'message': 'Cannot delete default owner'
        }), 400

    if owner.allocations.count() > 0:
        return jsonify({
            'status': 'error',
            'message': 'Cannot delete owner with existing allocations'
        }), 400

    db.session.delete(owner)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': f'Owner "{owner.name}" deleted'
    })


# ============ GOALS ============

@settings_bp.route('/goals', methods=['GET'])
def get_goals():
    """Get all goals."""
    goals = Goal.query.order_by(Goal.is_default.desc(), Goal.name).all()
    return jsonify({
        'status': 'success',
        'data': {
            'goals': [g.to_dict() for g in goals],
            'count': len(goals)
        }
    })


@settings_bp.route('/goals', methods=['POST'])
def create_goal():
    """
    Create a new goal.

    JSON body:
    - name: Goal name (required)
    - target_amount: Target amount (optional)
    """
    data = request.get_json() or {}

    name = validate_string(data.get('name'), 'Goal name', max_length=100)
    target_amount = validate_positive_decimal(
        data.get('target_amount'), 'Target amount', required=False
    )

    # Check for duplicate
    existing = Goal.query.filter_by(name=name).first()
    if existing:
        return jsonify({
            'status': 'error',
            'message': f'Goal "{name}" already exists'
        }), 400

    goal = Goal(
        name=name,
        target_amount=target_amount,
        is_default=False
    )
    db.session.add(goal)
    db.session.commit()

    logger.info(f"Created goal: {name}")

    return jsonify({
        'status': 'success',
        'data': goal.to_dict()
    }), 201


@settings_bp.route('/goals/<int:goal_id>', methods=['PUT'])
def update_goal(goal_id: int):
    """
    Update a goal.

    JSON body:
    - name: Goal name
    - target_amount: Target amount
    """
    goal = Goal.query.get_or_404(goal_id)

    if goal.is_default:
        return jsonify({
            'status': 'error',
            'message': 'Cannot modify default goal'
        }), 400

    data = request.get_json()

    if 'name' in data:
        name = data['name'].strip()
        existing = Goal.query.filter(Goal.name == name, Goal.id != goal_id).first()
        if existing:
            return jsonify({
                'status': 'error',
                'message': f'Goal "{name}" already exists'
            }), 400
        goal.name = name

    if 'target_amount' in data:
        goal.target_amount = data['target_amount']

    db.session.commit()

    return jsonify({
        'status': 'success',
        'data': goal.to_dict()
    })


@settings_bp.route('/goals/<int:goal_id>', methods=['DELETE'])
def delete_goal(goal_id: int):
    """Delete a goal."""
    goal = Goal.query.get_or_404(goal_id)

    if goal.is_default:
        return jsonify({
            'status': 'error',
            'message': 'Cannot delete default goal'
        }), 400

    if goal.allocations.count() > 0:
        return jsonify({
            'status': 'error',
            'message': 'Cannot delete goal with existing allocations'
        }), 400

    db.session.delete(goal)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': f'Goal "{goal.name}" deleted'
    })


# ============ SECTORS ============

@settings_bp.route('/sectors', methods=['GET'])
def get_sectors():
    """Get all sectors."""
    sectors = Sector.query.order_by(Sector.name).all()
    return jsonify({
        'status': 'success',
        'data': {
            'sectors': [s.to_dict() for s in sectors],
            'count': len(sectors)
        }
    })


@settings_bp.route('/sectors', methods=['POST'])
def create_sector():
    """
    Create a new sector.

    JSON body:
    - name: Sector name (required)
    """
    data = request.get_json()

    if not data or not data.get('name'):
        return jsonify({
            'status': 'error',
            'message': 'Sector name is required'
        }), 400

    name = data['name'].strip()

    # Check for duplicate
    existing = Sector.query.filter_by(name=name).first()
    if existing:
        return jsonify({
            'status': 'error',
            'message': f'Sector "{name}" already exists'
        }), 400

    sector = Sector(name=name)
    db.session.add(sector)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'data': sector.to_dict()
    }), 201
