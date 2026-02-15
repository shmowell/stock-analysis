"""
Daily Report - Primary daily workflow tool.

Checks data freshness, optionally refreshes stale data, runs the scoring
pipeline, compares with previous scores, and generates an actionable report.

Usage:
    python scripts/daily_report.py                  # Full run (refresh stale + score + report)
    python scripts/daily_report.py --skip-refresh    # Score with existing data
    python scripts/daily_report.py --force-refresh   # Force refresh all data
    python scripts/daily_report.py --ticker AAPL     # Report for a single ticker
    python scripts/daily_report.py --no-save         # Don't persist scores to DB

Framework Reference: Section 7 (Recommendations), Section 10 (Daily Workflow)

Author: Stock Analysis Framework v2.0
Date: 2026-02-14
"""

import argparse
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from database import get_db_session
from scoring import ScoringPipeline
from scoring.pipeline import PipelineResult
from utils.staleness import StalenessChecker, StalenessResult
from backtesting.snapshot_manager import SnapshotManager


# Data collection scripts in dependency order
REFRESH_SCRIPTS = [
    ('price_data',           'scripts/collect_price_data.py'),
    ('fundamental_data',     'scripts/collect_fundamental_data.py'),
    ('technical_indicators', 'scripts/calculate_technical_indicators.py'),
    ('sentiment_data',       'scripts/collect_sentiment_data.py'),
    ('market_sentiment',     'scripts/collect_market_sentiment.py'),
    ('fmp_estimate_snapshots', 'scripts/collect_fmp_data.py'),
]


def parse_args():
    parser = argparse.ArgumentParser(description="Daily stock analysis report")
    parser.add_argument('--skip-refresh', action='store_true',
                        help='Skip data refresh, use existing data')
    parser.add_argument('--force-refresh', action='store_true',
                        help='Force refresh all data regardless of staleness')
    parser.add_argument('--ticker', type=str, default=None,
                        help='Report for a single ticker only')
    parser.add_argument('--no-save', action='store_true',
                        help='Do not persist scores to database')
    return parser.parse_args()


def refresh_data(stale_tables: List[str], force: bool = False) -> Dict[str, bool]:
    """Run data collection scripts for stale (or all) tables.

    Args:
        stale_tables: List of table keys that need refresh.
        force: If True, refresh all tables regardless of staleness.

    Returns:
        Dict mapping script name to success (True/False).
    """
    results = {}
    for table_key, script_path in REFRESH_SCRIPTS:
        if not force and table_key not in stale_tables:
            continue

        full_path = project_root / script_path
        print(f"  Refreshing {table_key}...")
        try:
            proc = subprocess.run(
                [sys.executable, str(full_path)],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(project_root),
            )
            if proc.returncode == 0:
                results[table_key] = True
                print(f"    [OK] {table_key}")
            else:
                results[table_key] = False
                # Show last few lines of stderr for diagnosis
                stderr_lines = proc.stderr.strip().split('\n')[-3:]
                print(f"    [FAIL] {table_key}")
                for line in stderr_lines:
                    print(f"      {line}")
        except subprocess.TimeoutExpired:
            results[table_key] = False
            print(f"    [TIMEOUT] {table_key}")

    return results


def compute_movers(
    current: PipelineResult,
    previous: Optional[Dict[str, Dict]],
) -> List[Dict]:
    """Identify stocks with significant score changes.

    Args:
        current: Current pipeline result.
        previous: Previous scores from load_previous_scores(), or None.

    Returns:
        List of dicts with ticker, old/new scores, and change.
    """
    if not previous:
        return []

    movers = []
    for cr in current.composite_results:
        prev = previous.get(cr.ticker)
        if not prev or prev.get('composite_score') is None:
            continue
        change = cr.composite_score - prev['composite_score']
        if abs(change) >= 1.0:  # Only report meaningful moves (>= 1 point)
            movers.append({
                'ticker': cr.ticker,
                'old_score': prev['composite_score'],
                'new_score': cr.composite_score,
                'change': change,
                'old_rec': prev.get('recommendation', '?'),
                'new_rec': cr.recommendation.value,
                'rec_changed': prev.get('recommendation', '') != cr.recommendation.value,
            })

    movers.sort(key=lambda m: abs(m['change']), reverse=True)
    return movers


