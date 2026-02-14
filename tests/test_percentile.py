"""
Unit tests for percentile ranking engine

Framework Reference: Section 1.2, Appendix A
Tests the core percentile ranking functionality that underlies all scoring
"""

import pytest
import numpy as np
from calculators.percentile import (
    percentile_rank,
    percentile_rank_inverted,
    rank_universe,
    average_percentile_ranks,
    validate_percentile_score,
    handle_missing_data
)


class TestPercentileRank:
    """Test percentile_rank() function for 'higher is better' metrics"""

    def test_basic_ranking(self):
        """Test basic percentile ranking"""
        universe = [10, 20, 30, 40, 50]

        # Value of 35 should be better than 60% (3 out of 5 are lower)
        assert percentile_rank(35, universe) == 60.0

        # Value of 50 should be better than 80% (4 out of 5 are lower)
        assert percentile_rank(50, universe) == 80.0

        # Value of 10 should be better than 0% (0 out of 5 are lower)
        assert percentile_rank(10, universe) == 0.0

    def test_exclude_self(self):
        """Test excluding value from its own universe"""
        universe = [10, 20, 30, 40, 50]

        # When excluding self, 30 is better than 50% (2 out of 4)
        assert percentile_rank(30, universe, exclude_self=True) == 50.0

        # When not excluding, 30 is better than 40% (2 out of 5)
        assert percentile_rank(30, universe, exclude_self=False) == 40.0

    def test_identical_values(self):
        """Test ranking when multiple values are identical"""
        universe = [10, 20, 20, 20, 30]

        # Value of 20 should be better than 20% (1 out of 5 are lower)
        assert percentile_rank(20, universe) == 20.0

        # Value of 25 should be better than 80% (4 out of 5 are lower)
        assert percentile_rank(25, universe) == 80.0

    def test_none_value(self):
        """Test handling None value"""
        universe = [10, 20, 30, 40, 50]
        assert percentile_rank(None, universe) is None

    def test_nan_value(self):
        """Test handling NaN value"""
        universe = [10, 20, 30, 40, 50]
        assert percentile_rank(np.nan, universe) is None

    def test_empty_universe(self):
        """Test handling empty universe"""
        assert percentile_rank(25, []) is None

    def test_universe_with_nones(self):
        """Test universe containing None values"""
        universe = [10, None, 20, None, 30, 40, 50]

        # Should filter out Nones and rank against [10, 20, 30, 40, 50]
        assert percentile_rank(35, universe) == 60.0

    def test_all_none_universe(self):
        """Test universe with only None values"""
        universe = [None, None, None]
        assert percentile_rank(25, universe) is None

    def test_single_value_universe(self):
        """Test universe with single value (excluding self)"""
        universe = [30]
        # After excluding self, universe is empty -> neutral rank
        assert percentile_rank(30, universe, exclude_self=True) == 50.0

    def test_real_world_roe_example(self):
        """Test real-world example: ROE percentile ranking"""
        # Sample ROE values (%) from different stocks
        roe_universe = [8.5, 12.3, 15.7, 18.2, 22.1, 25.4, 28.9, 31.2, 35.6, 42.3]

        # Stock with ROE of 30% should rank high
        rank = percentile_rank(30.0, roe_universe)
        assert 70.0 <= rank <= 80.0  # Better than most

        # Stock with ROE of 10% should rank low
        rank = percentile_rank(10.0, roe_universe)
        assert 0.0 <= rank <= 20.0  # Worse than most


