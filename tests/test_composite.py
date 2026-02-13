"""
Unit tests for composite score calculator.

Tests the core composite scoring logic including:
- Recommendation threshold boundaries
- Weight validation
- Composite score calculation
- Signal agreement and conviction levels
- Percentile ranking edge cases
- Universe-wide score calculation

Framework Reference: Section 1.3, Section 7

Author: Stock Analysis Framework v2.0
Date: 2026-02-12
"""

import pytest
from src.models.composite import (
    Recommendation,
    CompositeScore,
    CompositeScoreCalculator
)


# ============================================================================
# Recommendation Tests
# ============================================================================

class TestRecommendation:
    """Test recommendation threshold boundaries.

    Framework Section 7.2:
    - ≥85th: STRONG BUY
    - 70-84th: BUY
    - 30-69th: HOLD
    - 16-29th: SELL
    - ≤15th: STRONG SELL
    """

    def test_strong_buy_at_85(self):
        """Test STRONG BUY at exactly 85th percentile."""
        assert Recommendation.from_percentile(85.0) == Recommendation.STRONG_BUY

    def test_strong_buy_above_85(self):
        """Test STRONG BUY above 85th percentile."""
        assert Recommendation.from_percentile(90.0) == Recommendation.STRONG_BUY
        assert Recommendation.from_percentile(95.0) == Recommendation.STRONG_BUY
        assert Recommendation.from_percentile(100.0) == Recommendation.STRONG_BUY

    def test_buy_at_70(self):
        """Test BUY at exactly 70th percentile."""
        assert Recommendation.from_percentile(70.0) == Recommendation.BUY

    def test_buy_just_below_85(self):
        """Test BUY just below 85th percentile boundary."""
        assert Recommendation.from_percentile(84.9) == Recommendation.BUY
        assert Recommendation.from_percentile(84.0) == Recommendation.BUY

    def test_buy_between_70_and_85(self):
        """Test BUY in the 70-84 range."""
        assert Recommendation.from_percentile(75.0) == Recommendation.BUY
        assert Recommendation.from_percentile(80.0) == Recommendation.BUY

    def test_hold_at_30(self):
        """Test HOLD at exactly 30th percentile."""
        assert Recommendation.from_percentile(30.0) == Recommendation.HOLD

    def test_hold_at_69(self):
        """Test HOLD at 69th percentile (just below BUY)."""
        assert Recommendation.from_percentile(69.0) == Recommendation.HOLD
        assert Recommendation.from_percentile(69.9) == Recommendation.HOLD

    def test_hold_in_middle(self):
        """Test HOLD in the middle range (30-69)."""
        assert Recommendation.from_percentile(50.0) == Recommendation.HOLD
        assert Recommendation.from_percentile(40.0) == Recommendation.HOLD
        assert Recommendation.from_percentile(60.0) == Recommendation.HOLD

    def test_sell_at_16(self):
        """Test SELL at exactly 16th percentile."""
        assert Recommendation.from_percentile(16.0) == Recommendation.SELL

    def test_sell_just_below_30(self):
        """Test SELL just below 30th percentile boundary."""
        assert Recommendation.from_percentile(29.9) == Recommendation.SELL
        assert Recommendation.from_percentile(29.0) == Recommendation.SELL

    def test_sell_between_16_and_30(self):
        """Test SELL in the 16-29 range."""
        assert Recommendation.from_percentile(20.0) == Recommendation.SELL
        assert Recommendation.from_percentile(25.0) == Recommendation.SELL

    def test_strong_sell_at_15(self):
        """Test STRONG SELL at exactly 15th percentile."""
        assert Recommendation.from_percentile(15.0) == Recommendation.STRONG_SELL

    def test_strong_sell_below_15(self):
        """Test STRONG SELL below 15th percentile."""
        assert Recommendation.from_percentile(10.0) == Recommendation.STRONG_SELL
        assert Recommendation.from_percentile(5.0) == Recommendation.STRONG_SELL
        assert Recommendation.from_percentile(0.0) == Recommendation.STRONG_SELL

    def test_edge_case_15_point_9(self):
        """Test boundary edge case at 15.9 (should be STRONG SELL, <16)."""
        assert Recommendation.from_percentile(15.9) == Recommendation.STRONG_SELL


