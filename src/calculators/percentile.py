"""
Percentile Ranking Engine

Framework Reference: Section 1.2, Appendix A
Purpose: Convert raw metric values to percentile ranks within universe

Key Principle: ALL scores are percentile-based (0-100), never linear scaling.
This approach is robust to outliers and handles skewed distributions naturally.

Research Support: Gu, Kelly & Xiu (2020) - nonlinear predictor interactions
achieve Sharpe ratios of 1.35-1.45 vs 0.61 for linear models.
"""

import numpy as np
from typing import List, Optional, Union
import logging

logger = logging.getLogger(__name__)


def percentile_rank(
    value: float,
    universe: List[float],
    exclude_self: bool = False
) -> Optional[float]:
    """
    Calculate percentile rank of value within universe.

    For metrics where HIGHER is BETTER (e.g., ROE, revenue growth, margins).

    Framework Section 1.2: A stock at 85th percentile means it's better
    than 85% of the universe.

    Args:
        value: The value to rank
        universe: List of all values in the universe (including value itself)
        exclude_self: If True, exclude the value itself from comparison
                     (useful when value is already in universe)

    Returns:
        Percentile rank (0-100), or None if inputs are invalid

    Example:
        >>> universe = [10, 20, 30, 40, 50]
        >>> percentile_rank(35, universe)
        60.0  # Better than 60% of universe (3 out of 5 values are lower)
    """
    # Validate inputs
    if value is None or np.isnan(value):
        logger.warning("Cannot rank None or NaN value")
        return None

    if not universe or len(universe) == 0:
        logger.warning("Cannot rank with empty universe")
        return None

    # Convert to numpy array and filter out None/NaN values
    universe_array = np.array([v for v in universe if v is not None and not np.isnan(v)])

    if len(universe_array) == 0:
        logger.warning("Universe contains only None/NaN values")
        return None

    # If excluding self, remove the value from universe
    if exclude_self:
        universe_array = universe_array[universe_array != value]

    if len(universe_array) == 0:
        logger.warning("Universe is empty after excluding self")
        return 50.0  # Neutral rank if alone

    # Calculate percentile rank
    # Count how many values are LESS than the target value
    count_below = np.sum(universe_array < value)
    total_count = len(universe_array)

    rank = (count_below / total_count) * 100

    return round(rank, 2)


def percentile_rank_inverted(
    value: float,
    universe: List[float],
    exclude_self: bool = False
) -> Optional[float]:
    """
    Calculate percentile rank of value within universe (inverted).

    For metrics where LOWER is BETTER (e.g., P/E, P/B, debt-to-equity).

    Framework Section 1.2: A stock at 85th percentile for P/E means it's
    CHEAPER than 85% of the universe (lower P/E = better).

    Args:
        value: The value to rank
        universe: List of all values in the universe (including value itself)
        exclude_self: If True, exclude the value itself from comparison

    Returns:
        Percentile rank (0-100), or None if inputs are invalid

    Example:
        >>> universe = [10, 20, 30, 40, 50]
        >>> percentile_rank_inverted(15, universe)
        80.0  # Better than 80% (only 1 value is lower, 4 are higher)
    """
    # Validate inputs
    if value is None or np.isnan(value):
        logger.warning("Cannot rank None or NaN value")
        return None

    if not universe or len(universe) == 0:
        logger.warning("Cannot rank with empty universe")
        return None

    # Convert to numpy array and filter out None/NaN values
    universe_array = np.array([v for v in universe if v is not None and not np.isnan(v)])

    if len(universe_array) == 0:
        logger.warning("Universe contains only None/NaN values")
        return None

    # If excluding self, remove the value from universe
    if exclude_self:
        universe_array = universe_array[universe_array != value]

    if len(universe_array) == 0:
        logger.warning("Universe is empty after excluding self")
        return 50.0  # Neutral rank if alone

    # Calculate inverted percentile rank
    # Count how many values are GREATER than the target value
    count_above = np.sum(universe_array > value)
    total_count = len(universe_array)

    rank = (count_above / total_count) * 100

    return round(rank, 2)


