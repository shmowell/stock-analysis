"""Backtesting framework for stock analysis model validation.

Framework Reference: Section 10, Phase 4-5 (Backtesting & Paper Trading)
"""

from .indicator_builder import IndicatorBuilder
from .snapshot_manager import SnapshotManager

__all__ = ['IndicatorBuilder', 'SnapshotManager']
