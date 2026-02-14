"""
Override Data Models

Framework Reference: Section 6.2, 6.4, 6.5
Data structures for override requests, results, and documentation.

Author: Stock Analysis Framework v2.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class OverrideType(Enum):
    """Type of override applied. Framework Section 6.2."""
    WEIGHT_ADJUSTMENT = "weight_adjustment"
    SENTIMENT_ADJUSTMENT = "sentiment_adjustment"
    BOTH = "both"
    NONE = "none"


class ConvictionLevel(Enum):
    """Conviction level for override justification. Framework Section 6.4."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


@dataclass
class WeightOverride:
    """Weight adjustment specification.

    Framework Section 6.2: Permissible ranges:
    - Fundamental: 35-55% (base 45%, +/-10%)
    - Technical: 25-45% (base 35%, +/-10%)
    - Sentiment: 10-30% (base 20%, +/-10%)
    Must sum to 100%.
    """
    fundamental_weight: float  # 0.35 - 0.55
    technical_weight: float    # 0.25 - 0.45
    sentiment_weight: float    # 0.10 - 0.30


@dataclass
class SentimentOverride:
    """Sentiment score adjustment specification.

    Framework Section 6.2: Adjust base sentiment by +/-15 points max.
    """
    adjustment: float  # -15.0 to +15.0


@dataclass
class OverrideDocumentation:
    """Mandatory documentation for every override.

    Framework Section 6.4: No override without documentation.
    All three reasoning fields are REQUIRED.
    """
    what_model_misses: str       # Specific info the model cannot capture
    why_view_more_accurate: str  # Evidence supporting the override
    what_proves_wrong: str       # Falsification criteria
    conviction: ConvictionLevel
    additional_notes: Optional[str] = None
    evidence_pieces: Optional[List[str]] = None  # Required if extreme override (>15pt)


@dataclass
class OverrideRequest:
    """Complete override request for a single stock.

    Framework Section 6: Combines override type, adjustments, and documentation.
    """
    ticker: str
    override_type: OverrideType
    weight_override: Optional[WeightOverride] = None
    sentiment_override: Optional[SentimentOverride] = None
    documentation: Optional[OverrideDocumentation] = None
    current_price: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class OverrideResult:
    """Result of applying an override, with before/after comparison.

    Contains all data needed for the override log (Section 6.4)
    and quarterly review (Section 8).
    """
    ticker: str
    timestamp: datetime
    override_type: OverrideType

    # Base model output (before override)
    base_fundamental_score: float
    base_technical_score: float
    base_sentiment_score: float
    base_weights: Dict[str, float]
    base_composite_score: float
    base_composite_percentile: float
    base_recommendation: str

    # Override details
    adjusted_weights: Optional[Dict[str, float]] = None
    adjusted_sentiment: Optional[float] = None

    # After override
    final_composite_score: float = 0.0
    final_composite_percentile: float = 0.0
    final_recommendation: str = ""

    # Impact analysis
    percentile_impact: float = 0.0
    recommendation_changed: bool = False

    # Guardrail flags
    extreme_override: bool = False
    guardrail_violations: List[str] = field(default_factory=list)

    # Documentation
    documentation: Optional[OverrideDocumentation] = None
    current_price: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Handles nested dataclasses, Enums, and datetime objects.
        """
        def _serialize(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, Enum):
                return obj.value
            if hasattr(obj, '__dataclass_fields__'):
                return {k: _serialize(v) for k, v in obj.__dict__.items()}
            if isinstance(obj, list):
                return [_serialize(item) for item in obj]
            if isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            return obj

        return {
            "ticker": self.ticker,
            "timestamp": self.timestamp.isoformat(),
            "override_type": self.override_type.value,
            "base_model": {
                "fundamental_score": self.base_fundamental_score,
                "technical_score": self.base_technical_score,
                "sentiment_score": self.base_sentiment_score,
                "weights": self.base_weights,
                "composite_score": self.base_composite_score,
                "composite_percentile": self.base_composite_percentile,
                "recommendation": self.base_recommendation,
            },
            "override": {
                "adjusted_weights": self.adjusted_weights,
                "adjusted_sentiment": self.adjusted_sentiment,
            },
            "result": {
                "final_composite_score": self.final_composite_score,
                "final_composite_percentile": self.final_composite_percentile,
                "final_recommendation": self.final_recommendation,
                "percentile_impact": self.percentile_impact,
                "recommendation_changed": self.recommendation_changed,
                "extreme_override": self.extreme_override,
                "guardrail_violations": self.guardrail_violations,
            },
            "documentation": _serialize(self.documentation) if self.documentation else None,
            "current_price": self.current_price,
        }
