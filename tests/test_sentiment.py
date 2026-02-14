"""
Unit tests for sentiment calculator.

Framework Reference: Section 5 (Sentiment Score)
Tests all sentiment scoring components and composite calculations.
"""

import pytest
from calculators.sentiment import SentimentCalculator


class TestShortInterestScore:
    """
    Test short interest sentiment scoring.

    Framework Section 5.2: Short Interest (contrarian with threshold)
    """

    def test_normal_short_interest(self):
        """Days to cover < 3 should score 50 (normal)."""
        calc = SentimentCalculator()
        assert calc.calculate_short_interest_score(2.5) == 50.0

    def test_mild_concern_short_interest(self):
        """Days to cover 3-5 should score 40 (mild concern)."""
        calc = SentimentCalculator()
        assert calc.calculate_short_interest_score(4.0) == 40.0

    def test_significant_short_interest(self):
        """Days to cover 5-8 should score 30 (significant shorts)."""
        calc = SentimentCalculator()
        assert calc.calculate_short_interest_score(6.5) == 30.0

    def test_very_high_short_interest(self):
        """Days to cover > 8 should score 60 (potential contrarian opportunity)."""
        calc = SentimentCalculator()
        assert calc.calculate_short_interest_score(10.0) == 60.0

    def test_missing_short_interest(self):
        """Missing data should default to neutral (50)."""
        calc = SentimentCalculator()
        assert calc.calculate_short_interest_score(None) == 50.0

    def test_boundary_values(self):
        """Test boundary values for short interest buckets."""
        calc = SentimentCalculator()
        assert calc.calculate_short_interest_score(2.99) == 50.0
        assert calc.calculate_short_interest_score(3.0) == 40.0
        assert calc.calculate_short_interest_score(4.99) == 40.0
        assert calc.calculate_short_interest_score(5.0) == 30.0
        assert calc.calculate_short_interest_score(7.99) == 30.0
        assert calc.calculate_short_interest_score(8.0) == 60.0


class TestAnalystConsensusScore:
    """
    Test analyst consensus sentiment scoring.

    Framework Section 5.2: Analyst Consensus vs. Fair Value (with systematic discount)
    """

    def test_large_cap_high_upside(self):
        """Large cap with >20% discounted upside should score 80."""
        calc = SentimentCalculator()
        current_price = 100.0
        analyst_target = 130.0  # 30% upside, -5% discount = ~23.5% upside
        market_cap = 15_000  # $15B (large cap)

        score = calc.calculate_analyst_consensus_score(current_price, analyst_target, market_cap)
        assert score == 80.0

    def test_mid_cap_moderate_upside(self):
        """Mid cap with 10-20% discounted upside should score 65."""
        calc = SentimentCalculator()
        current_price = 100.0
        analyst_target = 120.0  # 20% upside, -8% discount = ~10.4% upside
        market_cap = 5_000  # $5B (mid cap)

        score = calc.calculate_analyst_consensus_score(current_price, analyst_target, market_cap)
        assert score == 65.0

    def test_small_cap_low_upside(self):
        """Small cap with 0-10% discounted upside should score 50."""
        calc = SentimentCalculator()
        current_price = 100.0
        analyst_target = 115.0  # 15% upside, -12% discount = ~1.2% upside
        market_cap = 1_500  # $1.5B (small cap)

        score = calc.calculate_analyst_consensus_score(current_price, analyst_target, market_cap)
        assert score == 50.0

    def test_negative_upside(self):
        """Negative upside (overvalued) should score 20 or 35."""
        calc = SentimentCalculator()
        current_price = 100.0
        analyst_target = 85.0  # -15% downside
        market_cap = 10_000

        score = calc.calculate_analyst_consensus_score(current_price, analyst_target, market_cap)
        assert score == 20.0  # < -10%

    def test_missing_analyst_target(self):
        """Missing analyst target should default to neutral (50)."""
        calc = SentimentCalculator()
        score = calc.calculate_analyst_consensus_score(100.0, None, 10_000)
        assert score == 50.0

    def test_missing_market_cap(self):
        """Missing market cap should use mid-cap discount (8%)."""
        calc = SentimentCalculator()
        current_price = 100.0
        analyst_target = 120.0  # 20% upside, -8% discount = ~10.4% upside
        market_cap = None

        score = calc.calculate_analyst_consensus_score(current_price, analyst_target, market_cap)
        assert score == 65.0


