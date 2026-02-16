"""Backtest execution and viewing routes."""

from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app

bp = Blueprint('backtest', __name__)


@bp.route('/')
def index():
    """Backtest configuration form."""
    from database import get_db_session
    from database.models import PriceData

    data_start = None
    data_end = None

    try:
        with get_db_session() as session:
            result = session.query(
                PriceData.date
            ).order_by(PriceData.date.asc()).first()
            if result:
                data_start = result[0]

            result = session.query(
                PriceData.date
            ).order_by(PriceData.date.desc()).first()
            if result:
                data_end = result[0]
    except Exception:
        pass

    return render_template(
        'backtest/index.html',
        data_start=data_start,
        data_end=data_end,
    )


@bp.route('/run', methods=['POST'])
def run():
    """Kick off backtest as a background task."""
    from web.tasks import submit_task

    start_str = request.form.get('start', '')
    end_str = request.form.get('end', '')

    app = current_app._get_current_object()

    def _run_backtest(start_str, end_str):
        with app.app_context():
            import pandas as pd
            from database import get_db_session
            from database.models import Stock, PriceData
            from backtesting.technical_backtest import TechnicalBacktester

            project_root = app.config['PROJECT_ROOT']

            with get_db_session() as session:
                stocks = session.query(Stock).filter_by(is_active=True).all()
                stock_sectors = {s.ticker: s.sector or 'Unknown' for s in stocks}

                price_data = {}
                for ticker in stock_sectors:
                    rows = (
                        session.query(PriceData)
                        .filter(PriceData.ticker == ticker)
                        .order_by(PriceData.date)
                        .all()
                    )
                    if not rows:
                        continue

                    data = {
                        'date': [r.date for r in rows],
                        'open': [float(r.open) if r.open else None for r in rows],
                        'high': [float(r.high) if r.high else None for r in rows],
                        'low': [float(r.low) if r.low else None for r in rows],
                        'close': [float(r.close) if r.close else None for r in rows],
                        'volume': [int(r.volume) if r.volume else 0 for r in rows],
                    }
                    df = pd.DataFrame(data)
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').set_index('date')
                    price_data[ticker] = df

            if not price_data:
                raise RuntimeError("No price data available")

            # Determine date range
            all_max = [df.index.max() for df in price_data.values()]
            all_min = [df.index.min() for df in price_data.values()]
            data_end = min(all_max).date()
            data_start = max(all_min).date()

            if end_str:
                end_date = date.fromisoformat(end_str)
            else:
                end_date = data_end - timedelta(days=31)

            if start_str:
                start_date = date.fromisoformat(start_str)
            else:
                start_date = date(end_date.year - 1, end_date.month, end_date.day)

            earliest_allowed = data_start + timedelta(days=365)
            if start_date < earliest_allowed:
                start_date = earliest_allowed

            backtester = TechnicalBacktester()
            report = backtester.run(
                price_data=price_data,
                stock_sectors=stock_sectors,
                start_date=start_date,
                end_date=end_date,
            )

            # Save report
            reports_dir = project_root / 'data' / 'reports'
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_path = reports_dir / f"backtest_{date.today().isoformat()}.txt"
            with open(report_path, 'w') as f:
                f.write(report.summary())

            return f"Backtest complete: {start_date} to {end_date}"

    task_id = submit_task('Run Backtest', _run_backtest, start_str, end_str)
    return redirect(url_for('api.task_progress', task_id=task_id, redirect_to='/backtest/report'))


@bp.route('/report')
def report():
    """Display the latest backtest report."""
    project_root = current_app.config['PROJECT_ROOT']
    reports_dir = project_root / 'data' / 'reports'

    report_text = None
    report_file = None
    all_reports = []

    if reports_dir.exists():
        all_reports = sorted(reports_dir.glob('backtest_*.txt'), reverse=True)
        if all_reports:
            report_file = all_reports[0].name
            report_text = all_reports[0].read_text()

    return render_template(
        'backtest/report.html',
        report_text=report_text,
        report_file=report_file,
        all_reports=[r.name for r in all_reports],
    )
