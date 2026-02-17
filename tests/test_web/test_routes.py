"""Tests for Flask web GUI routes."""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock


def _mock_db_session(mock_session=None):
    """Create a mock for get_db_session context manager."""
    if mock_session is None:
        mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


class TestAppCreation:
    """Verify app factory and route registration."""

    def test_app_creates(self, app):
        assert app is not None
        assert app.config['TESTING'] is True

    def test_all_blueprints_registered(self, app):
        bp_names = list(app.blueprints.keys())
        assert 'dashboard' in bp_names
        assert 'scores' in bp_names
        assert 'universe' in bp_names
        assert 'overrides' in bp_names
        assert 'backtest' in bp_names
        assert 'data' in bp_names
        assert 'api' in bp_names

    def test_route_count(self, app):
        rules = [r.rule for r in app.url_map.iter_rules()
                 if not r.rule.startswith('/static')]
        assert len(rules) >= 20


class TestDashboard:
    """Dashboard route tests."""

    @patch('database.get_db_session')
    @patch('overrides.override_logger.OverrideLogger')
    @patch('utils.staleness.StalenessChecker')
    def test_dashboard_loads(self, mock_stale_cls, mock_logger_cls, mock_db, client):
        mock_session = MagicMock()
        mock_db.return_value = _mock_db_session(mock_session)
        mock_session.query.return_value.filter_by.return_value.count.return_value = 0
        mock_session.query.return_value.order_by.return_value.first.return_value = None

        mock_stale_cls.return_value.check_all.return_value = []
        mock_logger_cls.return_value.load_all_overrides.return_value = []

        response = client.get('/')
        assert response.status_code == 200
        assert b'Dashboard' in response.data


class TestScoresRoutes:
    """Score page tests."""

    @patch('database.get_db_session')
    def test_scores_list_loads(self, mock_db, client):
        mock_session = MagicMock()
        mock_db.return_value = _mock_db_session(mock_session)
        mock_session.query.return_value.order_by.return_value.first.return_value = None

        response = client.get('/scores/')
        assert response.status_code == 200
        assert b'Stock Scores' in response.data

    @patch('database.get_db_session')
    def test_score_detail_redirects_if_not_found(self, mock_db, client):
        mock_session = MagicMock()
        mock_db.return_value = _mock_db_session(mock_session)
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        mock_session.query.return_value.filter_by.return_value.order_by.return_value.first.return_value = None

        response = client.get('/scores/FAKE')
        assert response.status_code == 302

    def test_report_page_loads(self, client):
        response = client.get('/scores/report')
        assert response.status_code == 200


class TestUniverseRoutes:
    """Universe management tests."""

    @patch('database.get_db_session')
    def test_universe_list_loads(self, mock_db, client):
        mock_session = MagicMock()
        mock_db.return_value = _mock_db_session(mock_session)
        mock_session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = []

        response = client.get('/universe/')
        assert response.status_code == 200
        assert b'Stock Universe' in response.data

    def test_add_page_loads(self, client):
        response = client.get('/universe/add')
        assert response.status_code == 200
        assert b'Add Stocks' in response.data

    def test_add_empty_tickers_redirects(self, client):
        response = client.post('/universe/add', data={'tickers': ''})
        assert response.status_code == 302

    @patch('web.tasks.submit_task')
    @patch('database.get_db_session')
    @patch('data_collection.YahooFinanceCollector')
    def test_add_stock_triggers_background_task(
        self, mock_yf_cls, mock_db, mock_submit, client
    ):
        """Adding a new stock should submit a background collect+score task."""
        mock_session = MagicMock()
        mock_db.return_value = _mock_db_session(mock_session)

        # Stock doesn't exist yet
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Yahoo Finance returns valid data
        mock_yf_cls.return_value.get_stock_data.return_value = {
            'company_info': {'name': 'Tesla', 'sector': 'Tech', 'industry': 'Auto'},
            'fundamental': {'market_cap': 500e9},
        }

        mock_submit.return_value = 'abc123'

        response = client.post('/universe/add', data={'tickers': 'TSLA'})
        assert response.status_code == 302
        assert '/api/task/abc123/progress' in response.location

        mock_submit.assert_called_once()
        task_name = mock_submit.call_args[0][0]
        assert 'TSLA' in task_name

    @patch('database.get_db_session')
    def test_add_existing_stock_no_task(self, mock_db, client):
        """Adding an already-active stock should not submit a task."""
        mock_session = MagicMock()
        mock_db.return_value = _mock_db_session(mock_session)

        # Stock already exists and is active
        existing = MagicMock()
        existing.is_active = True
        mock_session.query.return_value.filter_by.return_value.first.return_value = existing

        response = client.post('/universe/add', data={'tickers': 'AAPL'})
        assert response.status_code == 302
        # Should redirect to universe list, not task progress
        assert '/universe/' in response.location

    def test_remove_empty_ticker_redirects(self, client):
        response = client.post('/universe/remove', data={'ticker': ''})
        assert response.status_code == 302

    def test_reactivate_empty_ticker_redirects(self, client):
        response = client.post('/universe/reactivate', data={'ticker': ''})
        assert response.status_code == 302


