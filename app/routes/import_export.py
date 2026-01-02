"""
Import/Export Routes - Handle file uploads and data import.
"""
import os
import logging
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from app.extensions import db, limiter
from app.models import ImportLog, CorporateAction
from app.services.import_service import ImportService

logger = logging.getLogger(__name__)

import_bp = Blueprint('import', __name__)


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'xlsx'}


def get_upload_folder() -> Path:
    """Get or create upload folder."""
    upload_folder = Path(current_app.instance_path) / 'uploads'
    upload_folder.mkdir(parents=True, exist_ok=True)
    return upload_folder


@import_bp.route('/tradebook', methods=['POST'])
@limiter.limit("10 per hour")
def import_tradebook():
    """
    Import tradebook file(s).

    Expects multipart/form-data with:
    - files: One or more .xlsx tradebook files
    - broker: Broker name (default: Zerodha)
    """
    if 'files' not in request.files:
        return jsonify({
            'status': 'error',
            'message': 'No files provided'
        }), 400

    files = request.files.getlist('files')
    broker_name = request.form.get('broker', 'Zerodha')

    if not files or all(f.filename == '' for f in files):
        return jsonify({
            'status': 'error',
            'message': 'No files selected'
        }), 400

    upload_folder = get_upload_folder()
    import_service = ImportService()
    results = []

    for file in files:
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = upload_folder / filename
            file.save(str(file_path))

            try:
                result = import_service.import_tradebook(str(file_path), broker_name)
                results.append(result)
                logger.info(f"Successfully imported tradebook: {filename}")
            except Exception as e:
                logger.error(f"Error importing tradebook {filename}: {e}", exc_info=True)
                results.append({
                    'status': 'error',
                    'file': filename,
                    'error': str(e)
                })
            finally:
                # Clean up uploaded file
                if file_path.exists():
                    file_path.unlink()
        else:
            results.append({
                'status': 'error',
                'file': file.filename,
                'error': 'Invalid file type. Only .xlsx files are allowed.'
            })

    return jsonify({
        'status': 'success' if all(r.get('status') == 'success' for r in results) else 'partial',
        'data': {
            'imports': results,
            'total_files': len(files),
            'successful': sum(1 for r in results if r.get('status') == 'success')
        }
    })


@import_bp.route('/taxpnl', methods=['POST'])
@limiter.limit("10 per hour")
def import_taxpnl():
    """
    Import Tax P&L file(s).

    Expects multipart/form-data with:
    - files: One or more .xlsx Tax P&L files
    - broker: Broker name (default: Zerodha)
    """
    if 'files' not in request.files:
        return jsonify({
            'status': 'error',
            'message': 'No files provided'
        }), 400

    files = request.files.getlist('files')
    broker_name = request.form.get('broker', 'Zerodha')

    if not files or all(f.filename == '' for f in files):
        return jsonify({
            'status': 'error',
            'message': 'No files selected'
        }), 400

    upload_folder = get_upload_folder()
    import_service = ImportService()
    results = []

    for file in files:
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = upload_folder / filename
            file.save(str(file_path))

            try:
                result = import_service.import_taxpnl(str(file_path), broker_name)
                results.append(result)
                logger.info(f"Successfully imported Tax P&L: {filename}")
            except Exception as e:
                logger.error(f"Error importing Tax P&L {filename}: {e}", exc_info=True)
                results.append({
                    'status': 'error',
                    'file': filename,
                    'error': str(e)
                })
            finally:
                if file_path.exists():
                    file_path.unlink()
        else:
            results.append({
                'status': 'error',
                'file': file.filename,
                'error': 'Invalid file type. Only .xlsx files are allowed.'
            })

    return jsonify({
        'status': 'success' if all(r.get('status') == 'success' for r in results) else 'partial',
        'data': {
            'imports': results,
            'total_files': len(files),
            'successful': sum(1 for r in results if r.get('status') == 'success')
        }
    })


