"""
Override Manager - Core override logic with guardrail enforcement.

Framework Reference: Section 6 (Model-First Override System)

Implements the two-phase process:
1. Base model calculates objective scores (already done by CompositeScoreCalculator)
2. Override system validates and applies human adjustments with guardrails

Guardrails enforced:
- Weight adjustment: +/-10% per pillar, must sum to 100%
- Sentiment adjustment: +/-15 points
- Weight impact: max +/-10 percentile points
- Sentiment impact: max +/-3 percentile points
- Combined impact: max +/-12 percentile points
- Extreme override (>15 pts): requires HIGH conviction + 3 evidence pieces
- Forbidden: SELL->BUY or BUY->SELL without HIGH conviction

Author: Stock Analysis Framework v2.0
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from src.models.composite import CompositeScore, CompositeScoreCalculator, Recommendation
from .models import (
    ConvictionLevel,
    OverrideDocumentation,
    OverrideRequest,
    OverrideResult,
    OverrideType,
    SentimentOverride,
    WeightOverride,
)

logger = logging.getLogger(__name__)


class OverrideValidationError(Exception):
    """Raised when an override request fails validation."""
    pass


class OverrideManager:
    """Manages override application and guardrail enforcement.

    Framework Reference: Section 6.2, 6.5
    """

    # Base weights from Framework Section 1.3
    BASE_WEIGHTS = {
        'fundamental': 0.45,
        'technical': 0.35,
        'sentiment': 0.20,
    }

    # Permissible weight ranges (Framework Section 6.2)
    WEIGHT_RANGES = {
        'fundamental': (0.35, 0.55),
        'technical': (0.25, 0.45),
        'sentiment': (0.10, 0.30),
    }

    def __init__(self, config_path: Optional[str] = None):
        """Initialize OverrideManager with config from settings.yaml.

        Args:
            config_path: Path to settings.yaml. If None, uses default location.
        """
        self.config = self._load_config(config_path)

        # Override limits from config (Framework Section 6.5)
        limits = self.config.get('override_limits', {})
        self.max_weight_adjustment = limits.get('weight_adjustment', 0.10)
        self.max_sentiment_adjustment = limits.get('sentiment_adjustment', 15)
        self.max_composite_impact = limits.get('max_composite_impact', 12)
        self.extreme_override_threshold = limits.get('extreme_override_threshold', 15)

        # Impact sub-limits (Framework Section 6.5 item 1)
        self.max_weight_impact = 10   # Max ±10 percentile points for weight-only
        self.max_sentiment_impact = 3  # Max ±3 percentile points for sentiment-only

        self._calculator = CompositeScoreCalculator()

    def _load_config(self, config_path: Optional[str] = None) -> dict:
        """Load configuration from settings.yaml."""
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / 'config' / 'settings.yaml'
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Config file not found at {config_path}, using defaults")
            return {}

    def validate_override_request(self, request: OverrideRequest) -> List[str]:
        """Validate an override request against all guardrails.

        Framework Section 6.5: Override Guardrails

        Args:
            request: The override request to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # No-op override needs no validation
        if request.override_type == OverrideType.NONE:
            return errors

        # Documentation is mandatory for all non-NONE overrides (Section 6.4)
        if request.documentation is None:
            errors.append("Documentation is required for all overrides (Section 6.4)")
        else:
            errors.extend(self.validate_documentation(request.documentation))

        # Validate override type matches provided data
        if request.override_type in (OverrideType.WEIGHT_ADJUSTMENT, OverrideType.BOTH):
            if request.weight_override is None:
                errors.append("Weight override data required for weight adjustment type")
            else:
                errors.extend(self.validate_weight_override(request.weight_override))

        if request.override_type in (OverrideType.SENTIMENT_ADJUSTMENT, OverrideType.BOTH):
            if request.sentiment_override is None:
                errors.append("Sentiment override data required for sentiment adjustment type")
            else:
                errors.extend(self.validate_sentiment_override(request.sentiment_override))

        return errors

    def validate_weight_override(self, weight_override: WeightOverride) -> List[str]:
        """Validate weight adjustment against permissible ranges.

        Framework Section 6.2:
        - Fundamental: 35-55%
        - Technical: 25-45%
        - Sentiment: 10-30%
        - Must sum to 100%

        Args:
            weight_override: Weight adjustment to validate

        Returns:
            List of validation error messages
        """
        errors = []
        weights = {
            'fundamental': weight_override.fundamental_weight,
            'technical': weight_override.technical_weight,
            'sentiment': weight_override.sentiment_weight,
        }

        for pillar, value in weights.items():
            min_val, max_val = self.WEIGHT_RANGES[pillar]
            if value < min_val or value > max_val:
                errors.append(
                    f"{pillar.capitalize()} weight {value:.2f} outside "
                    f"permissible range [{min_val:.2f}, {max_val:.2f}]"
                )

        # Check sum to 1.0
        total = sum(weights.values())
        if not (0.999 <= total <= 1.001):
            errors.append(
                f"Weights must sum to 1.0, got {total:.4f} "
                f"(F: {weights['fundamental']}, T: {weights['technical']}, "
                f"S: {weights['sentiment']})"
            )

        return errors

    def validate_sentiment_override(self, sentiment_override: SentimentOverride) -> List[str]:
        """Validate sentiment score adjustment.

        Framework Section 6.2: +/-15 points maximum.

        Args:
            sentiment_override: Sentiment adjustment to validate

        Returns:
            List of validation error messages
        """
        errors = []
        adj = sentiment_override.adjustment

        if abs(adj) > self.max_sentiment_adjustment:
            errors.append(
                f"Sentiment adjustment {adj:+.1f} exceeds "
                f"±{self.max_sentiment_adjustment} limit"
            )

        return errors

    def validate_documentation(self, doc: OverrideDocumentation) -> List[str]:
        """Validate override documentation is complete.

        Framework Section 6.4: All three reasoning fields are REQUIRED.

        Args:
            doc: Override documentation to validate

        Returns:
            List of validation error messages
        """
        errors = []

        if not doc.what_model_misses or not doc.what_model_misses.strip():
            errors.append("Documentation required: 'What does the model miss?'")

        if not doc.why_view_more_accurate or not doc.why_view_more_accurate.strip():
            errors.append("Documentation required: 'Why is your view more accurate?'")

        if not doc.what_proves_wrong or not doc.what_proves_wrong.strip():
            errors.append("Documentation required: 'What would prove you wrong?'")

        return errors

    def apply_override(
        self,
        composite_score: CompositeScore,
        request: OverrideRequest,
        universe_scores: List[CompositeScore],
    ) -> OverrideResult:
        """Apply an override to a composite score.

        Framework Section 6, Section 7.1:
        1. Validate the override request
        2. Apply weight/sentiment adjustments
        3. Recalculate composite and percentile
        4. Check guardrails and forbidden overrides
        5. Return OverrideResult with before/after comparison

        Args:
            composite_score: The base CompositeScore for this stock
            request: The override request with adjustments and documentation
            universe_scores: All CompositeScore objects in the universe
                            (needed to recalculate percentile rank)

        Returns:
            OverrideResult with before/after comparison

        Raises:
            OverrideValidationError: If override request is invalid
        """
        logger.info(f"Applying override for {request.ticker} (type: {request.override_type.value})")

        # Step 1: Validate
        errors = self.validate_override_request(request)
        if errors:
            raise OverrideValidationError(
                f"Override validation failed for {request.ticker}: " +
                "; ".join(errors)
            )

        # Base values
        base_weights = dict(self.BASE_WEIGHTS)
        fundamental = composite_score.fundamental_score
        technical = composite_score.technical_score
        sentiment = composite_score.sentiment_score

        # Step 2: Determine effective weights
        effective_weights = dict(base_weights)
        adjusted_weights_dict = None
        if request.weight_override is not None:
            effective_weights = {
                'fundamental': request.weight_override.fundamental_weight,
                'technical': request.weight_override.technical_weight,
                'sentiment': request.weight_override.sentiment_weight,
            }
            adjusted_weights_dict = dict(effective_weights)

        # Step 3: Determine effective sentiment
        effective_sentiment = sentiment
        adjusted_sentiment_value = None
        if request.sentiment_override is not None:
            effective_sentiment = sentiment + request.sentiment_override.adjustment
            # Clamp to [0, 100]
            effective_sentiment = max(0.0, min(100.0, effective_sentiment))
            adjusted_sentiment_value = effective_sentiment

        # Step 4: Recalculate composite
        new_composite = self._recalculate_composite(
            fundamental, technical, effective_sentiment, effective_weights
        )

        # Step 5: Recalculate percentile within universe
        new_percentile = self._recalculate_percentile(
            new_composite, universe_scores, composite_score.ticker
        )

        # Step 6: New recommendation
        new_recommendation = Recommendation.from_percentile(new_percentile)

        # Step 7-9: Check guardrails
        percentile_impact = new_percentile - composite_score.composite_percentile
        guardrail_violations = []

        # Impact guardrails
        _, impact_violations = self.check_impact_guardrails(
            composite_score.composite_percentile,
            new_percentile,
            request.override_type,
        )
        guardrail_violations.extend(impact_violations)

        # Forbidden override check
        is_forbidden, forbidden_reason = self.check_forbidden_override(
            composite_score.recommendation,
            new_recommendation,
            request.documentation.conviction if request.documentation else ConvictionLevel.LOW,
        )
        if is_forbidden:
            guardrail_violations.append(forbidden_reason)

        # Extreme override check
        is_extreme, extreme_warning = self.check_extreme_override(
            abs(percentile_impact),
            request.documentation,
        )

        recommendation_changed = (
            composite_score.recommendation.value != new_recommendation.value
        )

        if guardrail_violations:
            logger.warning(
                f"Override for {request.ticker} has guardrail violations: "
                f"{guardrail_violations}"
            )

        result = OverrideResult(
            ticker=request.ticker,
            timestamp=request.timestamp,
            override_type=request.override_type,
            base_fundamental_score=fundamental,
            base_technical_score=technical,
            base_sentiment_score=sentiment,
            base_weights=base_weights,
            base_composite_score=composite_score.composite_score,
            base_composite_percentile=composite_score.composite_percentile,
            base_recommendation=composite_score.recommendation.value,
            adjusted_weights=adjusted_weights_dict,
            adjusted_sentiment=adjusted_sentiment_value,
            final_composite_score=new_composite,
            final_composite_percentile=new_percentile,
            final_recommendation=new_recommendation.value,
            percentile_impact=percentile_impact,
            recommendation_changed=recommendation_changed,
            extreme_override=is_extreme,
            guardrail_violations=guardrail_violations,
            documentation=request.documentation,
            current_price=request.current_price,
        )

        logger.info(
            f"Override applied for {request.ticker}: "
            f"percentile {composite_score.composite_percentile:.1f} -> {new_percentile:.1f} "
            f"({percentile_impact:+.1f}), recommendation: "
            f"{composite_score.recommendation.value} -> {new_recommendation.value}"
        )

        return result

    def _recalculate_composite(
        self,
        fundamental_score: float,
        technical_score: float,
        sentiment_score: float,
        weights: Dict[str, float],
    ) -> float:
        """Recalculate composite score with override weights/sentiment.

        Framework Section 7.1:
        Final Composite = (Fundamental x Weight_F) +
                          (Technical x Weight_T) +
                          (Adjusted_Sentiment x Weight_S)

        Args:
            fundamental_score: Fundamental pillar score (0-100)
            technical_score: Technical pillar score (0-100)
            sentiment_score: Sentiment score (may be adjusted)
            weights: Weight dict with fundamental/technical/sentiment keys

        Returns:
            Recalculated composite score
        """
        return (
            fundamental_score * weights['fundamental'] +
            technical_score * weights['technical'] +
            sentiment_score * weights['sentiment']
        )

    def _recalculate_percentile(
        self,
        new_composite: float,
        universe_scores: List[CompositeScore],
        exclude_ticker: str,
    ) -> float:
        """Recalculate percentile rank after override.

        Ranks the overridden stock's new composite score against the
        rest of the universe (which remains unchanged).

        Args:
            new_composite: New composite score after override
            universe_scores: All universe CompositeScore objects
            exclude_ticker: Ticker being overridden (replaced with new score)

        Returns:
            New percentile rank (0-100)
        """
        # Build universe of composite scores, replacing the target ticker
        all_composites = []
        for score in universe_scores:
            if score.ticker == exclude_ticker:
                all_composites.append(new_composite)
            else:
                all_composites.append(score.composite_score)

        return self._calculator.calculate_percentile_rank(new_composite, all_composites)

    def check_impact_guardrails(
        self,
        base_percentile: float,
        final_percentile: float,
        override_type: OverrideType,
    ) -> Tuple[bool, List[str]]:
        """Check if override impact exceeds guardrail limits.

        Framework Section 6.5:
        - Weight adjustment alone: max ±10 percentile impact
        - Sentiment adjustment alone: max ±3 percentile impact
        - Combined: max ±12 percentile impact

        Args:
            base_percentile: Original percentile before override
            final_percentile: New percentile after override
            override_type: Type of override applied

        Returns:
            Tuple of (passes_guardrails: bool, violations: List[str])
        """
        impact = abs(final_percentile - base_percentile)
        violations = []

        if override_type == OverrideType.WEIGHT_ADJUSTMENT:
            if impact > self.max_weight_impact:
                violations.append(
                    f"Weight override impact ({impact:.1f}pt) exceeds "
                    f"±{self.max_weight_impact}pt limit"
                )
        elif override_type == OverrideType.SENTIMENT_ADJUSTMENT:
            if impact > self.max_sentiment_impact:
                violations.append(
                    f"Sentiment override impact ({impact:.1f}pt) exceeds "
                    f"±{self.max_sentiment_impact}pt limit"
                )
        elif override_type == OverrideType.BOTH:
            if impact > self.max_composite_impact:
                violations.append(
                    f"Combined override impact ({impact:.1f}pt) exceeds "
                    f"±{self.max_composite_impact}pt limit"
                )

        passes = len(violations) == 0
        return passes, violations

    def check_forbidden_override(
        self,
        base_recommendation: Recommendation,
        final_recommendation: Recommendation,
        conviction: ConvictionLevel,
    ) -> Tuple[bool, Optional[str]]:
        """Check for forbidden recommendation transitions.

        Framework Section 6.5 item 4:
        - Cannot override from SELL to BUY (or vice versa) without
          HIGH conviction.

        Args:
            base_recommendation: Original recommendation
            final_recommendation: New recommendation after override
            conviction: Conviction level from documentation

        Returns:
            Tuple of (is_forbidden: bool, reason: Optional[str])
        """
        # Define opposing pairs that require HIGH conviction
        opposing_pairs = {
            (Recommendation.SELL, Recommendation.BUY),
            (Recommendation.SELL, Recommendation.STRONG_BUY),
            (Recommendation.STRONG_SELL, Recommendation.BUY),
            (Recommendation.STRONG_SELL, Recommendation.STRONG_BUY),
            (Recommendation.BUY, Recommendation.SELL),
            (Recommendation.BUY, Recommendation.STRONG_SELL),
            (Recommendation.STRONG_BUY, Recommendation.SELL),
            (Recommendation.STRONG_BUY, Recommendation.STRONG_SELL),
        }

        pair = (base_recommendation, final_recommendation)
        if pair in opposing_pairs:
            if conviction != ConvictionLevel.HIGH:
                return True, (
                    f"Forbidden override: {base_recommendation.value} -> "
                    f"{final_recommendation.value} requires HIGH conviction "
                    f"(current: {conviction.value})"
                )
            else:
                logger.warning(
                    f"Extreme recommendation change: {base_recommendation.value} -> "
                    f"{final_recommendation.value} (allowed with HIGH conviction)"
                )

        return False, None

    def check_extreme_override(
        self,
        percentile_impact: float,
        documentation: Optional[OverrideDocumentation],
    ) -> Tuple[bool, Optional[str]]:
        """Check if override is extreme and has sufficient evidence.

        Framework Section 6.5 item 2:
        - If final score differs by >15 percentiles -> REQUIRES HIGH CONVICTION
        - Must document 3 specific pieces of evidence

        Args:
            percentile_impact: Absolute percentile change
            documentation: Override documentation

        Returns:
            Tuple of (is_extreme: bool, warning: Optional[str])
        """
        if percentile_impact <= self.extreme_override_threshold:
            return False, None

        # It's extreme — check requirements
        warnings = []
        if documentation is None or documentation.conviction != ConvictionLevel.HIGH:
            warnings.append(
                f"Extreme override ({percentile_impact:.1f}pt) requires HIGH conviction"
            )

        evidence_count = len(documentation.evidence_pieces) if (
            documentation and documentation.evidence_pieces
        ) else 0
        if evidence_count < 3:
            warnings.append(
                f"Extreme override requires 3+ evidence pieces (have {evidence_count})"
            )

        warning_str = "; ".join(warnings) if warnings else None
        if warning_str:
            logger.warning(f"Extreme override: {warning_str}")

        return True, warning_str