# ============================================================================
# CompositeScore Tests
# ============================================================================

class TestCompositeScore:
    """Test CompositeScore dataclass functionality."""

    def test_creation(self):
        """Test creating a CompositeScore object."""
        score = CompositeScore(
            ticker="AAPL",
            fundamental_score=75.0,
            technical_score=80.0,
            sentiment_score=65.0,
            composite_score=74.0,
            composite_percentile=85.5,
            recommendation=Recommendation.STRONG_BUY
        )

        assert score.ticker == "AAPL"
        assert score.fundamental_score == 75.0
        assert score.technical_score == 80.0
        assert score.sentiment_score == 65.0
        assert score.composite_score == 74.0
        assert score.composite_percentile == 85.5
        assert score.recommendation == Recommendation.STRONG_BUY

    def test_str_representation(self):
        """Test string representation of CompositeScore."""
        score = CompositeScore(
            ticker="MSFT",
            fundamental_score=70.0,
            technical_score=75.0,
            sentiment_score=68.0,
            composite_score=71.5,
            composite_percentile=72.3,
            recommendation=Recommendation.BUY
        )

        result = str(score)
        assert "MSFT" in result
        assert "BUY" in result
        assert "71.5" in result
        assert "72.3" in result

    def test_optional_fields(self):
        """Test optional signal_agreement and conviction_level fields."""
        score = CompositeScore(
            ticker="GOOGL",
            fundamental_score=80.0,
            technical_score=85.0,
            sentiment_score=70.0,
            composite_score=79.5,
            composite_percentile=88.0,
            recommendation=Recommendation.STRONG_BUY,
            signal_agreement=85.5,
            conviction_level="High"
        )

        assert score.signal_agreement == 85.5
        assert score.conviction_level == "High"


# ============================================================================
# CompositeScoreCalculator Initialization Tests
# ============================================================================

class TestCompositeScoreCalculatorInit:
    """Test CompositeScoreCalculator initialization and weight validation."""

    def test_default_weights(self):
        """Test initialization with default weights (45/35/20)."""
        calc = CompositeScoreCalculator()

        assert calc.fundamental_weight == 0.45
        assert calc.technical_weight == 0.35
        assert calc.sentiment_weight == 0.20

    def test_custom_weights_valid(self):
        """Test initialization with valid custom weights."""
        calc = CompositeScoreCalculator(
            fundamental_weight=0.50,
            technical_weight=0.30,
            sentiment_weight=0.20
        )

        assert calc.fundamental_weight == 0.50
        assert calc.technical_weight == 0.30
        assert calc.sentiment_weight == 0.20

    def test_custom_weights_equal(self):
        """Test initialization with equal weights (33.33% each)."""
        calc = CompositeScoreCalculator(
            fundamental_weight=0.3333,
            technical_weight=0.3333,
            sentiment_weight=0.3334
        )

        # Should succeed (within floating point tolerance)
        assert calc.fundamental_weight == 0.3333

    def test_weights_sum_to_one_exactly(self):
        """Test that weights summing to exactly 1.0 is valid."""
        calc = CompositeScoreCalculator(
            fundamental_weight=0.4,
            technical_weight=0.4,
            sentiment_weight=0.2
        )

        total = calc.fundamental_weight + calc.technical_weight + calc.sentiment_weight
        assert abs(total - 1.0) < 0.001

    def test_weights_too_high(self):
        """Test that weights summing above 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            CompositeScoreCalculator(
                fundamental_weight=0.50,
                technical_weight=0.40,
                sentiment_weight=0.30  # Sum = 1.20
            )

    def test_weights_too_low(self):
        """Test that weights summing below 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            CompositeScoreCalculator(
                fundamental_weight=0.30,
                technical_weight=0.30,
                sentiment_weight=0.20  # Sum = 0.80
            )

    def test_weights_at_upper_tolerance(self):
        """Test weights at upper floating point tolerance (1.001)."""
        # Should succeed - within tolerance
        calc = CompositeScoreCalculator(
            fundamental_weight=0.4504,
            technical_weight=0.3503,
            sentiment_weight=0.2003  # Sum ≈ 1.001
        )
        assert calc.fundamental_weight == 0.4504

    def test_weights_at_lower_tolerance(self):
        """Test weights at lower floating point tolerance (0.999)."""
        # Should succeed - within tolerance
        calc = CompositeScoreCalculator(
            fundamental_weight=0.4496,
            technical_weight=0.3497,
            sentiment_weight=0.1997  # Sum ≈ 0.999
        )
        assert calc.fundamental_weight == 0.4496

    def test_weights_beyond_tolerance(self):
        """Test weights beyond tolerance limits."""
        with pytest.raises(ValueError):
            CompositeScoreCalculator(
                fundamental_weight=0.46,
                technical_weight=0.36,
                sentiment_weight=0.20  # Sum = 1.02 (beyond tolerance)
            )