class TestPercentileRankInverted:
    """Test percentile_rank_inverted() for 'lower is better' metrics"""

    def test_basic_inverted_ranking(self):
        """Test basic inverted percentile ranking"""
        universe = [10, 20, 30, 40, 50]

        # Value of 15 should rank high (only 1 is lower, 4 are higher)
        assert percentile_rank_inverted(15, universe) == 80.0

        # Value of 45 should rank low (4 are lower, 1 is higher)
        assert percentile_rank_inverted(45, universe) == 20.0

        # Value of 50 should rank lowest (4 are lower, 0 are higher)
        assert percentile_rank_inverted(50, universe) == 0.0

    def test_inverted_exclude_self(self):
        """Test inverted ranking with self exclusion"""
        universe = [10, 20, 30, 40, 50]

        # 30 with self excluded: 2 below, 2 above -> 50%
        assert percentile_rank_inverted(30, universe, exclude_self=True) == 50.0

    def test_real_world_pe_example(self):
        """Test real-world example: P/E ratio (lower is better)"""
        # Sample P/E ratios from different stocks
        pe_universe = [8.2, 12.5, 15.3, 18.7, 22.4, 25.8, 28.1, 32.6, 38.2, 45.9]

        # Stock with P/E of 10 should rank high (cheaper)
        rank = percentile_rank_inverted(10.0, pe_universe)
        assert 80.0 <= rank <= 100.0

        # Stock with P/E of 40 should rank low (expensive)
        rank = percentile_rank_inverted(40.0, pe_universe)
        assert 0.0 <= rank <= 20.0

    def test_inverted_none_handling(self):
        """Test inverted ranking with None values"""
        universe = [10, None, 20, 30, None, 40, 50]
        assert percentile_rank_inverted(None, universe) is None
        assert percentile_rank_inverted(25, universe) == 60.0  # 3 higher out of 5


class TestRankUniverse:
    """Test batch ranking of entire universe"""

    def test_batch_ranking(self):
        """Test ranking all values in universe at once"""
        values = [10, 20, 30, 40, 50]
        ranks = rank_universe(values)

        # Each value should be ranked against others (excluding self)
        # 10: better than 0/4 = 0%
        # 20: better than 1/4 = 25%
        # 30: better than 2/4 = 50%
        # 40: better than 3/4 = 75%
        # 50: better than 4/4 = 100%
        assert ranks == [0.0, 25.0, 50.0, 75.0, 100.0]

    def test_batch_ranking_inverted(self):
        """Test inverted batch ranking"""
        values = [10, 20, 30, 40, 50]
        ranks = rank_universe(values, inverted=True)

        # Inverted: lower is better
        # 10: 4/4 higher = 100%
        # 20: 3/4 higher = 75%
        # 30: 2/4 higher = 50%
        # 40: 1/4 higher = 25%
        # 50: 0/4 higher = 0%
        assert ranks == [100.0, 75.0, 50.0, 25.0, 0.0]

    def test_batch_with_nones(self):
        """Test batch ranking with None values"""
        values = [10, None, 30, None, 50]
        ranks = rank_universe(values)

        # Should preserve None positions
        assert ranks[1] is None
        assert ranks[3] is None

        # Valid values should be ranked against each other
        assert ranks[0] == 0.0   # 10: better than 0/2
        assert ranks[2] == 50.0  # 30: better than 1/2
        assert ranks[4] == 100.0 # 50: better than 2/2

    def test_empty_universe(self):
        """Test batch ranking with empty list"""
        assert rank_universe([]) == []

    def test_all_nones(self):
        """Test batch ranking with all None values"""
        values = [None, None, None]
        ranks = rank_universe(values)
        assert ranks == [None, None, None]


class TestAveragePercentileRanks:
    """Test averaging of percentile ranks"""

    def test_simple_average(self):
        """Test simple average without weights"""
        ranks = [78, 82, 71, 88, 65]
        avg = average_percentile_ranks(ranks)
        assert avg == 76.8  # (78+82+71+88+65)/5

    def test_weighted_average(self):
        """Test weighted average"""
        ranks = [75.8, 88.1, 51.8]
        weights = [0.45, 0.35, 0.20]  # Fundamental, Technical, Sentiment

        avg = average_percentile_ranks(ranks, weights)

        # Manual calculation: 75.8*0.45 + 88.1*0.35 + 51.8*0.20 = 75.31
        assert abs(avg - 75.31) < 0.1

    def test_average_with_nones(self):
        """Test average excluding None values"""
        ranks = [78, 82, None, 88, None, 65]
        avg = average_percentile_ranks(ranks)

        # Should average only valid values: (78+82+88+65)/4 = 78.25
        assert avg == 78.25

    def test_all_nones(self):
        """Test average of all None values"""
        ranks = [None, None, None]
        assert average_percentile_ranks(ranks) is None

    def test_empty_list(self):
        """Test average of empty list"""
        assert average_percentile_ranks([]) is None

    def test_weights_dont_sum_to_one(self):
        """Test that weights are automatically normalized"""
        ranks = [80, 90, 70]
        weights = [2, 1, 1]  # Sum to 4, not 1

        avg = average_percentile_ranks(ranks, weights)

        # Normalized weights: [0.5, 0.25, 0.25]
        # 80*0.5 + 90*0.25 + 70*0.25 = 80
        assert avg == 80.0


