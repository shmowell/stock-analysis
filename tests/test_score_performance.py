"""Tests for ScorePerformanceAnalyzer."""

import sys
from pathlib import Path
from datetime import date, timedelta

import numpy as np
import pytest

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from analysis.score_performance import (
    ScorePerformanceAnalyzer,
    ScoreReturnPair,
)


def _make_pair(
    ticker: str,
    snap_date: date,
    score: float,
    rec: str,
    ret_1m: float = None,
    ret_3m: float = None,
) -> ScoreReturnPair:
    return ScoreReturnPair(
        ticker=ticker,
        snapshot_date=snap_date,
        composite_score=score,
        composite_percentile=score,
        recommendation=rec,
        fundamental_score=score * 0.9,
        technical_score=score * 1.1,
        sentiment_score=score * 0.8,
        forward_returns={'1m': ret_1m, '3m': ret_3m},
    )


def _make_correlated_pairs(n=50, seed=42):
    """Create pairs where high scores correlate with high returns."""
    np.random.seed(seed)
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META',
               'JPM', 'V', 'JNJ', 'UNH', 'PG']
    pairs = []

    for i in range(n):
        score = np.random.uniform(30, 90)
        ret_1m = (score - 60) / 1000 + np.random.normal(0, 0.01)
        ret_3m = (score - 60) / 500 + np.random.normal(0, 0.02)

        if score >= 80:
            rec = 'STRONG BUY'
        elif score >= 65:
            rec = 'BUY'
        elif score >= 45:
            rec = 'HOLD'
        elif score >= 30:
            rec = 'SELL'
        else:
            rec = 'STRONG SELL'

        snap_date = date(2025, 3, 31) + timedelta(days=30 * (i // len(tickers)))

        pairs.append(_make_pair(
            ticker=tickers[i % len(tickers)],
            snap_date=snap_date,
            score=score,
            rec=rec,
            ret_1m=ret_1m,
            ret_3m=ret_3m,
        ))

    return pairs


class TestUniverseAnalysis:
    def setup_method(self):
        self.analyzer = ScorePerformanceAnalyzer()
        self.pairs = _make_correlated_pairs(50)

    def test_total_observations(self):
        result = self.analyzer.analyze_universe(self.pairs)
        assert result.total_observations == 50

    def test_observations_with_returns(self):
        result = self.analyzer.analyze_universe(self.pairs)
        assert result.observations_with_1m == 50
        assert result.observations_with_3m == 50

    def test_recommendation_buckets_computed(self):
        result = self.analyzer.analyze_universe(self.pairs)
        rec_names = [b.recommendation for b in result.recommendation_buckets]
        assert 'STRONG BUY' in rec_names
        assert 'HOLD' in rec_names

    def test_recommendation_buckets_have_correct_order(self):
        result = self.analyzer.analyze_universe(self.pairs)
        expected_order = ['STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL']
        actual_order = [b.recommendation for b in result.recommendation_buckets]
        assert actual_order == expected_order

    def test_quintile_returns_have_5_quintiles(self):
        result = self.analyzer.analyze_universe(self.pairs)
        assert len(result.quintile_returns_1m) == 5
        assert len(result.quintile_returns_3m) == 5

    def test_quintile_q1_beats_q5_for_correlated_data(self):
        result = self.analyzer.analyze_universe(self.pairs)
        assert result.quintile_returns_1m[1] > result.quintile_returns_1m[5]
        assert result.quintile_returns_3m[1] > result.quintile_returns_3m[5]

    def test_spearman_positive_for_correlated_data(self):
        result = self.analyzer.analyze_universe(self.pairs)
        assert result.spearman_1m is not None
        assert result.spearman_1m > 0
        assert result.spearman_3m is not None
        assert result.spearman_3m > 0

    def test_hit_rate_above_50_for_correlated_data(self):
        result = self.analyzer.analyze_universe(self.pairs)
        assert result.hit_rate_1m is not None
        assert result.hit_rate_1m > 0.5

    def test_long_short_positive_for_correlated_data(self):
        result = self.analyzer.analyze_universe(self.pairs)
        assert result.long_short_1m is not None
        assert result.long_short_1m > 0

    def test_monthly_long_short_computed(self):
        result = self.analyzer.analyze_universe(self.pairs)
        assert len(result.monthly_long_short) > 0
        for entry in result.monthly_long_short:
            assert 'date' in entry
            assert 'spread_1m' in entry
            assert 'n_stocks' in entry

    def test_snapshot_dates_collected(self):
        result = self.analyzer.analyze_universe(self.pairs)
        assert len(result.snapshot_dates) > 0

    def test_handles_missing_forward_returns(self):
        """Pairs with None returns should be excluded from that horizon."""
        pairs = _make_correlated_pairs(30)
        # Set half the 3m returns to None
        for p in pairs[:15]:
            p.forward_returns['3m'] = None

        result = self.analyzer.analyze_universe(pairs)
        assert result.observations_with_1m == 30
        assert result.observations_with_3m == 15

    def test_empty_pairs(self):
        result = self.analyzer.analyze_universe([])
        assert result.total_observations == 0
        assert result.spearman_1m is None
        assert result.quintile_returns_1m == {}

    def test_too_few_pairs(self):
        """Fewer than 10 pairs should return None for correlations."""
        pairs = _make_correlated_pairs(5)
        result = self.analyzer.analyze_universe(pairs)
        assert result.total_observations == 5
        assert result.spearman_1m is None


class TestStockAnalysis:
    def setup_method(self):
        self.analyzer = ScorePerformanceAnalyzer()
        self.pairs = _make_correlated_pairs(50)

    def test_filters_to_single_ticker(self):
        result = self.analyzer.analyze_stock(self.pairs, 'AAPL')
        assert result is not None
        assert result.ticker == 'AAPL'
        assert all(s['date'] for s in result.scores)

    def test_returns_none_for_unknown_ticker(self):
        result = self.analyzer.analyze_stock(self.pairs, 'ZZZZ')
        assert result is None

    def test_score_dates_sorted(self):
        result = self.analyzer.analyze_stock(self.pairs, 'AAPL')
        dates = result.score_dates
        assert dates == sorted(dates)

    def test_avg_score_computed(self):
        result = self.analyzer.analyze_stock(self.pairs, 'AAPL')
        assert result.avg_score is not None
        assert 0 < result.avg_score < 100

    def test_avg_returns_computed(self):
        result = self.analyzer.analyze_stock(self.pairs, 'MSFT')
        assert result.avg_return_1m is not None
        assert result.avg_return_3m is not None

    def test_correlation_computed_with_enough_data(self):
        result = self.analyzer.analyze_stock(self.pairs, 'AAPL')
        assert result.observations >= 4
        assert result.score_return_correlation is not None

    def test_correlation_none_with_too_few_observations(self):
        pairs = [_make_pair('SOLO', date(2025, 3, 31), 70, 'BUY', 0.02, 0.05)]
        result = self.analyzer.analyze_stock(pairs, 'SOLO')
        assert result.score_return_correlation is None

    def test_forward_returns_lists_match_length(self):
        result = self.analyzer.analyze_stock(self.pairs, 'GOOGL')
        assert len(result.forward_returns_1m) == result.observations
        assert len(result.forward_returns_3m) == result.observations
        assert len(result.composite_scores) == result.observations


class TestStatisticalMethods:
    def test_quintile_analysis_basic(self):
        scores = np.array([90, 80, 70, 60, 50, 40, 30, 20, 10, 5])
        returns = np.array([0.1, 0.08, 0.06, 0.04, 0.02, -0.01, -0.02, -0.04, -0.06, -0.08])
        result = ScorePerformanceAnalyzer._quintile_analysis(scores, returns)
        assert 1 in result
        assert 5 in result
        assert result[1] > result[5]

    def test_spearman_perfect_positive(self):
        scores = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        returns = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
        rho = ScorePerformanceAnalyzer._spearman_correlation(scores, returns)
        assert abs(rho - 1.0) < 0.01

    def test_spearman_perfect_negative(self):
        scores = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        returns = np.array([0.05, 0.04, 0.03, 0.02, 0.01])
        rho = ScorePerformanceAnalyzer._spearman_correlation(scores, returns)
        assert abs(rho - (-1.0)) < 0.01

    def test_spearman_too_few_returns_zero(self):
        scores = np.array([1.0, 2.0])
        returns = np.array([0.01, 0.02])
        rho = ScorePerformanceAnalyzer._spearman_correlation(scores, returns)
        assert rho == 0.0

    def test_hit_rate_perfect(self):
        scores = np.array([90, 80, 70, 60, 50, 40, 30, 20, 10, 5])
        returns = np.array([0.1, 0.08, 0.06, 0.04, 0.02, -0.01, -0.02, -0.04, -0.06, -0.08])
        hr = ScorePerformanceAnalyzer._hit_rate(scores, returns)
        assert hr == 1.0

    def test_hit_rate_too_few(self):
        scores = np.array([1.0, 2.0, 3.0])
        returns = np.array([0.01, 0.02, 0.03])
        hr = ScorePerformanceAnalyzer._hit_rate(scores, returns)
        assert hr == 0.0


class TestPriceLookup:
    def test_find_price_on_exact_date(self):
        dates = [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)]
        prices = [100.0, 101.0, 102.0]
        result = ScorePerformanceAnalyzer._find_price_on_or_before(
            date(2025, 1, 2), dates, prices,
        )
        assert result == 101.0

    def test_find_price_falls_back_to_previous(self):
        dates = [date(2025, 1, 1), date(2025, 1, 3)]
        prices = [100.0, 102.0]
        result = ScorePerformanceAnalyzer._find_price_on_or_before(
            date(2025, 1, 2), dates, prices,
        )
        assert result == 100.0

    def test_find_price_returns_none_beyond_tolerance(self):
        dates = [date(2025, 1, 1)]
        prices = [100.0]
        result = ScorePerformanceAnalyzer._find_price_on_or_before(
            date(2025, 1, 10), dates, prices, tolerance_days=5,
        )
        assert result is None

    def test_find_price_returns_none_for_date_before_all(self):
        dates = [date(2025, 1, 5)]
        prices = [100.0]
        result = ScorePerformanceAnalyzer._find_price_on_or_before(
            date(2025, 1, 1), dates, prices,
        )
        assert result is None

    def test_find_price_empty_data(self):
        result = ScorePerformanceAnalyzer._find_price_on_or_before(
            date(2025, 1, 1), [], [],
        )
        assert result is None

    def test_forward_returns_computed(self):
        analyzer = ScorePerformanceAnalyzer()
        # Build a price cache with a month of daily data
        dates_list = [date(2025, 1, 1) + timedelta(days=i) for i in range(120)]
        # Price goes from 100 to ~120 linearly
        prices_list = [100.0 + i * 0.2 for i in range(120)]
        cache = {'TEST': (dates_list, prices_list)}

        result = analyzer._get_forward_returns_from_cache(
            'TEST', date(2025, 1, 1), cache,
        )
        assert result['1m'] is not None
        assert result['1m'] > 0  # Price should be higher after 30 days
        assert result['3m'] is not None
        assert result['3m'] > result['1m']  # 3m return > 1m return

    def test_forward_returns_missing_ticker(self):
        analyzer = ScorePerformanceAnalyzer()
        cache = {}
        result = analyzer._get_forward_returns_from_cache(
            'MISSING', date(2025, 1, 1), cache,
        )
        assert result['1m'] is None
        assert result['3m'] is None
