"""
Composite scoring models.

This module combines individual pillar scores (fundamental, technical, sentiment)
into final composite scores and recommendations.

Framework Reference: Section 1.3, Section 7
"""

from .composite import CompositeScoreCalculator

__all__ = ['CompositeScoreCalculator']