# ============================================================================
# Composite Score Calculation Tests
# ============================================================================

class TestCalculateCompositeScore:
    """Test composite score weighted average calculation."""

    def test_composite_with_default_weights(self):
        """Test composite calculation with default weights (45/35/20).

        Example: F=80, T=70, S=60
        Expected: (80 * 0.45) + (70 * 0.35) + (60 * 0.20) = 36 + 24.5 + 12 = 72.5
        """
        calc = CompositeScoreCalculator()
        result = calc.calculate_composite_score(
            fundamental_score=80.0,
            technical_score=70.0,
            sentiment_score=60.0
        )

        expected = (80.0 * 0.45) + (70.0 * 0.35) + (60.0 * 0.20)
        assert abs(result - expected) < 0.01
        assert abs(result - 72.5) < 0.01

    def test_composite_all_same_score(self):
        """Test when all pillar scores are identical."""
        calc = CompositeScoreCalculator()
        result = calc.calculate_composite_score(
            fundamental_score=75.0,
            technical_score=75.0,
            sentiment_score=75.0
        )

        # If all inputs are same, output should be same regardless of weights
        assert abs(result - 75.0) < 0.01

    def test_composite_all_zeros(self):
        """Test with all zero scores."""
        calc = CompositeScoreCalculator()
        result = calc.calculate_composite_score(
            fundamental_score=0.0,
            technical_score=0.0,
            sentiment_score=0.0
        )

        assert result == 0.0

    def test_composite_all_hundreds(self):
        """Test with all maximum scores."""
        calc = CompositeScoreCalculator()
        result = calc.calculate_composite_score(
            fundamental_score=100.0,
            technical_score=100.0,
            sentiment_score=100.0
        )

        assert abs(result - 100.0) < 0.01

    def test_composite_with_custom_weights(self):
        """Test composite with custom weights.

        Weights: 50/30/20
        Scores: F=90, T=60, S=40
        Expected: (90 * 0.5) + (60 * 0.3) + (40 * 0.2) = 45 + 18 + 8 = 71
        """
        calc = CompositeScoreCalculator(
            fundamental_weight=0.50,
            technical_weight=0.30,
            sentiment_weight=0.20
        )
        result = calc.calculate_composite_score(
            fundamental_score=90.0,
            technical_score=60.0,
            sentiment_score=40.0
        )

        expected = (90.0 * 0.5) + (60.0 * 0.3) + (40.0 * 0.2)
        assert abs(result - expected) < 0.01
        assert abs(result - 71.0) < 0.01

    def test_composite_fundamental_dominates(self):
        """Test when fundamental weight dominates (high weight)."""
        calc = CompositeScoreCalculator(
            fundamental_weight=0.80,
            technical_weight=0.10,
            sentiment_weight=0.10
        )
        result = calc.calculate_composite_score(
            fundamental_score=100.0,
            technical_score=0.0,
            sentiment_score=0.0
        )

        # Should be close to fundamental score since it's weighted 80%
        assert abs(result - 80.0) < 0.01

    def test_composite_realistic_scenario(self):
        """Test realistic scenario with varied scores.

        Real-world example:
        - Fundamental: 64.8 (decent value)
        - Technical: 42.5 (weak momentum)
        - Sentiment: 52.0 (neutral)

        With 45/35/20 weights:
        = (64.8 * 0.45) + (42.5 * 0.35) + (52.0 * 0.20)
        = 29.16 + 14.875 + 10.4
        = 54.435
        """
        calc = CompositeScoreCalculator()
        result = calc.calculate_composite_score(
            fundamental_score=64.8,
            technical_score=42.5,
            sentiment_score=52.0
        )

        expected = (64.8 * 0.45) + (42.5 * 0.35) + (52.0 * 0.20)
        assert abs(result - expected) < 0.01


