"""
Flask web application for Stock Analysis Framework.

Usage:
    python run_web.py
"""

from flask import Flask
from pathlib import Path


def create_app(testing=False):
    """Application factory for the Flask web GUI.

    Args:
        testing: If True, use testing configuration.

    Returns:
        Configured Flask application.
    """
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static',
    )

    app.secret_key = 'stock-analysis-local-dev'

    if testing:
        app.config['TESTING'] = True

    # Project root for resolving paths to scripts/, data/, etc.
    app.config['PROJECT_ROOT'] = Path(__file__).parent.parent.parent

    # Register blueprints
    from .routes.dashboard import bp as dashboard_bp
    from .routes.scores import bp as scores_bp
    from .routes.universe import bp as universe_bp
    from .routes.overrides import bp as overrides_bp
    from .routes.backtest import bp as backtest_bp
    from .routes.performance import bp as performance_bp
    from .routes.data import bp as data_bp
    from .routes.api import bp as api_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(scores_bp, url_prefix='/scores')
    app.register_blueprint(universe_bp, url_prefix='/universe')
    app.register_blueprint(overrides_bp, url_prefix='/overrides')
    app.register_blueprint(backtest_bp, url_prefix='/backtest')
    app.register_blueprint(performance_bp, url_prefix='/performance')
    app.register_blueprint(data_bp, url_prefix='/data')
    app.register_blueprint(api_bp, url_prefix='/api')

    return app
