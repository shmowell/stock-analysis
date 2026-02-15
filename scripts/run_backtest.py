"""
Run Technical Backtest — CLI entry point.

Loads historical price data from the database, runs the TechnicalBacktester
across a configurable date range, and prints a report with quintile analysis,
Spearman correlation, and hit rates.

Usage:
    python scripts/run_backtest.py
    python scripts/run_backtest.py --start 2024-03-01 --end 2025-06-30
    python scripts/run_backtest.py --start 2024-06-01 --end 2025-01-31

Framework Reference: Section 10 (Backtesting & Paper Trading)
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import select

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from database import get_db_session
from database.models import Stock, PriceData
from backtesting.technical_backtest import TechnicalBacktester


def parse_args():
    parser = argparse.ArgumentParser(description="Run technical scoring backtest")
    parser.add_argument(
        '--start', type=str, default=None,
        help='Start date (YYYY-MM-DD). Default: 12 months before end date.',
    )
    parser.add_argument(
        '--end', type=str, default=None,
        help='End date (YYYY-MM-DD). Default: latest available data minus 1 month.',
    )
    return parser.parse_args()


def load_price_data(session) -> dict:
    """Load price data for all active stocks from the database.

    Returns:
        Tuple of (price_data dict, stock_sectors dict).
    """
    # Get active stocks with sectors
    stocks = session.query(Stock).filter_by(is_active=True).all()
    stock_sectors = {s.ticker: s.sector or 'Unknown' for s in stocks}
    tickers = list(stock_sectors.keys())

    print(f"Loading price data for {len(tickers)} stocks...")

    price_data = {}
    for ticker in tickers:
        rows = (
            session.query(PriceData)
            .filter(PriceData.ticker == ticker)
            .order_by(PriceData.date)
            .all()
        )

        if not rows:
            print(f"  WARNING: No price data for {ticker}, skipping")
            continue

        data = {
            'date': [r.date for r in rows],
            'open': [float(r.open) if r.open else None for r in rows],
            'high': [float(r.high) if r.high else None for r in rows],
            'low': [float(r.low) if r.low else None for r in rows],
            'close': [float(r.close) if r.close else None for r in rows],
            'volume': [int(r.volume) if r.volume else 0 for r in rows],
        }

        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').set_index('date')
        price_data[ticker] = df

        print(f"  {ticker}: {len(df)} days ({df.index.min().date()} to {df.index.max().date()})")

    return price_data, stock_sectors


def determine_date_range(price_data, args):
    """Determine backtest date range from args or data availability."""
    # Find the range of available data
    all_max_dates = [df.index.max() for df in price_data.values()]
    all_min_dates = [df.index.min() for df in price_data.values()]
    data_end = min(all_max_dates).date()  # Use earliest end for safety
    data_start = max(all_min_dates).date()  # Use latest start

    if args.end:
        end_date = date.fromisoformat(args.end)
    else:
        # Default: 1 month before data end (need forward returns)
        end_date = data_end - timedelta(days=31)

    if args.start:
        start_date = date.fromisoformat(args.start)
    else:
        # Default: 12 months before end
        start_date = date(end_date.year - 1, end_date.month, end_date.day)

    # Need at least 252 trading days of lookback for 12-1m momentum
    earliest_allowed = data_start + timedelta(days=365)
    if start_date < earliest_allowed:
        print(f"  Adjusting start from {start_date} to {earliest_allowed} "
              f"(need 1yr lookback for indicators)")
        start_date = earliest_allowed

    return start_date, end_date


def main():
    args = parse_args()

    print("=" * 80)
    print("TECHNICAL SCORING BACKTEST")
    print("=" * 80)
    print()

    with get_db_session() as session:
        price_data, stock_sectors = load_price_data(session)

    if not price_data:
        print("ERROR: No price data available")
        sys.exit(1)

    start_date, end_date = determine_date_range(price_data, args)
    print(f"\nBacktest period: {start_date} to {end_date}")
    print(f"Universe: {len(price_data)} stocks across "
          f"{len(set(stock_sectors.values()))} sectors")
    print()

    # Run backtest
    backtester = TechnicalBacktester()
    report = backtester.run(
        price_data=price_data,
        stock_sectors=stock_sectors,
        start_date=start_date,
        end_date=end_date,
    )

    # Print report
    print(report.summary())

    # Save report to file
    reports_dir = project_root / 'data' / 'reports'
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"backtest_{date.today().isoformat()}.txt"
    with open(report_path, 'w') as f:
        f.write(report.summary())
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