class TestOverrideRoutes:
    """Override routes tests."""

    @patch('overrides.override_logger.OverrideLogger')
    def test_override_list_loads(self, mock_logger_cls, client):
        mock_logger_cls.return_value.load_all_overrides.return_value = []
        response = client.get('/overrides/')
        assert response.status_code == 200

    @patch('overrides.override_logger.OverrideLogger')
    def test_override_summary_loads(self, mock_logger_cls, client):
        mock_logger_cls.return_value.load_all_overrides.return_value = []
        mock_logger_cls.return_value.calculate_override_statistics.return_value = {
            'total_overrides': 0,
            'avg_percentile_impact': 0,
            'recommendation_changes': 0,
            'extreme_overrides': 0,
            'guardrail_violations': 0,
        }
        response = client.get('/overrides/summary')
        assert response.status_code == 200

    @patch('overrides.override_logger.OverrideLogger')
    def test_override_detail_loads(self, mock_logger_cls, client):
        mock_logger_cls.return_value.load_all_overrides.return_value = []
        response = client.get('/overrides/detail/AAPL')
        assert response.status_code == 200

    def test_apply_form_loads(self, client):
        response = client.get('/overrides/apply')
        assert response.status_code == 200
        assert b'Apply Override' in response.data


class TestBacktestRoutes:
    """Backtest routes tests."""

    @patch('database.get_db_session')
    def test_backtest_index_loads(self, mock_db, client):
        mock_session = MagicMock()
        mock_db.return_value = _mock_db_session(mock_session)
        mock_session.query.return_value.order_by.return_value.first.return_value = None

        response = client.get('/backtest/')
        assert response.status_code == 200
        assert b'Backtest' in response.data

    def test_backtest_report_loads(self, client):
        response = client.get('/backtest/report')
        assert response.status_code == 200


class TestDataRoutes:
    """Data freshness routes tests."""

    @patch('database.get_db_session')
    @patch('utils.staleness.StalenessChecker')
    def test_data_status_loads(self, mock_stale_cls, mock_db, client):
        mock_session = MagicMock()
        mock_db.return_value = _mock_db_session(mock_session)
        mock_stale_cls.return_value.check_all.return_value = []

        response = client.get('/data/status')
        assert response.status_code == 200
        assert b'Data Freshness' in response.data


class TestAPIRoutes:
    """API endpoint tests."""

    def test_task_not_found(self, client):
        response = client.get('/api/task/nonexistent')
        assert response.status_code == 404

    def test_task_progress_page_loads(self, client):
        from web.tasks import submit_task
        import time

        task_id = submit_task('Test', lambda: time.sleep(0) or "done")
        response = client.get(f'/api/task/{task_id}/progress?redirect_to=/')
        assert response.status_code == 200
        assert b'Test' in response.data


class TestTaskSystem:
    """Background task system tests."""

    def test_submit_and_complete(self):
        from web.tasks import submit_task, get_task
        import time

        task_id = submit_task('test-task', lambda: "result-value")
        time.sleep(0.5)

        task = get_task(task_id)
        assert task['status'] == 'completed'
        assert task['result'] == 'result-value'

    def test_submit_and_fail(self):
        from web.tasks import submit_task, get_task
        import time

        def _fail():
            raise ValueError("test error")

        task_id = submit_task('fail-task', _fail)
        time.sleep(0.5)

        task = get_task(task_id)
        assert task['status'] == 'failed'
        assert 'test error' in task['error']

    def test_get_nonexistent_task(self):
        from web.tasks import get_task
        assert get_task('does-not-exist') is None
