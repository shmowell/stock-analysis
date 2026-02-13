"""
Technical Score Calculator

Framework Reference: Section 4
Calculates technical pillar score (35% of composite) using six sub-components:
- Cross-Sectional Momentum: 35% (12-1 month return)
- Trend Strength: 25% (Price vs 200-MA + MAD)
- Volume-Qualified Momentum: 20% (Momentum with volume adjustment)
- Relative Strength vs Sector: 10% (6-month return vs sector)
- RSI Trend Confirmation: 5% (Binary above/below 50)
- Multi-Speed Trend Blend: 5% (Short-term + long-term uptrend)

Research Support: Jegadeesh & Titman - momentum across 30+ years and dozens
of countries. Blitz et al. (2023) - short-term momentum produces uncorrelated alpha.
"""

from typing import Dict, List, Optional
import numpy as np
import logging

from .percentile import (
    percentile_rank,
    average_percentile_ranks
)

logger = logging.getLogger(__name__)


class TechnicalCalculator:
    """
    Calculates technical scores using percentile ranking.

    Framework Section 4: Technical Score (35% weight)
    """

    def __init__(self):
        """Initialize technical calculator."""
        self.logger = logger

        # Sub-component weights (Framework Section 4.3)
        self.MOMENTUM_WEIGHT = 0.35
        self.TREND_WEIGHT = 0.25
        self.VOLUME_QUALIFIED_WEIGHT = 0.20
        self.RELATIVE_STRENGTH_WEIGHT = 0.10
        self.RSI_WEIGHT = 0.05
        self.MULTI_SPEED_WEIGHT = 0.05

    def calculate_momentum_score(
        self,
        stock_metrics: Dict[str, float],
        universe_metrics: Dict[str, List[float]]
    ) -> Optional[float]:
        """
        Calculate cross-sectional momentum component score.

        Framework Section 4.2: Cross-Sectional Momentum (35% of Technical)

        Metric:
        - 12-1 Month Return: Total return from 12 months ago to 1 month ago
          (Excludes most recent month to avoid reversal effect)
        - Higher return = stronger momentum
        - Ranked across universe as percentile

        Args:
            stock_metrics: Dict with stock's technical metrics
            universe_metrics: Dict with lists of all universe values for each metric

        Returns:
            Momentum score (0-100 percentile), or None if insufficient data
        """
        # 12-1 month return (higher is better)
        if stock_metrics.get('momentum_12_1') is None:
            self.logger.warning("12-1 month return not available")
            return None

        if not universe_metrics.get('momentum_12_1'):
            self.logger.warning("Universe 12-1 month returns not available")
            return None

        momentum_rank = percentile_rank(
            stock_metrics['momentum_12_1'],
            universe_metrics['momentum_12_1']
        )

        if momentum_rank is not None:
            self.logger.info(f"Momentum score: {momentum_rank:.1f}")

        return momentum_rank

    def calculate_trend_strength_score(
        self,
        stock_metrics: Dict[str, float],
        universe_metrics: Dict[str, List[float]]
    ) -> Optional[float]:
        """
        Calculate trend strength component score.

        Framework Section 4.2: Trend Strength (25% of Technical)

        Two components:
        1. Binary: Price vs 200-day MA (above=100, below=0)
        2. MAD percentile: (50-day MA - 200-day MA) / 200-day MA ranked

        Trend Score = (Binary × 0.5) + (MAD_rank × 0.5)

        Args:
            stock_metrics: Dict with stock's technical metrics
            universe_metrics: Dict with lists of all universe values for each metric

        Returns:
            Trend strength score (0-100), or None if insufficient data
        """
        # Component 1: Price vs 200-day MA (binary)
        price_vs_ma200 = stock_metrics.get('price_vs_200ma')
        if price_vs_ma200 is None:
            self.logger.warning("Price vs 200-MA binary not available")
            return None

        binary_score = 100.0 if price_vs_ma200 else 0.0

        # Component 2: MAD percentile
        mad = stock_metrics.get('mad')
        if mad is None or not universe_metrics.get('mad'):
            self.logger.warning("MAD not available")
            # Use only binary component if MAD unavailable
            trend_score = binary_score
            self.logger.info(f"Trend score (binary only): {trend_score:.1f}")
            return trend_score

        # Rank MAD across universe (higher MAD = stronger uptrend)
        mad_rank = percentile_rank(mad, universe_metrics['mad'])

        if mad_rank is None:
            # Fallback to binary only
            trend_score = binary_score
        else:
            # Combine binary and MAD (50/50)
            trend_score = (binary_score * 0.5) + (mad_rank * 0.5)

        self.logger.info(
            f"Trend score: {trend_score:.1f} "
            f"(Binary: {binary_score}, MAD rank: {mad_rank})"
        )

        return trend_score

    def calculate_volume_qualified_momentum_score(
        self,
        stock_metrics: Dict[str, float],
        universe_metrics: Dict[str, List[float]]
    ) -> Optional[float]:
        """
        Calculate volume-qualified momentum component score.

        Framework Section 4.2: Volume-Qualified Momentum (20% of Technical)

        Research (Lee & Swaminathan 2000): High-volume winners = late-stage
        momentum (reversal risk). Low-volume winners = early-stage momentum
        (more persistent).

        Logic:
        1. Start with base momentum score
        2. Calculate relative volume: Current avg volume / 90-day avg volume
        3. Adjust:
           - If relative volume < 1.2 (low): +10 (early stage bonus)
           - If relative volume 1.2-1.8 (normal): no adjustment
           - If relative volume > 1.8 (high): -10 (late stage penalty)
        4. Cap at 0-100 range

        Args:
            stock_metrics: Dict with stock's technical metrics
            universe_metrics: Dict with lists of all universe values for each metric

        Returns:
            Volume-qualified momentum score (0-100), or None if insufficient data
        """
        # Get base momentum score
        momentum_score = self.calculate_momentum_score(stock_metrics, universe_metrics)
        if momentum_score is None:
            return None

        # Get relative volume
        relative_volume = stock_metrics.get('relative_volume')
        if relative_volume is None:
            self.logger.warning("Relative volume not available, using base momentum")
            return momentum_score

        # Apply volume qualification
        if relative_volume < 1.2:
            # Low volume = early stage = bonus
            adjusted_score = momentum_score + 10
            adjustment = "+10 (early stage)"
        elif relative_volume <= 1.8:
            # Normal volume = no adjustment
            adjusted_score = momentum_score
            adjustment = "0 (normal)"
        else:
            # High volume = late stage = penalty
            adjusted_score = momentum_score - 10
            adjustment = "-10 (late stage)"

        # Cap at 0-100
        adjusted_score = max(0.0, min(100.0, adjusted_score))

        self.logger.info(
            f"Volume-qualified momentum: {adjusted_score:.1f} "
            f"(Base: {momentum_score:.1f}, RelVol: {relative_volume:.2f}, Adj: {adjustment})"
        )

        return adjusted_score

    def calculate_relative_strength_score(
        self,
        stock_metrics: Dict[str, float],
        universe_metrics: Dict[str, List[float]]
    ) -> Optional[float]:
        """
        Calculate relative strength vs sector component score.

        Framework Section 4.2: Relative Strength vs Sector (10% of Technical)

        Metric:
        - 6-month return of stock vs 6-month return of sector
        - Spread is ranked across universe
        - Higher relative outperformance = higher score

        Args:
            stock_metrics: Dict with stock's technical metrics
            universe_metrics: Dict with lists of all universe values for each metric

        Returns:
            Relative strength score (0-100 percentile), or None if insufficient data
        """
        # Check if we have pre-calculated sector relative performance
        sector_relative = stock_metrics.get('sector_relative_6m')

        if sector_relative is not None:
            # Use pre-calculated spread directly
            if not universe_metrics.get('sector_relative_6m'):
                self.logger.warning("Universe sector relative 6m not available")
                return None

            rs_rank = percentile_rank(
                sector_relative,
                universe_metrics['sector_relative_6m']
            )

            if rs_rank is not None:
                self.logger.info(
                    f"Relative strength: {rs_rank:.1f} (Sector relative: {sector_relative:.2%})"
                )
            return rs_rank

        # Fallback: Calculate from individual returns if available
        stock_return_6m = stock_metrics.get('momentum_6m')
        sector_return_6m = stock_metrics.get('sector_return_6m')

        if stock_return_6m is None or sector_return_6m is None:
            self.logger.warning("6-month returns not available - relative strength will be skipped")
            return None

        # Calculate spread (stock return - sector return)
        relative_strength_spread = stock_return_6m - sector_return_6m

        # Rank spread across universe
        if not universe_metrics.get('relative_strength_spread'):
            self.logger.warning("Universe relative strength spreads not available")
            return None

        rs_rank = percentile_rank(
            relative_strength_spread,
            universe_metrics['relative_strength_spread']
        )

        if rs_rank is not None:
            self.logger.info(
                f"Relative strength: {rs_rank:.1f} "
                f"(Stock: {stock_return_6m:.2%}, Sector: {sector_return_6m:.2%})"
            )

        return rs_rank

    def calculate_rsi_trend_score(
        self,
        stock_metrics: Dict[str, float],
        universe_metrics: Dict[str, List[float]]
    ) -> Optional[float]:
        """
        Calculate RSI trend confirmation component score.

        Framework Section 4.2: RSI Trend Confirmation (5% of Technical)

        Note: RSI is retained ONLY as binary trend confirmation, not
        overbought/oversold signals (weak predictive power).

        Logic:
        - RSI > 50 → Bullish trend → 100 points
        - RSI ≤ 50 → Bearish trend → 0 points

        Args:
            stock_metrics: Dict with stock's technical metrics
            universe_metrics: Dict with lists of all universe values for each metric

        Returns:
            RSI trend score (0 or 100), or None if insufficient data
        """
        rsi = stock_metrics.get('rsi_14')
        if rsi is None:
            self.logger.warning("RSI not available")
            return None

        # Binary: above 50 = bullish, below 50 = bearish
        rsi_score = 100.0 if rsi > 50 else 0.0

        self.logger.info(f"RSI trend: {rsi_score:.1f} (RSI: {rsi:.1f})")

        return rsi_score

    def calculate_multi_speed_trend_score(
        self,
        stock_metrics: Dict[str, float],
        universe_metrics: Dict[str, List[float]]
    ) -> Optional[float]:
        """
        Calculate multi-speed trend blend component score.

        Framework Section 4.2: Multi-Speed Trend Blend (5% of Technical)

        Combines two trend signals:
        1. Short-term: Price > 20-day MA AND 20-day > 50-day
        2. Long-term: Price > 50-day MA AND 50-day > 200-day

        Scoring:
        - Both uptrends: 100
        - One uptrend: 50
        - No uptrends: 0

        Args:
            stock_metrics: Dict with stock's technical metrics
            universe_metrics: Dict with lists of all universe values for each metric

        Returns:
            Multi-speed trend score (0, 50, or 100), or None if insufficient data
        """
        # Short-term uptrend
        short_term_uptrend = stock_metrics.get('short_term_uptrend')

        # Long-term uptrend
        long_term_uptrend = stock_metrics.get('long_term_uptrend')

        if short_term_uptrend is None or long_term_uptrend is None:
            self.logger.warning("Multi-speed trend signals not available")
            return None

        # Count uptrends
        uptrend_count = int(short_term_uptrend) + int(long_term_uptrend)

        if uptrend_count == 2:
            multi_speed_score = 100.0
        elif uptrend_count == 1:
            multi_speed_score = 50.0
        else:
            multi_speed_score = 0.0

        self.logger.info(
            f"Multi-speed trend: {multi_speed_score:.1f} "
            f"(Short-term: {short_term_uptrend}, Long-term: {long_term_uptrend})"
        )

        return multi_speed_score

    def calculate_technical_score(
        self,
        stock_metrics: Dict[str, float],
        universe_metrics: Dict[str, List[float]]
    ) -> Dict[str, Optional[float]]:
        """
        Calculate complete technical pillar score.

        Framework Section 4.3:
        Technical Score = (Momentum × 0.35) + (Trend × 0.25) +
                         (Volume-Qualified × 0.20) + (Relative Strength × 0.10) +
                         (RSI × 0.05) + (Multi-Speed × 0.05)

        Args:
            stock_metrics: Dict with all technical metrics for the stock
            universe_metrics: Dict with lists of all universe values for each metric

        Returns:
            Dict with:
            - momentum_score: Cross-sectional momentum score (0-100)
            - trend_score: Trend strength score (0-100)
            - volume_qualified_score: Volume-qualified momentum score (0-100)
            - relative_strength_score: Relative strength score (0-100)
            - rsi_score: RSI trend confirmation score (0-100)
            - multi_speed_score: Multi-speed trend score (0-100)
            - technical_score: Composite technical score (0-100)
        """
        # Calculate sub-components
        momentum_score = self.calculate_momentum_score(stock_metrics, universe_metrics)
        trend_score = self.calculate_trend_strength_score(stock_metrics, universe_metrics)
        volume_qualified_score = self.calculate_volume_qualified_momentum_score(
            stock_metrics, universe_metrics
        )
        relative_strength_score = self.calculate_relative_strength_score(
            stock_metrics, universe_metrics
        )
        rsi_score = self.calculate_rsi_trend_score(stock_metrics, universe_metrics)
        multi_speed_score = self.calculate_multi_speed_trend_score(
            stock_metrics, universe_metrics
        )

        # Calculate composite technical score
        sub_scores = []
        weights = []

        if momentum_score is not None:
            sub_scores.append(momentum_score)
            weights.append(self.MOMENTUM_WEIGHT)

        if trend_score is not None:
            sub_scores.append(trend_score)
            weights.append(self.TREND_WEIGHT)

        if volume_qualified_score is not None:
            sub_scores.append(volume_qualified_score)
            weights.append(self.VOLUME_QUALIFIED_WEIGHT)

        if relative_strength_score is not None:
            sub_scores.append(relative_strength_score)
            weights.append(self.RELATIVE_STRENGTH_WEIGHT)

        if rsi_score is not None:
            sub_scores.append(rsi_score)
            weights.append(self.RSI_WEIGHT)

        if multi_speed_score is not None:
            sub_scores.append(multi_speed_score)
            weights.append(self.MULTI_SPEED_WEIGHT)

        # Calculate weighted average (weights will be auto-normalized)
        if len(sub_scores) == 0:
            self.logger.error("No technical sub-components available")
            technical_score = None
        else:
            technical_score = average_percentile_ranks(sub_scores, weights)
            self.logger.info(
                f"Technical score: {technical_score:.1f} "
                f"(Momentum: {momentum_score}, Trend: {trend_score}, "
                f"VolQual: {volume_qualified_score}, RelStr: {relative_strength_score}, "
                f"RSI: {rsi_score}, MultiSpeed: {multi_speed_score})"
            )

        return {
            'momentum_score': momentum_score,
            'trend_score': trend_score,
            'volume_qualified_score': volume_qualified_score,
            'relative_strength_score': relative_strength_score,
            'rsi_score': rsi_score,
            'multi_speed_score': multi_speed_score,
            'technical_score': technical_score
        }


