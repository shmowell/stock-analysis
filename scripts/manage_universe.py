"""
Universe Manager - Add, remove, list, and reactivate stocks.

Usage:
    python scripts/manage_universe.py list
    python scripts/manage_universe.py add TSLA META AMD
    python scripts/manage_universe.py remove DIS
    python scripts/manage_universe.py reactivate DIS

Author: Stock Analysis Framework v2.0
Date: 2026-02-14
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from database import get_db_session
from database.models import Stock
from data_collection import YahooFinanceCollector
from utils.validators import DataValidationError


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


def add_stocks(tickers: list):
    """Add new stocks to the universe.

    Fetches company info from Yahoo Finance and inserts into the stocks table.
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
        print("Run data collection scripts to populate data for new stocks.")
    if errors:
        print(f"\nFailed to add {len(errors)} stock(s)")


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
        add_stocks(args.tickers)
    elif args.command == 'remove':
        remove_stocks(args.tickers)
    elif args.command == 'reactivate':
        reactivate_stocks(args.tickers)


if __name__ == "__main__":
    main()
