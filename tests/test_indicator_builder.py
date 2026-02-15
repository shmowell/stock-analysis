"""
Tests for IndicatorBuilder — backtesting indicator calculation engine.

Validates that IndicatorBuilder produces correct indicators from price DataFrames
and matches the behavior of the existing TechnicalIndicatorCalculator.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta

from backtesting.indicator_builder import IndicatorBuilder, _safe_float


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def builder():
    return IndicatorBuilder()


@pytest.fixture
def price_df():
    """Create a realistic price DataFrame spanning 300 trading days."""
    np.random.seed(42)
    dates = pd.bdate_range(start='2024-01-02', periods=300)
    # Random walk starting at 100
    returns = np.random.normal(0.0005, 0.015, 300)
    prices = 100 * np.cumprod(1 + returns)

    volumes = np.random.randint(1_000_000, 10_000_000, 300).astype(float)

    return pd.DataFrame({
        'open': prices * 0.999,
        'high': prices * 1.005,
        'low': prices * 0.995,
        'close': prices,
        'volume': volumes,
    }, index=dates)


@pytest.fixture
def short_price_df():
    """Price DataFrame with only 50 days (too short for 200-MA)."""
    dates = pd.bdate_range(start='2024-01-02', periods=50)
    prices = np.linspace(100, 110, 50)
    return pd.DataFrame({
        'close': prices,
        'volume': [1_000_000] * 50,
    }, index=dates)


# ---------------------------------------------------------------------------
# Tests: compute()
# ---------------------------------------------------------------------------

class TestCompute:

    def test_returns_all_indicator_columns(self, builder, price_df):
        result = builder.compute(price_df)
        expected_cols = {
            'sma_20', 'sma_50', 'sma_200', 'mad', 'rsi_14',
            'avg_volume_20d', 'avg_volume_90d', 'relative_volume',
            'momentum_1m', 'momentum_3m', 'momentum_6m', 'momentum_12_1',
            'price_vs_200ma',
        }
        assert set(result.columns) == expected_cols

    def test_same_index_as_input(self, builder, price_df):
        result = builder.compute(price_df)
        assert len(result) == len(price_df)
        assert (result.index == price_df.index).all()

    def test_sma_values_correct(self, builder, price_df):
        result = builder.compute(price_df)
        # SMA-20 at index 19 should equal mean of first 20 closes
        expected = price_df['close'].iloc[:20].mean()
        assert result['sma_20'].iloc[19] == pytest.approx(expected, rel=1e-6)

    def test_sma_200_nan_before_200_days(self, builder, price_df):
        result = builder.compute(price_df)
        # First 199 rows should be NaN for sma_200
        assert result['sma_200'].iloc[:199].isna().all()
        # Row 199 (index 200th) should have a value
        assert pd.notna(result['sma_200'].iloc[199])

    def test_mad_calculation(self, builder, price_df):
        result = builder.compute(price_df)
        # MAD = (SMA50 - SMA200) / SMA200
        idx = 250  # Well past 200 days
        sma50 = result['sma_50'].iloc[idx]
        sma200 = result['sma_200'].iloc[idx]
        expected_mad = (sma50 - sma200) / sma200
        assert result['mad'].iloc[idx] == pytest.approx(expected_mad, rel=1e-6)

    def test_rsi_in_valid_range(self, builder, price_df):
        result = builder.compute(price_df)
        valid_rsi = result['rsi_14'].dropna()
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()

    def test_momentum_1m(self, builder, price_df):
        result = builder.compute(price_df)
        idx = 50
        expected = (price_df['close'].iloc[idx] - price_df['close'].iloc[idx - 21]) / price_df['close'].iloc[idx - 21]
        assert result['momentum_1m'].iloc[idx] == pytest.approx(expected, rel=1e-6)

    def test_momentum_12_1_excludes_recent_month(self, builder, price_df):
        """12-1 month momentum should use price 1 month ago vs 12 months ago."""
        result = builder.compute(price_df)
        idx = 260  # Need 252 + 21 days
        close = price_df['close']
        p_12m_ago = close.iloc[idx - 252]
        p_1m_ago = close.iloc[idx - 21]
        expected = (p_1m_ago - p_12m_ago) / p_12m_ago
        assert result['momentum_12_1'].iloc[idx] == pytest.approx(expected, rel=1e-6)

    def test_relative_volume(self, builder, price_df):
        result = builder.compute(price_df)
        idx = 100
        vol_20 = price_df['volume'].iloc[idx - 19:idx + 1].mean()
        vol_90 = price_df['volume'].iloc[idx - 89:idx + 1].mean()
        expected = vol_20 / vol_90
        assert result['relative_volume'].iloc[idx] == pytest.approx(expected, rel=1e-4)

    def test_price_vs_200ma_boolean(self, builder, price_df):
        result = builder.compute(price_df)
        valid = result.loc[result['sma_200'].notna()]
        # Check the boolean values match direct comparison
        for idx in valid.index[:5]:  # Spot check a few
            expected = price_df.loc[idx, 'close'] > valid.loc[idx, 'sma_200']
            assert result.loc[idx, 'price_vs_200ma'] == expected

    def test_empty_input(self, builder):
        result = builder.compute(pd.DataFrame())
        assert result.empty

    def test_no_volume_column(self, builder):
        """Should handle missing volume gracefully."""
        dates = pd.bdate_range(start='2024-01-02', periods=100)
        prices = np.linspace(100, 120, 100)
        df = pd.DataFrame({'close': prices}, index=dates)

        result = builder.compute(df)
        assert result['avg_volume_20d'].isna().all()
        assert result['relative_volume'].isna().all()

    def test_short_data_produces_nans(self, builder, short_price_df):
        """With only 50 days, 200-day SMA should be all NaN."""
        result = builder.compute(short_price_df)
        assert result['sma_200'].isna().all()
        assert result['momentum_12_1'].isna().all()


# ---------------------------------------------------------------------------
# Tests: get_as_of()
# ---------------------------------------------------------------------------

class TestGetAsOf:

    def test_exact_date_match(self, builder, price_df):
        indicators = builder.compute(price_df)
        target = indicators.index[250]
        row = builder.get_as_of(indicators, target)
        assert row is not None
        assert row.name == target

    def test_weekend_falls_back_to_friday(self, builder, price_df):
        indicators = builder.compute(price_df)
        # Find an actual Friday in the index
        fridays = [d for d in indicators.index if d.weekday() == 4]
        assert len(fridays) > 0
        friday = fridays[10]
        saturday = friday + pd.Timedelta(days=1)
        row = builder.get_as_of(indicators, saturday)
        assert row is not None
        assert row.name == friday

    def test_before_all_data_returns_none(self, builder, price_df):
        indicators = builder.compute(price_df)
        early = indicators.index[0] - pd.Timedelta(days=10)
        row = builder.get_as_of(indicators, early)
        assert row is None

    def test_empty_indicators(self, builder):
        row = builder.get_as_of(pd.DataFrame(), pd.Timestamp('2024-06-01'))
        assert row is None


# ---------------------------------------------------------------------------
# Tests: build_snapshot()
# ---------------------------------------------------------------------------

class TestBuildSnapshot:

    def test_returns_all_expected_keys(self, builder, price_df):
        indicators = builder.compute(price_df)
        target = indicators.index[250]
        price = float(price_df.loc[target, 'close'])
        snapshot = builder.build_snapshot(indicators, target, price)

        expected_keys = {
            'sma_20', 'sma_50', 'sma_200', 'mad', 'rsi_14',
            'avg_volume_20d', 'avg_volume_90d', 'relative_volume',
            'momentum_1m', 'momentum_3m', 'momentum_6m', 'momentum_12_1',
            'price_vs_200ma', 'current_price',
            'short_term_uptrend', 'long_term_uptrend', 'sector_relative_6m',
        }
        assert set(snapshot.keys()) == expected_keys

    def test_current_price_passed_through(self, builder, price_df):
        indicators = builder.compute(price_df)
        target = indicators.index[250]
        snapshot = builder.build_snapshot(indicators, target, 123.45)
        assert snapshot['current_price'] == 123.45

    def test_uptrend_signals_computed(self, builder, price_df):
        indicators = builder.compute(price_df)
        target = indicators.index[250]
        price = float(price_df.loc[target, 'close'])
        snapshot = builder.build_snapshot(indicators, target, price)
        # Should be bool or None, not NaN
        assert snapshot['short_term_uptrend'] in (True, False, None)
        assert snapshot['long_term_uptrend'] in (True, False, None)

    def test_sector_relative_initially_none(self, builder, price_df):
        indicators = builder.compute(price_df)
        target = indicators.index[250]
        price = float(price_df.loc[target, 'close'])
        snapshot = builder.build_snapshot(indicators, target, price)
        assert snapshot['sector_relative_6m'] is None

    def test_no_data_returns_none(self, builder):
        result = builder.build_snapshot(pd.DataFrame(), pd.Timestamp('2024-06-01'), 100.0)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: compute_sector_relative()
# ---------------------------------------------------------------------------

class TestComputeSectorRelative:

    def test_basic_calculation(self, builder):
        snapshots = {
            'AAPL': {'momentum_6m': 0.10, 'sector_relative_6m': None},
            'MSFT': {'momentum_6m': 0.20, 'sector_relative_6m': None},
            'XOM': {'momentum_6m': 0.15, 'sector_relative_6m': None},
        }
        sectors = {
            'AAPL': 'Technology',
            'MSFT': 'Technology',
            'XOM': 'Energy',
        }
        builder.compute_sector_relative(snapshots, sectors)

        tech_avg = (0.10 + 0.20) / 2  # 0.15
        assert snapshots['AAPL']['sector_relative_6m'] == pytest.approx(0.10 - tech_avg)
        assert snapshots['MSFT']['sector_relative_6m'] == pytest.approx(0.20 - tech_avg)
        # XOM is the only stock in Energy, so relative = 0
        assert snapshots['XOM']['sector_relative_6m'] == pytest.approx(0.0)

    def test_missing_momentum_skipped(self, builder):
        snapshots = {
            'AAPL': {'momentum_6m': 0.10, 'sector_relative_6m': None},
            'MSFT': {'momentum_6m': None, 'sector_relative_6m': None},
        }
        sectors = {'AAPL': 'Technology', 'MSFT': 'Technology'}
        builder.compute_sector_relative(snapshots, sectors)

        # AAPL is the only one with data; sector avg = 0.10
        assert snapshots['AAPL']['sector_relative_6m'] == pytest.approx(0.0)
        # MSFT had no momentum_6m, should remain None
        assert snapshots['MSFT']['sector_relative_6m'] is None


# ---------------------------------------------------------------------------
# Tests: _safe_float()
# ---------------------------------------------------------------------------

class TestSafeFloat:

    def test_normal_float(self):
        assert _safe_float(3.14) == 3.14

    def test_int(self):
        assert _safe_float(42) == 42.0

    def test_nan(self):
        assert _safe_float(np.nan) is None

    def test_none(self):
        assert _safe_float(None) is None

    def test_numpy_float(self):
        assert _safe_float(np.float64(2.5)) == 2.5

    def test_string_fails(self):
        assert _safe_float("abc") is None
