"""
Fundamental Score Calculator

Framework Reference: Section 3
Calculates fundamental pillar score (45% of composite) using three sub-components:
- Value: 33% (P/E, P/B, P/S, EV/EBITDA, dividend yield)
- Quality: 33% (ROE, ROA, margins, earnings stability)
- Growth: 34% (revenue, EPS, FCF growth)

Research Support: AQR "Craftsmanship Alpha" - diversified composite factors
outperformed single metrics in nearly every 5-year period since 1990.
"""

from typing import Dict, List, Optional
import numpy as np
import logging

from .percentile import (
    percentile_rank,
    percentile_rank_inverted,
    average_percentile_ranks
)

logger = logging.getLogger(__name__)


class FundamentalCalculator:
    """
    Calculates fundamental scores using percentile ranking.

    Framework Section 3: Fundamental Score (45% weight)
    """

    def __init__(self):
        """Initialize fundamental calculator."""
        self.logger = logger

        # Sub-component weights (Framework Section 3.3)
        self.VALUE_WEIGHT = 0.33
        self.QUALITY_WEIGHT = 0.33
        self.GROWTH_WEIGHT = 0.34

    def calculate_value_score(
        self,
        stock_metrics: Dict[str, float],
        universe_metrics: Dict[str, List[float]]
    ) -> Optional[float]:
        """
        Calculate value component score.

        Framework Section 3.2: Value Component (33% of Fundamental)

        Metrics (percentile-ranked):
        1. P/E ratio (lower is better → inverted)
        2. P/B ratio (lower is better → inverted)
        3. P/S ratio (lower is better → inverted)
        4. EV/EBITDA (lower is better → inverted)
        5. Dividend yield (higher is better)

        Args:
            stock_metrics: Dict with stock's valuation metrics
            universe_metrics: Dict with lists of all universe values for each metric

        Returns:
            Value score (0-100 percentile), or None if insufficient data
        """
        ranks = []

        # P/E ratio (lower is better)
        if stock_metrics.get('pe_ratio') and universe_metrics.get('pe_ratio'):
            pe_rank = percentile_rank_inverted(
                stock_metrics['pe_ratio'],
                universe_metrics['pe_ratio']
            )
            if pe_rank is not None:
                ranks.append(pe_rank)
                self.logger.debug(f"P/E rank: {pe_rank}")

        # P/B ratio (lower is better)
        if stock_metrics.get('pb_ratio') and universe_metrics.get('pb_ratio'):
            pb_rank = percentile_rank_inverted(
                stock_metrics['pb_ratio'],
                universe_metrics['pb_ratio']
            )
            if pb_rank is not None:
                ranks.append(pb_rank)
                self.logger.debug(f"P/B rank: {pb_rank}")

        # P/S ratio (lower is better)
        if stock_metrics.get('ps_ratio') and universe_metrics.get('ps_ratio'):
            ps_rank = percentile_rank_inverted(
                stock_metrics['ps_ratio'],
                universe_metrics['ps_ratio']
            )
            if ps_rank is not None:
                ranks.append(ps_rank)
                self.logger.debug(f"P/S rank: {ps_rank}")

        # EV/EBITDA (lower is better)
        if stock_metrics.get('ev_ebitda') and universe_metrics.get('ev_ebitda'):
            ev_rank = percentile_rank_inverted(
                stock_metrics['ev_ebitda'],
                universe_metrics['ev_ebitda']
            )
            if ev_rank is not None:
                ranks.append(ev_rank)
                self.logger.debug(f"EV/EBITDA rank: {ev_rank}")

        # Dividend yield (higher is better)
        if stock_metrics.get('dividend_yield') and universe_metrics.get('dividend_yield'):
            div_rank = percentile_rank(
                stock_metrics['dividend_yield'],
                universe_metrics['dividend_yield']
            )
            if div_rank is not None:
                ranks.append(div_rank)
                self.logger.debug(f"Dividend yield rank: {div_rank}")

        # Calculate average of available ranks
        if len(ranks) == 0:
            self.logger.warning("No valid value metrics available")
            return None

        value_score = average_percentile_ranks(ranks)
        self.logger.info(f"Value score: {value_score} (from {len(ranks)} metrics)")

        return value_score

    def calculate_quality_score(
        self,
        stock_metrics: Dict[str, float],
        universe_metrics: Dict[str, List[float]]
    ) -> Optional[float]:
        """
        Calculate quality component score.

        Framework Section 3.2: Quality Component (33% of Fundamental)

        Metrics (percentile-ranked):
        1. ROE (higher is better)
        2. ROA (higher is better)
        3. Net margin (higher is better)
        4. Operating margin (higher is better)
        5. Gross margin (higher is better)

        Note: Earnings stability not implemented yet (requires historical data)

        Args:
            stock_metrics: Dict with stock's quality metrics
            universe_metrics: Dict with lists of all universe values for each metric

        Returns:
            Quality score (0-100 percentile), or None if insufficient data
        """
        ranks = []

        # ROE (higher is better)
        if stock_metrics.get('roe') and universe_metrics.get('roe'):
            roe_rank = percentile_rank(
                stock_metrics['roe'],
                universe_metrics['roe']
            )
            if roe_rank is not None:
                ranks.append(roe_rank)
                self.logger.debug(f"ROE rank: {roe_rank}")

        # ROA (higher is better)
        if stock_metrics.get('roa') and universe_metrics.get('roa'):
            roa_rank = percentile_rank(
                stock_metrics['roa'],
                universe_metrics['roa']
            )
            if roa_rank is not None:
                ranks.append(roa_rank)
                self.logger.debug(f"ROA rank: {roa_rank}")

        # Net margin (higher is better)
        if stock_metrics.get('net_margin') and universe_metrics.get('net_margin'):
            margin_rank = percentile_rank(
                stock_metrics['net_margin'],
                universe_metrics['net_margin']
            )
            if margin_rank is not None:
                ranks.append(margin_rank)
                self.logger.debug(f"Net margin rank: {margin_rank}")

        # Operating margin (higher is better)
        if stock_metrics.get('operating_margin') and universe_metrics.get('operating_margin'):
            op_margin_rank = percentile_rank(
                stock_metrics['operating_margin'],
                universe_metrics['operating_margin']
            )
            if op_margin_rank is not None:
                ranks.append(op_margin_rank)
                self.logger.debug(f"Operating margin rank: {op_margin_rank}")

        # Gross margin (higher is better)
        if stock_metrics.get('gross_margin') and universe_metrics.get('gross_margin'):
            gross_margin_rank = percentile_rank(
                stock_metrics['gross_margin'],
                universe_metrics['gross_margin']
            )
            if gross_margin_rank is not None:
                ranks.append(gross_margin_rank)
                self.logger.debug(f"Gross margin rank: {gross_margin_rank}")

        # Calculate average of available ranks
        if len(ranks) == 0:
            self.logger.warning("No valid quality metrics available")
            return None

        quality_score = average_percentile_ranks(ranks)
        self.logger.info(f"Quality score: {quality_score} (from {len(ranks)} metrics)")

        return quality_score

    def calculate_growth_score(
        self,
        stock_metrics: Dict[str, float],
        universe_metrics: Dict[str, List[float]]
    ) -> Optional[float]:
        """
        Calculate growth component score.

        Framework Section 3.2: Growth Component (34% of Fundamental)

        Metrics (percentile-ranked):
        1. Revenue growth YoY (higher is better)
        2. EPS growth YoY (higher is better)
        3. FCF growth (higher is better)

        Note: 3-year CAGR not implemented yet (requires historical data)

        Args:
            stock_metrics: Dict with stock's growth metrics
            universe_metrics: Dict with lists of all universe values for each metric

        Returns:
            Growth score (0-100 percentile), or None if insufficient data
        """
        ranks = []

        # Revenue growth YoY (higher is better)
        if stock_metrics.get('revenue_growth') and universe_metrics.get('revenue_growth'):
            rev_growth_rank = percentile_rank(
                stock_metrics['revenue_growth'],
                universe_metrics['revenue_growth']
            )
            if rev_growth_rank is not None:
                ranks.append(rev_growth_rank)
                self.logger.debug(f"Revenue growth rank: {rev_growth_rank}")

        # EPS growth YoY (higher is better)
        if stock_metrics.get('earnings_growth') and universe_metrics.get('earnings_growth'):
            eps_growth_rank = percentile_rank(
                stock_metrics['earnings_growth'],
                universe_metrics['earnings_growth']
            )
            if eps_growth_rank is not None:
                ranks.append(eps_growth_rank)
                self.logger.debug(f"EPS growth rank: {eps_growth_rank}")

        # FCF growth (higher is better)
        if stock_metrics.get('fcf_growth') and universe_metrics.get('fcf_growth'):
            fcf_growth_rank = percentile_rank(
                stock_metrics['fcf_growth'],
                universe_metrics['fcf_growth']
            )
            if fcf_growth_rank is not None:
                ranks.append(fcf_growth_rank)
                self.logger.debug(f"FCF growth rank: {fcf_growth_rank}")

        # Calculate average of available ranks
        if len(ranks) == 0:
            self.logger.warning("No valid growth metrics available")
            return None

        growth_score = average_percentile_ranks(ranks)
        self.logger.info(f"Growth score: {growth_score} (from {len(ranks)} metrics)")

        return growth_score

    def calculate_fundamental_score(
        self,
        stock_metrics: Dict[str, float],
        universe_metrics: Dict[str, List[float]]
    ) -> Dict[str, Optional[float]]:
        """
        Calculate complete fundamental pillar score.

        Framework Section 3.3:
        Fundamental Score = (Value × 0.33) + (Quality × 0.33) + (Growth × 0.34)

        Args:
            stock_metrics: Dict with all fundamental metrics for the stock
            universe_metrics: Dict with lists of all universe values for each metric

        Returns:
            Dict with:
            - value_score: Value component score (0-100)
            - quality_score: Quality component score (0-100)
            - growth_score: Growth component score (0-100)
            - fundamental_score: Composite fundamental score (0-100)
        """
        # Calculate sub-components
        value_score = self.calculate_value_score(stock_metrics, universe_metrics)
        quality_score = self.calculate_quality_score(stock_metrics, universe_metrics)
        growth_score = self.calculate_growth_score(stock_metrics, universe_metrics)

        # Calculate composite fundamental score
        sub_scores = []
        weights = []

        if value_score is not None:
            sub_scores.append(value_score)
            weights.append(self.VALUE_WEIGHT)

        if quality_score is not None:
            sub_scores.append(quality_score)
            weights.append(self.QUALITY_WEIGHT)

        if growth_score is not None:
            sub_scores.append(growth_score)
            weights.append(self.GROWTH_WEIGHT)

        # Calculate weighted average (weights will be auto-normalized)
        if len(sub_scores) == 0:
            self.logger.error("No fundamental sub-components available")
            fundamental_score = None
        else:
            fundamental_score = average_percentile_ranks(sub_scores, weights)
            self.logger.info(
                f"Fundamental score: {fundamental_score} "
                f"(Value: {value_score}, Quality: {quality_score}, Growth: {growth_score})"
            )

        return {
            'value_score': value_score,
            'quality_score': quality_score,
            'growth_score': growth_score,
            'fundamental_score': fundamental_score
        }


def extract_fundamental_metrics_from_db(fundamental_data_row) -> Dict[str, float]:
    """
    Extract fundamental metrics from database row.

    Args:
        fundamental_data_row: SQLAlchemy FundamentalData model instance

    Returns:
        Dict with metric names and values
    """
    return {
        'pe_ratio': fundamental_data_row.pe_ratio,
        'pb_ratio': fundamental_data_row.pb_ratio,
        'ps_ratio': fundamental_data_row.ps_ratio,
        'ev_ebitda': fundamental_data_row.ev_to_ebitda,
        'dividend_yield': fundamental_data_row.dividend_yield,
        'roe': fundamental_data_row.roe,
        'roa': fundamental_data_row.roa,
        'net_margin': fundamental_data_row.net_margin,
        'operating_margin': fundamental_data_row.operating_margin,
        'gross_margin': fundamental_data_row.gross_margin,
        'revenue_growth': fundamental_data_row.revenue_growth,
        'earnings_growth': fundamental_data_row.earnings_growth,
        'fcf_growth': fundamental_data_row.fcf_growth
    }
