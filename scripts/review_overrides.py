"""
Override Reviewer - View and summarize applied overrides.

Usage:
    python scripts/review_overrides.py list                  # List all overrides
    python scripts/review_overrides.py list --ticker GOOGL   # Filter by ticker
    python scripts/review_overrides.py summary               # Statistics summary
    python scripts/review_overrides.py detail GOOGL          # Detailed view for one ticker

Framework Reference: Section 8 (Override Tracking & Learning)

Author: Stock Analysis Framework v2.0
Date: 2026-02-14
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from overrides.override_logger import OverrideLogger


def list_overrides(ticker=None):
    """List all override records, optionally filtered by ticker."""
    logger = OverrideLogger()
    overrides = logger.load_all_overrides(ticker=ticker)

    if not overrides:
        filter_msg = f" for {ticker}" if ticker else ""
        print(f"No overrides found{filter_msg}.")
        return

    print(f"Overrides: {len(overrides)}")
    print("-" * 90)
    print(f"  {'Date':<20} {'Ticker':<8} {'Type':<12} {'Conviction':<12} "
          f"{'Impact':>8} {'Rec Changed':<12}")
    print("  " + "-" * 82)

    for o in overrides:
        ts = o.get('timestamp', '?')[:19]
        tk = o.get('ticker', '?')
        otype = o.get('override_type', '?')
        doc = o.get('documentation') or {}
        conviction = doc.get('conviction', '?')
        result = o.get('result', {})
        impact = result.get('percentile_impact')
        impact_str = f"{impact:+.1f}pt" if impact is not None else "N/A"
        rec_changed = "YES" if result.get('recommendation_changed') else "no"

        print(f"  {ts:<20} {tk:<8} {otype:<12} {conviction:<12} "
              f"{impact_str:>8} {rec_changed:<12}")


def show_summary():
    """Show override statistics summary."""
    logger = OverrideLogger()
    overrides = logger.load_all_overrides()
    stats = logger.calculate_override_statistics(overrides)

    print("OVERRIDE SUMMARY")
    print("-" * 50)
    print(f"  Total overrides:          {stats['total_overrides']}")
    print()

    if stats['by_type']:
        print("  By type:")
        for t, c in stats['by_type'].items():
            print(f"    {t:<20} {c}")

    if stats['by_conviction']:
        print("\n  By conviction:")
        for cv, c in stats['by_conviction'].items():
            print(f"    {cv:<20} {c}")

    print(f"\n  Avg percentile impact:    {stats['avg_percentile_impact']:.1f}pt")
    print(f"  Recommendation changes:   {stats['recommendation_changes']}")
    print(f"  Extreme overrides:        {stats['extreme_overrides']}")
    print(f"  Guardrail violations:     {stats['guardrail_violations']}")


def show_detail(ticker):
    """Show detailed override records for a specific ticker."""
    logger = OverrideLogger()
    overrides = logger.load_all_overrides(ticker=ticker.upper())

    if not overrides:
        print(f"No overrides found for {ticker.upper()}.")
        return

    print(f"OVERRIDE DETAIL: {ticker.upper()} ({len(overrides)} override(s))")
    print("=" * 80)

    for i, o in enumerate(overrides, 1):
        ts = o.get('timestamp', '?')
        otype = o.get('override_type', '?')
        doc = o.get('documentation') or {}
        result = o.get('result', {})

        print(f"\n--- Override #{i} ({ts}) ---")
        print(f"  Type:        {otype}")
        print(f"  Conviction:  {doc.get('conviction', '?')}")

        # Documentation
        if doc.get('thesis'):
            print(f"  Thesis:      {doc['thesis']}")
        if doc.get('what_model_misses'):
            print(f"  Model miss:  {doc['what_model_misses']}")
        if doc.get('what_would_prove_wrong'):
            print(f"  Falsifiable: {doc['what_would_prove_wrong']}")
        if doc.get('evidence'):
            print(f"  Evidence:")
            for ev in doc['evidence']:
                print(f"    - {ev}")

        # Adjustments
        weight_adj = o.get('weight_override')
        if weight_adj:
            print(f"  Weight adj:  F={weight_adj.get('fundamental_delta', 0):+.0%} "
                  f"T={weight_adj.get('technical_delta', 0):+.0%} "
                  f"S={weight_adj.get('sentiment_delta', 0):+.0%}")

        sent_adj = o.get('sentiment_override')
        if sent_adj:
            print(f"  Sent adj:    {sent_adj.get('adjustment', 0):+.1f}pt "
                  f"({sent_adj.get('reason', '')})")

        # Result
        print(f"  Impact:      {result.get('percentile_impact', 'N/A')}")
        if result.get('recommendation_changed'):
            print(f"  Rec change:  {result.get('base_recommendation')} -> "
                  f"{result.get('final_recommendation')}")
        print(f"  Base score:  {result.get('base_composite', 'N/A')}")
        print(f"  Final score: {result.get('final_composite', 'N/A')}")


def main():
    parser = argparse.ArgumentParser(description="Review applied overrides")
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # list
    list_parser = subparsers.add_parser('list', help='List all overrides')
    list_parser.add_argument('--ticker', type=str, help='Filter by ticker')

    # summary
    subparsers.add_parser('summary', help='Show override statistics')

    # detail
    detail_parser = subparsers.add_parser('detail', help='Detailed view for one ticker')
    detail_parser.add_argument('ticker', help='Ticker symbol')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == 'list':
        list_overrides(ticker=args.ticker)
    elif args.command == 'summary':
        show_summary()
    elif args.command == 'detail':
        show_detail(args.ticker)


if __name__ == "__main__":
    main()