def extract_technical_metrics_from_db(
    technical_indicator_row,
    current_price: float,
    sector_return_6m: Optional[float] = None
) -> Dict[str, float]:
    """
    Extract technical metrics from database row.

    Note: Database uses different column names than ORM model
    (calculation_date, sma_*, momentum_*, rsi_14, etc.)

    Args:
        technical_indicator_row: Database row from technical_indicators table
        current_price: Current stock price
        sector_return_6m: 6-month sector return (optional)

    Returns:
        Dict with metric names and values for calculator
    """
    # Get values from database row (using actual column names)
    sma_20 = float(technical_indicator_row.sma_20) if technical_indicator_row.sma_20 else None
    sma_50 = float(technical_indicator_row.sma_50) if technical_indicator_row.sma_50 else None
    sma_200 = float(technical_indicator_row.sma_200) if technical_indicator_row.sma_200 else None
    mad = float(technical_indicator_row.mad) if technical_indicator_row.mad else None

    momentum_12_1 = float(technical_indicator_row.momentum_12_1) if technical_indicator_row.momentum_12_1 else None
    momentum_6m = float(technical_indicator_row.momentum_6m) if technical_indicator_row.momentum_6m else None

    rsi_14 = float(technical_indicator_row.rsi_14) if technical_indicator_row.rsi_14 else None

    relative_volume = float(technical_indicator_row.relative_volume) if technical_indicator_row.relative_volume else None
    price_vs_200ma_binary = technical_indicator_row.price_vs_200ma

    # Calculate multi-speed trend signals
    # Short-term: Price > 20-MA AND 20-MA > 50-MA
    short_term_uptrend = None
    if current_price and sma_20 and sma_50:
        short_term_uptrend = (current_price > sma_20) and (sma_20 > sma_50)

    # Long-term: Price > 50-MA AND 50-MA > 200-MA
    long_term_uptrend = None
    if current_price and sma_50 and sma_200:
        long_term_uptrend = (current_price > sma_50) and (sma_50 > sma_200)

    # Calculate relative strength spread (stock return - sector return)
    relative_strength_spread = None
    if momentum_6m is not None and sector_return_6m is not None:
        relative_strength_spread = momentum_6m - sector_return_6m

    return {
        # Momentum metrics
        'return_12_1_month': momentum_12_1,
        'return_6_month': momentum_6m,

        # Trend metrics
        'price_vs_ma200_binary': price_vs_200ma_binary,
        'mad': mad,

        # Volume metrics
        'relative_volume': relative_volume,

        # Sector comparison
        'sector_return_6_month': sector_return_6m,
        'relative_strength_spread': relative_strength_spread,

        # RSI
        'rsi': rsi_14,

        # Multi-speed trend
        'short_term_uptrend': short_term_uptrend,
        'long_term_uptrend': long_term_uptrend,
    }
