"""
Sentiment Score Calculator

Framework Reference: Section 5
Calculates sentiment pillar score (20% of composite) using two components:
- Market-Wide Sentiment: 40% (VIX, AAII, Put/Call, Fund Flows)
- Stock-Specific Sentiment: 60% (Short interest, analyst data, insider activity)

Research Support:
- Rapach, Ringgenberg & Zhou (2016): Short interest R² of 13% for returns
- Baker & Wurgler: Sentiment effects concentrated in hard-to-value stocks
- Hong & Kubik: Analysts systematically optimistic (career incentives)
"""

from typing import Dict, List, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


class SentimentCalculator:
    """
    Calculates sentiment scores using rules-based methodology.

    Framework Section 5: Sentiment Score (20% weight)
    """

    def __init__(self):
        """Initialize sentiment calculator."""
        self.logger = logger

        # Component weights (Framework Section 5.3)
        self.MARKET_SENTIMENT_WEIGHT = 0.40
        self.STOCK_SENTIMENT_WEIGHT = 0.60

    def calculate_short_interest_score(
        self,
        days_to_cover: Optional[float]
    ) -> float:
        """
        Calculate short interest sentiment score.

        Framework Section 5.2: Stock-Specific Sentiment #1

        Contrarian with threshold approach:
        - Days to Cover < 3: Score = 50 (normal)
        - Days to Cover 3-5: Score = 40 (mild concern)
        - Days to Cover 5-8: Score = 30 (significant shorts)
        - Days to Cover > 8: Score = 60 (potential contrarian opportunity)

        Note: Very high short interest can be either informed bearishness
        OR setup for squeeze. Use 60 not 70+ to reflect ambiguity.

        Args:
            days_to_cover: Days to cover short interest (None if unavailable)

        Returns:
            Short interest score (0-100), 50 if data unavailable
        """
        if days_to_cover is None:
            self.logger.debug("No short interest data, using neutral score 50")
            return 50.0

        if days_to_cover < 3:
            score = 50.0  # Normal
        elif days_to_cover < 5:
            score = 40.0  # Mild concern
        elif days_to_cover < 8:
            score = 30.0  # Significant shorts
        else:
            score = 60.0  # Potential contrarian opportunity

        self.logger.debug(f"Days to cover: {days_to_cover:.2f} → score: {score}")
        return score

    def calculate_analyst_consensus_score(
        self,
        current_price: float,
        analyst_target: Optional[float],
        market_cap: Optional[float]
    ) -> float:
        """
        Calculate analyst consensus vs. fair value score.

        Framework Section 5.2: Stock-Specific Sentiment #3

        Step 1: Apply systematic discount to consensus target:
        - Large cap (>$10B), low volatility: Discount 5%
        - Mid cap ($2-10B), moderate volatility: Discount 8%
        - Small cap (<$2B), high volatility: Discount 12%

        Step 2: Calculate implied return from discounted target

        Step 3: Score based on return:
        - > 20%: Score = 80
        - 10-20%: Score = 65
        - 0-10%: Score = 50
        - -10 to 0%: Score = 35
        - < -10%: Score = 20

        Args:
            current_price: Current stock price
            analyst_target: Analyst consensus target price (None if unavailable)
            market_cap: Market capitalization in billions (None if unavailable)

        Returns:
            Analyst consensus score (0-100), 50 if data unavailable
        """
        if analyst_target is None or analyst_target <= 0:
            self.logger.debug("No analyst target, using neutral score 50")
            return 50.0

        # Step 1: Determine discount rate based on market cap
        if market_cap is None:
            # Default to mid-cap discount if market cap unavailable
            discount_rate = 0.08
            self.logger.debug("Market cap unavailable, using 8% discount (mid-cap)")
        elif market_cap > 10_000:  # > $10B (market_cap in millions)
            discount_rate = 0.05
            self.logger.debug(f"Large cap (${market_cap/1000:.1f}B), using 5% discount")
        elif market_cap > 2_000:  # $2-10B
            discount_rate = 0.08
            self.logger.debug(f"Mid cap (${market_cap/1000:.1f}B), using 8% discount")
        else:  # < $2B
            discount_rate = 0.12
            self.logger.debug(f"Small cap (${market_cap/1000:.1f}B), using 12% discount")

        # Step 2: Apply discount and calculate implied return
        discounted_target = analyst_target * (1 - discount_rate)
        implied_return = (discounted_target - current_price) / current_price

        # Step 3: Score based on return
        if implied_return > 0.20:
            score = 80.0
        elif implied_return > 0.10:
            score = 65.0
        elif implied_return > 0:
            score = 50.0
        elif implied_return > -0.10:
            score = 35.0
        else:
            score = 20.0

        self.logger.debug(
            f"Target: ${analyst_target:.2f}, Discounted: ${discounted_target:.2f}, "
            f"Return: {implied_return*100:.1f}% → score: {score}"
        )
        return score

    def calculate_insider_activity_score(
        self,
        insider_net_shares: Optional[int]
    ) -> float:
        """
        Calculate insider activity sentiment score.

        Framework Section 5.2: Stock-Specific Sentiment #4

        Note: This is a simplified version. The framework specifies:
        - Cluster buying (3+ insiders within 1 month): Score = 75
        - Single insider buying: Score = 60
        - No activity: Score = 50
        - Single insider selling: Score = 40
        - Cluster selling: Score = 25

        For MVP, we use net shares as a proxy:
        - Significant net buying (>100k shares): Score = 75
        - Moderate net buying (10k-100k shares): Score = 60
        - Neutral (-10k to 10k shares): Score = 50
        - Moderate net selling (-100k to -10k shares): Score = 40
        - Significant net selling (<-100k shares): Score = 25

        Args:
            insider_net_shares: Net insider buying in shares (positive = buying)

        Returns:
            Insider activity score (0-100), 50 if data unavailable
        """
        if insider_net_shares is None:
            self.logger.debug("No insider activity data, using neutral score 50")
            return 50.0

        if insider_net_shares > 100_000:
            score = 75.0  # Significant buying
        elif insider_net_shares > 10_000:
            score = 60.0  # Moderate buying
        elif insider_net_shares >= -10_000:
            score = 50.0  # Neutral
        elif insider_net_shares >= -100_000:
            score = 40.0  # Moderate selling
        else:
            score = 25.0  # Significant selling

        self.logger.debug(f"Insider net shares: {insider_net_shares:,} → score: {score}")
        return score

    def calculate_analyst_revision_score(
        self,
        recommendation_mean: Optional[float],
        analyst_count: Optional[int]
    ) -> float:
        """
        Calculate analyst revision momentum score.

        Framework Section 5.2: Stock-Specific Sentiment #2

        Note: Framework specifies % of estimates revised UP in past 90 days.
        For MVP, we use recommendation_mean as a proxy:
        - recommendation_mean scale: 1.0 (Strong Buy) to 5.0 (Strong Sell)

        Mapping:
        - 1.0-1.5 (Strong Buy): Score = 75
        - 1.5-2.5 (Buy): Score = 60
        - 2.5-3.5 (Hold): Score = 40
        - 3.5-4.5 (Sell): Score = 25
        - 4.5-5.0 (Strong Sell): Score = 15

        Args:
            recommendation_mean: Average analyst recommendation (1-5 scale)
            analyst_count: Number of analysts covering the stock

        Returns:
            Analyst revision score (0-100), 50 if data unavailable
        """
        if recommendation_mean is None:
            self.logger.debug("No analyst recommendation data, using neutral score 50")
            return 50.0

        # Fewer analysts = less reliable signal, dampen the score toward neutral
        confidence_factor = 1.0
        if analyst_count is not None and analyst_count < 5:
            confidence_factor = 0.7
            self.logger.debug(f"Low analyst coverage ({analyst_count}), damping score")

        # Calculate base score from recommendation mean
        if recommendation_mean <= 1.5:
            base_score = 75.0
        elif recommendation_mean <= 2.5:
            base_score = 60.0
        elif recommendation_mean <= 3.5:
            base_score = 40.0
        elif recommendation_mean <= 4.5:
            base_score = 25.0
        else:
            base_score = 15.0

        # Apply confidence factor (pull toward 50 for low coverage)
        score = 50 + (base_score - 50) * confidence_factor

        self.logger.debug(
            f"Recommendation mean: {recommendation_mean:.2f}, "
            f"Analysts: {analyst_count}, score: {score:.1f}"
        )
        return score

    def calculate_stock_specific_sentiment(
        self,
        stock_data: Dict[str, any],
        current_price: float
    ) -> Optional[float]:
        """
        Calculate stock-specific sentiment component.

        Framework Section 5.2: Stock-Specific Sentiment (60% of Sentiment)

        Four indicators, each scored 0-100 then averaged:
        1. Short Interest (contrarian with threshold)
        2. Analyst Revision Momentum (past 3 months)
        3. Analyst Consensus vs. Fair Value (with systematic discount)
        4. Insider Activity (past 6 months)

        Args:
            stock_data: Dict containing sentiment data fields
            current_price: Current stock price for analyst target calculation

        Returns:
            Stock-specific sentiment score (0-100), or None if no data available
        """
        scores = []

        # 1. Short Interest
        short_score = self.calculate_short_interest_score(
            stock_data.get('days_to_cover')
        )
        scores.append(short_score)

        # 2. Analyst Revision (using recommendation_mean as proxy)
        revision_score = self.calculate_analyst_revision_score(
            stock_data.get('recommendation_mean'),
            stock_data.get('analyst_count')
        )
        scores.append(revision_score)

        # 3. Analyst Consensus vs. Fair Value
        consensus_score = self.calculate_analyst_consensus_score(
            current_price,
            stock_data.get('analyst_target'),
            stock_data.get('market_cap')
        )
        scores.append(consensus_score)

        # 4. Insider Activity
        insider_score = self.calculate_insider_activity_score(
            stock_data.get('insider_net_shares')
        )
        scores.append(insider_score)

        # Average the four components
        stock_sentiment = np.mean(scores)

        self.logger.info(
            f"Stock sentiment components: Short={short_score:.1f}, "
            f"Revision={revision_score:.1f}, Consensus={consensus_score:.1f}, "
            f"Insider={insider_score:.1f} → Average={stock_sentiment:.1f}"
        )

        return stock_sentiment

    def calculate_market_sentiment(
        self,
        market_data: Optional[Dict[str, any]] = None
    ) -> float:
        """
        Calculate market-wide sentiment component.

        Framework Section 5.2: Market-Wide Sentiment (40% of Sentiment)

        Four indicators, each scored 0-100 then averaged:
        1. VIX Z-Score (contrarian)
        2. AAII Bear-Bull Spread (contrarian)
        3. Put/Call Ratio (contrarian)
        4. Equity Fund Flows (directional)

        Note: For MVP, market sentiment data collection is not yet implemented.
        This method returns a neutral score (50) as a placeholder.

        TODO: Implement market sentiment data collection and scoring in future phase.

        Args:
            market_data: Dict containing market sentiment indicators (optional)

        Returns:
            Market sentiment score (0-100), currently returns 50 (neutral)
        """
        if market_data is None:
            self.logger.debug("Market sentiment not implemented, using neutral score 50")
            return 50.0

        # TODO: Implement market sentiment scoring
        # This will require:
        # 1. VIX data and z-score calculation
        # 2. AAII sentiment data
        # 3. Put/Call ratio data
        # 4. Equity fund flow data

        return 50.0

    def calculate_sentiment_score(
        self,
        stock_data: Dict[str, any],
        current_price: float,
        market_data: Optional[Dict[str, any]] = None
    ) -> Optional[float]:
        """
        Calculate base sentiment pillar score.

        Framework Section 5.3: Base Sentiment Pillar Score

        Base Sentiment = (Market Sentiment × 0.40) + (Stock Sentiment × 0.60)

        Args:
            stock_data: Dict containing stock-specific sentiment data
            current_price: Current stock price
            market_data: Dict containing market-wide sentiment data (optional)

        Returns:
            Sentiment score (0-100), or None if insufficient data
        """
        # Calculate stock-specific sentiment
        stock_sentiment = self.calculate_stock_specific_sentiment(
            stock_data,
            current_price
        )

        if stock_sentiment is None:
            self.logger.warning("Insufficient stock sentiment data")
            return None

        # Calculate market-wide sentiment
        market_sentiment = self.calculate_market_sentiment(market_data)

        # Combine with Framework weights
        sentiment_score = (
            market_sentiment * self.MARKET_SENTIMENT_WEIGHT +
            stock_sentiment * self.STOCK_SENTIMENT_WEIGHT
        )

        self.logger.info(
            f"Sentiment score: Market={market_sentiment:.1f} (40%), "
            f"Stock={stock_sentiment:.1f} (60%) → Total={sentiment_score:.1f}"
        )

        return sentiment_score


def calculate_sentiment(
    stock_data: Dict[str, any],
    current_price: float,
    market_data: Optional[Dict[str, any]] = None
) -> Optional[float]:
    """
    Convenience function to calculate sentiment score.

    Args:
        stock_data: Dict containing stock-specific sentiment data
        current_price: Current stock price
        market_data: Dict containing market-wide sentiment data (optional)

    Returns:
        Sentiment score (0-100), or None if insufficient data
    """
    calculator = SentimentCalculator()
    return calculator.calculate_sentiment_score(stock_data, current_price, market_data)
