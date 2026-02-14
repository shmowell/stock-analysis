"""
Unit tests for FMP (Financial Modeling Prep) data collector.

Framework Reference: Section 5.2 (Analyst Revision Momentum), Section 9.3
Tests API integration, grade counting, and estimate revision logic.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from data_collection.fmp import FMPCollector
from utils.validators import DataValidationError


# --- Fixtures ---

@pytest.fixture
def fmp():
    """Create FMPCollector with test API key."""
    return FMPCollector(api_key='test_key')


@pytest.fixture
def sample_grades():
    """Sample stock grades response from FMP API."""
    today = datetime.now()
    return [
        {
            'symbol': 'AAPL',
            'date': (today - timedelta(days=5)).strftime('%Y-%m-%d'),
            'gradingCompany': 'Morgan Stanley',
            'previousGrade': 'Neutral',
            'newGrade': 'Overweight',
            'action': 'upgrade'
        },
        {
            'symbol': 'AAPL',
            'date': (today - timedelta(days=10)).strftime('%Y-%m-%d'),
            'gradingCompany': 'JP Morgan',
            'previousGrade': 'Overweight',
            'newGrade': 'Overweight',
            'action': 'maintain'
        },
        {
            'symbol': 'AAPL',
            'date': (today - timedelta(days=15)).strftime('%Y-%m-%d'),
            'gradingCompany': 'Barclays',
            'previousGrade': 'Overweight',
            'newGrade': 'Equal-Weight',
            'action': 'downgrade'
        },
        {
            'symbol': 'AAPL',
            'date': (today - timedelta(days=20)).strftime('%Y-%m-%d'),
            'gradingCompany': 'Wedbush',
            'previousGrade': 'Neutral',
            'newGrade': 'Outperform',
            'action': 'upgrade'
        },
        # Outside 30-day window
        {
            'symbol': 'AAPL',
            'date': (today - timedelta(days=45)).strftime('%Y-%m-%d'),
            'gradingCompany': 'Goldman Sachs',
            'previousGrade': 'Buy',
            'newGrade': 'Sell',
            'action': 'downgrade'
        },
    ]


@pytest.fixture
def sample_estimates():
    """Sample analyst estimates response from FMP API (real field names)."""
    return [
        {
            'symbol': 'AAPL',
            'date': '2026-06-30',
            'epsAvg': 1.65,
            'epsHigh': 1.80,
            'epsLow': 1.50,
            'revenueAvg': 95000000000,
            'revenueHigh': 98000000000,
            'revenueLow': 90000000000,
            'numAnalystsEps': 30,
            'numAnalystsRevenue': 28,
        },
        {
            'symbol': 'AAPL',
            'date': '2026-09-30',
            'epsAvg': 1.72,
            'epsHigh': 1.90,
            'epsLow': 1.55,
            'revenueAvg': 100000000000,
            'revenueHigh': 105000000000,
            'revenueLow': 95000000000,
            'numAnalystsEps': 25,
            'numAnalystsRevenue': 24,
        },
    ]


# --- Constructor Tests ---

class TestFMPCollectorInit:
    """Test FMPCollector initialization."""

    def test_init_with_api_key(self):
        """Constructor accepts explicit API key."""
        fmp = FMPCollector(api_key='test_key_123')
        assert fmp.api_key == 'test_key_123'

    @patch.dict('os.environ', {'FMP_API_KEY': 'env_key_456'})
    def test_init_from_env(self):
        """Constructor reads API key from environment."""
        fmp = FMPCollector()
        assert fmp.api_key == 'env_key_456'

    @patch.dict('os.environ', {}, clear=True)
    def test_init_no_key_raises(self):
        """Constructor raises ValueError without API key."""
        with pytest.raises(ValueError, match="FMP API key not provided"):
            FMPCollector()

    def test_rate_limiter_initialized(self):
        """Rate limiter is configured on init."""
        fmp = FMPCollector(api_key='test_key')
        assert fmp.rate_limiter is not None
        assert fmp.rate_limiter.max_calls == 10
        assert fmp.rate_limiter.period == 60


# --- API Request Tests ---

class TestMakeRequest:
    """Test _make_request error handling."""

    @patch('src.data_collection.fmp.requests.get')
    def test_successful_request(self, mock_get, fmp):
        """Successful API call returns parsed JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'symbol': 'AAPL'}]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fmp._make_request('grades', {'symbol': 'AAPL'})
        assert result == [{'symbol': 'AAPL'}]

    @patch('src.data_collection.fmp.requests.get')
    def test_402_premium_endpoint(self, mock_get, fmp):
        """402 status raises DataValidationError for premium endpoints."""
        mock_response = MagicMock()
        mock_response.status_code = 402
        mock_get.return_value = mock_response

        with pytest.raises(DataValidationError, match="premium subscription"):
            fmp._make_request('insider-trading/search', {'symbol': 'AAPL'})

    @patch('src.data_collection.fmp.requests.get')
    def test_429_rate_limit(self, mock_get, fmp):
        """429 status raises DataValidationError for rate limit."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        with pytest.raises(DataValidationError, match="rate limit"):
            fmp._make_request('grades', {'symbol': 'AAPL'})

    @patch('src.data_collection.fmp.requests.get')
    def test_network_timeout(self, mock_get, fmp):
        """Network timeout raises DataValidationError."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

        with pytest.raises(DataValidationError, match="request failed"):
            fmp._make_request('grades', {'symbol': 'AAPL'})

    @patch('src.data_collection.fmp.requests.get')
    def test_error_message_in_response(self, mock_get, fmp):
        """FMP error message in response raises DataValidationError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'Error Message': 'Invalid API key'}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with pytest.raises(DataValidationError, match="Invalid API key"):
            fmp._make_request('grades', {'symbol': 'AAPL'})


# --- Analyst Estimates Tests ---

class TestAnalystEstimates:
    """Test analyst estimates fetching and parsing."""

    @patch.object(FMPCollector, '_make_request')
    def test_parse_valid_response(self, mock_request, fmp, sample_estimates):
        """Correctly parses FMP estimates response."""
        mock_request.return_value = sample_estimates

        result = fmp.get_analyst_estimates('AAPL')

        assert len(result) == 2
        assert result[0]['date'] == '2026-06-30'
        assert result[0]['estimatedEpsAvg'] == 1.65
        assert result[0]['estimatedRevenueAvg'] == 95000000000
        assert result[0]['numberAnalystEstimatedEps'] == 30

    @patch.object(FMPCollector, '_make_request')
    def test_empty_response(self, mock_request, fmp):
        """Empty response returns empty list."""
        mock_request.return_value = []
        result = fmp.get_analyst_estimates('AAPL')
        assert result == []

    def test_invalid_ticker(self, fmp):
        """Invalid ticker raises DataValidationError."""
        with pytest.raises(DataValidationError, match="Invalid ticker"):
            fmp.get_analyst_estimates('')

    @patch.object(FMPCollector, '_make_request')
    def test_validates_numeric_fields(self, mock_request, fmp):
        """Numeric fields are validated (None/NaN handled)."""
        mock_request.return_value = [{
            'symbol': 'AAPL',
            'date': '2026-06-30',
            'epsAvg': 'not_a_number',
            'epsHigh': None,
            'epsLow': 1.50,
            'revenueAvg': -100,  # Below min_value=0
            'revenueHigh': 98000000000,
            'revenueLow': None,
            'numAnalystsEps': 30,
            'numAnalystsRevenue': None,
        }]

        result = fmp.get_analyst_estimates('AAPL')
        assert len(result) == 1
        assert result[0]['estimatedEpsAvg'] is None  # Invalid string
        assert result[0]['estimatedEpsHigh'] is None  # None stays None
        assert result[0]['estimatedEpsLow'] == 1.50
        assert result[0]['estimatedRevenueAvg'] is None  # Negative revenue


# --- Stock Grades Tests ---

class TestStockGrades:
    """Test stock grades fetching."""

    @patch.object(FMPCollector, '_make_request')
    def test_parse_valid_response(self, mock_request, fmp, sample_grades):
        """Correctly returns grade records."""
        mock_request.return_value = sample_grades
        result = fmp.get_stock_grades('AAPL')
        assert len(result) == 5

    @patch.object(FMPCollector, '_make_request')
    def test_empty_grades(self, mock_request, fmp):
        """Empty response returns empty list."""
        mock_request.return_value = []
        result = fmp.get_stock_grades('AAPL')
        assert result == []

    def test_invalid_ticker(self, fmp):
        """Invalid ticker raises DataValidationError."""
        with pytest.raises(DataValidationError, match="Invalid ticker"):
            fmp.get_stock_grades('')


# --- Upgrades/Downgrades Tests ---

class TestUpgradesDowngrades:
    """Test upgrade/downgrade counting logic."""

    @patch.object(FMPCollector, 'get_stock_grades')
    def test_count_in_window(self, mock_grades, fmp, sample_grades):
        """Only counts grades within 30-day window."""
        mock_grades.return_value = sample_grades
        result = fmp.calculate_upgrades_downgrades('AAPL', lookback_days=30)

        assert result['upgrades'] == 2
        assert result['downgrades'] == 1
        assert result['maintains'] == 1
        assert result['total'] == 4

    @patch.object(FMPCollector, 'get_stock_grades')
    def test_excludes_old_grades(self, mock_grades, fmp, sample_grades):
        """Grades older than lookback are excluded."""
        mock_grades.return_value = sample_grades

        # Only 5-day window should catch 1 upgrade
        result = fmp.calculate_upgrades_downgrades('AAPL', lookback_days=6)
        assert result['upgrades'] == 1
        assert result['downgrades'] == 0
        assert result['total'] == 1

    @patch.object(FMPCollector, 'get_stock_grades')
    def test_all_upgrades(self, mock_grades, fmp):
        """All upgrades counted correctly."""
        today = datetime.now().strftime('%Y-%m-%d')
        mock_grades.return_value = [
            {'date': today, 'action': 'upgrade'},
            {'date': today, 'action': 'upgrade'},
            {'date': today, 'action': 'upgrade'},
        ]
        result = fmp.calculate_upgrades_downgrades('AAPL')
        assert result['upgrades'] == 3
        assert result['downgrades'] == 0

    @patch.object(FMPCollector, 'get_stock_grades')
    def test_all_downgrades(self, mock_grades, fmp):
        """All downgrades counted correctly."""
        today = datetime.now().strftime('%Y-%m-%d')
        mock_grades.return_value = [
            {'date': today, 'action': 'downgrade'},
            {'date': today, 'action': 'downgrade'},
        ]
        result = fmp.calculate_upgrades_downgrades('AAPL')
        assert result['upgrades'] == 0
        assert result['downgrades'] == 2

    @patch.object(FMPCollector, 'get_stock_grades')
    def test_empty_grades(self, mock_grades, fmp):
        """No grades returns all zeros."""
        mock_grades.return_value = []
        result = fmp.calculate_upgrades_downgrades('AAPL')
        assert result == {'upgrades': 0, 'downgrades': 0, 'maintains': 0, 'total': 0}

    @patch.object(FMPCollector, 'get_stock_grades')
    def test_missing_action_ignored(self, mock_grades, fmp):
        """Grades with missing action field are ignored."""
        today = datetime.now().strftime('%Y-%m-%d')
        mock_grades.return_value = [
            {'date': today, 'action': None},
            {'date': today, 'action': 'upgrade'},
        ]
        result = fmp.calculate_upgrades_downgrades('AAPL')
        assert result['upgrades'] == 1
        assert result['total'] == 1


# --- Estimate Revisions Tests ---

class TestEstimateRevisions:
    """Test estimate revision calculation logic."""

    @patch.object(FMPCollector, 'get_analyst_estimates')
    def test_first_run_no_baseline(self, mock_estimates, fmp, sample_estimates):
        """First run (no previous snapshots) returns None for revisions."""
        mock_estimates.return_value = sample_estimates

        result = fmp.calculate_estimate_revisions('AAPL', previous_snapshots=None)

        assert result['revisions_up'] is None
        assert result['revisions_down'] is None
        assert result['total'] is None
        assert len(result['current_estimates']) == 2

    @patch.object(FMPCollector, 'get_analyst_estimates')
    def test_revisions_up(self, mock_estimates, fmp):
        """Detects upward revisions for EPS and revenue."""
        mock_estimates.return_value = [
            {
                'date': '2026-06-30',
                'estimatedEpsAvg': 1.70,  # Up from 1.60
                'estimatedRevenueAvg': 100000000000,  # Up from 95B (>0.5%)
            }
        ]

        previous = {
            '2026-06-30': {
                'eps_avg': 1.60,
                'revenue_avg': 95000000000,
            }
        }

        result = fmp.calculate_estimate_revisions('AAPL', previous_snapshots=previous)

        assert result['revisions_up'] == 2  # EPS + revenue both up
        assert result['revisions_down'] == 0
        assert result['total'] == 2

    @patch.object(FMPCollector, 'get_analyst_estimates')
    def test_revisions_down(self, mock_estimates, fmp):
        """Detects downward revisions for EPS and revenue."""
        mock_estimates.return_value = [
            {
                'date': '2026-06-30',
                'estimatedEpsAvg': 1.50,  # Down from 1.65
                'estimatedRevenueAvg': 90000000000,  # Down from 95B (>0.5%)
            }
        ]

        previous = {
            '2026-06-30': {
                'eps_avg': 1.65,
                'revenue_avg': 95000000000,
            }
        }

        result = fmp.calculate_estimate_revisions('AAPL', previous_snapshots=previous)

        assert result['revisions_up'] == 0
        assert result['revisions_down'] == 2
        assert result['total'] == 2

    @patch.object(FMPCollector, 'get_analyst_estimates')
    def test_no_change_within_tolerance(self, mock_estimates, fmp):
        """Small changes within tolerance are not counted as revisions."""
        mock_estimates.return_value = [
            {
                'date': '2026-06-30',
                'estimatedEpsAvg': 1.605,  # Within $0.01 of 1.60
                'estimatedRevenueAvg': 95200000000,  # Within 0.5% of 95B
            }
        ]

        previous = {
            '2026-06-30': {
                'eps_avg': 1.60,
                'revenue_avg': 95000000000,
            }
        }

        result = fmp.calculate_estimate_revisions('AAPL', previous_snapshots=previous)

        assert result['revisions_up'] == 0
        assert result['revisions_down'] == 0
        assert result['total'] == 0

    @patch.object(FMPCollector, 'get_analyst_estimates')
    def test_mixed_revisions(self, mock_estimates, fmp):
        """Mixed revisions across multiple periods."""
        mock_estimates.return_value = [
            {
                'date': '2026-06-30',
                'estimatedEpsAvg': 1.75,  # Up
                'estimatedRevenueAvg': 90000000000,  # Down
            },
            {
                'date': '2026-09-30',
                'estimatedEpsAvg': 1.50,  # Down
                'estimatedRevenueAvg': 105000000000,  # Up
            },
        ]

        previous = {
            '2026-06-30': {'eps_avg': 1.60, 'revenue_avg': 95000000000},
            '2026-09-30': {'eps_avg': 1.70, 'revenue_avg': 100000000000},
        }

        result = fmp.calculate_estimate_revisions('AAPL', previous_snapshots=previous)

        assert result['revisions_up'] == 2
        assert result['revisions_down'] == 2
        assert result['total'] == 4

    @patch.object(FMPCollector, 'get_analyst_estimates')
    def test_unmatched_periods_ignored(self, mock_estimates, fmp):
        """Fiscal periods without a previous match are ignored."""
        mock_estimates.return_value = [
            {
                'date': '2026-12-31',  # No previous snapshot for this date
                'estimatedEpsAvg': 2.00,
                'estimatedRevenueAvg': 110000000000,
            }
        ]

        previous = {
            '2026-06-30': {'eps_avg': 1.60, 'revenue_avg': 95000000000},
        }

        result = fmp.calculate_estimate_revisions('AAPL', previous_snapshots=previous)

        assert result['revisions_up'] == 0
        assert result['revisions_down'] == 0
        assert result['total'] == 0

    @patch.object(FMPCollector, 'get_analyst_estimates')
    def test_none_values_handled(self, mock_estimates, fmp):
        """None values in estimates don't cause errors."""
        mock_estimates.return_value = [
            {
                'date': '2026-06-30',
                'estimatedEpsAvg': None,
                'estimatedRevenueAvg': None,
            }
        ]

        previous = {
            '2026-06-30': {'eps_avg': 1.60, 'revenue_avg': 95000000000},
        }

        result = fmp.calculate_estimate_revisions('AAPL', previous_snapshots=previous)

        assert result['revisions_up'] == 0
        assert result['revisions_down'] == 0

    @patch.object(FMPCollector, 'get_analyst_estimates')
    def test_empty_estimates(self, mock_estimates, fmp):
        """Empty estimates list returns None for all fields."""
        mock_estimates.return_value = []

        result = fmp.calculate_estimate_revisions('AAPL', previous_snapshots={'2026-06-30': {}})

        assert result['revisions_up'] is None
        assert result['revisions_down'] is None