class TestValidatePercentileScore:
    """Test percentile score validation"""

    def test_valid_scores(self):
        """Test valid percentile scores"""
        assert validate_percentile_score(0.0) is True
        assert validate_percentile_score(50.0) is True
        assert validate_percentile_score(100.0) is True
        assert validate_percentile_score(75.5) is True

    def test_invalid_scores(self):
        """Test invalid percentile scores"""
        assert validate_percentile_score(-1) is False
        assert validate_percentile_score(101) is False
        assert validate_percentile_score(None) is False
        assert validate_percentile_score(np.nan) is False

    def test_boundary_values(self):
        """Test boundary values"""
        assert validate_percentile_score(0) is True
        assert validate_percentile_score(100) is True
        assert validate_percentile_score(-0.01) is False
        assert validate_percentile_score(100.01) is False


class TestHandleMissingData:
    """Test missing data handling strategies"""

    def test_skip_strategy(self):
        """Test skip strategy (default)"""
        universe = [10, 20, 30, 40, 50]
        assert handle_missing_data(None, universe, strategy="skip") is None
        assert handle_missing_data(25, universe, strategy="skip") == 25

    def test_median_strategy(self):
        """Test median imputation strategy"""
        universe = [10, 20, 30, 40, 50]
        result = handle_missing_data(None, universe, strategy="median")
        assert result == 30  # Median of universe

    def test_neutral_strategy(self):
        """Test neutral (50th percentile) strategy"""
        universe = [10, 20, 30, 40, 50]
        result = handle_missing_data(None, universe, strategy="neutral")
        assert result == 50.0

    def test_median_with_nones_in_universe(self):
        """Test median strategy with None values in universe"""
        universe = [10, None, 20, None, 30, 40, 50]
        result = handle_missing_data(None, universe, strategy="median")
        assert result == 30  # Median of valid values

    def test_unknown_strategy(self):
        """Test unknown strategy falls back to None"""
        universe = [10, 20, 30, 40, 50]
        result = handle_missing_data(None, universe, strategy="unknown")
        assert result is None


class TestFrameworkExamples:
    """Test examples from the framework specification"""

    def test_framework_example_section_1_2(self):
        """
        Test the exact example from Framework Section 1.2

        Stock ABC:
        - P/E rank: 78th percentile (cheaper than 78%)
        - P/B rank: 82nd percentile
        - EV/EBITDA rank: 71st percentile
        - ROE rank: 88th percentile
        - Revenue growth rank: 65th percentile

        Fundamental Score = Average(78, 82, 71, 88, 65) = 76.8
        """
        ranks = [78, 82, 71, 88, 65]
        fundamental_score = average_percentile_ranks(ranks)
        assert fundamental_score == 76.8

    def test_framework_composite_calculation(self):
        """
        Test composite score calculation from Framework Appendix B

        Fundamental: 75.8
        Technical: 88.1
        Sentiment: 51.8

        Base Composite = 75.8*0.45 + 88.1*0.35 + 51.8*0.20 = 75.31
        """
        fundamental = 75.8
        technical = 88.1
        sentiment = 51.8

        composite = average_percentile_ranks(
            [fundamental, technical, sentiment],
            weights=[0.45, 0.35, 0.20]
        )

        assert abs(composite - 75.31) < 0.1

    def test_percentile_interpretation(self):
        """
        Test that percentile interpretation is correct:
        - 85th percentile = better than 85% of universe
        - Works for both regular and inverted metrics
        """
        # ROE example (higher is better)
        roe_values = [5, 10, 15, 20, 25]
        roe_22 = percentile_rank(22, roe_values)
        assert roe_22 == 80.0  # Better than 4/5 = 80%

        # P/E example (lower is better)
        pe_values = [10, 15, 20, 25, 30]
        pe_12 = percentile_rank_inverted(12, pe_values)
        assert pe_12 == 80.0  # Better than 4/5 = 80% (cheaper)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
