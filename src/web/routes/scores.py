"""Score viewing and calculation routes."""

import json
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app

bp = Blueprint('scores', __name__)


@bp.route('/')
def score_list():
    """Full ranked table of all stocks with scores."""
    from database import get_db_session
    from database.models import StockScore, Stock

    scores = []
    previous = {}
    calc_date = None

    try:
        with get_db_session() as session:
            latest_date = (
                session.query(StockScore.calculation_date)
                .order_by(StockScore.calculation_date.desc())
                .first()
            )
            if latest_date:
                calc_date = latest_date[0]
                rows = (
                    session.query(StockScore)
                    .filter(StockScore.calculation_date == calc_date)
                    .order_by(StockScore.final_composite_score.desc())
                    .all()
                )
                for s in rows:
                    scores.append({
                        'ticker': s.ticker,
                        'recommendation': s.recommendation,
                        'final_composite_score': float(s.final_composite_score) if s.final_composite_score else 0,
                        'fundamental_score': float(s.fundamental_score) if s.fundamental_score else 0,
                        'technical_score': float(s.technical_score) if s.technical_score else 0,
                        'sentiment_score': float(s.sentiment_score) if s.sentiment_score else 0,
                    })

        # Load previous scores and data status from JSON
        scores_path = current_app.config['PROJECT_ROOT'] / 'data' / 'processed' / 'latest_scores.json'
        if scores_path.exists():
            with open(scores_path) as f:
                data = json.load(f)
            for s in data.get('scores', []):
                previous[s['ticker']] = s
    except Exception as e:
        flash(f'Error loading scores: {e}', 'error')

    # Build data_status lookup for list view badges
    data_statuses = {}
    for s in previous.values():
        ds = s.get('data_status', {})
        if 'no_data' in ds.values():
            data_statuses[s['ticker']] = ds

    return render_template(
        'scores/list.html',
        scores=scores,
        previous=previous,
        calc_date=calc_date,
        data_statuses=data_statuses,
    )


@bp.route('/<ticker>')
def score_detail(ticker):
    """Detail view for a single stock."""
    from database import get_db_session
    from database.models import StockScore, Stock

    ticker = ticker.upper()
    stock = None
    score = None
    pillar_scores = {}

    try:
        with get_db_session() as session:
            stock_row = session.query(Stock).filter_by(ticker=ticker).first()
            if stock_row:
                stock = {
                    'ticker': stock_row.ticker,
                    'company_name': stock_row.company_name,
                    'sector': stock_row.sector,
                    'industry': stock_row.industry,
                    'market_cap': float(stock_row.market_cap) if stock_row.market_cap else None,
                }
            score_row = (
                session.query(StockScore)
                .filter_by(ticker=ticker)
                .order_by(StockScore.calculation_date.desc())
                .first()
            )
            if score_row:
                score = {
                    'ticker': score_row.ticker,
                    'recommendation': score_row.recommendation,
                    'final_composite_score': float(score_row.final_composite_score) if score_row.final_composite_score else 0,
                    'fundamental_score': float(score_row.fundamental_score) if score_row.fundamental_score else 0,
                    'technical_score': float(score_row.technical_score) if score_row.technical_score else 0,
                    'sentiment_score': float(score_row.sentiment_score) if score_row.sentiment_score else 0,
                    'calculation_date': score_row.calculation_date,
                }

        # Load pillar detail from JSON
        scores_path = current_app.config['PROJECT_ROOT'] / 'data' / 'processed' / 'latest_scores.json'
        if scores_path.exists():
            with open(scores_path) as f:
                data = json.load(f)
            for s in data.get('scores', []):
                if s['ticker'] == ticker:
                    pillar_scores = s
                    break
    except Exception as e:
        flash(f'Error loading detail: {e}', 'error')

    if not stock:
        flash(f'Ticker {ticker} not found', 'error')
        return redirect(url_for('scores.score_list'))

    sub_components = pillar_scores.get('sub_components', {})
    data_status = pillar_scores.get('data_status', {})

    return render_template(
        'scores/detail.html',
        stock=stock,
        score=score,
        pillar=pillar_scores,
        sub_components=sub_components,
        data_status=data_status,
    )


@bp.route('/calculate', methods=['POST'])
def calculate():
    """Trigger score calculation as a background task."""
    from web.tasks import submit_task

    skip_refresh = 'skip_refresh' in request.form
    force_refresh = 'force_refresh' in request.form

    def _run_scoring(skip_refresh, force_refresh):
        from database import get_db_session
        from scoring import ScoringPipeline
        from utils.staleness import StalenessChecker
        from backtesting.snapshot_manager import SnapshotManager
        import subprocess, sys

        project_root = current_app.config['PROJECT_ROOT']

        # Refresh data if needed
        if not skip_refresh:
            REFRESH_SCRIPTS = [
                ('price_data',           'scripts/collect_price_data.py'),
                ('fundamental_data',     'scripts/collect_fundamental_data.py'),
                ('technical_indicators', 'scripts/calculate_technical_indicators.py'),
                ('sentiment_data',       'scripts/collect_sentiment_data.py'),
                ('market_sentiment',     'scripts/collect_market_sentiment.py'),
                ('fmp_estimate_snapshots', 'scripts/collect_fmp_data.py'),
            ]

            if force_refresh:
                tables_to_refresh = [t for t, _ in REFRESH_SCRIPTS]
            else:
                checker = StalenessChecker()
                with get_db_session() as session:
                    staleness = checker.check_all(session)
                tables_to_refresh = [s.table for s in staleness if s.stale]

            for table_key, script_path in REFRESH_SCRIPTS:
                if table_key in tables_to_refresh:
                    full_path = project_root / script_path
                    subprocess.run(
                        [sys.executable, str(full_path)],
                        capture_output=True, text=True, timeout=300,
                        cwd=str(project_root),
                    )

        # Run scoring
        pipeline = ScoringPipeline(verbose=False)
        with get_db_session() as session:
            result = pipeline.run(session)
            pipeline.persist_to_db(session, result)
            pipeline.persist_to_json(result)
            snapshot_mgr = SnapshotManager()
            snapshot_mgr.save(result)

        return f"Scored {len(result.composite_results)} stocks"

    # Need app context for background thread
    app = current_app._get_current_object()

    def _run_with_context(skip_refresh, force_refresh):
        with app.app_context():
            return _run_scoring(skip_refresh, force_refresh)

    task_id = submit_task('Calculate Scores', _run_with_context, skip_refresh, force_refresh)
    return redirect(url_for('api.task_progress', task_id=task_id, redirect_to='/scores/'))


@bp.route('/report')
def latest_report():
    """View the latest saved daily report."""
    project_root = current_app.config['PROJECT_ROOT']
    reports_dir = project_root / 'data' / 'reports'

    report_text = None
    report_file = None
    if reports_dir.exists():
        daily_reports = sorted(reports_dir.glob('daily_*.txt'), reverse=True)
        if daily_reports:
            report_file = daily_reports[0].name
            report_text = daily_reports[0].read_text()

    return render_template(
        'scores/report.html',
        report_text=report_text,
        report_file=report_file,
    )