@import_bp.route('/full', methods=['POST'])
@limiter.limit("10 per hour")
def full_import():
    """
    Full import with tradebook and Tax P&L files.

    Expects multipart/form-data with:
    - tradebook_files: Tradebook .xlsx files
    - taxpnl_files: Tax P&L .xlsx files (optional)
    - broker: Broker name (default: Zerodha)
    """
    tradebook_files = request.files.getlist('tradebook_files')
    taxpnl_files = request.files.getlist('taxpnl_files')
    broker_name = request.form.get('broker', 'Zerodha')

    if not tradebook_files or all(f.filename == '' for f in tradebook_files):
        return jsonify({
            'status': 'error',
            'message': 'At least one tradebook file is required'
        }), 400

    upload_folder = get_upload_folder()
    tradebook_paths = []
    taxpnl_paths = []

    try:
        # Save tradebook files
        for file in tradebook_files:
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = upload_folder / f"tb_{filename}"
                file.save(str(file_path))
                tradebook_paths.append(str(file_path))

        # Save Tax P&L files
        for file in taxpnl_files:
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = upload_folder / f"pnl_{filename}"
                file.save(str(file_path))
                taxpnl_paths.append(str(file_path))

        # Run full import
        import_service = ImportService()
        results = import_service.full_import(
            tradebook_files=tradebook_paths,
            taxpnl_files=taxpnl_paths if taxpnl_paths else None,
            broker_name=broker_name
        )

        return jsonify({
            'status': 'success' if not results.get('errors') else 'partial',
            'data': results
        })

    finally:
        # Clean up uploaded files
        for path in tradebook_paths + taxpnl_paths:
            try:
                Path(path).unlink()
            except OSError as e:
                logger.warning(f"Failed to clean up file {path}: {e}")


@import_bp.route('/reconcile/<int:account_id>', methods=['POST'])
def run_reconciliation(account_id: int):
    """
    Run reconciliation for an account.

    URL parameters:
    - account_id: Account ID

    Query parameters:
    - fy: Financial year filter (optional)
    """
    financial_year = request.args.get('fy')

    import_service = ImportService()
    try:
        result = import_service.run_reconciliation(account_id, financial_year)
        logger.info(f"Reconciliation completed for account {account_id}")
        return jsonify({
            'status': 'success',
            'data': result
        })
    except Exception as e:
        logger.error(f"Reconciliation failed for account {account_id}: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@import_bp.route('/corporate-actions', methods=['GET'])
def get_corporate_actions():
    """Get all detected corporate actions."""
    pending_only = request.args.get('pending', 'false').lower() == 'true'

    query = CorporateAction.query
    if pending_only:
        query = query.filter_by(applied=False)

    actions = query.order_by(CorporateAction.created_at.desc()).all()

    return jsonify({
        'status': 'success',
        'data': {
            'corporate_actions': [a.to_dict() for a in actions],
            'count': len(actions)
        }
    })


@import_bp.route('/corporate-actions/<int:action_id>/apply', methods=['POST'])
def apply_corporate_action(action_id: int):
    """Apply a detected corporate action."""
    action = CorporateAction.query.get_or_404(action_id)

    if action.applied:
        return jsonify({
            'status': 'error',
            'message': 'Corporate action already applied'
        }), 400

    # Mark as applied (actual adjustment logic would go here)
    action.applied = True
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': f'{action.action_type.title()} for {action.stock.symbol} marked as applied',
        'data': action.to_dict()
    })


@import_bp.route('/logs', methods=['GET'])
def get_import_logs():
    """Get import history."""
    limit = request.args.get('limit', 20, type=int)

    logs = ImportLog.get_recent(limit)

    return jsonify({
        'status': 'success',
        'data': {
            'logs': [log.to_dict() for log in logs],
            'count': len(logs)
        }
    })


@import_bp.route('/allocations/<int:account_id>', methods=['POST'])
def create_allocations(account_id: int):
    """Create default allocations for an account."""
    import_service = ImportService()
    try:
        result = import_service.create_default_allocations(account_id)
        return jsonify({
            'status': 'success',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
