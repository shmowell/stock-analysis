"""
Populate stock universe table.

Framework Reference: Section 10 - Phase 1 Week 1
- Define initial universe of 10-20 stocks
- Collect basic company information
- Populate stocks table

Usage:
    python scripts/populate_universe.py
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_db_session, test_connection
from src.database.models import Stock
from src.data_collection import YahooFinanceCollector
from src.utils.validators import DataValidationError
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Sample universe - diverse sectors
SAMPLE_UNIVERSE = [
    # Technology
    'AAPL',   # Apple - Consumer Electronics
    'MSFT',   # Microsoft - Software
    'GOOGL',  # Alphabet - Internet
    'NVDA',   # NVIDIA - Semiconductors

    # Finance
    'JPM',    # JPMorgan Chase - Banking
    'V',      # Visa - Payment Processing

    # Healthcare
    'JNJ',    # Johnson & Johnson - Pharmaceuticals
    'UNH',    # UnitedHealth - Health Insurance

    # Consumer
    'PG',     # Procter & Gamble - Consumer Goods
    'KO',     # Coca-Cola - Beverages
    'WMT',    # Walmart - Retail

    # Industrial
    'BA',     # Boeing - Aerospace
    'CAT',    # Caterpillar - Heavy Machinery

    # Energy
    'XOM',    # Exxon Mobil - Oil & Gas

    # Communication
    'DIS',    # Disney - Entertainment
]


def populate_stock_universe(tickers: list[str], collector: YahooFinanceCollector):
    """
    Populate stocks table with universe of stocks.

    Args:
        tickers: List of ticker symbols
        collector: Yahoo Finance collector instance
    """
    logger.info(f"Starting universe population with {len(tickers)} stocks")

    success_count = 0
    error_count = 0
    errors = []

    with get_db_session() as session:
        for ticker in tickers:
            try:
                logger.info(f"Processing {ticker}...")

                # Check if stock already exists
                existing = session.query(Stock).filter_by(ticker=ticker).first()
                if existing:
                    logger.info(f"  {ticker} already exists, updating...")
                    stock = existing
                else:
                    stock = Stock(ticker=ticker)

                # Get company info from Yahoo Finance
                try:
                    data = collector.get_stock_data(ticker)
                    company_info = data['company_info']
                    fundamental = data['fundamental']

                    # Update stock information
                    stock.company_name = company_info.get('name')
                    stock.sector = company_info.get('sector')
                    stock.industry = company_info.get('industry')
                    stock.market_cap = fundamental.get('market_cap')
                    stock.is_active = True

                    logger.info(f"  ✓ {ticker}: {stock.company_name} ({stock.sector})")

                except DataValidationError as e:
                    logger.error(f"  ✗ Error fetching data for {ticker}: {e}")
                    # Still add the stock but mark as inactive
                    stock.company_name = f"Unknown ({ticker})"
                    stock.is_active = False
                    stock.notes = f"Error fetching data: {e}"
                    error_count += 1
                    errors.append((ticker, str(e)))
                    continue

                # Add or update stock
                if not existing:
                    session.add(stock)

                success_count += 1

            except Exception as e:
                logger.error(f"  ✗ Unexpected error processing {ticker}: {e}")
                error_count += 1
                errors.append((ticker, str(e)))
                continue

        # Commit all changes
        try:
            session.commit()
            logger.info(f"\n✓ Successfully processed {success_count} stocks")
            if error_count > 0:
                logger.warning(f"✗ Errors encountered for {error_count} stocks:")
                for ticker, error in errors:
                    logger.warning(f"  - {ticker}: {error}")
        except Exception as e:
            logger.error(f"✗ Error committing to database: {e}")
            session.rollback()
            raise


def show_universe_summary():
    """Display summary of current stock universe."""
    logger.info("\n" + "="*60)
    logger.info("STOCK UNIVERSE SUMMARY")
    logger.info("="*60)

    with get_db_session() as session:
        stocks = session.query(Stock).filter_by(is_active=True).order_by(Stock.sector, Stock.ticker).all()

        if not stocks:
            logger.info("No stocks in universe")
            return

        logger.info(f"\nTotal Active Stocks: {len(stocks)}\n")

        # Group by sector
        sectors = {}
        for stock in stocks:
            sector = stock.sector or 'Unknown'
            if sector not in sectors:
                sectors[sector] = []
            sectors[sector].append(stock)

        # Display by sector
        for sector in sorted(sectors.keys()):
            logger.info(f"\n{sector}:")
            for stock in sectors[sector]:
                market_cap_str = f"${float(stock.market_cap)/1e9:.1f}B" if stock.market_cap else "N/A"
                logger.info(f"  {stock.ticker:6s} - {stock.company_name:40s} {market_cap_str}")

    logger.info("\n" + "="*60)


def main():
    """Main execution."""
    logger.info("Stock Universe Populator")
    logger.info("Framework Phase 1 - Week 1: Data Infrastructure\n")

    # Test database connection
    logger.info("Testing database connection...")
    if not test_connection():
        logger.error("Database connection failed. Check your .env configuration.")
        return 1

    # Create collector
    logger.info("Initializing Yahoo Finance collector...")
    collector = YahooFinanceCollector()

    # Populate universe
    logger.info(f"\nPopulating universe with {len(SAMPLE_UNIVERSE)} stocks...")
    populate_stock_universe(SAMPLE_UNIVERSE, collector)

    # Show summary
    show_universe_summary()

    logger.info("\n✓ Universe population complete!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