# ============================================================================
# Signal Agreement Tests
# ============================================================================

class TestCalculateSignalAgreement:
    """Test signal agreement and conviction level calculation.

    Framework Section 7.3:
    - High conviction: >75% or <25% agreement (strong directional agreement)
    - Medium conviction: 50-75% or 25-50%
    - Low conviction: around 50% (no clear direction)
    """

    def test_all_bullish_signals(self):
        """Test all bullish signals (>50) - should give High conviction."""
        calc = CompositeScoreCalculator()

        fundamental = {'value': 75, 'quality': 80, 'growth': 70}
        technical = {'momentum': 85, 'trend': 90, 'volume': 80}
        sentiment = {'market': 65, 'stock': 70}

        agreement, conviction = calc.calculate_signal_agreement(
            fundamental, technical, sentiment
        )

        # All signals bullish: 100% agreement
        assert agreement == 100.0
        assert conviction == "High"

    def test_all_bearish_signals(self):
        """Test all bearish signals (<50) - should give High conviction."""
        calc = CompositeScoreCalculator()

        fundamental = {'value': 25, 'quality': 20, 'growth': 30}
        technical = {'momentum': 15, 'trend': 10, 'volume': 20}
        sentiment = {'market': 35, 'stock': 30}

        agreement, conviction = calc.calculate_signal_agreement(
            fundamental, technical, sentiment
        )

        # All signals bearish: 0% agreement (strong bearish)
        assert agreement == 0.0
        assert conviction == "High"

    def test_mixed_signals_medium_conviction(self):
        """Test mixed signals - should give Medium conviction."""
        calc = CompositeScoreCalculator()

        # Fundamental: 2/3 bullish (66.67%)
        fundamental = {'value': 75, 'quality': 80, 'growth': 40}
        # Technical: 2/3 bullish (66.67%)
        technical = {'momentum': 85, 'trend': 45, 'volume': 70}
        # Sentiment: 1/2 bullish (50%)
        sentiment = {'market': 65, 'stock': 45}

        agreement, conviction = calc.calculate_signal_agreement(
            fundamental, technical, sentiment
        )

        # Average: (66.67 + 66.67 + 50) / 3 = 61.11%
        assert 60.0 < agreement < 62.0
        assert conviction == "Medium"

    def test_exactly_50_percent_neutral(self):
        """Test exactly 50% agreement - edge case."""
        calc = CompositeScoreCalculator()

        # Each pillar: exactly 50% bullish
        fundamental = {'value': 60, 'quality': 40}
        technical = {'momentum': 70, 'trend': 30}
        sentiment = {'market': 55, 'stock': 45}

        agreement, conviction = calc.calculate_signal_agreement(
            fundamental, technical, sentiment
        )

        assert agreement == 50.0
        assert conviction == "Medium"

    def test_high_conviction_at_76_percent(self):
        """Test High conviction threshold at >75%."""
        calc = CompositeScoreCalculator()

        # Fundamental: 3/3 = 100%
        fundamental = {'value': 80, 'quality': 85, 'growth': 70}
        # Technical: 2/3 = 66.67%
        technical = {'momentum': 75, 'trend': 45, 'volume': 65}
        # Sentiment: 2/2 = 100%
        sentiment = {'market': 60, 'stock': 70}

        agreement, conviction = calc.calculate_signal_agreement(
            fundamental, technical, sentiment
        )

        # Average: (100 + 66.67 + 100) / 3 = 88.89%
        assert agreement > 75.0
        assert conviction == "High"

    def test_high_conviction_at_24_percent(self):
        """Test High conviction threshold at <25% (bearish)."""
        calc = CompositeScoreCalculator()

        # Fundamental: 0/3 = 0%
        fundamental = {'value': 20, 'quality': 15, 'growth': 30}
        # Technical: 1/3 = 33.33%
        technical = {'momentum': 55, 'trend': 25, 'volume': 15}
        # Sentiment: 0/2 = 0%
        sentiment = {'market': 40, 'stock': 30}

        agreement, conviction = calc.calculate_signal_agreement(
            fundamental, technical, sentiment
        )

        # Average: (0 + 33.33 + 0) / 3 = 11.11%
        assert agreement < 25.0
        assert conviction == "High"

    def test_empty_subsignals(self):
        """Test handling of empty subsignal dictionaries."""
        calc = CompositeScoreCalculator()

        agreement, conviction = calc.calculate_signal_agreement(
            {}, {}, {}
        )

        # Should handle gracefully
        assert agreement == 0.0
        assert conviction == "High"  # 0% is <25%, so High conviction bearish

    def test_single_pillar_only(self):
        """Test with only one pillar having signals."""
        calc = CompositeScoreCalculator()

        fundamental = {'value': 75, 'quality': 80, 'growth': 70}

        agreement, conviction = calc.calculate_signal_agreement(
            fundamental, {}, {}
        )

        # Average: (100 + 0 + 0) / 3 = 33.33%
        assert 33.0 < agreement < 34.0
        assert conviction == "Medium"