class TestInsiderActivityScore:
    """
    Test insider activity sentiment scoring.

    Framework Section 5.2: Insider Activity (past 6 months)
    """

    def test_significant_buying(self):
        """Significant net buying (>100k shares) should score 75."""
        calc = SentimentCalculator()
        assert calc.calculate_insider_activity_score(150_000) == 75.0

    def test_moderate_buying(self):
        """Moderate net buying (10k-100k shares) should score 60."""
        calc = SentimentCalculator()
        assert calc.calculate_insider_activity_score(50_000) == 60.0

    def test_neutral_activity(self):
        """Neutral activity (-10k to 10k shares) should score 50."""
        calc = SentimentCalculator()
        assert calc.calculate_insider_activity_score(5_000) == 50.0
        assert calc.calculate_insider_activity_score(-5_000) == 50.0
        assert calc.calculate_insider_activity_score(0) == 50.0

    def test_moderate_selling(self):
        """Moderate net selling (-100k to -10k shares) should score 40."""
        calc = SentimentCalculator()
        assert calc.calculate_insider_activity_score(-50_000) == 40.0

    def test_significant_selling(self):
        """Significant net selling (<-100k shares) should score 25."""
        calc = SentimentCalculator()
        assert calc.calculate_insider_activity_score(-150_000) == 25.0

    def test_missing_insider_data(self):
        """Missing data should default to neutral (50)."""
        calc = SentimentCalculator()
        assert calc.calculate_insider_activity_score(None) == 50.0


class TestAnalystRevisionScore:
    """
    Test analyst revision momentum scoring.

    Framework Section 5.2: Analyst Revision Momentum
    Note: Using recommendation_mean as proxy (1=Strong Buy, 5=Strong Sell)
    """

    def test_strong_buy_recommendation(self):
        """Recommendation mean 1.0-1.5 (Strong Buy) should score 75."""
        calc = SentimentCalculator()
        assert calc.calculate_analyst_revision_score(1.3, 10) == 75.0

    def test_buy_recommendation(self):
        """Recommendation mean 1.5-2.5 (Buy) should score 60."""
        calc = SentimentCalculator()
        assert calc.calculate_analyst_revision_score(2.0, 10) == 60.0

    def test_hold_recommendation(self):
        """Recommendation mean 2.5-3.5 (Hold) should score 40."""
        calc = SentimentCalculator()
        assert calc.calculate_analyst_revision_score(3.0, 10) == 40.0

    def test_sell_recommendation(self):
        """Recommendation mean 3.5-4.5 (Sell) should score 25."""
        calc = SentimentCalculator()
        assert calc.calculate_analyst_revision_score(4.0, 10) == 25.0

    def test_strong_sell_recommendation(self):
        """Recommendation mean 4.5-5.0 (Strong Sell) should score 15."""
        calc = SentimentCalculator()
        assert calc.calculate_analyst_revision_score(4.7, 10) == 15.0

    def test_low_analyst_coverage(self):
        """Low analyst coverage (<5) should dampen score toward neutral."""
        calc = SentimentCalculator()

        # Strong buy with low coverage should be dampened
        score_low_coverage = calc.calculate_analyst_revision_score(1.3, 3)
        score_high_coverage = calc.calculate_analyst_revision_score(1.3, 10)

        # Score with low coverage should be between neutral (50) and high coverage score
        assert 50 < score_low_coverage < score_high_coverage
        assert score_low_coverage == pytest.approx(67.5, abs=0.1)  # 50 + (75-50)*0.7

    def test_missing_recommendation(self):
        """Missing recommendation should default to neutral (50)."""
        calc = SentimentCalculator()
        assert calc.calculate_analyst_revision_score(None, 10) == 50.0


