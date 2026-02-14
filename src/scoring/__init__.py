"""
Scoring module - reusable scoring pipeline for stock analysis.

Provides ScoringPipeline class that orchestrates the complete workflow:
data loading -> pillar scoring -> composite scoring -> persistence.
"""

from .pipeline import ScoringPipeline

__all__ = ['ScoringPipeline']