# ============================================================================
# Percentile Rank Tests
# ============================================================================

class TestCalculatePercentileRank:
    """Test percentile ranking edge cases."""

    def test_percentile_in_middle(self):
        """Test percentile calculation for middle value.

        Universe: [10, 20, 30, 40, 50]
        Value: 30
        Expected: 40% (30 beats 2 out of 5 values = 2/5 = 40%)
        """
        calc = CompositeScoreCalculator()
        universe = [10, 20, 30, 40, 50]

        result = calc.calculate_percentile_rank(30, universe)

        # 30 is better than 10 and 20 (2 values)
        # Percentile = 2/5 * 100 = 40%
        assert result == 40.0

    def test_percentile_at_minimum(self):
        """Test percentile for lowest value in universe."""
        calc = CompositeScoreCalculator()
        universe = [10, 20, 30, 40, 50]

        result = calc.calculate_percentile_rank(10, universe)

        # 10 beats 0 values
        assert result == 0.0

    def test_percentile_at_maximum(self):
        """Test percentile for highest value in universe."""
        calc = CompositeScoreCalculator()
        universe = [10, 20, 30, 40, 50]

        result = calc.calculate_percentile_rank(50, universe)

        # 50 beats 4 values (10, 20, 30, 40)
        # Percentile = 4/5 * 100 = 80%
        assert result == 80.0

    def test_percentile_value_not_in_universe(self):
        """Test percentile for value not in universe."""
        calc = CompositeScoreCalculator()
        universe = [10, 20, 30, 40, 50]

        result = calc.calculate_percentile_rank(35, universe)

        # 35 beats 10, 20, 30 (3 values)
        # Percentile = 3/5 * 100 = 60%
        assert result == 60.0

    def test_percentile_empty_universe(self):
        """Test percentile with empty universe."""
        calc = CompositeScoreCalculator()

        result = calc.calculate_percentile_rank(50, [])

        # Should return 50.0 as default
        assert result == 50.0

    def test_percentile_single_value_universe(self):
        """Test percentile with single value in universe."""
        calc = CompositeScoreCalculator()
        universe = [50]

        result = calc.calculate_percentile_rank(50, universe)

        # 50 beats 0 values (itself doesn't count)
        assert result == 0.0

    def test_percentile_all_same_values(self):
        """Test percentile when all values in universe are identical."""
        calc = CompositeScoreCalculator()
        universe = [50, 50, 50, 50, 50]

        result = calc.calculate_percentile_rank(50, universe)

        # 50 beats 0 values (all are equal)
        assert result == 0.0

    def test_percentile_with_duplicates(self):
        """Test percentile with duplicate values in universe."""
        calc = CompositeScoreCalculator()
        universe = [10, 20, 20, 30, 30, 30, 40]

        result = calc.calculate_percentile_rank(30, universe)

        # 30 beats 10, 20, 20 (3 values)
        # Percentile = 3/7 * 100 = 42.86%
        expected = (3 / 7) * 100
        assert abs(result - expected) < 0.01

    def test_percentile_large_universe(self):
        """Test percentile with larger universe."""
        calc = CompositeScoreCalculator()
        universe = list(range(0, 101))  # 0 to 100

        result = calc.calculate_percentile_rank(75, universe)

        # 75 beats 0-74 (75 values)
        # Percentile = 75/101 * 100 = 74.26%
        expected = (75 / 101) * 100
        assert abs(result - expected) < 0.01


