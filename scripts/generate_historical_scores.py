"""
Generate Historical Scores - Backfill monthly score snapshots for trend analysis.

Recalculates composite scores at monthly checkpoints using historical price data
for technical indicators, combined with current fundamental and sentiment data
(held constant since we only have point-in-time data for those pillars).

This populates the stock_scores DB table and data/snapshots/ directory so the
web UI trend charts show historical score evolution.

Usage:
    python scripts/generate_historical_scores.py                # Last 12 months
    python scripts/generate_historical_scores.py --months 6     # Last 6 months
    python scripts/generate_historical_scores.py --dry-run      # Preview without saving

Framework Reference: Section 10 (Backtesting & Paper Trading)
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from database import get_db_session
from database.models import (
    Stock, PriceData, FundamentalData, TechnicalIndicator,
    SentimentData, MarketSentiment, StockScore,
)
from backtesting.indicator_builder import IndicatorBuilder
from calculators.fundamental import FundamentalCalculator
from calculators.technical import TechnicalCalculator
from calculators.sentiment import SentimentCalculator
from models.composite import CompositeScoreCalculator, Recommendation
from backtesting.snapshot_manager import SnapshotManager
from scoring.pipeline import ScoringPipeline, PipelineResult


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate historical monthly score snapshots for trend analysis"
    )
    parser.add_argument(
        '--months', type=int, default=12,
        help='Number of months of history to generate (default: 12)',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Preview checkpoint dates and stock counts without saving',
    )
    parser.add_argument(
        '--overwrite', action='store_true',
        help='Overwrite existing scores for dates that already have data',
    )
    return parser.parse_args()


def generate_month_end_dates(months_back: int) -> List[date]:
    """Generate month-end checkpoint dates going back N months from today.

    Returns dates in ascending order (oldest first).
    """
    today = date.today()
    dates = []

    for i in range(months_back, 0, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1

        # Last day of that month
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        dates.append(month_end)

    return dates


def load_price_dataframes(session, tickers: List[str]) -> Dict[str, pd.DataFrame]:
    """Load all price data into DataFrames indexed by date.

    Returns:
        {ticker: DataFrame with DatetimeIndex and close/volume columns}
    """
    price_dfs = {}
    for ticker in tickers:
        rows = (
            session.query(PriceData)
            .filter(PriceData.ticker == ticker)
            .order_by(PriceData.date)
            .all()
        )
        if not rows:
            continue

        data = {
            'close': [float(r.close) for r in rows],
            'volume': [int(r.volume) if r.volume else 0 for r in rows],
        }
        index = pd.DatetimeIndex([r.date for r in rows])
        price_dfs[ticker] = pd.DataFrame(data, index=index)

    return price_dfs


def score_checkpoint(
    checkpoint_date: date,
    price_dfs: Dict[str, pd.DataFrame],
    indicator_cache: Dict[str, pd.DataFrame],
    stock_sectors: Dict[str, str],
    fundamental_data: Dict,
    sentiment_data: Dict,
    market_sentiment: Optional[Dict],
    market_caps: Dict[str, float],
    weights: Dict[str, float],
) -> Optional[PipelineResult]:
    """Score all stocks at a single historical checkpoint.

    Technical indicators are recalculated from historical price data.
    Fundamental and sentiment use current data (held constant).

    Returns PipelineResult or None if insufficient data.
    """
    cp_ts = pd.Timestamp(checkpoint_date)
    indicator_builder = IndicatorBuilder()

    # Build technical snapshots for each stock at this date
    tech_snapshots: Dict[str, Dict] = {}
    latest_prices: Dict[str, float] = {}

    for ticker, indicators in indicator_cache.items():
        # Get closing price at checkpoint
        close_series = price_dfs[ticker]['close']
        price_df = pd.DataFrame({'close': close_series})
        price_row = indicator_builder.get_as_of(price_df, cp_ts)
        if price_row is None:
            continue

        # Skip if data is more than 7 days stale from checkpoint
        if cp_ts - price_row.name > pd.Timedelta(days=7):
            continue

        current_price = float(price_row['close'])
        latest_prices[ticker] = current_price

        snapshot = indicator_builder.build_snapshot(indicators, cp_ts, current_price)
        if snapshot:
            tech_snapshots[ticker] = snapshot

    if len(tech_snapshots) < 5:
        return None

    # Compute sector-relative metrics
    indicator_builder.compute_sector_relative(tech_snapshots, stock_sectors)

    # Initialize calculators
    fund_calc = FundamentalCalculator()
    tech_calc = TechnicalCalculator()
    sent_calc = SentimentCalculator()
    composite_calc = CompositeScoreCalculator(
        fundamental_weight=weights['fundamental'],
        technical_weight=weights['technical'],
        sentiment_weight=weights['sentiment'],
    )

    # Prepare fundamental data (same as pipeline._prepare_fundamental)
    fund_stock, fund_universe = ScoringPipeline._prepare_fundamental(fundamental_data)

    # Prepare technical data from historical snapshots
    tech_stock, tech_universe = ScoringPipeline._prepare_technical(tech_snapshots)

    # Prepare sentiment data (enrich with market caps)
    enriched_sentiment = {}
    for ticker, sdata in sentiment_data.items():
        enriched = dict(sdata)
        if ticker in market_caps:
            enriched['market_cap'] = market_caps[ticker]
        enriched_sentiment[ticker] = enriched
    sent_stock, sent_universe = ScoringPipeline._prepare_sentiment(enriched_sentiment)

    # Calculate per-stock pillar scores
    all_tickers = set(tech_snapshots.keys())
    pillar_scores: Dict[str, Dict] = {}

    for ticker in all_tickers:
        fund_detail = {}
        tech_detail = {}
        sent_detail = {}
        data_status = {}

        # Fundamental (current data - held constant)
        if ticker in fund_stock:
            fund_result = fund_calc.calculate_fundamental_score(
                fund_stock[ticker], fund_universe
            )
            fund_score = fund_result.get('fundamental_score')
            fund_detail = {
                'value_score': fund_result.get('value_score'),
                'quality_score': fund_result.get('quality_score'),
                'growth_score': fund_result.get('growth_score'),
            }
            data_status['fundamental'] = 'calculated'
        else:
            fund_score = None
            data_status['fundamental'] = 'no_data'

        # Technical (from historical price data - varies by checkpoint)
        if ticker in tech_stock:
            tech_result = tech_calc.calculate_technical_score(
                tech_stock[ticker], tech_universe
            )
            tech_score = tech_result.get('technical_score')
            tech_detail = {
                'momentum_score': tech_result.get('momentum_score'),
                'trend_score': tech_result.get('trend_score'),
                'volume_qualified_score': tech_result.get('volume_qualified_score'),
                'relative_strength_score': tech_result.get('relative_strength_score'),
                'rsi_score': tech_result.get('rsi_score'),
                'multi_speed_score': tech_result.get('multi_speed_score'),
            }
            data_status['technical'] = 'calculated'
        else:
            tech_score = None
            data_status['technical'] = 'no_data'

        # Sentiment (current data - held constant)
        if ticker in sent_stock and ticker in latest_prices:
            sent_result = sent_calc.calculate_sentiment_score(
                sent_stock[ticker],
                latest_prices[ticker],
                market_data=market_sentiment,
            )
            sent_score = sent_result.get('sentiment_score')
            sent_detail = {
                'market_sentiment': sent_result.get('market_sentiment'),
                'stock_sentiment': sent_result.get('stock_sentiment'),
                'short_interest_score': sent_result.get('short_interest_score'),
                'revision_score': sent_result.get('revision_score'),
                'consensus_score': sent_result.get('consensus_score'),
                'insider_score': sent_result.get('insider_score'),
            }
            data_status['sentiment'] = 'calculated'
        else:
            sent_score = None
            data_status['sentiment'] = 'no_data'

        pillar_scores[ticker] = {
            'fundamental': fund_score,
            'technical': tech_score,
            'sentiment': sent_score,
            'fundamental_detail': fund_detail,
            'technical_detail': tech_detail,
            'sentiment_detail': sent_detail,
            'data_status': data_status,
        }

    # Filter to only fully-scored stocks
    scorable = {
        ticker: scores for ticker, scores in pillar_scores.items()
        if scores['fundamental'] is not None
        and scores['technical'] is not None
        and scores['sentiment'] is not None
    }

    if len(scorable) < 3:
        return None

    # Compute composite scores
    composite_results = composite_calc.calculate_scores_for_universe(scorable)

    return PipelineResult(
        composite_results=composite_results,
        pillar_scores=pillar_scores,
        data={
            'tickers': list(all_tickers),
            'fundamental_data': fundamental_data,
            'technical_data': tech_snapshots,
            'sentiment_data': sentiment_data,
            'latest_prices': latest_prices,
            'market_caps': market_caps,
            'market_sentiment': market_sentiment,
        },
        weights=weights,
    )


def main():
    args = parse_args()

    print(f"Historical Score Generator")
    print(f"  Months: {args.months}")
    print(f"  Dry run: {args.dry_run}")
    print(f"  Overwrite: {args.overwrite}")
    print()

    # Generate checkpoint dates
    checkpoints = generate_month_end_dates(args.months)
    print(f"Checkpoint dates ({len(checkpoints)}):")
    for d in checkpoints:
        print(f"  {d}")
    print()

    weights = ScoringPipeline.DEFAULT_WEIGHTS.copy()

    with get_db_session() as session:
        # Load active stocks
        stocks = session.query(Stock).filter_by(is_active=True).all()
        tickers = [s.ticker for s in stocks]
        stock_sectors = {s.ticker: s.sector for s in stocks}
        market_caps = {
            s.ticker: float(s.market_cap) if s.market_cap else None
            for s in stocks
        }
        print(f"Active stocks: {len(tickers)} ({', '.join(tickers)})")

        # Check for existing scores
        existing_dates = set()
        if not args.overwrite:
            existing_rows = (
                session.query(StockScore.calculation_date)
                .distinct()
                .all()
            )
            existing_dates = {r[0] for r in existing_rows}

        # Load price data into DataFrames
        print("\nLoading price data...")
        price_dfs = load_price_dataframes(session, tickers)
        print(f"  Loaded price data for {len(price_dfs)} stocks")

        # Precompute indicators for all tickers
        print("\nPrecomputing technical indicators...")
        indicator_builder = IndicatorBuilder()
        indicator_cache: Dict[str, pd.DataFrame] = {}
        for ticker, df in price_dfs.items():
            indicator_cache[ticker] = indicator_builder.compute(df)
        print(f"  Computed indicators for {len(indicator_cache)} stocks")

        # Load current fundamental and sentiment data (held constant)
        print("\nLoading fundamental and sentiment data (held constant across checkpoints)...")
        pipeline = ScoringPipeline(verbose=False)
        pipeline_data = pipeline.load_data(session, tickers=tickers)
        fundamental_data = pipeline_data['fundamental_data']
        sentiment_data = pipeline_data['sentiment_data']
        market_sentiment = pipeline_data['market_sentiment']
        print(f"  Fundamental: {len(fundamental_data)} stocks")
        print(f"  Sentiment: {len(sentiment_data)} stocks")
        print(f"  Market sentiment: {'available' if market_sentiment else 'N/A'}")

        if args.dry_run:
            print("\n[DRY RUN] Would generate scores for:")
            for cp_date in checkpoints:
                if cp_date in existing_dates:
                    print(f"  {cp_date} — SKIP (existing scores)")
                else:
                    print(f"  {cp_date} — would score")
            print("\nDry run complete. Use without --dry-run to save.")
            return

        # Score each checkpoint
        snapshot_mgr = SnapshotManager()
        scored_count = 0
        skipped_count = 0

        print("\nScoring checkpoints...")
        print("-" * 70)

        for cp_date in checkpoints:
            if cp_date in existing_dates and not args.overwrite:
                print(f"  {cp_date}: SKIP (existing scores, use --overwrite to replace)")
                skipped_count += 1
                continue

            result = score_checkpoint(
                checkpoint_date=cp_date,
                price_dfs=price_dfs,
                indicator_cache=indicator_cache,
                stock_sectors=stock_sectors,
                fundamental_data=fundamental_data,
                sentiment_data=sentiment_data,
                market_sentiment=market_sentiment,
                market_caps=market_caps,
                weights=weights,
            )

            if result is None:
                print(f"  {cp_date}: SKIP (insufficient data)")
                skipped_count += 1
                continue

            n_scored = len(result.composite_results)

            # Persist to DB
            pipeline.persist_to_db(session, result, calculation_date=cp_date)

            # Save snapshot
            snapshot_mgr.save(result, snapshot_date=cp_date)

            # Show top/bottom stock
            top = result.composite_results[0]
            bot = result.composite_results[-1]
            print(
                f"  {cp_date}: {n_scored} stocks scored | "
                f"Top: {top.ticker} ({top.composite_score:.1f}) | "
                f"Bot: {bot.ticker} ({bot.composite_score:.1f})"
            )
            scored_count += 1

    print("-" * 70)
    print(f"\nDone! Generated {scored_count} checkpoints, skipped {skipped_count}")
    print()
    print("NOTE: Fundamental and sentiment scores are held constant (only current")
    print("data available). Technical scores vary based on historical price data.")
    print("Composite trends are primarily driven by technical score changes (35% weight).")
    print()
    print("The web UI trend charts will now show historical score data.")


if __name__ == "__main__":
    main()