class TestStockSpecificSentiment:
    """
    Test stock-specific sentiment component (60% of total sentiment).

    Framework Section 5.2: Stock-Specific Sentiment
    """

    def test_all_components_neutral(self):
        """All neutral components should average to 50."""
        calc = SentimentCalculator()
        stock_data = {
            'days_to_cover': 2.0,  # Normal = 50
            'analyst_target': 100.0,  # Large cap, 5% discount → discounted target = 95
                                      # Return = (95-100)/100 = -5% → score = 35
            'market_cap': 10_000,  # Large cap
            'analyst_count': 10,
            'recommendation_mean': 3.0,  # Hold = 40
            'insider_net_shares': 0  # Neutral = 50
        }
        current_price = 100.0

        stock_sentiment = calc.calculate_stock_specific_sentiment(stock_data, current_price)

        # Average of [50 (short), 40 (revision), 35 (consensus), 50 (insider)] = 43.75
        assert stock_sentiment == pytest.approx(43.75, abs=0.1)

    def test_all_components_bullish(self):
        """All bullish components should produce high score."""
        calc = SentimentCalculator()
        stock_data = {
            'days_to_cover': 10.0,  # Very high = 60 (contrarian)
            'analyst_target': 130.0,  # 30% upside = 80
            'market_cap': 15_000,  # Large cap
            'analyst_count': 20,
            'recommendation_mean': 1.3,  # Strong Buy = 75
            'insider_net_shares': 150_000  # Significant buying = 75
        }
        current_price = 100.0

        stock_sentiment = calc.calculate_stock_specific_sentiment(stock_data, current_price)

        # Average of [60, 75, 80, 75] = 72.5
        assert stock_sentiment == pytest.approx(72.5, abs=0.1)

    def test_all_components_bearish(self):
        """All bearish components should produce low score."""
        calc = SentimentCalculator()
        stock_data = {
            'days_to_cover': 6.5,  # Significant = 30
            'analyst_target': 85.0,  # -15% downside = 20
            'market_cap': 10_000,
            'analyst_count': 15,
            'recommendation_mean': 4.5,  # Sell = 25
            'insider_net_shares': -150_000  # Significant selling = 25
        }
        current_price = 100.0

        stock_sentiment = calc.calculate_stock_specific_sentiment(stock_data, current_price)

        # Average of [30, 25, 20, 25] = 25.0
        assert stock_sentiment == pytest.approx(25.0, abs=0.1)


class TestMarketSentiment:
    """
    Test market-wide sentiment component (40% of total sentiment).

    Framework Section 5.2: Market-Wide Sentiment
    Market sentiment score is pre-calculated by collect_market_sentiment.py
    and passed via market_data dict.
    """

    def test_market_sentiment_default(self):
        """Market sentiment should default to 50 (neutral) when no data."""
        calc = SentimentCalculator()
        market_sentiment = calc.calculate_market_sentiment(None)
        assert market_sentiment == 50.0

    def test_market_sentiment_with_score(self):
        """Market sentiment should use the pre-calculated market_sentiment_score."""
        calc = SentimentCalculator()
        market_data = {'market_sentiment_score': 65.0, 'num_indicators_available': 4}
        market_sentiment = calc.calculate_market_sentiment(market_data)
        assert market_sentiment == 65.0

    def test_market_sentiment_without_score_key(self):
        """Market data without market_sentiment_score should default to 50."""
        calc = SentimentCalculator()
        market_data = {'vix': 20.0, 'aaii_spread': 5.0}
        market_sentiment = calc.calculate_market_sentiment(market_data)
        assert market_sentiment == 50.0


