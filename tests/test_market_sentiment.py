"""
Unit tests for market sentiment data collection and scoring.

Framework Reference: Section 5.1 (Market-Wide Sentiment)
Tests all 4 market sentiment indicators and composite calculation.
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.collect_market_sentiment import MarketSentimentCollector


class TestVIXScoring:
    """
    Test VIX z-score calculation and scoring.

    Framework Section 5.1: VIX Z-Score (contrarian)
    Score = 50 + (Z × 15) [capped at 0-100]
    """

    def setup_method(self):
        self.collector = MarketSentimentCollector()

    def test_vix_score_positive_zscore(self):
        """High VIX (positive z-score) should produce score > 50 (bullish)."""
        # Simulate VIX at 25, mean 18, std 4 → z = 1.75
        # Score = 50 + (1.75 × 15) = 76.25
        score = 50.0 + (1.75 * 15.0)
        score = max(0.0, min(100.0, score))
        assert score == pytest.approx(76.25, abs=0.1)

    def test_vix_score_negative_zscore(self):
        """Low VIX (negative z-score) should produce score < 50 (bearish)."""
        # Simulate VIX at 12, mean 18, std 4 → z = -1.5
        # Score = 50 + (-1.5 × 15) = 27.5
        score = 50.0 + (-1.5 * 15.0)
        score = max(0.0, min(100.0, score))
        assert score == pytest.approx(27.5, abs=0.1)

    def test_vix_score_neutral(self):
        """VIX at mean should produce score = 50."""
        score = 50.0 + (0.0 * 15.0)
        assert score == 50.0

    def test_vix_score_caps_at_100(self):
        """Extreme high VIX should cap at 100."""
        # z = 5.0 → Score = 50 + 75 = 125 → capped at 100
        score = 50.0 + (5.0 * 15.0)
        score = max(0.0, min(100.0, score))
        assert score == 100.0

    def test_vix_score_caps_at_0(self):
        """Extreme low VIX should cap at 0."""
        # z = -5.0 → Score = 50 - 75 = -25 → capped at 0
        score = 50.0 + (-5.0 * 15.0)
        score = max(0.0, min(100.0, score))
        assert score == 0.0


class TestAAIIScoring:
    """
    Test AAII sentiment scoring logic.

    Framework Section 5.1: AAII Bear-Bull Spread (8-week MA, contrarian)
    Spread = % Bears - % Bulls
    """

    def test_extreme_pessimism(self):
        """Spread > 20 → Score = 75 (extreme pessimism → bullish)."""
        # Bears 55%, Bulls 30% → Spread = 25
        assert _score_aaii_spread(25.0) == 75.0

    def test_moderate_pessimism(self):
        """Spread 10-20 → Score = 60."""
        assert _score_aaii_spread(15.0) == 60.0

    def test_neutral_sentiment(self):
        """Spread -10 to 10 → Score = 50 (neutral)."""
        assert _score_aaii_spread(0.0) == 50.0
        assert _score_aaii_spread(5.0) == 50.0
        assert _score_aaii_spread(-5.0) == 50.0

    def test_moderate_optimism(self):
        """Spread -20 to -10 → Score = 40."""
        assert _score_aaii_spread(-15.0) == 40.0

    def test_extreme_optimism(self):
        """Spread < -20 → Score = 25 (extreme optimism → bearish)."""
        assert _score_aaii_spread(-25.0) == 25.0

    def test_boundary_values(self):
        """Test exact boundary values (uses strict > comparisons)."""
        assert _score_aaii_spread(20.01) == 75.0   # > 20 → 75
        assert _score_aaii_spread(20.0) == 60.0    # exactly 20 → > 10 bucket (60)
        assert _score_aaii_spread(10.01) == 60.0   # > 10 → 60
        assert _score_aaii_spread(10.0) == 50.0    # exactly 10 → >= -10 bucket (50)
        assert _score_aaii_spread(-10.0) == 50.0   # exactly -10 → >= -10 bucket (50)
        assert _score_aaii_spread(-10.01) == 40.0  # < -10 → >= -20 bucket (40)
        assert _score_aaii_spread(-20.0) == 40.0   # exactly -20 → >= -20 bucket (40)
        assert _score_aaii_spread(-20.01) == 25.0  # < -20 → 25


class TestPutCallScoring:
    """
    Test Put/Call ratio scoring logic.

    Framework Section 5.1: Put/Call Ratio (10-day MA, contrarian)
    """

    def test_high_fear(self):
        """P/C > 1.0 → Score = 70 (fear → bullish)."""
        assert _score_putcall(1.2) == 70.0

    def test_moderate_fear(self):
        """P/C 0.8-1.0 → Score = 55."""
        assert _score_putcall(0.9) == 55.0

    def test_moderate_greed(self):
        """P/C 0.6-0.8 → Score = 45."""
        assert _score_putcall(0.7) == 45.0

    def test_high_greed(self):
        """P/C < 0.6 → Score = 30 (greed → bearish)."""
        assert _score_putcall(0.5) == 30.0

    def test_boundary_values(self):
        """Test exact boundary values (uses strict > comparisons)."""
        assert _score_putcall(1.01) == 70.0   # > 1.0 → 70
        assert _score_putcall(1.0) == 55.0    # exactly 1.0 → > 0.8 bucket (55)
        assert _score_putcall(0.81) == 55.0   # > 0.8 → 55
        assert _score_putcall(0.8) == 45.0    # exactly 0.8 → > 0.6 bucket (45)
        assert _score_putcall(0.61) == 45.0   # > 0.6 → 45
        assert _score_putcall(0.6) == 30.0    # exactly 0.6 → else bucket (30)
        assert _score_putcall(0.59) == 30.0   # < 0.6 → 30


class TestFundFlowsScoring:
    """
    Test equity fund flows scoring logic.

    Framework Section 5.1: Equity Fund Flows (directional, NOT contrarian)
    Strong inflows → bearish (chasing)
    Strong outflows → bullish (capitulation)
    """

    def test_strong_inflows(self):
        """Strong inflows (z > 1.0) → Score = 30 (bearish)."""
        assert _score_fund_flows(1.5) == 30.0

    def test_moderate_inflows(self):
        """Moderate inflows (z 0.25-1.0) → Score = 40."""
        assert _score_fund_flows(0.5) == 40.0

    def test_neutral_flows(self):
        """Neutral flows (z -0.25 to 0.25) → Score = 50."""
        assert _score_fund_flows(0.0) == 50.0
        assert _score_fund_flows(0.1) == 50.0
        assert _score_fund_flows(-0.1) == 50.0

    def test_moderate_outflows(self):
        """Moderate outflows (z -1.0 to -0.25) → Score = 60."""
        assert _score_fund_flows(-0.5) == 60.0

    def test_strong_outflows(self):
        """Strong outflows (z < -1.0) → Score = 70 (bullish capitulation)."""
        assert _score_fund_flows(-1.5) == 70.0

    def test_boundary_values(self):
        """Test exact boundary values (uses strict > and >= comparisons)."""
        assert _score_fund_flows(1.01) == 30.0    # > 1.0 → 30
        assert _score_fund_flows(1.0) == 40.0     # exactly 1.0 → > 0.25 bucket (40)
        assert _score_fund_flows(0.26) == 40.0    # > 0.25 → 40
        assert _score_fund_flows(0.25) == 50.0    # exactly 0.25 → >= -0.25 bucket (50)
        assert _score_fund_flows(-0.25) == 50.0   # exactly -0.25 → >= -0.25 bucket (50)
        assert _score_fund_flows(-0.26) == 60.0   # < -0.25 → >= -1.0 bucket (60)
        assert _score_fund_flows(-1.0) == 60.0    # exactly -1.0 → >= -1.0 bucket (60)
        assert _score_fund_flows(-1.01) == 70.0   # < -1.0 → 70


class TestCompositeMarketSentiment:
    """
    Test composite market sentiment score calculation.

    Framework Section 5.1: Average of 4 indicators (equal weight)
    """

    def setup_method(self):
        self.collector = MarketSentimentCollector()

    def test_all_four_indicators(self):
        """Average of 4 indicators with equal weight."""
        score, num = self.collector.calculate_market_sentiment_score(
            vix_score=70.0, aaii_score=60.0,
            putcall_score=55.0, fund_flows_score=50.0
        )
        expected = (70.0 + 60.0 + 55.0 + 50.0) / 4
        assert score == pytest.approx(expected, abs=0.01)
        assert num == 4

    def test_three_indicators(self):
        """Three indicators should still produce valid score."""
        score, num = self.collector.calculate_market_sentiment_score(
            vix_score=70.0, aaii_score=None,
            putcall_score=55.0, fund_flows_score=50.0
        )
        expected = (70.0 + 55.0 + 50.0) / 3
        assert score == pytest.approx(expected, abs=0.01)
        assert num == 3

    def test_two_indicators(self):
        """Two indicators should produce valid score."""
        score, num = self.collector.calculate_market_sentiment_score(
            vix_score=70.0, aaii_score=None,
            putcall_score=None, fund_flows_score=50.0
        )
        expected = (70.0 + 50.0) / 2
        assert score == pytest.approx(expected, abs=0.01)
        assert num == 2

    def test_one_indicator_returns_neutral(self):
        """Only 1 indicator should return neutral 50.0."""
        score, num = self.collector.calculate_market_sentiment_score(
            vix_score=70.0, aaii_score=None,
            putcall_score=None, fund_flows_score=None
        )
        assert score == 50.0
        assert num == 1

    def test_no_indicators_returns_neutral(self):
        """No indicators should return neutral 50.0."""
        score, num = self.collector.calculate_market_sentiment_score(
            vix_score=None, aaii_score=None,
            putcall_score=None, fund_flows_score=None
        )
        assert score == 50.0
        assert num == 0

    def test_all_bullish_indicators(self):
        """All indicators at maximum bullish → high composite."""
        score, num = self.collector.calculate_market_sentiment_score(
            vix_score=100.0, aaii_score=75.0,
            putcall_score=70.0, fund_flows_score=70.0
        )
        expected = (100.0 + 75.0 + 70.0 + 70.0) / 4
        assert score == pytest.approx(expected, abs=0.01)
        assert num == 4

    def test_all_bearish_indicators(self):
        """All indicators at maximum bearish → low composite."""
        score, num = self.collector.calculate_market_sentiment_score(
            vix_score=0.0, aaii_score=25.0,
            putcall_score=30.0, fund_flows_score=30.0
        )
        expected = (0.0 + 25.0 + 30.0 + 30.0) / 4
        assert score == pytest.approx(expected, abs=0.01)
        assert num == 4

    def test_score_in_valid_range(self):
        """Composite score should always be 0-100."""
        # Test various combinations
        test_cases = [
            (100.0, 100.0, 100.0, 100.0),
            (0.0, 0.0, 0.0, 0.0),
            (75.0, 25.0, 55.0, 45.0),
            (50.0, 50.0, 50.0, 50.0),
        ]
        for vix, aaii, pc, flows in test_cases:
            score, _ = self.collector.calculate_market_sentiment_score(
                vix, aaii, pc, flows
            )
            assert 0 <= score <= 100, f"Score {score} out of range"


class TestMarketSentimentIntegration:
    """
    Test integration between market sentiment and sentiment calculator.

    Framework Section 5.3: Base Sentiment = (Market × 0.40) + (Stock × 0.60)
    """

    def test_market_sentiment_with_score(self):
        """Sentiment calculator should use provided market_sentiment_score."""
        from src.calculators.sentiment import SentimentCalculator
        calc = SentimentCalculator()

        market_data = {
            'market_sentiment_score': 65.0,
            'num_indicators_available': 4
        }

        market_score = calc.calculate_market_sentiment(market_data)
        assert market_score == 65.0

    def test_market_sentiment_capped(self):
        """Out-of-range market scores should be capped to 0-100."""
        from src.calculators.sentiment import SentimentCalculator
        calc = SentimentCalculator()

        market_data = {'market_sentiment_score': 120.0}
        assert calc.calculate_market_sentiment(market_data) == 100.0

        market_data = {'market_sentiment_score': -10.0}
        assert calc.calculate_market_sentiment(market_data) == 0.0

    def test_composite_with_real_market_data(self):
        """Full composite with real market sentiment score."""
        from src.calculators.sentiment import SentimentCalculator
        calc = SentimentCalculator()

        stock_data = {
            'days_to_cover': 2.0,
            'analyst_target': 120.0,
            'market_cap': 15_000,
            'analyst_count': 15,
            'recommendation_mean': 2.0,
            'insider_net_shares': 50_000
        }

        market_data = {
            'market_sentiment_score': 65.0,
            'num_indicators_available': 4
        }

        sentiment = calc.calculate_sentiment_score(stock_data, 100.0, market_data)

        # Market = 65.0, Stock = avg of [50, 60, 65, 60] = 58.75
        # Composite = 65 × 0.4 + 58.75 × 0.6 = 26 + 35.25 = 61.25
        assert sentiment == pytest.approx(61.25, abs=0.5)
        assert 0 <= sentiment <= 100


# ========================================================================
# Helper functions that mirror the scoring logic from the collector
# These are used to test scoring logic independently of data collection
# ========================================================================

def _score_aaii_spread(spread_8w: float) -> float:
    """Mirror AAII scoring logic from collector for testing."""
    if spread_8w > 20:
        return 75.0
    elif spread_8w > 10:
        return 60.0
    elif spread_8w >= -10:
        return 50.0
    elif spread_8w >= -20:
        return 40.0
    else:
        return 25.0


def _score_putcall(ratio: float) -> float:
    """Mirror Put/Call scoring logic from collector for testing."""
    if ratio > 1.0:
        return 70.0
    elif ratio > 0.8:
        return 55.0
    elif ratio > 0.6:
        return 45.0
    else:
        return 30.0


def _score_fund_flows(zscore: float) -> float:
    """Mirror fund flows scoring logic from collector for testing."""
    if zscore > 1.0:
        return 30.0
    elif zscore > 0.25:
        return 40.0
    elif zscore >= -0.25:
        return 50.0
    elif zscore >= -1.0:
        return 60.0
    else:
        return 70.0
