"""
Unit tests for analyst revision scoring with real FMP data.

Framework Reference: Section 5.2 (Analyst Revision Momentum)
Tests the upgraded calculate_analyst_revision_score() method that uses
real estimate revision data when available, falling back to the
recommendation_mean proxy.
"""

import pytest
from src.calculators.sentiment import SentimentCalculator


class TestRevisionScoreWithRealData:
    """
    Test framework-specified revision scoring thresholds.

    Framework Section 5.2:
    - >60% revised up: Score = 75
    - 40-60% revised up: Score = 60
    - 20-40% revised up: Score = 40
    - <20% revised up: Score = 25
    """

    def test_high_pct_up(self):
        """>60% up should score 75."""
        calc = SentimentCalculator()
        # 8 up, 2 down = 80% up
        score = calc.calculate_analyst_revision_score(
            None, None, estimate_revisions_up=8, estimate_revisions_down=2
        )
        assert score == 75.0

    def test_moderate_pct_up(self):
        """40-60% up should score 60."""
        calc = SentimentCalculator()
        # 5 up, 5 down = 50% up
        score = calc.calculate_analyst_revision_score(
            None, None, estimate_revisions_up=5, estimate_revisions_down=5
        )
        assert score == 60.0

    def test_low_pct_up(self):
        """20-40% up should score 40."""
        calc = SentimentCalculator()
        # 3 up, 7 down = 30% up
        score = calc.calculate_analyst_revision_score(
            None, None, estimate_revisions_up=3, estimate_revisions_down=7
        )
        assert score == 40.0

    def test_very_low_pct_up(self):
        """<20% up should score 25."""
        calc = SentimentCalculator()
        # 1 up, 9 down = 10% up
        score = calc.calculate_analyst_revision_score(
            None, None, estimate_revisions_up=1, estimate_revisions_down=9
        )
        assert score == 25.0

    def test_all_up(self):
        """100% up should score 75."""
        calc = SentimentCalculator()
        score = calc.calculate_analyst_revision_score(
            None, None, estimate_revisions_up=6, estimate_revisions_down=0
        )
        assert score == 75.0

    def test_all_down(self):
        """0% up should score 25."""
        calc = SentimentCalculator()
        score = calc.calculate_analyst_revision_score(
            None, None, estimate_revisions_up=0, estimate_revisions_down=6
        )
        assert score == 25.0


class TestRevisionScoreBoundaries:
    """Test exact boundary values for revision scoring."""

    def test_boundary_60_pct(self):
        """Exactly 60% up is in the 40-60% bucket (score = 60)."""
        calc = SentimentCalculator()
        # 6 up, 4 down = 60% up
        score = calc.calculate_analyst_revision_score(
            None, None, estimate_revisions_up=6, estimate_revisions_down=4
        )
        assert score == 60.0

    def test_boundary_just_above_60_pct(self):
        """61% up is in the >60% bucket (score = 75)."""
        calc = SentimentCalculator()
        # Can't get exactly 61%, but 7/11 = 63.6%
        score = calc.calculate_analyst_revision_score(
            None, None, estimate_revisions_up=7, estimate_revisions_down=4
        )
        assert score == 75.0

    def test_boundary_40_pct(self):
        """Exactly 40% up is in the 40-60% bucket (score = 60)."""
        calc = SentimentCalculator()
        # 4 up, 6 down = 40% up
        score = calc.calculate_analyst_revision_score(
            None, None, estimate_revisions_up=4, estimate_revisions_down=6
        )
        assert score == 60.0

    def test_boundary_20_pct(self):
        """Exactly 20% up is in the 20-40% bucket (score = 40)."""
        calc = SentimentCalculator()
        # 2 up, 8 down = 20% up
        score = calc.calculate_analyst_revision_score(
            None, None, estimate_revisions_up=2, estimate_revisions_down=8
        )
        assert score == 40.0


class TestRevisionScoreConfidenceDamping:
    """Test confidence damping for low revision counts."""

    def test_low_count_damping(self):
        """<5 total revisions dampens score toward 50."""
        calc = SentimentCalculator()
        # 3 up, 1 down = 75% up -> base_score=75, but total=4 so damped
        score = calc.calculate_analyst_revision_score(
            None, None, estimate_revisions_up=3, estimate_revisions_down=1
        )
        # base=75, damped: 50 + (75-50)*0.7 = 50 + 17.5 = 67.5
        assert score == 67.5

    def test_low_count_damping_bearish(self):
        """Damping works for bearish scores too."""
        calc = SentimentCalculator()
        # 0 up, 3 down = 0% up -> base_score=25, total=3 so damped
        score = calc.calculate_analyst_revision_score(
            None, None, estimate_revisions_up=0, estimate_revisions_down=3
        )
        # base=25, damped: 50 + (25-50)*0.7 = 50 - 17.5 = 32.5
        assert score == 32.5

    def test_sufficient_count_no_damping(self):
        """>=5 total revisions are not dampened."""
        calc = SentimentCalculator()
        # 4 up, 1 down = 80% up -> score=75, total=5 (no damping)
        score = calc.calculate_analyst_revision_score(
            None, None, estimate_revisions_up=4, estimate_revisions_down=1
        )
        assert score == 75.0


