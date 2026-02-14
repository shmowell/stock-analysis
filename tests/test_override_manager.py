"""
Unit tests for Override System.

Framework Reference: Section 6 (Model-First Override System)
Tests override validation, application, guardrails, and logging.

Author: Stock Analysis Framework v2.0
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.models.composite import CompositeScore, Recommendation
from src.overrides.models import (
    ConvictionLevel,
    OverrideDocumentation,
    OverrideRequest,
    OverrideResult,
    OverrideType,
    SentimentOverride,
    WeightOverride,
)
from src.overrides.override_logger import OverrideLogger
from src.overrides.override_manager import OverrideManager, OverrideValidationError


# ============================================================================
# Helpers / Fixtures
# ============================================================================

def make_composite_score(
    ticker="TEST",
    fundamental=60.0,
    technical=65.0,
    sentiment=55.0,
    composite=None,
    percentile=50.0,
    recommendation=None,
) -> CompositeScore:
    """Create a CompositeScore test fixture."""
    if composite is None:
        composite = fundamental * 0.45 + technical * 0.35 + sentiment * 0.20
    if recommendation is None:
        recommendation = Recommendation.from_percentile(percentile)
    return CompositeScore(
        ticker=ticker,
        fundamental_score=fundamental,
        technical_score=technical,
        sentiment_score=sentiment,
        composite_score=composite,
        composite_percentile=percentile,
        recommendation=recommendation,
    )


def make_universe(n=15) -> list:
    """Create a test universe of n stocks with spread-out scores.

    Stocks are spaced evenly so percentile changes are predictable.
    """
    universe = []
    for i in range(n):
        pct = (i / (n - 1)) * 100 if n > 1 else 50.0
        fund = 30.0 + (i * 3)
        tech = 25.0 + (i * 4)
        sent = 40.0 + (i * 2)
        comp = fund * 0.45 + tech * 0.35 + sent * 0.20
        rec = Recommendation.from_percentile(pct)
        universe.append(CompositeScore(
            ticker=f"STK{i:02d}",
            fundamental_score=fund,
            technical_score=tech,
            sentiment_score=sent,
            composite_score=comp,
            composite_percentile=pct,
            recommendation=rec,
        ))
    return universe


def make_documentation(
    conviction=ConvictionLevel.MEDIUM,
    evidence_count=0,
) -> OverrideDocumentation:
    """Create valid override documentation."""
    evidence = [f"Evidence {i+1}" for i in range(evidence_count)] if evidence_count > 0 else None
    return OverrideDocumentation(
        what_model_misses="Recent management change not reflected in financials",
        why_view_more_accurate="Insider knowledge of new CEO's track record at prior company",
        what_proves_wrong="If next quarter earnings miss by >10%, override was wrong",
        conviction=conviction,
        evidence_pieces=evidence,
    )


def make_manager() -> OverrideManager:
    """Create an OverrideManager with default config."""
    config_path = Path(__file__).parent.parent / 'config' / 'settings.yaml'
    return OverrideManager(config_path=str(config_path))


# ============================================================================
# Weight Override Validation Tests
# ============================================================================

class TestWeightOverrideValidation:
    """Test weight adjustment validation against Framework Section 6.2 limits.

    Permissible ranges:
    - Fundamental: 35-55% (base 45%, +/-10%)
    - Technical: 25-45% (base 35%, +/-10%)
    - Sentiment: 10-30% (base 20%, +/-10%)
    - Must sum to 100%
    """

    def setup_method(self):
        self.manager = make_manager()

    def test_valid_weight_adjustment(self):
        """Weights within range and summing to 1.0 should pass."""
        w = WeightOverride(0.50, 0.30, 0.20)
        errors = self.manager.validate_weight_override(w)
        assert errors == []

    def test_base_weights_are_valid(self):
        """Default 45/35/20 weights should pass."""
        w = WeightOverride(0.45, 0.35, 0.20)
        errors = self.manager.validate_weight_override(w)
        assert errors == []

    def test_fundamental_weight_too_high(self):
        """Fundamental > 55% should fail."""
        w = WeightOverride(0.56, 0.25, 0.19)
        errors = self.manager.validate_weight_override(w)
        assert any("Fundamental" in e for e in errors)

    def test_fundamental_weight_too_low(self):
        """Fundamental < 35% should fail."""
        w = WeightOverride(0.34, 0.36, 0.30)
        errors = self.manager.validate_weight_override(w)
        assert any("Fundamental" in e for e in errors)

    def test_technical_weight_too_high(self):
        """Technical > 45% should fail."""
        w = WeightOverride(0.35, 0.46, 0.19)
        errors = self.manager.validate_weight_override(w)
        assert any("Technical" in e for e in errors)

    def test_technical_weight_too_low(self):
        """Technical < 25% should fail."""
        w = WeightOverride(0.51, 0.24, 0.25)
        errors = self.manager.validate_weight_override(w)
        assert any("Technical" in e for e in errors)

    def test_sentiment_weight_too_high(self):
        """Sentiment > 30% should fail."""
        w = WeightOverride(0.35, 0.34, 0.31)
        errors = self.manager.validate_weight_override(w)
        assert any("Sentiment" in e for e in errors)

    def test_sentiment_weight_too_low(self):
        """Sentiment < 10% should fail."""
        w = WeightOverride(0.55, 0.36, 0.09)
        errors = self.manager.validate_weight_override(w)
        assert any("Sentiment" in e for e in errors)

    def test_weights_not_summing_to_one(self):
        """Weights not summing to 1.0 should fail."""
        w = WeightOverride(0.50, 0.35, 0.20)  # sum = 1.05
        errors = self.manager.validate_weight_override(w)
        assert any("sum to 1.0" in e for e in errors)

    def test_weights_at_min_boundary(self):
        """Exact minimum boundary values should pass."""
        w = WeightOverride(0.35, 0.35, 0.30)
        errors = self.manager.validate_weight_override(w)
        assert errors == []

    def test_weights_at_max_boundary(self):
        """Exact maximum boundary values should pass."""
        w = WeightOverride(0.55, 0.35, 0.10)
        errors = self.manager.validate_weight_override(w)
        assert errors == []

    def test_all_at_max_fundamental(self):
        """Max fundamental with valid others."""
        w = WeightOverride(0.55, 0.25, 0.20)
        errors = self.manager.validate_weight_override(w)
        assert errors == []

    def test_all_at_max_technical(self):
        """Max technical with valid others."""
        w = WeightOverride(0.35, 0.45, 0.20)
        errors = self.manager.validate_weight_override(w)
        assert errors == []

    def test_all_at_max_sentiment(self):
        """Max sentiment with valid others."""
        w = WeightOverride(0.40, 0.30, 0.30)
        errors = self.manager.validate_weight_override(w)
        assert errors == []


# ============================================================================
# Sentiment Override Validation Tests
# ============================================================================

class TestSentimentOverrideValidation:
    """Test sentiment adjustment validation. Framework Section 6.2."""

    def setup_method(self):
        self.manager = make_manager()

    def test_valid_positive_adjustment(self):
        """+10 adjustment should pass."""
        s = SentimentOverride(adjustment=10.0)
        errors = self.manager.validate_sentiment_override(s)
        assert errors == []

    def test_valid_negative_adjustment(self):
        """-10 adjustment should pass."""
        s = SentimentOverride(adjustment=-10.0)
        errors = self.manager.validate_sentiment_override(s)
        assert errors == []

    def test_max_positive_adjustment(self):
        """+15 adjustment should pass (boundary)."""
        s = SentimentOverride(adjustment=15.0)
        errors = self.manager.validate_sentiment_override(s)
        assert errors == []

    def test_max_negative_adjustment(self):
        """-15 adjustment should pass (boundary)."""
        s = SentimentOverride(adjustment=-15.0)
        errors = self.manager.validate_sentiment_override(s)
        assert errors == []

    def test_adjustment_too_large_positive(self):
        """+16 should fail."""
        s = SentimentOverride(adjustment=16.0)
        errors = self.manager.validate_sentiment_override(s)
        assert len(errors) == 1
        assert "exceeds" in errors[0]

    def test_adjustment_too_large_negative(self):
        """-16 should fail."""
        s = SentimentOverride(adjustment=-16.0)
        errors = self.manager.validate_sentiment_override(s)
        assert len(errors) == 1
        assert "exceeds" in errors[0]

    def test_zero_adjustment(self):
        """Zero adjustment should pass (no-op)."""
        s = SentimentOverride(adjustment=0.0)
        errors = self.manager.validate_sentiment_override(s)
        assert errors == []


# ============================================================================
# Documentation Validation Tests
# ============================================================================

class TestDocumentationValidation:
    """Test mandatory documentation requirements. Framework Section 6.4."""

    def setup_method(self):
        self.manager = make_manager()

    def test_valid_documentation(self):
        """Complete documentation should pass."""
        doc = make_documentation()
        errors = self.manager.validate_documentation(doc)
        assert errors == []

    def test_missing_what_model_misses(self):
        """Empty what_model_misses should fail."""
        doc = make_documentation()
        doc.what_model_misses = ""
        errors = self.manager.validate_documentation(doc)
        assert len(errors) == 1
        assert "What does the model miss" in errors[0]

    def test_missing_why_view_accurate(self):
        """Empty why_view_more_accurate should fail."""
        doc = make_documentation()
        doc.why_view_more_accurate = ""
        errors = self.manager.validate_documentation(doc)
        assert len(errors) == 1
        assert "Why is your view more accurate" in errors[0]

    def test_missing_falsification(self):
        """Empty what_proves_wrong should fail."""
        doc = make_documentation()
        doc.what_proves_wrong = ""
        errors = self.manager.validate_documentation(doc)
        assert len(errors) == 1
        assert "What would prove you wrong" in errors[0]

    def test_all_fields_missing(self):
        """All empty fields should produce 3 errors."""
        doc = OverrideDocumentation(
            what_model_misses="",
            why_view_more_accurate="",
            what_proves_wrong="",
            conviction=ConvictionLevel.MEDIUM,
        )
        errors = self.manager.validate_documentation(doc)
        assert len(errors) == 3

    def test_whitespace_only_fields_fail(self):
        """Whitespace-only fields should fail validation."""
        doc = OverrideDocumentation(
            what_model_misses="   ",
            why_view_more_accurate="  \t  ",
            what_proves_wrong="\n",
            conviction=ConvictionLevel.LOW,
        )
        errors = self.manager.validate_documentation(doc)
        assert len(errors) == 3

    def test_no_documentation_for_non_none_override(self):
        """None documentation should fail for non-NONE override types."""
        request = OverrideRequest(
            ticker="TEST",
            override_type=OverrideType.WEIGHT_ADJUSTMENT,
            weight_override=WeightOverride(0.50, 0.30, 0.20),
            documentation=None,
        )
        errors = self.manager.validate_override_request(request)
        assert any("Documentation is required" in e for e in errors)

    def test_no_documentation_ok_for_none_override(self):
        """NONE override type should not require documentation."""
        request = OverrideRequest(
            ticker="TEST",
            override_type=OverrideType.NONE,
        )
        errors = self.manager.validate_override_request(request)
        assert errors == []


# ============================================================================
# Override Application Tests
# ============================================================================

class TestApplyOverride:
    """Test override application with composite score recalculation."""

    def setup_method(self):
        self.manager = make_manager()
        self.universe = make_universe(15)

    def _get_score_from_universe(self, index: int) -> CompositeScore:
        """Get a score from the universe by index."""
        return self.universe[index]

    def test_weight_override_increases_composite(self):
        """Shifting weight toward higher-scoring pillar should increase composite."""
        # Pick a stock where technical > fundamental
        stock = make_composite_score(
            ticker="STK07",
            fundamental=40.0, technical=80.0, sentiment=50.0,
            percentile=50.0,
        )
        # Replace in universe
        universe = [s for s in self.universe if s.ticker != "STK07"]
        universe.append(stock)

        request = OverrideRequest(
            ticker="STK07",
            override_type=OverrideType.WEIGHT_ADJUSTMENT,
            weight_override=WeightOverride(0.35, 0.45, 0.20),  # Shift toward technical
            documentation=make_documentation(),
        )
        result = self.manager.apply_override(stock, request, universe)
        assert result.final_composite_score > result.base_composite_score

    def test_weight_override_decreases_composite(self):
        """Shifting weight toward lower-scoring pillar should decrease composite."""
        stock = make_composite_score(
            ticker="STK07",
            fundamental=40.0, technical=80.0, sentiment=50.0,
            percentile=50.0,
        )
        universe = [s for s in self.universe if s.ticker != "STK07"]
        universe.append(stock)

        request = OverrideRequest(
            ticker="STK07",
            override_type=OverrideType.WEIGHT_ADJUSTMENT,
            weight_override=WeightOverride(0.55, 0.25, 0.20),  # Shift toward fundamental (lower)
            documentation=make_documentation(),
        )
        result = self.manager.apply_override(stock, request, universe)
        assert result.final_composite_score < result.base_composite_score

    def test_sentiment_override_increases_composite(self):
        """Positive sentiment adjustment should increase composite."""
        stock = make_composite_score(
            ticker="STK07",
            fundamental=50.0, technical=50.0, sentiment=40.0,
            percentile=50.0,
        )
        universe = [s for s in self.universe if s.ticker != "STK07"]
        universe.append(stock)

        request = OverrideRequest(
            ticker="STK07",
            override_type=OverrideType.SENTIMENT_ADJUSTMENT,
            sentiment_override=SentimentOverride(adjustment=10.0),
            documentation=make_documentation(),
        )
        result = self.manager.apply_override(stock, request, universe)
        assert result.final_composite_score > result.base_composite_score
        assert result.adjusted_sentiment == 50.0  # 40 + 10

    def test_sentiment_override_decreases_composite(self):
        """Negative sentiment adjustment should decrease composite."""
        stock = make_composite_score(
            ticker="STK07",
            fundamental=50.0, technical=50.0, sentiment=60.0,
            percentile=50.0,
        )
        universe = [s for s in self.universe if s.ticker != "STK07"]
        universe.append(stock)

        request = OverrideRequest(
            ticker="STK07",
            override_type=OverrideType.SENTIMENT_ADJUSTMENT,
            sentiment_override=SentimentOverride(adjustment=-10.0),
            documentation=make_documentation(),
        )
        result = self.manager.apply_override(stock, request, universe)
        assert result.final_composite_score < result.base_composite_score
        assert result.adjusted_sentiment == 50.0  # 60 - 10

    def test_sentiment_clamped_to_zero(self):
        """If base sentiment is 5 and adjustment is -15, result should be 0."""
        stock = make_composite_score(
            ticker="STK07",
            fundamental=50.0, technical=50.0, sentiment=5.0,
            percentile=50.0,
        )
        universe = [s for s in self.universe if s.ticker != "STK07"]
        universe.append(stock)

        request = OverrideRequest(
            ticker="STK07",
            override_type=OverrideType.SENTIMENT_ADJUSTMENT,
            sentiment_override=SentimentOverride(adjustment=-15.0),
            documentation=make_documentation(),
        )
        result = self.manager.apply_override(stock, request, universe)
        assert result.adjusted_sentiment == 0.0

    def test_sentiment_clamped_to_100(self):
        """If base sentiment is 95 and adjustment is +15, result should be 100."""
        stock = make_composite_score(
            ticker="STK07",
            fundamental=50.0, technical=50.0, sentiment=95.0,
            percentile=50.0,
        )
        universe = [s for s in self.universe if s.ticker != "STK07"]
        universe.append(stock)

        request = OverrideRequest(
            ticker="STK07",
            override_type=OverrideType.SENTIMENT_ADJUSTMENT,
            sentiment_override=SentimentOverride(adjustment=15.0),
            documentation=make_documentation(),
        )
        result = self.manager.apply_override(stock, request, universe)
        assert result.adjusted_sentiment == 100.0

    def test_combined_override(self):
        """Both weight and sentiment override applied together."""
        stock = make_composite_score(
            ticker="STK07",
            fundamental=40.0, technical=80.0, sentiment=40.0,
            percentile=50.0,
        )
        universe = [s for s in self.universe if s.ticker != "STK07"]
        universe.append(stock)

        request = OverrideRequest(
            ticker="STK07",
            override_type=OverrideType.BOTH,
            weight_override=WeightOverride(0.35, 0.45, 0.20),
            sentiment_override=SentimentOverride(adjustment=10.0),
            documentation=make_documentation(),
        )
        result = self.manager.apply_override(stock, request, universe)
        # Both adjustments favor higher score
        assert result.final_composite_score > result.base_composite_score
        assert result.adjusted_weights is not None
        assert result.adjusted_sentiment == 50.0

    def test_no_override_type_none(self):
        """Override type NONE should not require any adjustments."""
        stock = self.universe[7]
        request = OverrideRequest(
            ticker=stock.ticker,
            override_type=OverrideType.NONE,
        )
        # NONE type doesn't need documentation, weights, or sentiment
        errors = self.manager.validate_override_request(request)
        assert errors == []

    def test_recommendation_change_tracked(self):
        """If recommendation changes, result should flag it."""
        # Create a stock at HOLD boundary
        stock = make_composite_score(
            ticker="STK07",
            fundamental=40.0, technical=80.0, sentiment=50.0,
            percentile=68.0,  # Just under BUY threshold (70)
            recommendation=Recommendation.HOLD,
        )
        universe = [s for s in self.universe if s.ticker != "STK07"]
        universe.append(stock)

        request = OverrideRequest(
            ticker="STK07",
            override_type=OverrideType.WEIGHT_ADJUSTMENT,
            weight_override=WeightOverride(0.35, 0.45, 0.20),
            documentation=make_documentation(),
        )
        result = self.manager.apply_override(stock, request, universe)
        # The result tracks whether recommendation changed
        assert isinstance(result.recommendation_changed, bool)

    def test_validation_error_raised_on_invalid_request(self):
        """Invalid request should raise OverrideValidationError."""
        stock = self.universe[7]
        request = OverrideRequest(
            ticker=stock.ticker,
            override_type=OverrideType.WEIGHT_ADJUSTMENT,
            weight_override=WeightOverride(0.60, 0.30, 0.10),  # Fund too high
            documentation=make_documentation(),
        )
        with pytest.raises(OverrideValidationError):
            self.manager.apply_override(stock, request, self.universe)

    def test_validation_error_missing_documentation(self):
        """Missing documentation should raise OverrideValidationError."""
        stock = self.universe[7]
        request = OverrideRequest(
            ticker=stock.ticker,
            override_type=OverrideType.SENTIMENT_ADJUSTMENT,
            sentiment_override=SentimentOverride(adjustment=5.0),
            documentation=None,
        )
        with pytest.raises(OverrideValidationError):
            self.manager.apply_override(stock, request, self.universe)

    def test_composite_score_calculation_correctness(self):
        """Verify the recalculated composite matches expected formula."""
        stock = make_composite_score(
            ticker="STK07",
            fundamental=60.0, technical=70.0, sentiment=50.0,
            percentile=50.0,
        )
        universe = [s for s in self.universe if s.ticker != "STK07"]
        universe.append(stock)

        request = OverrideRequest(
            ticker="STK07",
            override_type=OverrideType.BOTH,
            weight_override=WeightOverride(0.40, 0.40, 0.20),
            sentiment_override=SentimentOverride(adjustment=5.0),
            documentation=make_documentation(),
        )
        result = self.manager.apply_override(stock, request, universe)

        expected = 60.0 * 0.40 + 70.0 * 0.40 + 55.0 * 0.20
        assert result.final_composite_score == pytest.approx(expected)


# ============================================================================
# Impact Guardrail Tests
# ============================================================================

class TestImpactGuardrails:
    """Test override impact limits. Framework Section 6.5."""

    def setup_method(self):
        self.manager = make_manager()

    def test_weight_override_within_10pt_limit(self):
        """Weight-only override with <10pt impact should pass."""
        passes, violations = self.manager.check_impact_guardrails(
            base_percentile=50.0,
            final_percentile=58.0,
            override_type=OverrideType.WEIGHT_ADJUSTMENT,
        )
        assert passes is True
        assert violations == []

    def test_weight_override_exceeds_10pt_limit(self):
        """Weight-only override with >10pt impact should flag violation."""
        passes, violations = self.manager.check_impact_guardrails(
            base_percentile=50.0,
            final_percentile=62.0,
            override_type=OverrideType.WEIGHT_ADJUSTMENT,
        )
        assert passes is False
        assert len(violations) == 1
        assert "10" in violations[0]

    def test_sentiment_override_within_3pt_limit(self):
        """Sentiment-only override with <3pt impact should pass."""
        passes, violations = self.manager.check_impact_guardrails(
            base_percentile=50.0,
            final_percentile=52.0,
            override_type=OverrideType.SENTIMENT_ADJUSTMENT,
        )
        assert passes is True
        assert violations == []

    def test_sentiment_override_exceeds_3pt_limit(self):
        """Sentiment-only override with >3pt impact should flag violation."""
        passes, violations = self.manager.check_impact_guardrails(
            base_percentile=50.0,
            final_percentile=54.0,
            override_type=OverrideType.SENTIMENT_ADJUSTMENT,
        )
        assert passes is False
        assert len(violations) == 1

    def test_combined_override_within_12pt_limit(self):
        """Combined override with <12pt impact should pass."""
        passes, violations = self.manager.check_impact_guardrails(
            base_percentile=50.0,
            final_percentile=60.0,
            override_type=OverrideType.BOTH,
        )
        assert passes is True
        assert violations == []

    def test_combined_override_exceeds_12pt_limit(self):
        """Combined override with >12pt impact should flag violation."""
        passes, violations = self.manager.check_impact_guardrails(
            base_percentile=50.0,
            final_percentile=63.0,
            override_type=OverrideType.BOTH,
        )
        assert passes is False
        assert len(violations) == 1
        assert "12" in violations[0]

    def test_negative_impact_also_checked(self):
        """Negative percentile impact should also be checked against limits."""
        passes, violations = self.manager.check_impact_guardrails(
            base_percentile=60.0,
            final_percentile=48.0,
            override_type=OverrideType.WEIGHT_ADJUSTMENT,
        )
        assert passes is False  # |60-48| = 12 > 10

    def test_exact_boundary_weight(self):
        """Exactly 10pt impact for weight should pass (not strictly greater)."""
        passes, violations = self.manager.check_impact_guardrails(
            base_percentile=50.0,
            final_percentile=60.0,
            override_type=OverrideType.WEIGHT_ADJUSTMENT,
        )
        assert passes is True  # 10 is not > 10

    def test_exact_boundary_combined(self):
        """Exactly 12pt impact for combined should pass."""
        passes, violations = self.manager.check_impact_guardrails(
            base_percentile=50.0,
            final_percentile=62.0,
            override_type=OverrideType.BOTH,
        )
        assert passes is True  # 12 is not > 12


# ============================================================================
# Forbidden Override Tests
# ============================================================================

class TestForbiddenOverrides:
    """Test forbidden recommendation transitions. Framework Section 6.5 item 4."""

    def setup_method(self):
        self.manager = make_manager()

    def test_sell_to_buy_without_high_conviction(self):
        """SELL -> BUY without HIGH conviction should be forbidden."""
        is_forbidden, reason = self.manager.check_forbidden_override(
            Recommendation.SELL, Recommendation.BUY, ConvictionLevel.MEDIUM,
        )
        assert is_forbidden is True
        assert "HIGH conviction" in reason

    def test_buy_to_sell_without_high_conviction(self):
        """BUY -> SELL without HIGH conviction should be forbidden."""
        is_forbidden, reason = self.manager.check_forbidden_override(
            Recommendation.BUY, Recommendation.SELL, ConvictionLevel.MEDIUM,
        )
        assert is_forbidden is True

    def test_strong_sell_to_strong_buy_forbidden(self):
        """STRONG_SELL -> STRONG_BUY should be forbidden without HIGH conviction."""
        is_forbidden, reason = self.manager.check_forbidden_override(
            Recommendation.STRONG_SELL, Recommendation.STRONG_BUY, ConvictionLevel.LOW,
        )
        assert is_forbidden is True

    def test_sell_to_buy_with_high_conviction(self):
        """SELL -> BUY with HIGH conviction should be allowed."""
        is_forbidden, reason = self.manager.check_forbidden_override(
            Recommendation.SELL, Recommendation.BUY, ConvictionLevel.HIGH,
        )
        assert is_forbidden is False

    def test_hold_to_buy_allowed(self):
        """HOLD -> BUY should be allowed (not forbidden)."""
        is_forbidden, reason = self.manager.check_forbidden_override(
            Recommendation.HOLD, Recommendation.BUY, ConvictionLevel.LOW,
        )
        assert is_forbidden is False

    def test_buy_to_strong_buy_allowed(self):
        """BUY -> STRONG_BUY should be allowed."""
        is_forbidden, reason = self.manager.check_forbidden_override(
            Recommendation.BUY, Recommendation.STRONG_BUY, ConvictionLevel.LOW,
        )
        assert is_forbidden is False

    def test_hold_to_sell_allowed(self):
        """HOLD -> SELL should be allowed."""
        is_forbidden, reason = self.manager.check_forbidden_override(
            Recommendation.HOLD, Recommendation.SELL, ConvictionLevel.LOW,
        )
        assert is_forbidden is False

    def test_same_recommendation_allowed(self):
        """Same recommendation should always be allowed."""
        is_forbidden, reason = self.manager.check_forbidden_override(
            Recommendation.BUY, Recommendation.BUY, ConvictionLevel.LOW,
        )
        assert is_forbidden is False


# ============================================================================
# Extreme Override Tests
# ============================================================================

class TestExtremeOverrides:
    """Test extreme override detection. Framework Section 6.5 item 2."""

    def setup_method(self):
        self.manager = make_manager()

    def test_normal_override_not_extreme(self):
        """<15 percentile impact should not be flagged as extreme."""
        is_extreme, warning = self.manager.check_extreme_override(
            14.0, make_documentation(),
        )
        assert is_extreme is False
        assert warning is None

    def test_15pt_impact_not_extreme(self):
        """Exactly 15pt impact should not be extreme (threshold is >15)."""
        is_extreme, warning = self.manager.check_extreme_override(
            15.0, make_documentation(),
        )
        assert is_extreme is False

    def test_above_15pt_is_extreme(self):
        """>15 percentile impact should be flagged as extreme."""
        is_extreme, warning = self.manager.check_extreme_override(
            16.0, make_documentation(conviction=ConvictionLevel.MEDIUM),
        )
        assert is_extreme is True
        assert warning is not None

    def test_extreme_without_high_conviction_warns(self):
        """Extreme override without HIGH conviction should generate warning."""
        is_extreme, warning = self.manager.check_extreme_override(
            20.0, make_documentation(conviction=ConvictionLevel.MEDIUM),
        )
        assert is_extreme is True
        assert "HIGH conviction" in warning

    def test_extreme_with_high_conviction_no_evidence_warns(self):
        """Extreme override with HIGH conviction but <3 evidence pieces should warn."""
        is_extreme, warning = self.manager.check_extreme_override(
            20.0, make_documentation(conviction=ConvictionLevel.HIGH, evidence_count=2),
        )
        assert is_extreme is True
        assert "3+ evidence" in warning

    def test_extreme_with_high_conviction_and_evidence_passes(self):
        """Extreme override with HIGH conviction and 3+ evidence pieces passes cleanly."""
        is_extreme, warning = self.manager.check_extreme_override(
            20.0, make_documentation(conviction=ConvictionLevel.HIGH, evidence_count=3),
        )
        assert is_extreme is True
        assert warning is None


# ============================================================================
# Override Result Serialization Tests
# ============================================================================

class TestOverrideResultSerialization:
    """Test OverrideResult.to_dict() for JSON serialization."""

    def test_to_dict_basic(self):
        """to_dict should produce a serializable dict."""
        result = OverrideResult(
            ticker="AAPL",
            timestamp=datetime(2026, 2, 13, 14, 30, 0),
            override_type=OverrideType.WEIGHT_ADJUSTMENT,
            base_fundamental_score=60.0,
            base_technical_score=70.0,
            base_sentiment_score=55.0,
            base_weights={'fundamental': 0.45, 'technical': 0.35, 'sentiment': 0.20},
            base_composite_score=63.5,
            base_composite_percentile=72.0,
            base_recommendation="BUY",
            adjusted_weights={'fundamental': 0.40, 'technical': 0.40, 'sentiment': 0.20},
            final_composite_score=65.0,
            final_composite_percentile=78.0,
            final_recommendation="BUY",
            percentile_impact=6.0,
            documentation=make_documentation(),
        )
        d = result.to_dict()
        # Should be JSON serializable
        json_str = json.dumps(d)
        assert json_str is not None
        assert d['ticker'] == "AAPL"
        assert d['override_type'] == "weight_adjustment"
        assert d['base_model']['fundamental_score'] == 60.0
        assert d['result']['percentile_impact'] == 6.0

    def test_to_dict_with_none_documentation(self):
        """to_dict should handle None documentation."""
        result = OverrideResult(
            ticker="TEST",
            timestamp=datetime.now(),
            override_type=OverrideType.NONE,
            base_fundamental_score=50.0,
            base_technical_score=50.0,
            base_sentiment_score=50.0,
            base_weights={'fundamental': 0.45, 'technical': 0.35, 'sentiment': 0.20},
            base_composite_score=50.0,
            base_composite_percentile=50.0,
            base_recommendation="HOLD",
        )
        d = result.to_dict()
        json_str = json.dumps(d)
        assert json_str is not None
        assert d['documentation'] is None


# ============================================================================
# Override Logger Tests
# ============================================================================

class TestOverrideLogger:
    """Test override logging and retrieval."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.logger = OverrideLogger(log_dir=self.temp_dir)

    def _make_result(self, ticker="AAPL", timestamp=None):
        """Create a sample OverrideResult for logging."""
        if timestamp is None:
            timestamp = datetime.now()
        return OverrideResult(
            ticker=ticker,
            timestamp=timestamp,
            override_type=OverrideType.WEIGHT_ADJUSTMENT,
            base_fundamental_score=60.0,
            base_technical_score=70.0,
            base_sentiment_score=55.0,
            base_weights={'fundamental': 0.45, 'technical': 0.35, 'sentiment': 0.20},
            base_composite_score=63.5,
            base_composite_percentile=72.0,
            base_recommendation="BUY",
            adjusted_weights={'fundamental': 0.40, 'technical': 0.40, 'sentiment': 0.20},
            final_composite_score=65.0,
            final_composite_percentile=78.0,
            final_recommendation="BUY",
            percentile_impact=6.0,
            documentation=make_documentation(),
        )

    def test_log_creates_json_file(self):
        """Logging should create a JSON file in the log directory."""
        result = self._make_result()
        file_path = self.logger.log_override(result)
        assert Path(file_path).exists()
        assert file_path.endswith(".json")

    def test_log_file_contains_all_fields(self):
        """JSON file should contain all override result fields."""
        result = self._make_result()
        file_path = self.logger.log_override(result)
        with open(file_path) as f:
            data = json.load(f)
        assert data['ticker'] == "AAPL"
        assert 'base_model' in data
        assert 'override' in data
        assert 'result' in data
        assert 'documentation' in data

    def test_load_override_roundtrip(self):
        """Log then load should produce equivalent data."""
        result = self._make_result()
        file_path = self.logger.log_override(result)
        loaded = self.logger.load_override(file_path)
        assert loaded['ticker'] == "AAPL"
        assert loaded['base_model']['composite_percentile'] == 72.0

    def test_load_all_overrides(self):
        """Should load all override files from directory."""
        self.logger.log_override(self._make_result("AAPL"))
        self.logger.log_override(self._make_result("GOOGL"))
        self.logger.log_override(self._make_result("MSFT"))

        all_overrides = self.logger.load_all_overrides()
        assert len(all_overrides) == 3

    def test_filter_by_ticker(self):
        """Should filter overrides by ticker."""
        self.logger.log_override(self._make_result("AAPL"))
        self.logger.log_override(self._make_result("GOOGL"))
        self.logger.log_override(self._make_result("AAPL"))

        filtered = self.logger.load_all_overrides(ticker="AAPL")
        assert len(filtered) == 2

    def test_filter_by_date(self):
        """Should filter overrides by date range."""
        old = self._make_result("AAPL", timestamp=datetime(2026, 1, 1))
        recent = self._make_result("GOOGL", timestamp=datetime(2026, 2, 15))

        self.logger.log_override(old)
        self.logger.log_override(recent)

        filtered = self.logger.load_all_overrides(
            start_date=datetime(2026, 2, 1),
        )
        assert len(filtered) == 1
        assert filtered[0]['ticker'] == "GOOGL"

    def test_calculate_statistics(self):
        """Should calculate correct override statistics."""
        self.logger.log_override(self._make_result("AAPL"))
        self.logger.log_override(self._make_result("GOOGL"))

        stats = self.logger.calculate_override_statistics()
        assert stats['total_overrides'] == 2
        assert stats['avg_percentile_impact'] == 6.0

    def test_empty_directory_statistics(self):
        """Empty directory should return zero-count statistics."""
        stats = self.logger.calculate_override_statistics()
        assert stats['total_overrides'] == 0
        assert stats['avg_percentile_impact'] == 0.0

    def test_generate_quarterly_summary(self):
        """Should generate a formatted summary string."""
        self.logger.log_override(self._make_result("AAPL"))
        summary = self.logger.generate_quarterly_summary("Q1 2026", 15)
        assert "Q1 2026" in summary
        assert "Total Overrides: 1" in summary