# ============================================================================
# Universe-Wide Score Calculation Tests
# ============================================================================

class TestCalculateScoresForUniverse:
    """Test full universe score calculation and ranking."""

    def test_calculate_three_stocks(self):
        """Test calculating scores for small universe of 3 stocks."""
        calc = CompositeScoreCalculator()

        stock_scores = {
            'AAPL': {'fundamental': 80, 'technical': 85, 'sentiment': 70},
            'MSFT': {'fundamental': 70, 'technical': 75, 'sentiment': 68},
            'GOOGL': {'fundamental': 60, 'technical': 65, 'sentiment': 55}
        }

        results = calc.calculate_scores_for_universe(stock_scores)

        # Should return 3 results
        assert len(results) == 3

        # Should be sorted by percentile (descending)
        assert results[0].composite_percentile >= results[1].composite_percentile
        assert results[1].composite_percentile >= results[2].composite_percentile

        # All results should have required fields
        for result in results:
            assert result.ticker is not None
            assert result.composite_score >= 0
            assert 0 <= result.composite_percentile <= 100
            assert result.recommendation is not None

    def test_sorting_by_percentile(self):
        """Test that results are sorted by composite_percentile descending."""
        calc = CompositeScoreCalculator()

        stock_scores = {
            'LOW': {'fundamental': 30, 'technical': 35, 'sentiment': 32},
            'HIGH': {'fundamental': 90, 'technical': 85, 'sentiment': 88},
            'MED': {'fundamental': 60, 'technical': 65, 'sentiment': 58}
        }

        results = calc.calculate_scores_for_universe(stock_scores)

        # Should be in order: HIGH, MED, LOW
        assert results[0].ticker == 'HIGH'
        assert results[1].ticker == 'MED'
        assert results[2].ticker == 'LOW'

        # Verify descending order
        assert results[0].composite_percentile > results[1].composite_percentile
        assert results[1].composite_percentile > results[2].composite_percentile

    def test_recommendation_assignment(self):
        """Test that recommendations are assigned based on percentiles."""
        calc = CompositeScoreCalculator()

        # Create 10 stocks with varied scores to test recommendation buckets
        stock_scores = {}
        for i in range(10):
            ticker = f"STOCK{i}"
            # Gradually increasing scores
            score = 10 + (i * 10)
            stock_scores[ticker] = {
                'fundamental': score,
                'technical': score,
                'sentiment': score
            }

        results = calc.calculate_scores_for_universe(stock_scores)

        # Verify recommendations exist
        for result in results:
            assert result.recommendation in [
                Recommendation.STRONG_BUY,
                Recommendation.BUY,
                Recommendation.HOLD,
                Recommendation.SELL,
                Recommendation.STRONG_SELL
            ]

    def test_single_stock_universe(self):
        """Test edge case with single stock."""
        calc = CompositeScoreCalculator()

        stock_scores = {
            'ONLY': {'fundamental': 75, 'technical': 80, 'sentiment': 70}
        }

        results = calc.calculate_scores_for_universe(stock_scores)

        assert len(results) == 1
        assert results[0].ticker == 'ONLY'
        # Single stock should be at 0th percentile (beats 0 others)
        assert results[0].composite_percentile == 0.0

    def test_identical_scores(self):
        """Test when all stocks have identical scores."""
        calc = CompositeScoreCalculator()

        stock_scores = {
            'STOCK1': {'fundamental': 50, 'technical': 50, 'sentiment': 50},
            'STOCK2': {'fundamental': 50, 'technical': 50, 'sentiment': 50},
            'STOCK3': {'fundamental': 50, 'technical': 50, 'sentiment': 50}
        }

        results = calc.calculate_scores_for_universe(stock_scores)

        assert len(results) == 3
        # All should have same composite score
        assert results[0].composite_score == results[1].composite_score
        assert results[1].composite_score == results[2].composite_score
        # All should have 0 percentile (none beat any others)
        assert all(r.composite_percentile == 0.0 for r in results)

    def test_composite_score_matches_calculation(self):
        """Test that stored composite scores match manual calculation."""
        calc = CompositeScoreCalculator()

        stock_scores = {
            'TEST': {'fundamental': 80, 'technical': 70, 'sentiment': 60}
        }

        results = calc.calculate_scores_for_universe(stock_scores)

        # Manual calculation: (80 * 0.45) + (70 * 0.35) + (60 * 0.20)
        expected_composite = 36 + 24.5 + 12  # = 72.5

        assert abs(results[0].composite_score - expected_composite) < 0.01