def rank_universe(
    values: List[Optional[float]],
    inverted: bool = False
) -> List[Optional[float]]:
    """
    Rank all values in a universe, returning percentile ranks.

    Useful for batch ranking all stocks in the universe for a single metric.

    Args:
        values: List of values to rank (can contain None)
        inverted: If True, use inverted ranking (lower is better)

    Returns:
        List of percentile ranks (same length as values), with None for invalid inputs

    Example:
        >>> values = [10, 20, None, 30, 40]
        >>> rank_universe(values)
        [0.0, 25.0, None, 50.0, 75.0]
    """
    if not values:
        return []

    # Filter out None values for ranking
    valid_values = [v for v in values if v is not None and not np.isnan(v)]

    if len(valid_values) == 0:
        return [None] * len(values)

    # Rank each value
    ranks = []
    rank_func = percentile_rank_inverted if inverted else percentile_rank

    for value in values:
        if value is None or np.isnan(value):
            ranks.append(None)
        else:
            rank = rank_func(value, valid_values, exclude_self=True)
            ranks.append(rank)

    return ranks


def average_percentile_ranks(
    ranks: List[Optional[float]],
    weights: Optional[List[float]] = None
) -> Optional[float]:
    """
    Calculate weighted average of percentile ranks.

    Framework Section 3-5: Pillar scores are weighted averages of
    sub-component percentile ranks.

    Args:
        ranks: List of percentile ranks (0-100), can contain None
        weights: Optional weights for each rank (must sum to 1.0)
                If None, uses equal weighting

    Returns:
        Weighted average percentile rank, or None if no valid ranks

    Example:
        >>> ranks = [78, 82, 71, None, 65]
        >>> average_percentile_ranks(ranks)
        74.0  # Average of 4 valid ranks

        >>> average_percentile_ranks([78, 82, 71], weights=[0.5, 0.3, 0.2])
        77.6  # Weighted average
    """
    # Filter out None values
    valid_ranks = [(r, w) for r, w in zip(ranks, weights or [1.0] * len(ranks))
                   if r is not None and not np.isnan(r)]

    if len(valid_ranks) == 0:
        logger.warning("No valid ranks to average")
        return None

    # Extract ranks and weights
    ranks_array = np.array([r for r, w in valid_ranks])
    weights_array = np.array([w for r, w in valid_ranks])

    # Normalize weights to sum to 1.0
    weights_normalized = weights_array / np.sum(weights_array)

    # Calculate weighted average
    avg = np.sum(ranks_array * weights_normalized)

    return round(avg, 2)


def validate_percentile_score(score: Optional[float]) -> bool:
    """
    Validate that a score is a valid percentile (0-100).

    Args:
        score: The score to validate

    Returns:
        True if valid, False otherwise
    """
    if score is None:
        return False

    if np.isnan(score):
        return False

    if score < 0 or score > 100:
        logger.error(f"Invalid percentile score: {score} (must be 0-100)")
        return False

    return True


def handle_missing_data(
    value: Optional[float],
    universe: List[float],
    strategy: str = "skip"
) -> Optional[float]:
    """
    Handle missing data when calculating percentile ranks.

    Framework Best Practice: Document how each metric handles missing data.

    Args:
        value: The value to rank (may be None)
        universe: List of universe values
        strategy: How to handle missing data:
                 - "skip": Return None (default)
                 - "median": Use median of universe
                 - "neutral": Return 50.0 (neutral percentile)

    Returns:
        Value to use for ranking, or None if should be skipped
    """
    if value is not None and not np.isnan(value):
        return value

    if strategy == "skip":
        return None
    elif strategy == "median":
        valid_values = [v for v in universe if v is not None and not np.isnan(v)]
        if valid_values:
            return np.median(valid_values)
        return None
    elif strategy == "neutral":
        return 50.0
    else:
        logger.warning(f"Unknown missing data strategy: {strategy}")
        return None
