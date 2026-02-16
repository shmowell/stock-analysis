"""Dashboard route — main landing page."""

from flask import Blueprint, render_template, current_app

bp = Blueprint('dashboard', __name__)


@bp.route('/')
def index():
    """Main dashboard showing scores summary, freshness, and recent overrides."""
    from database import get_db_session
    from database.models import StockScore, Stock
    from utils.staleness import StalenessChecker
    from overrides.override_logger import OverrideLogger

    # Latest scores
    scores = []
    stock_count = 0
    try:
        with get_db_session() as session:
            stock_count = session.query(Stock).filter_by(is_active=True).count()

            # Get the most recent calculation date
            latest_date = (
                session.query(StockScore.calculation_date)
                .order_by(StockScore.calculation_date.desc())
                .first()
            )
            if latest_date:
                rows = (
                    session.query(StockScore)
                    .filter(StockScore.calculation_date == latest_date[0])
                    .order_by(StockScore.final_composite_score.desc())
                    .all()
                )
                # Convert to dicts while session is open
                for s in rows:
                    scores.append({
                        'ticker': s.ticker,
                        'recommendation': s.recommendation,
                        'final_composite_score': float(s.final_composite_score) if s.final_composite_score else 0,
                        'fundamental_score': float(s.fundamental_score) if s.fundamental_score else 0,
                        'technical_score': float(s.technical_score) if s.technical_score else 0,
                        'sentiment_score': float(s.sentiment_score) if s.sentiment_score else 0,
                    })
    except Exception:
        scores = []

    # Data freshness
    staleness = []
    try:
        checker = StalenessChecker()
        with get_db_session() as session:
            staleness = checker.check_all(session)
    except Exception:
        pass

    stale_count = sum(1 for s in staleness if s.stale)

    # Recent overrides
    recent_overrides = []
    try:
        logger = OverrideLogger()
        all_overrides = logger.load_all_overrides()
        recent_overrides = all_overrides[-5:] if all_overrides else []
        recent_overrides.reverse()
    except Exception:
        pass

    return render_template(
        'dashboard.html',
        scores=scores,
        stock_count=stock_count,
        staleness=staleness,
        stale_count=stale_count,
        recent_overrides=recent_overrides,
    )