# ============================================================================
# Report Generation Tests
# ============================================================================

class TestGenerateReport:
    """Test report generation functionality."""

    def test_report_contains_headers(self):
        """Test that report contains expected headers."""
        calc = CompositeScoreCalculator()

        stock_scores = {
            'AAPL': {'fundamental': 80, 'technical': 85, 'sentiment': 70},
            'MSFT': {'fundamental': 70, 'technical': 75, 'sentiment': 68}
        }

        results = calc.calculate_scores_for_universe(stock_scores)
        report = calc.generate_report(results)

        assert "COMPOSITE SCORE REPORT" in report
        assert "Universe Size: 2 stocks" in report
        assert "Fundamental 45%" in report
        assert "Technical 35%" in report
        assert "Sentiment 20%" in report

    def test_report_contains_stock_data(self):
        """Test that report contains stock ticker and scores."""
        calc = CompositeScoreCalculator()

        stock_scores = {
            'AAPL': {'fundamental': 80, 'technical': 85, 'sentiment': 70}
        }

        results = calc.calculate_scores_for_universe(stock_scores)
        report = calc.generate_report(results)

        assert "AAPL" in report
        assert "80" in report  # Fundamental score
        assert "85" in report  # Technical score
        assert "70" in report  # Sentiment score

    def test_report_recommendation_distribution(self):
        """Test that report includes recommendation distribution."""
        calc = CompositeScoreCalculator()

        stock_scores = {
            'HIGH': {'fundamental': 90, 'technical': 85, 'sentiment': 88},
            'LOW': {'fundamental': 30, 'technical': 35, 'sentiment': 32}
        }

        results = calc.calculate_scores_for_universe(stock_scores)
        report = calc.generate_report(results)

        assert "RECOMMENDATION DISTRIBUTION:" in report
        assert "STRONG BUY:" in report
        assert "BUY:" in report
        assert "HOLD:" in report
        assert "SELL:" in report
        assert "STRONG SELL:" in report

    def test_report_with_custom_weights(self):
        """Test report shows custom weights correctly."""
        calc = CompositeScoreCalculator(
            fundamental_weight=0.50,
            technical_weight=0.30,
            sentiment_weight=0.20
        )

        stock_scores = {
            'TEST': {'fundamental': 75, 'technical': 80, 'sentiment': 70}
        }

        results = calc.calculate_scores_for_universe(stock_scores)
        report = calc.generate_report(results)

        assert "Fundamental 50%" in report
        assert "Technical 30%" in report
        assert "Sentiment 20%" in report