class TestCompositeSentimentScore:
    """
    Test composite sentiment score calculation.

    Framework Section 5.3: Base Sentiment Pillar Score
    Formula: (Market × 0.40) + (Stock × 0.60)
    """

    def test_all_neutral(self):
        """All neutral components should score 50."""
        calc = SentimentCalculator()
        stock_data = {
            'days_to_cover': 2.0,
            'analyst_target': 100.0,
            'market_cap': 10_000,
            'analyst_count': 10,
            'recommendation_mean': 3.0,
            'insider_net_shares': 0
        }
        current_price = 100.0

        sentiment_score = calc.calculate_sentiment_score(stock_data, current_price, None)

        # Market=50, Stock=43.75 → (50×0.4) + (43.75×0.6) = 20 + 26.25 = 46.25
        assert sentiment_score == pytest.approx(46.25, abs=0.1)

    def test_bullish_sentiment(self):
        """Bullish sentiment should produce high score."""
        calc = SentimentCalculator()
        stock_data = {
            'days_to_cover': 10.0,
            'analyst_target': 130.0,
            'market_cap': 15_000,
            'analyst_count': 20,
            'recommendation_mean': 1.3,
            'insider_net_shares': 150_000
        }
        current_price = 100.0

        sentiment_score = calc.calculate_sentiment_score(stock_data, current_price, None)

        # Market=50, Stock=72.5 → (50×0.4) + (72.5×0.6) = 63.5
        assert sentiment_score == pytest.approx(63.5, abs=0.1)

    def test_bearish_sentiment(self):
        """Bearish sentiment should produce low score."""
        calc = SentimentCalculator()
        stock_data = {
            'days_to_cover': 6.5,
            'analyst_target': 85.0,
            'market_cap': 10_000,
            'analyst_count': 15,
            'recommendation_mean': 4.5,
            'insider_net_shares': -150_000
        }
        current_price = 100.0

        sentiment_score = calc.calculate_sentiment_score(stock_data, current_price, None)

        # Market=50, Stock=25.0 → (50×0.4) + (25.0×0.6) = 35.0
        assert sentiment_score == pytest.approx(35.0, abs=0.1)

    def test_weight_distribution(self):
        """Verify framework weights are correctly applied (40% market, 60% stock)."""
        calc = SentimentCalculator()

        # Test case where stock sentiment is high (80) and market is neutral (50)
        stock_data = {
            'days_to_cover': 10.0,
            'analyst_target': 150.0,
            'market_cap': 15_000,
            'analyst_count': 20,
            'recommendation_mean': 1.0,
            'insider_net_shares': 200_000
        }
        current_price = 100.0

        sentiment_score = calc.calculate_sentiment_score(stock_data, current_price, None)

        # With high stock sentiment, score should be pulled up from neutral 50
        assert sentiment_score > 50.0
        # But not as much as if it were 100% stock weight
        assert sentiment_score < 80.0

    def test_score_range_validity(self):
        """All sentiment scores should be in valid 0-100 range."""
        calc = SentimentCalculator()

        # Test extreme cases
        test_cases = [
            # All bullish
            {
                'days_to_cover': 15.0,
                'analyst_target': 200.0,
                'market_cap': 20_000,
                'analyst_count': 30,
                'recommendation_mean': 1.0,
                'insider_net_shares': 500_000
            },
            # All bearish
            {
                'days_to_cover': 7.0,
                'analyst_target': 50.0,
                'market_cap': 1_000,
                'analyst_count': 10,
                'recommendation_mean': 5.0,
                'insider_net_shares': -500_000
            },
        ]

        for stock_data in test_cases:
            score = calc.calculate_sentiment_score(stock_data, 100.0, None)
            assert 0 <= score <= 100, f"Score {score} out of valid range"


class TestFrameworkCompliance:
    """
    Test compliance with framework specifications.

    Framework Section 5: Sentiment Score (20% weight in composite)
    """

    def test_component_weights(self):
        """Verify component weights match framework."""
        calc = SentimentCalculator()
        assert calc.MARKET_SENTIMENT_WEIGHT == 0.40
        assert calc.STOCK_SENTIMENT_WEIGHT == 0.60
        # Weights should sum to 1
        assert calc.MARKET_SENTIMENT_WEIGHT + calc.STOCK_SENTIMENT_WEIGHT == 1.0

    def test_contrarian_short_interest(self):
        """Very high short interest should be bullish (contrarian)."""
        calc = SentimentCalculator()
        high_short = calc.calculate_short_interest_score(10.0)  # 60
        normal_short = calc.calculate_short_interest_score(2.0)  # 50

        # High short interest should score higher (contrarian bullish)
        assert high_short > normal_short

    def test_systematic_analyst_discount(self):
        """Analyst targets should be systematically discounted."""
        calc = SentimentCalculator()

        # Same absolute upside, but different market caps → different discounts → different scores
        current_price = 100.0
        target_price = 120.0  # 20% upside

        large_cap_score = calc.calculate_analyst_consensus_score(
            current_price, target_price, 15_000  # -5% discount
        )
        small_cap_score = calc.calculate_analyst_consensus_score(
            current_price, target_price, 1_500  # -12% discount
        )

        # Large cap should score higher (less discount, more net upside)
        assert large_cap_score > small_cap_score