def format_report(
    result: PipelineResult,
    staleness: List[StalenessResult],
    movers: List[Dict],
    previous: Optional[Dict[str, Dict]],
    refresh_results: Optional[Dict[str, bool]] = None,
) -> str:
    """Build the full daily report string."""
    today = date.today()
    lines = []

    # Header
    lines.append("=" * 80)
    lines.append(f"  DAILY STOCK ANALYSIS REPORT — {today}")
    lines.append("=" * 80)
    lines.append("")

    # Action items section
    action_items = _get_action_items(result, movers)
    if action_items:
        lines.append("ACTION ITEMS")
        lines.append("-" * 80)
        for item in action_items:
            lines.append(f"  * {item}")
        lines.append("")

    # Ranked list
    lines.append("RANKED STOCK LIST")
    lines.append("-" * 80)
    lines.append(f"  {'Rank':<5} {'Ticker':<7} {'Rec':<13} {'Composite':>9} "
                 f"{'Fund':>6} {'Tech':>6} {'Sent':>6}  {'Chg':>6}")
    lines.append("  " + "-" * 72)

    for i, cr in enumerate(result.composite_results, 1):
        prev = previous.get(cr.ticker, {}) if previous else {}
        old_comp = prev.get('composite_score')
        chg_str = ""
        if old_comp is not None:
            chg = cr.composite_score - old_comp
            if abs(chg) >= 0.1:
                chg_str = f"{chg:+.1f}"

        lines.append(
            f"  {i:<5} {cr.ticker:<7} {cr.recommendation.value:<13} "
            f"{cr.composite_score:>9.1f} {cr.fundamental_score:>6.1f} "
            f"{cr.technical_score:>6.1f} {cr.sentiment_score:>6.1f}  {chg_str:>6}"
        )
    lines.append("")

    # Movers section
    if movers:
        lines.append("SIGNIFICANT MOVERS (>= 1pt change)")
        lines.append("-" * 80)
        for m in movers:
            arrow = "^" if m['change'] > 0 else "v"
            rec_flag = f"  ** REC CHANGE: {m['old_rec']} -> {m['new_rec']}" if m['rec_changed'] else ""
            lines.append(
                f"  {m['ticker']:<7} {m['old_score']:>5.1f} -> {m['new_score']:>5.1f} "
                f"({m['change']:+.1f} {arrow}){rec_flag}"
            )
        lines.append("")

    # Data freshness
    lines.append("DATA FRESHNESS")
    lines.append("-" * 80)
    for s in staleness:
        lines.append(f"  {s}")
    lines.append("")

    # Refresh results
    if refresh_results:
        lines.append("DATA REFRESH RESULTS")
        lines.append("-" * 80)
        for table, ok in refresh_results.items():
            status = "OK" if ok else "FAILED"
            lines.append(f"  {table:30s}  [{status}]")
        lines.append("")

    # Footer
    w = result.weights
    lines.append(f"Weights: F={w['fundamental']*100:.0f}% T={w['technical']*100:.0f}% S={w['sentiment']*100:.0f}%")
    lines.append(f"Universe: {len(result.composite_results)} stocks")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 80)

    return "\n".join(lines)


def _get_action_items(result: PipelineResult, movers: List[Dict]) -> List[str]:
    """Generate action items based on current results."""
    items = []

    # Recommendation changes
    rec_changes = [m for m in movers if m['rec_changed']]
    for m in rec_changes:
        items.append(f"{m['ticker']}: Recommendation changed {m['old_rec']} -> {m['new_rec']}")

    # Strong buys worth attention
    strong_buys = [cr for cr in result.composite_results
                   if cr.recommendation.value == "STRONG BUY"]
    if strong_buys:
        tickers = ", ".join(cr.ticker for cr in strong_buys)
        items.append(f"STRONG BUY signals: {tickers}")

    # Strong sells worth attention
    strong_sells = [cr for cr in result.composite_results
                    if cr.recommendation.value == "STRONG SELL"]
    if strong_sells:
        tickers = ", ".join(cr.ticker for cr in strong_sells)
        items.append(f"STRONG SELL signals: {tickers}")

    # Big movers (non-rec-change)
    big_movers = [m for m in movers if abs(m['change']) >= 3.0 and not m['rec_changed']]
    for m in big_movers:
        direction = "up" if m['change'] > 0 else "down"
        items.append(f"{m['ticker']}: Score moved {direction} {abs(m['change']):.1f} pts — review")

    return items


def save_report(report: str, ticker: Optional[str] = None) -> Path:
    """Save report to data/reports/."""
    reports_dir = project_root / 'data' / 'reports'
    reports_dir.mkdir(parents=True, exist_ok=True)

    today_str = date.today().isoformat()
    if ticker:
        filename = f"daily_{today_str}_{ticker}.txt"
    else:
        filename = f"daily_{today_str}.txt"

    path = reports_dir / filename
    with open(path, 'w') as f:
        f.write(report)
    return path


def main():
    args = parse_args()

    print(f"Daily Report — {date.today()}")
    print()

    # Step 1: Check data freshness
    print("Checking data freshness...")
    checker = StalenessChecker()
    with get_db_session() as session:
        staleness = checker.check_all(session)

    stale_tables = [s.table for s in staleness if s.stale]

    # Step 2: Refresh data if needed
    refresh_results = None
    if args.force_refresh:
        print("\nForce-refreshing ALL data...")
        all_tables = [table_key for table_key, _ in REFRESH_SCRIPTS]
        refresh_results = refresh_data(all_tables, force=True)
    elif not args.skip_refresh and stale_tables:
        print(f"\nRefreshing {len(stale_tables)} stale table(s)...")
        refresh_results = refresh_data(stale_tables)
    elif args.skip_refresh:
        print("  Skipping data refresh (--skip-refresh)")
    else:
        print("  All data is fresh")

    # Re-check staleness after refresh
    if refresh_results:
        print()
        with get_db_session() as session:
            staleness = checker.check_all(session)

    # Step 3: Run scoring pipeline
    print("\nRunning scoring pipeline...")
    pipeline = ScoringPipeline(verbose=False)
    tickers_filter = [args.ticker.upper()] if args.ticker else None

    with get_db_session() as session:
        # Load previous scores for comparison
        previous = pipeline.load_previous_scores(session)

        # Run pipeline
        result = pipeline.run(session, tickers=tickers_filter)

        if not result.composite_results:
            print("ERROR: No scores calculated")
            sys.exit(1)

        # Persist scores
        if not args.no_save:
            pipeline.persist_to_db(session, result)
            pipeline.persist_to_json(result)

            # Save point-in-time snapshot for future backtesting
            snapshot_mgr = SnapshotManager()
            snap_path = snapshot_mgr.save(result)
            print(f"  Snapshot saved to {snap_path}")

    # Step 4: Compute movers
    movers = compute_movers(result, previous)

    # Step 5: Generate report
    report = format_report(result, staleness, movers, previous, refresh_results)
    print()
    print(report)

    # Step 6: Save report
    report_path = save_report(report, ticker=args.ticker)
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
