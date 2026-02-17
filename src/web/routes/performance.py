"""Score vs. Price Performance analysis routes."""

from flask import Blueprint, render_template, jsonify, current_app

bp = Blueprint('performance', __name__)


@bp.route('/')
def index():
    """Universe-level performance analysis page."""
    return render_template('performance/index.html')


@bp.route('/data')
def universe_data():
    """JSON endpoint for universe-level performance analysis."""
    from database import get_db_session
    from analysis.score_performance import ScorePerformanceAnalyzer

    project_root = current_app.config['PROJECT_ROOT']
    snapshot_dir = str(project_root / 'data' / 'snapshots')

    analyzer = ScorePerformanceAnalyzer()

    try:
        with get_db_session() as session:
            pairs = analyzer.load_data(snapshot_dir, session)
            universe = analyzer.analyze_universe(pairs)

        return jsonify({
            'total_observations': universe.total_observations,
            'observations_with_1m': universe.observations_with_1m,
            'observations_with_3m': universe.observations_with_3m,
            'snapshot_dates': universe.snapshot_dates,
            'recommendation_buckets': [
                {
                    'recommendation': b.recommendation,
                    'count': b.count,
                    'avg_score': b.avg_score,
                    'avg_return_1m': b.avg_return_1m,
                    'avg_return_3m': b.avg_return_3m,
                    'median_return_1m': b.median_return_1m,
                    'median_return_3m': b.median_return_3m,
                    'win_rate_1m': b.win_rate_1m,
                    'win_rate_3m': b.win_rate_3m,
                }
                for b in universe.recommendation_buckets
            ],
            'quintile_returns_1m': universe.quintile_returns_1m,
            'quintile_returns_3m': universe.quintile_returns_3m,
            'spearman_1m': universe.spearman_1m,
            'spearman_3m': universe.spearman_3m,
            'long_short_1m': universe.long_short_1m,
            'long_short_3m': universe.long_short_3m,
            'hit_rate_1m': universe.hit_rate_1m,
            'hit_rate_3m': universe.hit_rate_3m,
            'monthly_long_short': universe.monthly_long_short,
        })
    except Exception as e:
        current_app.logger.error(f'Performance analysis error: {e}')
        return jsonify({'error': str(e)}), 500


@bp.route('/stock/<ticker>')
def stock_data(ticker):
    """JSON endpoint for per-stock performance analysis."""
    from database import get_db_session
    from analysis.score_performance import ScorePerformanceAnalyzer

    ticker = ticker.upper()
    project_root = current_app.config['PROJECT_ROOT']
    snapshot_dir = str(project_root / 'data' / 'snapshots')

    analyzer = ScorePerformanceAnalyzer()

    try:
        with get_db_session() as session:
            pairs = analyzer.load_data(snapshot_dir, session)
            stock = analyzer.analyze_stock(pairs, ticker)

        if not stock:
            return jsonify({'error': f'No data for {ticker}'}), 404

        return jsonify({
            'ticker': stock.ticker,
            'observations': stock.observations,
            'scores': stock.scores,
            'avg_score': stock.avg_score,
            'avg_return_1m': stock.avg_return_1m,
            'avg_return_3m': stock.avg_return_3m,
            'score_return_correlation': stock.score_return_correlation,
            'score_dates': stock.score_dates,
            'composite_scores': stock.composite_scores,
            'forward_returns_1m': stock.forward_returns_1m,
            'forward_returns_3m': stock.forward_returns_3m,
        })
    except Exception as e:
        current_app.logger.error(f'Stock performance analysis error for {ticker}: {e}')
        return jsonify({'error': str(e)}), 500
