"""Data freshness and refresh routes."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app

bp = Blueprint('data', __name__)


@bp.route('/status')
def status():
    """Show data freshness for all tables."""
    from database import get_db_session
    from utils.staleness import StalenessChecker

    staleness = []
    try:
        checker = StalenessChecker()
        with get_db_session() as session:
            staleness = checker.check_all(session)
    except Exception as e:
        flash(f'Error checking staleness: {e}', 'error')

    return render_template('data/status.html', staleness=staleness)


@bp.route('/refresh', methods=['POST'])
def refresh():
    """Trigger data refresh as a background task."""
    from web.tasks import submit_task

    force = 'force' in request.form
    app = current_app._get_current_object()

    def _run_refresh(force):
        with app.app_context():
            import subprocess, sys, logging
            from database import get_db_session
            from utils.staleness import StalenessChecker

            logger = logging.getLogger(__name__)
            project_root = app.config['PROJECT_ROOT']

            REFRESH_SCRIPTS = [
                ('price_data',           'scripts/collect_price_data.py'),
                ('fundamental_data',     'scripts/collect_fundamental_data.py'),
                ('technical_indicators', 'scripts/calculate_technical_indicators.py'),
                ('sentiment_data',       'scripts/collect_sentiment_data.py'),
                ('market_sentiment',     'scripts/collect_market_sentiment.py'),
                ('fmp_estimate_snapshots', 'scripts/collect_fmp_data.py'),
            ]

            if force:
                tables_to_refresh = [t for t, _ in REFRESH_SCRIPTS]
            else:
                checker = StalenessChecker()
                with get_db_session() as session:
                    staleness = checker.check_all(session)
                tables_to_refresh = [s.table for s in staleness if s.stale]

            results = {}
            errors = {}
            for table_key, script_path in REFRESH_SCRIPTS:
                if table_key in tables_to_refresh:
                    full_path = project_root / script_path
                    try:
                        proc = subprocess.run(
                            [sys.executable, str(full_path)],
                            capture_output=True, text=True, timeout=300,
                            cwd=str(project_root),
                        )
                        results[table_key] = proc.returncode == 0
                        if proc.returncode != 0:
                            errors[table_key] = proc.stderr[-500:] if proc.stderr else 'exit code ' + str(proc.returncode)
                            logger.warning("Refresh %s failed (rc=%d): %s", table_key, proc.returncode, proc.stderr[-500:] if proc.stderr else '')
                        else:
                            logger.info("Refresh %s succeeded", table_key)
                    except subprocess.TimeoutExpired:
                        results[table_key] = False
                        errors[table_key] = 'timed out after 300s'
                        logger.warning("Refresh %s timed out", table_key)

            ok = sum(1 for v in results.values() if v)
            fail = sum(1 for v in results.values() if not v)
            if not results:
                return "All data is fresh"
            msg = f"Refreshed {ok} tables ({fail} failed)"
            if errors:
                msg += ". Errors: " + "; ".join(f"{k}: {v}" for k, v in errors.items())
            return msg

    task_id = submit_task('Data Refresh', _run_refresh, force)
    return redirect(url_for('api.task_progress', task_id=task_id, redirect_to='/data/status'))
