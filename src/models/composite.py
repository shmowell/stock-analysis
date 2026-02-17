"""
Composite Score Calculator - Combines all three pillar scores.

This module implements the final composite scoring logic that combines:
- Fundamental Score (45% weight)
- Technical Score (35% weight)
- Sentiment Score (20% weight)

Framework Reference: Section 1.3 (Base Weighting), Section 7 (Final Recommendation Logic)

Research Support:
- Fama-French factors support fundamental weighting
- Jegadeesh-Titman momentum supports technical weighting
- Baker-Wurgler sentiment research supports 20% weight

Author: Stock Analysis Framework v2.0
Date: 2026-02-12
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class Recommendation(Enum):
    """Stock recommendation levels based on percentile thresholds.

    Framework Reference: Section 7.2 (Recommendation Thresholds)
    """
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG SELL"

    @classmethod
    def from_percentile(cls, percentile: float) -> 'Recommendation':
        """Convert percentile rank to recommendation.

        Framework Section 7.2:
        - ≥85th: STRONG BUY (top 15% of universe)
        - 70-84th: BUY (above average)
        - 30-69th: HOLD (insufficient edge)
        - 16-29th: SELL (below average)
        - ≤15th: STRONG SELL (bottom 15%)

        Args:
            percentile: Percentile rank (0-100)

        Returns:
            Recommendation enum value
        """
        if percentile >= 85:
            return cls.STRONG_BUY
        elif percentile >= 70:
            return cls.BUY
        elif percentile >= 30:
            return cls.HOLD
        elif percentile >= 16:
            return cls.SELL
        else:
            return cls.STRONG_SELL


@dataclass
class CompositeScore:
    """Container for composite scoring results.

    Attributes:
        ticker: Stock ticker symbol
        fundamental_score: Fundamental pillar score (0-100)
        technical_score: Technical pillar score (0-100)
        sentiment_score: Sentiment pillar score (0-100)
        composite_score: Weighted composite score (0-100)
        composite_percentile: Percentile rank of composite within universe
        recommendation: Final recommendation (STRONG BUY/BUY/HOLD/SELL/STRONG SELL)
        signal_agreement: Percentage of sub-signals agreeing on direction (0-100)
        conviction_level: High/Medium/Low based on signal agreement
    """
    ticker: str
    fundamental_score: float
    technical_score: float
    sentiment_score: float
    composite_score: float
    composite_percentile: float
    recommendation: Recommendation
    signal_agreement: Optional[float] = None
    conviction_level: Optional[str] = None

    def __str__(self) -> str:
        """Human-readable representation."""
        return (
            f"{self.ticker}: {self.recommendation.value} "
            f"(Composite: {self.composite_score:.1f}, "
            f"Percentile: {self.composite_percentile:.1f})"
        )


class CompositeScoreCalculator:
    """Calculate composite scores combining all three pillars.

    Framework Reference: Section 1.3, Section 7

    Base weights (research-backed, DO NOT change without justification):
    - Fundamental: 45% (range: 35-55%)
    - Technical: 35% (range: 25-45%)
    - Sentiment: 20% (range: 10-30%)

    These weights reflect the empirical evidence hierarchy per Section 1.3.
    """

    # Base weights from framework Section 1.3
    DEFAULT_WEIGHTS = {
        'fundamental': 0.45,  # 45% - strongest empirical support
        'technical': 0.35,    # 35% - momentum premium well-documented
        'sentiment': 0.20     # 20% - weaker standalone, adds diversification
    }

    def __init__(
        self,
        fundamental_weight: float = 0.45,
        technical_weight: float = 0.35,
        sentiment_weight: float = 0.20
    ):
        """Initialize composite score calculator.

        Args:
            fundamental_weight: Weight for fundamental score (default: 0.45)
            technical_weight: Weight for technical score (default: 0.35)
            sentiment_weight: Weight for sentiment score (default: 0.20)

        Raises:
            ValueError: If weights don't sum to 1.0
        """
        # Validate weights sum to 1.0
        total_weight = fundamental_weight + technical_weight + sentiment_weight
        if not (0.999 <= total_weight <= 1.001):  # Allow for floating point precision
            raise ValueError(
                f"Weights must sum to 1.0, got {total_weight:.4f} "
                f"(F: {fundamental_weight}, T: {technical_weight}, S: {sentiment_weight})"
            )

        self.fundamental_weight = fundamental_weight
        self.technical_weight = technical_weight
        self.sentiment_weight = sentiment_weight

    def calculate_composite_score(
        self,
        fundamental_score: float,
        technical_score: float,
        sentiment_score: float
    ) -> float:
        """Calculate weighted composite score from pillar scores.

        Framework Section 7.1:
        Final Composite = (Fundamental × Weight_F) +
                         (Technical × Weight_T) +
                         (Sentiment × Weight_S)

        Args:
            fundamental_score: Fundamental pillar score (0-100)
            technical_score: Technical pillar score (0-100)
            sentiment_score: Sentiment pillar score (0-100)

        Returns:
            Composite score (0-100)
        """
        composite = (
            fundamental_score * self.fundamental_weight +
            technical_score * self.technical_weight +
            sentiment_score * self.sentiment_weight
        )

        return composite

    def calculate_signal_agreement(
        self,
        fundamental_subsignals: Dict[str, float],
        technical_subsignals: Dict[str, float],
        sentiment_subsignals: Dict[str, float]
    ) -> Tuple[float, str]:
        """Calculate signal agreement score for conviction assessment.

        Framework Section 7.3: Signal Agreement Score

        Measures what % of individual sub-signals agree on direction (bullish vs bearish).
        High agreement (>75%) = increase conviction
        Low agreement (<50%) = decrease conviction

        Args:
            fundamental_subsignals: Dict of fundamental sub-factor scores
            technical_subsignals: Dict of technical sub-factor scores
            sentiment_subsignals: Dict of sentiment sub-factor scores

        Returns:
            Tuple of (agreement_percentage, conviction_level)
            - agreement_percentage: 0-100 scale
            - conviction_level: "High" (>75%), "Medium" (50-75%), or "Low" (<50%)
        """
        # Count bullish signals (score > 50) in each pillar
        fundamental_bullish = sum(1 for score in fundamental_subsignals.values() if score > 50)
        fundamental_total = len(fundamental_subsignals)
        fundamental_agreement = (fundamental_bullish / fundamental_total * 100) if fundamental_total > 0 else 0

        technical_bullish = sum(1 for score in technical_subsignals.values() if score > 50)
        technical_total = len(technical_subsignals)
        technical_agreement = (technical_bullish / technical_total * 100) if technical_total > 0 else 0

        sentiment_bullish = sum(1 for score in sentiment_subsignals.values() if score > 50)
        sentiment_total = len(sentiment_subsignals)
        sentiment_agreement = (sentiment_bullish / sentiment_total * 100) if sentiment_total > 0 else 0

        # Average agreement across pillars
        overall_agreement = (fundamental_agreement + technical_agreement + sentiment_agreement) / 3

        # Determine conviction level
        if overall_agreement > 75 or overall_agreement < 25:  # Strong directional agreement
            conviction_level = "High"
        elif 50 <= overall_agreement <= 75 or 25 <= overall_agreement < 50:
            conviction_level = "Medium"
        else:
            conviction_level = "Low"

        return overall_agreement, conviction_level

    def calculate_percentile_rank(
        self,
        value: float,
        universe: List[float]
    ) -> float:
        """Calculate percentile rank of a value within a universe.

        Higher percentile = better (higher value beats more of universe)

        Args:
            value: The value to rank
            universe: List of all values in the universe

        Returns:
            Percentile rank (0-100)
        """
        if not universe:
            return 50.0  # Neutral rank when no peers to compare against

        # Count how many values in universe are less than this value
        count_below = sum(1 for v in universe if v < value)

        # Percentile = (count below / total) * 100
        percentile = (count_below / len(universe)) * 100

        return percentile

    def calculate_scores_for_universe(
        self,
        stock_scores: Dict[str, Dict[str, float]]
    ) -> List[CompositeScore]:
        """Calculate composite scores for entire universe of stocks.

        This is the main integration function that:
        1. Calculates composite scores for each stock
        2. Ranks composites within universe to get percentiles
        3. Generates recommendations based on percentiles

        Framework Section 7.1: Calculate Final Composite Score

        Args:
            stock_scores: Dict mapping ticker to pillar scores
                Example: {
                    'AAPL': {
                        'fundamental': 75.0,
                        'technical': 82.0,
                        'sentiment': 68.0
                    },
                    ...
                }

        Returns:
            List of CompositeScore objects, sorted by composite_percentile (descending)
        """
        # Step 1: Calculate raw composite scores for all stocks
        composites = {}
        for ticker, scores in stock_scores.items():
            composite_score = self.calculate_composite_score(
                fundamental_score=scores['fundamental'],
                technical_score=scores['technical'],
                sentiment_score=scores['sentiment']
            )
            composites[ticker] = {
                'fundamental': scores['fundamental'],
                'technical': scores['technical'],
                'sentiment': scores['sentiment'],
                'composite': composite_score
            }

        # Step 2: Calculate percentile ranks for composite scores within universe
        all_composite_scores = [data['composite'] for data in composites.values()]

        # Step 3: Create CompositeScore objects with percentiles and recommendations
        results = []
        for ticker, scores in composites.items():
            percentile = self.calculate_percentile_rank(
                scores['composite'],
                all_composite_scores
            )

            recommendation = Recommendation.from_percentile(percentile)

            result = CompositeScore(
                ticker=ticker,
                fundamental_score=scores['fundamental'],
                technical_score=scores['technical'],
                sentiment_score=scores['sentiment'],
                composite_score=scores['composite'],
                composite_percentile=percentile,
                recommendation=recommendation
            )

            results.append(result)

        # Step 4: Sort by percentile (descending - best stocks first)
        results.sort(key=lambda x: x.composite_percentile, reverse=True)

        return results

    def generate_report(self, results: List[CompositeScore]) -> str:
        """Generate a human-readable report of composite scores.

        Args:
            results: List of CompositeScore objects

        Returns:
            Formatted report string
        """
        report_lines = [
            "=" * 100,
            "COMPOSITE SCORE REPORT",
            "=" * 100,
            f"Universe Size: {len(results)} stocks",
            f"Weights: Fundamental {self.fundamental_weight*100:.0f}%, "
            f"Technical {self.technical_weight*100:.0f}%, "
            f"Sentiment {self.sentiment_weight*100:.0f}%",
            "=" * 100,
            "",
            f"{'Rank':<6} {'Ticker':<8} {'Recommendation':<15} {'Composite':<12} "
            f"{'Percentile':<12} {'Fund':<8} {'Tech':<8} {'Sent':<8}",
            "-" * 100
        ]

        for rank, result in enumerate(results, 1):
            line = (
                f"{rank:<6} {result.ticker:<8} {result.recommendation.value:<15} "
                f"{result.composite_score:<12.1f} {result.composite_percentile:<12.1f} "
                f"{result.fundamental_score:<8.1f} {result.technical_score:<8.1f} "
                f"{result.sentiment_score:<8.1f}"
            )
            report_lines.append(line)

        report_lines.append("=" * 100)

        # Summary statistics
        strong_buys = sum(1 for r in results if r.recommendation == Recommendation.STRONG_BUY)
        buys = sum(1 for r in results if r.recommendation == Recommendation.BUY)
        holds = sum(1 for r in results if r.recommendation == Recommendation.HOLD)
        sells = sum(1 for r in results if r.recommendation == Recommendation.SELL)
        strong_sells = sum(1 for r in results if r.recommendation == Recommendation.STRONG_SELL)

        report_lines.extend([
            "",
            "RECOMMENDATION DISTRIBUTION:",
            f"  STRONG BUY:  {strong_buys:2d} stocks ({strong_buys/len(results)*100:5.1f}%)",
            f"  BUY:         {buys:2d} stocks ({buys/len(results)*100:5.1f}%)",
            f"  HOLD:        {holds:2d} stocks ({holds/len(results)*100:5.1f}%)",
            f"  SELL:        {sells:2d} stocks ({sells/len(results)*100:5.1f}%)",
            f"  STRONG SELL: {strong_sells:2d} stocks ({strong_sells/len(results)*100:5.1f}%)",
            "=" * 100
        ])

        return "\n".join(report_lines)
