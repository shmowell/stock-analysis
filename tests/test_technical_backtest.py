"""
Tests for TechnicalBacktester — backtest technical scoring model.

Uses synthetic price data to validate the full backtest pipeline:
checkpoints, scoring, forward returns, and metric aggregation.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta

from backtesting.technical_backtest import (
    TechnicalBacktester, BacktestResult, BacktestReport,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_price_df(start='2023-01-02', periods=600, seed=42, drift=0.0005):
    """Create a realistic price DataFrame."""
    np.random.seed(seed)
    dates = pd.bdate_range(start=start, periods=periods)
    returns = np.random.normal(drift, 0.015, periods)
    prices = 100 * np.cumprod(1 + returns)
    volumes = np.random.randint(500_000, 5_000_000, periods).astype(float)
    return pd.DataFrame({
        'open': prices * 0.999,
        'high': prices * 1.005,
        'low': prices * 0.995,
        'close': prices,
        'volume': volumes,
    }, index=dates)


@pytest.fixture
def backtester():
    return TechnicalBacktester()


@pytest.fixture
def price_data():
    """10 stocks across 3 sectors with 600 trading days (~2.4 years)."""
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META',
               'XOM', 'CVX', 'JNJ', 'PFE', 'UNH']
    data = {}
    for i, ticker in enumerate(tickers):
        # Different seeds and drifts for variety
        drift = 0.0003 + i * 0.00005
        data[ticker] = _make_price_df(seed=100 + i, drift=drift)
    return data


@pytest.fixture
def stock_sectors():
    return {
        'AAPL': 'Technology', 'MSFT': 'Technology',
        'GOOGL': 'Technology', 'AMZN': 'Consumer',
        'META': 'Technology', 'XOM': 'Energy',
        'CVX': 'Energy', 'JNJ': 'Healthcare',
        'PFE': 'Healthcare', 'UNH': 'Healthcare',
    }


# ---------------------------------------------------------------------------
# Tests: _generate_monthly_checkpoints
# ---------------------------------------------------------------------------

class TestGenerateCheckpoints:

    def test_basic_range(self, backtester):
        cps = backtester._generate_monthly_checkpoints(
            date(2024, 1, 1), date(2024, 6, 30),
        )
        assert len(cps) == 6
        assert cps[0] == date(2024, 1, 31)
        assert cps[-1] == date(2024, 6, 30)

    def test_single_month(self, backtester):
        cps = backtester._generate_monthly_checkpoints(
            date(2024, 3, 1), date(2024, 3, 31),
        )
        assert len(cps) == 1
        assert cps[0] == date(2024, 3, 31)

    def test_handles_february(self, backtester):
        cps = backtester._generate_monthly_checkpoints(
            date(2024, 2, 1), date(2024, 2, 29),
        )
        assert len(cps) == 1
        assert cps[0] == date(2024, 2, 29)  # 2024 is a leap year

    def test_cross_year_boundary(self, backtester):
        cps = backtester._generate_monthly_checkpoints(
            date(2024, 11, 1), date(2025, 2, 28),
        )
        assert len(cps) == 4
        assert cps[0] == date(2024, 11, 30)
        assert cps[-1] == date(2025, 2, 28)

    def test_empty_if_end_before_start(self, backtester):
        cps = backtester._generate_monthly_checkpoints(
            date(2025, 6, 1), date(2025, 1, 1),
        )
        assert len(cps) == 0


# ---------------------------------------------------------------------------
# Tests: _quintile_analysis
# ---------------------------------------------------------------------------

class TestQuintileAnalysis:

    def test_monotonic_scores_produce_ordered_quintiles(self):
        # High scores -> high returns (perfect signal)
        scores = np.array([90, 80, 70, 60, 50, 40, 30, 20, 10, 5.0])
        returns = np.array([0.10, 0.08, 0.06, 0.04, 0.02, -0.01, -0.03, -0.05, -0.07, -0.09])

        qr = TechnicalBacktester._quintile_analysis(scores, returns)
        # Q1 (top scores) should have highest returns
        assert qr[1] > qr[5]

    def test_five_quintiles_produced(self):
        scores = np.arange(100.0)
        returns = np.random.normal(0, 0.05, 100)
        qr = TechnicalBacktester._quintile_analysis(scores, returns)
        assert set(qr.keys()) == {1, 2, 3, 4, 5}


# ---------------------------------------------------------------------------
# Tests: _spearman_correlation
# ---------------------------------------------------------------------------

class TestSpearmanCorrelation:

    def test_perfect_positive(self):
        scores = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        returns = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
        rho = TechnicalBacktester._spearman_correlation(scores, returns)
        assert rho == pytest.approx(1.0, abs=1e-6)

    def test_perfect_negative(self):
        scores = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        returns = np.array([0.05, 0.04, 0.03, 0.02, 0.01])
        rho = TechnicalBacktester._spearman_correlation(scores, returns)
        assert rho == pytest.approx(-1.0, abs=1e-6)

    def test_zero_for_random(self):
        np.random.seed(42)
        scores = np.random.randn(1000)
        returns = np.random.randn(1000)
        rho = TechnicalBacktester._spearman_correlation(scores, returns)
        assert abs(rho) < 0.1  # Should be near zero for uncorrelated data

    def test_too_few_points(self):
        rho = TechnicalBacktester._spearman_correlation(
            np.array([1.0, 2.0]), np.array([0.01, 0.02]),
        )
        assert rho == 0.0  # Degenerate case


# ---------------------------------------------------------------------------
# Tests: _hit_rate
# ---------------------------------------------------------------------------

class TestHitRate:

    def test_perfect_signal(self):
        scores = np.array([100, 90, 80, 70, 60, 50, 40, 30, 20, 10.0])
        returns = np.array([0.10, 0.08, 0.06, 0.04, 0.02, -0.01, -0.03, -0.05, -0.07, -0.09])
        hr = TechnicalBacktester._hit_rate(scores, returns)
        assert hr == 1.0  # All top-quintile stocks beat median

    def test_inverse_signal(self):
        scores = np.array([100, 90, 80, 70, 60, 50, 40, 30, 20, 10.0])
        returns = np.array([-0.09, -0.07, -0.05, -0.03, -0.01, 0.02, 0.04, 0.06, 0.08, 0.10])
        hr = TechnicalBacktester._hit_rate(scores, returns)
        assert hr == 0.0  # No top-quintile stocks beat median


# ---------------------------------------------------------------------------
# Tests: _measure_forward_returns
# ---------------------------------------------------------------------------

class TestMeasureForwardReturns:

    def test_basic_forward_returns(self):
        dates = pd.bdate_range(start='2024-01-02', periods=250)
        prices = np.linspace(100, 125, 250)
        df = pd.DataFrame({'close': prices}, index=dates)

        cp = date(2024, 3, 1)
        fwd = TechnicalBacktester._measure_forward_returns(
            ['AAPL'], {'AAPL': df}, cp,
        )
        assert 'AAPL' in fwd
        assert fwd['AAPL']['1m'] is not None
        assert fwd['AAPL']['1m'] > 0  # Prices are increasing

    def test_no_data_after_checkpoint(self):
        dates = pd.bdate_range(start='2024-01-02', periods=30)
        prices = np.linspace(100, 105, 30)
        df = pd.DataFrame({'close': prices}, index=dates)

        # Checkpoint at end of data — no forward data
        cp = date(2024, 2, 15)
        fwd = TechnicalBacktester._measure_forward_returns(
            ['AAPL'], {'AAPL': df}, cp,
        )
        # 1m might still be within data, but 6m certainly won't be
        assert fwd['AAPL']['6m'] is None


# ---------------------------------------------------------------------------
# Tests: Full run (integration)
# ---------------------------------------------------------------------------

class TestFullRun:

    def test_run_produces_report(self, backtester, price_data, stock_sectors):
        """End-to-end test: run a backtest and get a report."""
        report = backtester.run(
            price_data=price_data,
            stock_sectors=stock_sectors,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 12, 31),
        )
        assert isinstance(report, BacktestReport)
        assert len(report.checkpoints) > 0

    def test_report_has_quintile_returns(self, backtester, price_data, stock_sectors):
        report = backtester.run(
            price_data=price_data,
            stock_sectors=stock_sectors,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 12, 31),
        )
        # Should have at least 1m quintile returns
        assert '1m' in report.quintile_returns

    def test_report_has_spearman(self, backtester, price_data, stock_sectors):
        report = backtester.run(
            price_data=price_data,
            stock_sectors=stock_sectors,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 12, 31),
        )
        assert '1m' in report.spearman_correlations
        rho = report.spearman_correlations['1m']
        assert -1.0 <= rho <= 1.0

    def test_report_summary_string(self, backtester, price_data, stock_sectors):
        report = backtester.run(
            price_data=price_data,
            stock_sectors=stock_sectors,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 12, 31),
        )
        summary = report.summary()
        assert "TECHNICAL BACKTEST REPORT" in summary
        assert "Quintile" in summary

    def test_empty_date_range(self, backtester, price_data, stock_sectors):
        """Date range with no valid checkpoints should not crash."""
        report = backtester.run(
            price_data=price_data,
            stock_sectors=stock_sectors,
            start_date=date(2030, 1, 1),
            end_date=date(2030, 6, 1),
        )
        assert len(report.checkpoints) == 0
