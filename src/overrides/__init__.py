"""
Override System Module

Framework Reference: Section 6 (Model-First Override System)
Implements weight adjustment and sentiment score adjustment overrides
with mandatory documentation, guardrails, and logging.
"""

from .models import (
    ConvictionLevel,
    OverrideDocumentation,
    OverrideRequest,
    OverrideResult,
    OverrideType,
    SentimentOverride,
    WeightOverride,
)
from .override_logger import OverrideLogger
from .override_manager import OverrideManager, OverrideValidationError

__all__ = [
    'ConvictionLevel',
    'OverrideDocumentation',
    'OverrideLogger',
    'OverrideManager',
    'OverrideRequest',
    'OverrideResult',
    'OverrideType',
    'OverrideValidationError',
    'SentimentOverride',
    'WeightOverride',
]