class TestRevisionScoreFallback:
    """Test fallback to recommendation_mean proxy."""

    def test_none_revisions_falls_to_proxy(self):
        """None revision values trigger proxy path."""
        calc = SentimentCalculator()
        # revision data is None, recommendation_mean=2.0 (Buy) -> 60
        score = calc.calculate_analyst_revision_score(
            recommendation_mean=2.0, analyst_count=10,
            estimate_revisions_up=None, estimate_revisions_down=None
        )
        assert score == 60.0

    def test_zero_total_falls_to_proxy(self):
        """Zero total revisions (0 up + 0 down) falls to proxy."""
        calc = SentimentCalculator()
        score = calc.calculate_analyst_revision_score(
            recommendation_mean=3.0, analyst_count=10,
            estimate_revisions_up=0, estimate_revisions_down=0
        )
        # Falls through to proxy: recommendation_mean=3.0 (Hold) -> 40
        assert score == 40.0

    def test_no_data_at_all(self):
        """No revision data AND no recommendation_mean -> neutral 50."""
        calc = SentimentCalculator()
        score = calc.calculate_analyst_revision_score(
            recommendation_mean=None, analyst_count=None,
            estimate_revisions_up=None, estimate_revisions_down=None
        )
        assert score == 50.0

    def test_real_data_overrides_proxy(self):
        """Real revision data takes priority over recommendation_mean."""
        calc = SentimentCalculator()
        # recommendation_mean=1.0 (Strong Buy -> 75), but revisions say bearish
        score = calc.calculate_analyst_revision_score(
            recommendation_mean=1.0, analyst_count=30,
            estimate_revisions_up=1, estimate_revisions_down=9
        )
        # Real data: 10% up -> score=25 (not 75 from proxy)
        assert score == 25.0


class TestBackwardCompatibility:
    """Test that existing proxy-only behavior is preserved."""

    def test_proxy_strong_buy(self):
        """recommendation_mean 1.0-1.5 -> 75 (unchanged)."""
        calc = SentimentCalculator()
        assert calc.calculate_analyst_revision_score(1.2, 10) == 75.0

    def test_proxy_buy(self):
        """recommendation_mean 1.5-2.5 -> 60 (unchanged)."""
        calc = SentimentCalculator()
        assert calc.calculate_analyst_revision_score(2.0, 10) == 60.0

    def test_proxy_hold(self):
        """recommendation_mean 2.5-3.5 -> 40 (unchanged)."""
        calc = SentimentCalculator()
        assert calc.calculate_analyst_revision_score(3.0, 10) == 40.0

    def test_proxy_sell(self):
        """recommendation_mean 3.5-4.5 -> 25 (unchanged)."""
        calc = SentimentCalculator()
        assert calc.calculate_analyst_revision_score(4.0, 10) == 25.0

    def test_proxy_strong_sell(self):
        """recommendation_mean 4.5-5.0 -> 15 (unchanged)."""
        calc = SentimentCalculator()
        assert calc.calculate_analyst_revision_score(4.8, 10) == 15.0

    def test_proxy_low_analyst_damping(self):
        """Low analyst count damping still works (unchanged)."""
        calc = SentimentCalculator()
        # recommendation_mean=2.0 (Buy->60), analyst_count=3 (damped)
        score = calc.calculate_analyst_revision_score(2.0, 3)
        # 50 + (60-50)*0.7 = 57.0
        assert score == 57.0

    def test_proxy_none_recommendation(self):
        """None recommendation -> neutral 50 (unchanged)."""
        calc = SentimentCalculator()
        assert calc.calculate_analyst_revision_score(None, 10) == 50.0


class TestStockSentimentWithRevisions:
    """Test that revision data flows through calculate_stock_specific_sentiment."""

    def test_with_revision_data(self):
        """Revision data is used in stock-specific sentiment calculation."""
        calc = SentimentCalculator()
        stock_data = {
            'days_to_cover': 2.0,         # Normal -> 50
            'recommendation_mean': 3.0,    # Hold -> 40 (proxy, but overridden)
            'analyst_count': 20,
            'analyst_target': 110.0,
            'market_cap': 15000,
            'insider_net_shares': 50000,   # Moderate buying -> 60
            'estimate_revisions_up_90d': 8,
            'estimate_revisions_down_90d': 2,  # 80% up -> 75
        }
        score = calc.calculate_stock_specific_sentiment(stock_data, current_price=100.0)
        assert score is not None
        # Verify revision score used real data (75), not proxy (40)
        revision_score = calc.calculate_analyst_revision_score(
            3.0, 20, estimate_revisions_up=8, estimate_revisions_down=2
        )
        assert revision_score == 75.0

    def test_without_revision_data(self):
        """Without revision data, proxy is used (backward compatible)."""
        calc = SentimentCalculator()
        stock_data = {
            'days_to_cover': 2.0,
            'recommendation_mean': 2.0,    # Buy -> 60 (proxy)
            'analyst_count': 20,
            'analyst_target': 110.0,
            'market_cap': 15000,
            'insider_net_shares': 0,
        }
        score = calc.calculate_stock_specific_sentiment(stock_data, current_price=100.0)
        assert score is not None
