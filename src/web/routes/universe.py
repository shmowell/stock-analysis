"""Stock universe management routes."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app

bp = Blueprint('universe', __name__)


@bp.route('/')
def universe_list():
    """Display current stock universe grouped by sector."""
    from database import get_db_session
    from database.models import Stock

    sectors = {}
    inactive = []

    try:
        with get_db_session() as session:
            active = (
                session.query(Stock)
                .filter_by(is_active=True)
                .order_by(Stock.sector, Stock.ticker)
                .all()
            )
            inactive = (
                session.query(Stock)
                .filter_by(is_active=False)
                .order_by(Stock.ticker)
                .all()
            )

            for s in active:
                sector = s.sector or 'Unknown'
                sectors.setdefault(sector, []).append({
                    'ticker': s.ticker,
                    'name': s.company_name or '',
                    'market_cap': float(s.market_cap) if s.market_cap else None,
                    'industry': s.industry or '',
                })

            inactive = [{
                'ticker': s.ticker,
                'name': s.company_name or '',
            } for s in inactive]

    except Exception as e:
        flash(f'Error loading universe: {e}', 'error')

    return render_template(
        'universe/list.html',
        sectors=sectors,
        inactive=inactive,
        total_active=sum(len(v) for v in sectors.values()),
    )


@bp.route('/add', methods=['GET', 'POST'])
def add():
    """Add stocks to the universe."""
    if request.method == 'GET':
        return render_template('universe/add.html')

    tickers_raw = request.form.get('tickers', '')
    tickers = [t.strip().upper() for t in tickers_raw.replace(',', ' ').split() if t.strip()]

    if not tickers:
        flash('No tickers provided', 'error')
        return redirect(url_for('universe.add'))

    from database import get_db_session
    from database.models import Stock
    from data_collection import YahooFinanceCollector

    collector = YahooFinanceCollector()
    added = []
    errors = []

    try:
        with get_db_session() as session:
            for ticker in tickers:
                existing = session.query(Stock).filter_by(ticker=ticker).first()

                if existing and existing.is_active:
                    flash(f'{ticker}: already in universe', 'warning')
                    continue
                elif existing and not existing.is_active:
                    existing.is_active = True
                    added.append(ticker)
                    flash(f'{ticker}: reactivated', 'success')
                    continue

                try:
                    data = collector.get_stock_data(ticker)
                    info = data['company_info']
                    fund = data['fundamental']

                    stock = Stock(
                        ticker=ticker,
                        company_name=info.get('name'),
                        sector=info.get('sector'),
                        industry=info.get('industry'),
                        market_cap=fund.get('market_cap'),
                        is_active=True,
                    )
                    session.add(stock)
                    added.append(ticker)
                    flash(f'{ticker}: added ({info.get("name", "")})', 'success')
                except Exception as e:
                    errors.append(ticker)
                    flash(f'{ticker}: failed - {e}', 'error')
    except Exception as e:
        flash(f'Database error: {e}', 'error')

    if added:
        # Auto-trigger data collection + scoring as background task
        from web.tasks import submit_task

        app = current_app._get_current_object()
        tickers_to_collect = list(added)  # copy for closure

        def _collect_and_score():
            with app.app_context():
                import subprocess, sys, logging
                from database import get_db_session as get_session
                from scoring import ScoringPipeline
                from backtesting.snapshot_manager import SnapshotManager

                task_logger = logging.getLogger(__name__)
                project_root = app.config['PROJECT_ROOT']

                COLLECT_SCRIPTS = [
                    ('price_data',           'scripts/collect_price_data.py'),
                    ('fundamental_data',     'scripts/collect_fundamental_data.py'),
                    ('technical_indicators', 'scripts/calculate_technical_indicators.py'),
                    ('sentiment_data',       'scripts/collect_sentiment_data.py'),
                    ('market_sentiment',     'scripts/collect_market_sentiment.py'),
                    ('fmp_estimate_snapshots', 'scripts/collect_fmp_data.py'),
                ]

                for table_key, script_path in COLLECT_SCRIPTS:
                    full_path = project_root / script_path
                    cmd = [sys.executable, str(full_path)]
                    if 'market_sentiment' not in script_path:
                        cmd.extend(['--ticker'] + tickers_to_collect)
                    try:
                        proc = subprocess.run(
                            cmd, capture_output=True, text=True, timeout=300,
                            cwd=str(project_root),
                        )
                        if proc.returncode != 0:
                            task_logger.warning(
                                "Collect %s failed (rc=%d): %s",
                                table_key, proc.returncode,
                                proc.stderr[-500:] if proc.stderr else '',
                            )
                    except subprocess.TimeoutExpired:
                        task_logger.warning("Collect %s timed out", table_key)

                # Score full universe
                pipeline = ScoringPipeline(verbose=False)
                with get_session() as session:
                    result = pipeline.run(session)
                    pipeline.persist_to_db(session, result)
                    pipeline.persist_to_json(result)
                    SnapshotManager().save(result)

                return (
                    f"Collected data for {', '.join(tickers_to_collect)} "
                    f"and scored {len(result.composite_results)} stocks"
                )

        ticker_label = ', '.join(tickers_to_collect)
        task_id = submit_task(
            f'Add & Score {ticker_label}', _collect_and_score
        )
        return redirect(url_for(
            'api.task_progress',
            task_id=task_id,
            redirect_to='/scores/',
        ))

    return redirect(url_for('universe.universe_list'))


@bp.route('/remove', methods=['POST'])
def remove():
    """Soft-delete a stock from the universe."""
    ticker = request.form.get('ticker', '').upper()
    if not ticker:
        flash('No ticker provided', 'error')
        return redirect(url_for('universe.universe_list'))

    from database import get_db_session
    from database.models import Stock

    try:
        with get_db_session() as session:
            stock = session.query(Stock).filter_by(ticker=ticker).first()
            if not stock:
                flash(f'{ticker}: not found', 'error')
            elif not stock.is_active:
                flash(f'{ticker}: already inactive', 'warning')
            else:
                stock.is_active = False
                flash(f'{ticker}: deactivated', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'error')

    return redirect(url_for('universe.universe_list'))


@bp.route('/reactivate', methods=['POST'])
def reactivate():
    """Reactivate a previously removed stock."""
    ticker = request.form.get('ticker', '').upper()
    if not ticker:
        flash('No ticker provided', 'error')
        return redirect(url_for('universe.universe_list'))

    from database import get_db_session
    from database.models import Stock

    try:
        with get_db_session() as session:
            stock = session.query(Stock).filter_by(ticker=ticker).first()
            if not stock:
                flash(f'{ticker}: not found', 'error')
            elif stock.is_active:
                flash(f'{ticker}: already active', 'warning')
            else:
                stock.is_active = True
                flash(f'{ticker}: reactivated', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'error')

    return redirect(url_for('universe.universe_list'))
