"""
Calculate Complete Composite Scores (thin wrapper around ScoringPipeline).

Usage:
    python scripts/calculate_scores.py

Framework Reference: Section 1.3, Section 7
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from database import get_db_session
from models.composite import Recommendation
from scoring import ScoringPipeline


def main():
    """Run the full scoring pipeline with detailed output."""
    print("=" * 100)
    print("COMPOSITE SCORE CALCULATION")
    print("=" * 100)
    print()

    pipeline = ScoringPipeline(verbose=True)

    with get_db_session() as session:
        # Run the pipeline
        result = pipeline.run(session)

        if not result.composite_results:
            print("ERROR: No scores calculated")
            sys.exit(1)

        # Generate and display report
        report = pipeline._composite_calc.generate_report(result.composite_results)
        print("\n" + report)

        # Detailed breakdown
        print("\n" + "=" * 120)
        print("DETAILED SCORE BREAKDOWN")
        print("=" * 120)
        for cr in result.composite_results:
            pillars = result.pillar_scores[cr.ticker]
            print(f"\n{cr.ticker} - {cr.recommendation.value}")
            print(f"  Fundamental: {pillars['fundamental']:6.2f}")
            print(f"  Technical:   {pillars['technical']:6.2f}")
            print(f"  Sentiment:   {pillars['sentiment']:6.2f}")
            print(f"  --------------------")
            print(f"  Composite:   {cr.composite_score:6.2f} "
                  f"(Percentile: {cr.composite_percentile:.1f})")

        # Validation summary
        print("\n" + "=" * 120)
        print("VALIDATION SUMMARY")
        print("=" * 120)

        percentiles = [r.composite_percentile for r in result.composite_results]
        print(f"\nComposite Percentile Distribution:")
        print(f"  Min:    {min(percentiles):6.2f}")
        print(f"  25th:   {sorted(percentiles)[len(percentiles)//4]:6.2f}")
        print(f"  Median: {sorted(percentiles)[len(percentiles)//2]:6.2f}")
        print(f"  75th:   {sorted(percentiles)[3*len(percentiles)//4]:6.2f}")
        print(f"  Max:    {max(percentiles):6.2f}")

        print(f"\nRecommendation Distribution:")
        for rec in Recommendation:
            count = sum(1 for r in result.composite_results if r.recommendation == rec)
            pct = count / len(result.composite_results) * 100
            print(f"  {rec.value:12s}: {count:2d} stocks ({pct:5.1f}%)")

        print("\n" + "=" * 120)
        print("[OK] SCORING COMPLETE")
        print("=" * 120)

        # Persist results
        pipeline.persist_to_db(session, result)
        pipeline.persist_to_json(result)

        print(f"\nSuccessfully calculated composite scores for "
              f"{len(result.composite_results)} stocks")


if __name__ == "__main__":
    main()
