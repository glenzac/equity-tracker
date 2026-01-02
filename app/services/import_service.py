"""
Import Service - Orchestrates the import of tradebook and Tax P&L files.

Handles:
1. Parsing files
2. Creating/updating stocks, accounts
3. Importing trades
4. Importing realized P&L
5. Running reconciliation
6. Detecting corporate actions
7. Creating default allocations
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from app.extensions import db

logger = logging.getLogger(__name__)
from app.models import (
    Broker, Account, Stock, Trade, RealizedPnL,
    CorporateAction, ImportLog, Owner, Goal, Allocation
)
from app.services.parsers import ZerodhaTradeBookParser, ZerodhaTaxPnLParser
from app.services.reconciliation import ReconciliationService
from app.services.fifo_engine import FIFOEngine


class ImportService:
    """Service to orchestrate file imports."""

    def __init__(self):
        self.import_logs: List[ImportLog] = []
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []

    def import_tradebook(self, file_path: str, broker_name: str = 'Zerodha') -> Dict[str, Any]:
        """
        Import a tradebook file.

        Args:
            file_path: Path to the tradebook Excel file
            broker_name: Name of the broker (default: Zerodha)

        Returns:
            Dictionary with import results
        """
        # Create import log
        import_log = ImportLog(
            file_type='tradebook',
            file_name=Path(file_path).name,
            status='pending'
        )
        db.session.add(import_log)

        try:
            # Parse the file
            parser = ZerodhaTradeBookParser(file_path)
            account_info = parser.get_account_info()
            trades = parser.parse()

            if parser.has_errors():
                self.errors.extend(parser.errors)

            # Get or create broker
            broker = Broker.query.filter_by(name=broker_name).first()
            if not broker:
                broker = Broker(name=broker_name)
                db.session.add(broker)
                db.session.flush()

            import_log.broker_id = broker.id

            # Get or create account
            client_id = account_info.get('client_id', 'UNKNOWN')
            account = Account.query.filter_by(
                broker_id=broker.id,
                account_number=client_id
            ).first()
            if not account:
                account = Account(broker_id=broker.id, account_number=client_id)
                db.session.add(account)
                db.session.flush()

            import_log.account_id = account.id

            # Import trades
            imported_count = 0
            skipped_count = 0

            for trade_data in trades:
                # Get or create stock
                stock = Stock.get_or_create(
                    symbol=trade_data['symbol'],
                    name=trade_data['symbol'],  # Will be updated later
                    isin=trade_data.get('isin')
                )

                # Check for duplicate
                if Trade.exists(account.id, trade_data['trade_id']):
                    skipped_count += 1
                    continue

                # Create trade
                trade = Trade(
                    account_id=account.id,
                    stock_id=stock.id,
                    trade_type=trade_data['trade_type'],
                    trade_date=trade_data['trade_date'],
                    trade_datetime=trade_data.get('trade_datetime'),
                    quantity=trade_data['quantity'],
                    price=trade_data['price'],
                    exchange=trade_data.get('exchange'),
                    order_id=trade_data.get('order_id'),
                    trade_id=trade_data['trade_id']
                )
                db.session.add(trade)
                imported_count += 1

            # Update import log
            import_log.mark_success(imported_count, skipped_count)

            # Extract financial year from date range if available
            date_range = account_info.get('date_range', '')
            if 'from' in date_range.lower():
                # Parse date range to get financial year
                # Format: "Tradebook for Equity from 2024-04-01 to 2025-03-31"
                try:
                    parts = date_range.split('from')[1].split('to')
                    start_date = parts[0].strip()
                    year = int(start_date.split('-')[0])
                    month = int(start_date.split('-')[1])
                    if month >= 4:
                        import_log.financial_year = f"{year}-{year+1}"
                    else:
                        import_log.financial_year = f"{year-1}-{year}"
                except (ValueError, IndexError) as e:
                    logger.warning(f"Could not parse date range '{date_range}': {e}")

            db.session.commit()
            self.import_logs.append(import_log)

            logger.info(f"Tradebook import complete: {imported_count} imported, {skipped_count} skipped")

            return {
                'status': 'success',
                'file': Path(file_path).name,
                'broker': broker_name,
                'account': client_id,
                'trades_imported': imported_count,
                'trades_skipped': skipped_count,
                'total_trades_in_file': len(trades),
                'errors': len(parser.errors),
                'import_log_id': import_log.id
            }

        except Exception as e:
            logger.error(f"Tradebook import failed: {e}", exc_info=True)
            import_log.mark_failed(str(e))
            db.session.commit()
            raise

    def import_taxpnl(self, file_path: str, broker_name: str = 'Zerodha') -> Dict[str, Any]:
        """
        Import a Tax P&L file.

        Args:
            file_path: Path to the Tax P&L Excel file
            broker_name: Name of the broker (default: Zerodha)

        Returns:
            Dictionary with import results
        """
        import_log = ImportLog(
            file_type='taxpnl',
            file_name=Path(file_path).name,
            status='pending'
        )
        db.session.add(import_log)

        try:
            # Parse the file
            parser = ZerodhaTaxPnLParser(file_path)
            account_info = parser.get_account_info()
            entries = parser.parse()

            if parser.has_errors():
                self.errors.extend(parser.errors)

            # Get or create broker
            broker = Broker.query.filter_by(name=broker_name).first()
            if not broker:
                broker = Broker(name=broker_name)
                db.session.add(broker)
                db.session.flush()

            import_log.broker_id = broker.id

            # Get or create account
            client_id = account_info.get('client_id', 'UNKNOWN')
            account = Account.query.filter_by(
                broker_id=broker.id,
                account_number=client_id
            ).first()
            if not account:
                account = Account(broker_id=broker.id, account_number=client_id)
                db.session.add(account)
                db.session.flush()

            import_log.account_id = account.id

            # Import P&L entries
            imported_count = 0
            skipped_count = 0

            for entry_data in entries:
                # Get or create stock
                stock = Stock.get_or_create(
                    symbol=entry_data['symbol'],
                    name=entry_data['symbol'],
                    isin=entry_data.get('isin')
                )

                # Check for duplicate (same stock, exit date, quantity, profit)
                existing = RealizedPnL.query.filter_by(
                    account_id=account.id,
                    stock_id=stock.id,
                    exit_date=entry_data['exit_date'],
                    quantity=entry_data['quantity'],
                    profit=entry_data['profit']
                ).first()

                if existing:
                    skipped_count += 1
                    continue

                # Create realized P&L entry
                pnl = RealizedPnL(
                    stock_id=stock.id,
                    account_id=account.id,
                    entry_date=entry_data['entry_date'],
                    exit_date=entry_data['exit_date'],
                    quantity=entry_data['quantity'],
                    buy_value=entry_data['buy_value'],
                    sell_value=entry_data['sell_value'],
                    profit=entry_data['profit'],
                    holding_days=entry_data['holding_days'],
                    tax_term=entry_data['tax_term'],
                    financial_year=entry_data['financial_year'],
                    source='imported',
                    brokerage=entry_data.get('brokerage', 0),
                    stt=entry_data.get('stt', 0),
                    other_charges=entry_data.get('other_charges', 0)
                )
                db.session.add(pnl)
                imported_count += 1

            # Update import log
            import_log.mark_success(imported_count, skipped_count)

            # Set financial year from entries
            if entries:
                fys = set(e['financial_year'] for e in entries)
                import_log.financial_year = ', '.join(sorted(fys))

            db.session.commit()
            self.import_logs.append(import_log)

            logger.info(f"Tax P&L import complete: {imported_count} imported, {skipped_count} skipped")

            return {
                'status': 'success',
                'file': Path(file_path).name,
                'broker': broker_name,
                'account': client_id,
                'entries_imported': imported_count,
                'entries_skipped': skipped_count,
                'total_entries_in_file': len(entries),
                'capital_gains_summary': parser.get_capital_gains_summary(),
                'errors': len(parser.errors),
                'import_log_id': import_log.id
            }

        except Exception as e:
            logger.error(f"Tax P&L import failed: {e}", exc_info=True)
            import_log.mark_failed(str(e))
            db.session.commit()
            raise

    def run_reconciliation(self, account_id: int,
                           financial_year: Optional[str] = None) -> Dict[str, Any]:
        """
        Run reconciliation between tradebook and Tax P&L for an account.

        Args:
            account_id: Account ID to reconcile
            financial_year: Optional financial year filter

        Returns:
            Reconciliation results
        """
        # Get trades and P&L entries from database
        trades = Trade.query.filter_by(account_id=account_id).all()
        pnl_entries = RealizedPnL.query.filter_by(account_id=account_id)

        if financial_year:
            pnl_entries = pnl_entries.filter_by(financial_year=financial_year)

        pnl_entries = pnl_entries.all()

        # Convert to dicts for reconciliation service
        trades_data = []
        for t in trades:
            trades_data.append({
                'symbol': t.stock.symbol,
                'isin': t.stock.isin,
                'trade_date': t.trade_date,
                'trade_datetime': t.trade_datetime,
                'trade_type': t.trade_type,
                'quantity': t.quantity,
                'price': t.price,
                'trade_id': t.trade_id
            })

        pnl_data = []
        for p in pnl_entries:
            pnl_data.append({
                'symbol': p.stock.symbol,
                'isin': p.stock.isin,
                'entry_date': p.entry_date,
                'exit_date': p.exit_date,
                'quantity': p.quantity,
                'buy_value': p.buy_value,
                'sell_value': p.sell_value,
                'profit': p.profit,
                'holding_days': p.holding_days,
                'tax_term': p.tax_term,
                'financial_year': p.financial_year
            })

        # Run reconciliation
        service = ReconciliationService(trades_data, pnl_data)
        result = service.reconcile(financial_year)

        # Save detected corporate actions
        for action in result.corporate_actions:
            stock = Stock.query.filter_by(symbol=action['symbol']).first()
            if stock:
                existing = CorporateAction.query.filter_by(
                    stock_id=stock.id,
                    action_type=action['action_type'],
                    ratio_from=action['ratio_from'],
                    ratio_to=action['ratio_to']
                ).first()

                if not existing:
                    ca = CorporateAction(
                        stock_id=stock.id,
                        action_type=action['action_type'],
                        ratio_from=action['ratio_from'],
                        ratio_to=action['ratio_to'],
                        old_price=action.get('old_price'),
                        new_price=action.get('new_price'),
                        detected_automatically=True,
                        applied=False
                    )
                    db.session.add(ca)

        db.session.commit()

        return result.to_dict()

    def create_default_allocations(self, account_id: int) -> Dict[str, Any]:
        """
        Create default allocations for all holdings in an account.

        Args:
            account_id: Account ID

        Returns:
            Dictionary with allocation results
        """
        # Get default owner and goal
        default_owner = Owner.get_default()
        default_goal = Goal.get_default()

        if not default_owner or not default_goal:
            raise ValueError("Default owner or goal not found. Run 'flask seed' first.")

        # Get all stocks with trades in this account
        stocks_with_trades = db.session.query(Stock).join(Trade).filter(
            Trade.account_id == account_id
        ).distinct().all()

        created_count = 0
        updated_count = 0

        for stock in stocks_with_trades:
            # Get all trades for this stock
            trades = Trade.query.filter_by(
                account_id=account_id,
                stock_id=stock.id
            ).order_by(Trade.trade_datetime, Trade.trade_date).all()

            # Run FIFO to get current holdings
            engine = FIFOEngine()
            for trade in trades:
                if trade.trade_type == 'buy':
                    engine.process_buy(
                        trade_date=trade.trade_date,
                        quantity=trade.quantity,
                        price=trade.price,
                        trade_id=trade.trade_id,
                        trade_datetime=trade.trade_datetime
                    )
                else:
                    try:
                        engine.process_sell(
                            trade_date=trade.trade_date,
                            quantity=trade.quantity,
                            price=trade.price,
                            trade_id=trade.trade_id,
                            trade_datetime=trade.trade_datetime
                        )
                    except ValueError:
                        # Skip if sell exceeds holdings (data issue)
                        pass

            # Get remaining holdings
            holdings = engine.get_current_holdings_as_lots()
            if not holdings:
                continue

            # Calculate weighted average price and earliest date
            total_qty = sum(lot.remaining_qty for lot in holdings)
            if total_qty == 0:
                continue

            total_value = sum(lot.remaining_qty * lot.price for lot in holdings)
            avg_price = total_value / total_qty
            earliest_date = min(lot.trade_date for lot in holdings)

            # Check for existing allocation
            existing = Allocation.query.filter_by(
                stock_id=stock.id,
                account_id=account_id,
                owner_id=default_owner.id,
                goal_id=default_goal.id
            ).first()

            if existing:
                # Update if quantity changed
                if existing.quantity != total_qty:
                    existing.quantity = total_qty
                    existing.buy_price = avg_price
                    existing.buy_date = earliest_date
                    updated_count += 1
            else:
                # Create new allocation
                allocation = Allocation(
                    stock_id=stock.id,
                    account_id=account_id,
                    owner_id=default_owner.id,
                    goal_id=default_goal.id,
                    quantity=total_qty,
                    buy_price=avg_price,
                    buy_date=earliest_date
                )
                db.session.add(allocation)
                created_count += 1

        db.session.commit()

        return {
            'status': 'success',
            'allocations_created': created_count,
            'allocations_updated': updated_count,
            'stocks_processed': len(stocks_with_trades)
        }

    def full_import(self, tradebook_files: List[str],
                    taxpnl_files: List[str] = None,
                    broker_name: str = 'Zerodha') -> Dict[str, Any]:
        """
        Perform a full import with multiple files.

        Args:
            tradebook_files: List of tradebook file paths
            taxpnl_files: List of Tax P&L file paths (optional)
            broker_name: Broker name

        Returns:
            Complete import results
        """
        results = {
            'tradebook_imports': [],
            'taxpnl_imports': [],
            'reconciliation': None,
            'allocations': None,
            'errors': [],
            'warnings': []
        }

        account_id = None

        # Import tradebooks
        for file_path in tradebook_files:
            try:
                result = self.import_tradebook(file_path, broker_name)
                results['tradebook_imports'].append(result)
                if result.get('import_log_id'):
                    log = ImportLog.query.get(result['import_log_id'])
                    if log:
                        account_id = log.account_id
            except Exception as e:
                results['errors'].append({
                    'file': file_path,
                    'type': 'tradebook',
                    'error': str(e)
                })

        # Import Tax P&L files
        if taxpnl_files:
            for file_path in taxpnl_files:
                try:
                    result = self.import_taxpnl(file_path, broker_name)
                    results['taxpnl_imports'].append(result)
                except Exception as e:
                    results['errors'].append({
                        'file': file_path,
                        'type': 'taxpnl',
                        'error': str(e)
                    })

        # Run reconciliation if we have both tradebook and Tax P&L data
        if account_id and results['tradebook_imports'] and results['taxpnl_imports']:
            try:
                results['reconciliation'] = self.run_reconciliation(account_id)
            except Exception as e:
                results['warnings'].append({
                    'type': 'reconciliation',
                    'message': str(e)
                })

        # Create default allocations
        if account_id:
            try:
                results['allocations'] = self.create_default_allocations(account_id)
            except Exception as e:
                results['warnings'].append({
                    'type': 'allocations',
                    'message': str(e)
                })

        return results
