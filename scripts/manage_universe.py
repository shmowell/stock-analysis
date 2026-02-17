"""
Universe Manager - Add, remove, list, and reactivate stocks.

Usage:
    python scripts/manage_universe.py list
    python scripts/manage_universe.py add TSLA META AMD
    python scripts/manage_universe.py add TSLA --no-collect
    python scripts/manage_universe.py remove DIS
    python scripts/manage_universe.py reactivate DIS

Author: Stock Analysis Framework v2.0
Date: 2026-02-14
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from database import get_db_session
from database.models import Stock
from data_collection import YahooFinanceCollector
from utils.validators import DataValidationError

logger = logging.getLogger(__name__)


def list_stocks():
    """Display current stock universe grouped by sector."""
    with get_db_session() as session:
        active = session.query(Stock).filter_by(is_active=True).order_by(Stock.sector, Stock.ticker).all()
        inactive = session.query(Stock).filter_by(is_active=False).order_by(Stock.ticker).all()

        print(f"Active stocks: {len(active)}")
        print("-" * 70)

        # Group by sector
        sectors = {}
        for s in active:
            sector = s.sector or 'Unknown'
            sectors.setdefault(sector, []).append(s)

        for sector in sorted(sectors):
            print(f"\n  {sector}:")
            for s in sectors[sector]:
                cap = f"${float(s.market_cap)/1e9:.1f}B" if s.market_cap else "N/A"
                print(f"    {s.ticker:6s}  {s.company_name or '':40s}  {cap}")

        if inactive:
            print(f"\nInactive stocks ({len(inactive)}):")
            for s in inactive:
                print(f"    {s.ticker:6s}  {s.company_name or ''}")


def add_stocks(tickers: list) -> list:
    """Add new stocks to the universe.

    Fetches company info from Yahoo Finance and inserts into the stocks table.

    Returns:
        List of successfully added/reactivated ticker symbols.
    """
    collector = YahooFinanceCollector()
    added = []
    errors = []

    with get_db_session() as session:
        for ticker in tickers:
            ticker = ticker.upper()
            existing = session.query(Stock).filter_by(ticker=ticker).first()

            if existing and existing.is_active:
                print(f"  {ticker}: already in universe (active)")
                continue
            elif existing and not existing.is_active:
                # Reactivate
                existing.is_active = True
                print(f"  {ticker}: reactivated (was inactive)")
                added.append(ticker)
                continue

            # Fetch from Yahoo Finance
            try:
                data = collector.get_stock_data(ticker)
                info = data['company_info']
                fund = data['fundamental']

                stock = Stock(
                    ticker=ticker,
                    company_name=info.get('name'),
                    sector=info.get('sector'),
                    industry=info.get('industry'),
                    market_cap=fund.get('market_cap'),
                    is_active=True,
                )
                session.add(stock)
                added.append(ticker)
                print(f"  {ticker}: {stock.company_name} ({stock.sector}) - added")

            except (DataValidationError, Exception) as e:
                errors.append((ticker, str(e)))
                print(f"  {ticker}: FAILED - {e}")

    if added:
        print(f"\nAdded {len(added)} stock(s): {', '.join(added)}")
    if errors:
        print(f"\nFailed to add {len(errors)} stock(s)")

    return added


def collect_and_score(tickers: list):
    """Run data collection for specific tickers, then re-score the full universe.

    Runs collection scripts in dependency order, then the scoring pipeline.
    """
    # Collection scripts in dependency order
    COLLECT_SCRIPTS = [
        ('Price data',           'scripts/collect_price_data.py'),
        ('Fundamental data',     'scripts/collect_fundamental_data.py'),
        ('Technical indicators', 'scripts/calculate_technical_indicators.py'),
        ('Sentiment data',       'scripts/collect_sentiment_data.py'),
        ('Market sentiment',     'scripts/collect_market_sentiment.py'),
        ('FMP data',             'scripts/collect_fmp_data.py'),
    ]

    print(f"\nCollecting data for: {', '.join(tickers)}")
    print("-" * 60)

    for name, script_path in COLLECT_SCRIPTS:
        full_path = project_root / script_path
        cmd = [sys.executable, str(full_path)]

        # Pass --ticker for per-stock scripts (not market_sentiment)
        if 'market_sentiment' not in script_path:
            cmd.extend(['--ticker'] + tickers)

        print(f"  {name}...", end=" ", flush=True)
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300,
                cwd=str(project_root),
            )
            if proc.returncode == 0:
                print("OK")
            else:
                print(f"WARNING (exit {proc.returncode})")
                if proc.stderr:
                    for line in proc.stderr.strip().split('\n')[-3:]:
                        print(f"    {line}")
        except subprocess.TimeoutExpired:
            print("TIMEOUT")

    # Score full universe (percentile ranking needs all stocks)
    print("\nScoring full universe...", end=" ", flush=True)
    try:
        from scoring import ScoringPipeline
        from backtesting.snapshot_manager import SnapshotManager

        pipeline = ScoringPipeline(verbose=False)
        with get_db_session() as session:
            result = pipeline.run(session)
            pipeline.persist_to_db(session, result)
            pipeline.persist_to_json(result)
            SnapshotManager().save(result)

        scored = len(result.composite_results)
        print(f"OK ({scored} stocks scored)")

        # Show scores for newly added tickers
        print(f"\nScores for new stocks:")
        for cs in result.composite_results:
            if cs.ticker in tickers:
                print(f"  {cs.ticker}: {cs.composite_score:.1f} ({cs.recommendation})")
        # Show any that weren't scored
        scored_tickers = {cs.ticker for cs in result.composite_results}
        for t in tickers:
            if t not in scored_tickers:
                print(f"  {t}: INSUFFICIENT DATA")

    except Exception as e:
        print(f"FAILED ({e})")


def remove_stocks(tickers: list):
    """Soft-delete stocks from the universe (set is_active=False)."""
    with get_db_session() as session:
        for ticker in tickers:
            ticker = ticker.upper()
            stock = session.query(Stock).filter_by(ticker=ticker).first()
            if not stock:
                print(f"  {ticker}: not found in database")
            elif not stock.is_active:
                print(f"  {ticker}: already inactive")
            else:
                stock.is_active = False
                print(f"  {ticker}: deactivated ({stock.company_name})")


def reactivate_stocks(tickers: list):
    """Reactivate previously removed stocks."""
    with get_db_session() as session:
        for ticker in tickers:
            ticker = ticker.upper()
            stock = session.query(Stock).filter_by(ticker=ticker).first()
            if not stock:
                print(f"  {ticker}: not found in database")
            elif stock.is_active:
                print(f"  {ticker}: already active")
            else:
                stock.is_active = True
                print(f"  {ticker}: reactivated ({stock.company_name})")


def main():
    parser = argparse.ArgumentParser(description="Manage stock analysis universe")
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # list
    subparsers.add_parser('list', help='List current universe')

    # add
    add_parser = subparsers.add_parser('add', help='Add stocks to universe')
    add_parser.add_argument('tickers', nargs='+', help='Ticker symbols to add')
    add_parser.add_argument('--no-collect', action='store_true',
                            help='Skip automatic data collection and scoring')

    # remove
    rm_parser = subparsers.add_parser('remove', help='Remove stocks from universe')
    rm_parser.add_argument('tickers', nargs='+', help='Ticker symbols to remove')

    # reactivate
    react_parser = subparsers.add_parser('reactivate', help='Reactivate removed stocks')
    react_parser.add_argument('tickers', nargs='+', help='Ticker symbols to reactivate')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == 'list':
        list_stocks()
    elif args.command == 'add':
        added = add_stocks(args.tickers)
        if added and not args.no_collect:
            collect_and_score(added)
        elif added:
            print("Skipping data collection (--no-collect). "
                  "Run 'Recalculate' in the web UI or daily_report.py to populate data.")
    elif args.command == 'remove':
        remove_stocks(args.tickers)
    elif args.command == 'reactivate':
        reactivate_stocks(args.tickers)


if __name__ == "__main__":
    main()