# ============================================================================
# Integration Tests
# ============================================================================

class TestCompositeIntegration:
    """Integration tests for full workflow."""

    def test_end_to_end_workflow(self):
        """Test complete workflow from scores to recommendations."""
        calc = CompositeScoreCalculator()

        # Simulate 5 stocks with varied characteristics
        stock_scores = {
            'WINNER': {'fundamental': 90, 'technical': 88, 'sentiment': 85},
            'STRONG': {'fundamental': 78, 'technical': 82, 'sentiment': 75},
            'AVERAGE': {'fundamental': 55, 'technical': 50, 'sentiment': 52},
            'WEAK': {'fundamental': 35, 'technical': 40, 'sentiment': 38},
            'LOSER': {'fundamental': 15, 'technical': 20, 'sentiment': 18}
        }

        results = calc.calculate_scores_for_universe(stock_scores)

        # Verify 5 results
        assert len(results) == 5

        # Verify ordering (WINNER should be first, LOSER last)
        assert results[0].ticker == 'WINNER'
        assert results[-1].ticker == 'LOSER'

        # Verify top stock gets STRONG BUY or BUY
        assert results[0].recommendation in [Recommendation.STRONG_BUY, Recommendation.BUY]

        # Verify bottom stock gets STRONG SELL or SELL
        assert results[-1].recommendation in [Recommendation.STRONG_SELL, Recommendation.SELL]

        # Verify percentiles are in descending order
        for i in range(len(results) - 1):
            assert results[i].composite_percentile >= results[i + 1].composite_percentile

    def test_realistic_15_stock_universe(self):
        """Test with realistic 15-stock universe (matches project data)."""
        calc = CompositeScoreCalculator()

        # Simulate 15 stocks with realistic score distribution
        stock_scores = {}
        tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA',
                   'JPM', 'V', 'JNJ', 'WMT', 'PG', 'UNH', 'HD', 'DIS']

        import random
        random.seed(42)  # For reproducibility

        for ticker in tickers:
            stock_scores[ticker] = {
                'fundamental': random.uniform(30, 80),
                'technical': random.uniform(20, 90),
                'sentiment': random.uniform(45, 60)
            }

        results = calc.calculate_scores_for_universe(stock_scores)

        # Verify all 15 stocks processed
        assert len(results) == 15

        # Verify all have valid percentiles
        assert all(0 <= r.composite_percentile <= 100 for r in results)

        # Verify recommendations exist
        assert all(r.recommendation is not None for r in results)

        # Verify sorted by percentile
        percentiles = [r.composite_percentile for r in results]
        assert percentiles == sorted(percentiles, reverse=True)

        # Generate report (should not crash)
        report = calc.generate_report(results)
        assert "Universe Size: 15 stocks" in report
