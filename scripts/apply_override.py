"""
Apply Override to Stock Score

Framework Section 6: Model-First Override System

Loads base composite scores from the most recent scoring run,
applies the specified override, validates guardrails, and logs the result.

Usage:
    python scripts/apply_override.py AAPL \\
        --weight-fundamental 0.50 --weight-technical 0.30 --weight-sentiment 0.20 \\
        --what-model-misses "Recent CEO change not in data" \\
        --why-accurate "New CEO led 30% growth at prior company" \\
        --what-proves-wrong "Next quarter earnings miss by >10%" \\
        --conviction Medium

    python scripts/apply_override.py AAPL \\
        --sentiment-adjustment 10 \\
        --what-model-misses "Insider buying cluster not captured" \\
        --why-accurate "3 executives bought >$1M each in last week" \\
        --what-proves-wrong "If insiders sell within 3 months" \\
        --conviction High \\
        --evidence "CEO bought 50K shares" "CFO bought 30K shares" "CTO bought 25K shares"

    python scripts/apply_override.py AAPL --from-file override_request.json

Author: Stock Analysis Framework v2.0
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from models.composite import CompositeScore, Recommendation
from overrides import (
    ConvictionLevel,
    OverrideDocumentation,
    OverrideLogger,
    OverrideManager,
    OverrideRequest,
    OverrideType,
    OverrideValidationError,
    SentimentOverride,
    WeightOverride,
)


def load_latest_scores(scores_path: Path) -> list:
    """Load latest composite scores from JSON file.

    Args:
        scores_path: Path to latest_scores.json

    Returns:
        List of CompositeScore objects
    """
    with open(scores_path, 'r') as f:
        data = json.load(f)

    scores = []
    for s in data['scores']:
        scores.append(CompositeScore(
            ticker=s['ticker'],
            fundamental_score=s['fundamental_score'],
            technical_score=s['technical_score'],
            sentiment_score=s['sentiment_score'],
            composite_score=s['composite_score'],
            composite_percentile=s['composite_percentile'],
            recommendation=Recommendation(s['recommendation']),
        ))
    return scores


def build_request_from_args(args) -> OverrideRequest:
    """Build an OverrideRequest from CLI arguments.

    Args:
        args: Parsed argparse namespace

    Returns:
        OverrideRequest object
    """
    # Determine override type
    has_weight = (
        args.weight_fundamental is not None or
        args.weight_technical is not None or
        args.weight_sentiment is not None
    )
    has_sentiment = args.sentiment_adjustment is not None

    if has_weight and has_sentiment:
        override_type = OverrideType.BOTH
    elif has_weight:
        override_type = OverrideType.WEIGHT_ADJUSTMENT
    elif has_sentiment:
        override_type = OverrideType.SENTIMENT_ADJUSTMENT
    else:
        override_type = OverrideType.NONE

    # Build weight override
    weight_override = None
    if has_weight:
        # Default to base weights for any not specified
        fund_w = args.weight_fundamental if args.weight_fundamental is not None else 0.45
        tech_w = args.weight_technical if args.weight_technical is not None else 0.35
        sent_w = args.weight_sentiment if args.weight_sentiment is not None else 0.20
        weight_override = WeightOverride(fund_w, tech_w, sent_w)

    # Build sentiment override
    sentiment_override = None
    if has_sentiment:
        sentiment_override = SentimentOverride(adjustment=args.sentiment_adjustment)

    # Build documentation
    documentation = None
    if override_type != OverrideType.NONE:
        conviction = ConvictionLevel(args.conviction)
        evidence = list(args.evidence) if args.evidence else None
        documentation = OverrideDocumentation(
            what_model_misses=args.what_model_misses or "",
            why_view_more_accurate=args.why_accurate or "",
            what_proves_wrong=args.what_proves_wrong or "",
            conviction=conviction,
            evidence_pieces=evidence,
        )

    return OverrideRequest(
        ticker=args.ticker.upper(),
        override_type=override_type,
        weight_override=weight_override,
        sentiment_override=sentiment_override,
        documentation=documentation,
    )


def build_request_from_file(ticker: str, file_path: str) -> OverrideRequest:
    """Build an OverrideRequest from a JSON file.

    Args:
        ticker: Stock ticker
        file_path: Path to JSON override request file

    Returns:
        OverrideRequest object
    """
    with open(file_path, 'r') as f:
        data = json.load(f)

    override_type = OverrideType(data['override_type'])

    weight_override = None
    if 'weight_override' in data and data['weight_override']:
        w = data['weight_override']
        weight_override = WeightOverride(w['fundamental'], w['technical'], w['sentiment'])

    sentiment_override = None
    if 'sentiment_override' in data and data['sentiment_override']:
        sentiment_override = SentimentOverride(adjustment=data['sentiment_override']['adjustment'])

    documentation = None
    if 'documentation' in data and data['documentation']:
        doc = data['documentation']
        documentation = OverrideDocumentation(
            what_model_misses=doc.get('what_model_misses', ''),
            why_view_more_accurate=doc.get('why_view_more_accurate', ''),
            what_proves_wrong=doc.get('what_proves_wrong', ''),
            conviction=ConvictionLevel(doc.get('conviction', 'Medium')),
            evidence_pieces=doc.get('evidence_pieces'),
            additional_notes=doc.get('additional_notes'),
        )

    return OverrideRequest(
        ticker=ticker.upper(),
        override_type=override_type,
        weight_override=weight_override,
        sentiment_override=sentiment_override,
        documentation=documentation,
    )


def display_result(result) -> None:
    """Display override result with before/after comparison."""
    print()
    print("=" * 80)
    print(f"OVERRIDE RESULT: {result.ticker}")
    print("=" * 80)

    print(f"\n{'':4s}{'Metric':<25s} {'Before':>10s} {'After':>10s} {'Change':>10s}")
    print(f"{'':4s}{'-'*55}")

    # Composite score
    comp_change = result.final_composite_score - result.base_composite_score
    print(f"{'':4s}{'Composite Score':<25s} {result.base_composite_score:>10.1f} "
          f"{result.final_composite_score:>10.1f} {comp_change:>+10.1f}")

    # Percentile
    print(f"{'':4s}{'Composite Percentile':<25s} {result.base_composite_percentile:>10.1f} "
          f"{result.final_composite_percentile:>10.1f} {result.percentile_impact:>+10.1f}")

    # Recommendation
    print(f"{'':4s}{'Recommendation':<25s} {result.base_recommendation:>10s} "
          f"{result.final_recommendation:>10s}")

    if result.adjusted_weights:
        print(f"\n    Adjusted Weights:")
        for pillar, w in result.adjusted_weights.items():
            base_w = result.base_weights[pillar]
            print(f"{'':6s}{pillar.capitalize()}: {base_w:.0%} -> {w:.0%}")

    if result.adjusted_sentiment is not None:
        print(f"\n    Adjusted Sentiment: {result.base_sentiment_score:.1f} -> "
              f"{result.adjusted_sentiment:.1f}")

    # Warnings
    if result.guardrail_violations:
        print(f"\n    GUARDRAIL VIOLATIONS:")
        for v in result.guardrail_violations:
            print(f"      [!] {v}")

    if result.extreme_override:
        print(f"\n    [!] EXTREME OVERRIDE: >15 percentile point change")

    if result.recommendation_changed:
        print(f"\n    [*] Recommendation changed: {result.base_recommendation} -> "
              f"{result.final_recommendation}")

    print()
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Apply override to stock score (Framework Section 6)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("ticker", help="Stock ticker symbol")

    # Weight overrides
    parser.add_argument("--weight-fundamental", type=float,
                        help="Adjusted fundamental weight (0.35-0.55)")
    parser.add_argument("--weight-technical", type=float,
                        help="Adjusted technical weight (0.25-0.45)")
    parser.add_argument("--weight-sentiment", type=float,
                        help="Adjusted sentiment weight (0.10-0.30)")

    # Sentiment override
    parser.add_argument("--sentiment-adjustment", type=float,
                        help="Sentiment score adjustment (-15 to +15)")

    # Documentation (required for non-NONE overrides)
    parser.add_argument("--what-model-misses", type=str,
                        help="What does the model miss? (required)")
    parser.add_argument("--why-accurate", type=str,
                        help="Why is your view more accurate? (required)")
    parser.add_argument("--what-proves-wrong", type=str,
                        help="What would prove you wrong? (required)")
    parser.add_argument("--conviction", choices=["Low", "Medium", "High"],
                        default="Medium", help="Conviction level (default: Medium)")
    parser.add_argument("--evidence", nargs="+",
                        help="Evidence pieces (required for extreme overrides)")

    # File-based input
    parser.add_argument("--from-file", type=str,
                        help="Load override request from JSON file")

    args = parser.parse_args()

    # Load latest scores
    scores_path = project_root / 'data' / 'processed' / 'latest_scores.json'
    if not scores_path.exists():
        print(f"ERROR: No latest scores found at {scores_path}")
        print("Run 'python scripts/calculate_scores.py' first to generate base scores.")
        sys.exit(1)

    universe = load_latest_scores(scores_path)
    print(f"Loaded {len(universe)} stocks from latest scores")

    # Find target stock
    ticker = args.ticker.upper()
    target = None
    for score in universe:
        if score.ticker == ticker:
            target = score
            break

    if target is None:
        print(f"ERROR: Ticker {ticker} not found in latest scores")
        print(f"Available tickers: {', '.join(s.ticker for s in universe)}")
        sys.exit(1)

    # Display base score (Model-First principle)
    print(f"\nBASE MODEL OUTPUT for {ticker}:")
    print(f"  Fundamental: {target.fundamental_score:.1f}")
    print(f"  Technical:   {target.technical_score:.1f}")
    print(f"  Sentiment:   {target.sentiment_score:.1f}")
    print(f"  Composite:   {target.composite_score:.1f} (Percentile: {target.composite_percentile:.1f})")
    print(f"  Recommendation: {target.recommendation.value}")

    # Build override request
    if args.from_file:
        request = build_request_from_file(ticker, args.from_file)
    else:
        request = build_request_from_args(args)

    if request.override_type == OverrideType.NONE:
        print("\nNo override specified. Use --weight-* or --sentiment-adjustment flags.")
        sys.exit(0)

    # Apply override
    manager = OverrideManager()
    override_logger = OverrideLogger()

    try:
        result = manager.apply_override(target, request, universe)
    except OverrideValidationError as e:
        print(f"\nOVERRIDE VALIDATION FAILED: {e}")
        sys.exit(1)

    # Display result
    display_result(result)

    # Log the override
    log_path = override_logger.log_override(result)
    print(f"Override logged to: {log_path}")


if __name__ == "__main__":
    main()
