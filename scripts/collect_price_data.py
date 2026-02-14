"""
Collect and store historical price data for all stocks in the universe.

Framework Reference: Section 2.2 (Technical Data)
Purpose: Populate price_data table with 2 years of daily prices
Required for: Percentile ranking and technical score calculations

Usage:
    python scripts/collect_price_data.py
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from datetime import datetime, date
import logging
from typing import List, Dict, Any
import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from database import get_db_session
from database.models import Stock, PriceData
from data_collection.yahoo_finance import YahooFinanceCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PriceDataCollector:
    """
    Collects and stores historical price data.

    Framework Section 2.2: Daily price history for technical analysis
    and percentile-based momentum calculations.
    """

    def __init__(self):
        self.yf_collector = YahooFinanceCollector()
        self.stats = {
            'stocks_processed': 0,
            'records_inserted': 0,
            'records_updated': 0,
            'errors': []
        }

    def get_active_stocks(self) -> List[str]:
        """
        Fetch all active stocks from database.

        Returns:
            List of ticker symbols
        """
        with get_db_session() as session:
            stmt = select(Stock.ticker).where(Stock.is_active == True)
            result = session.execute(stmt)
            tickers = [row[0] for row in result]
            logger.info(f"Found {len(tickers)} active stocks")
            return tickers

    def collect_price_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        """
        Collect price history for a ticker.

        Args:
            ticker: Stock ticker symbol
            period: Time period (default: 1y)

        Returns:
            DataFrame with price history
        """
        logger.info(f"Collecting price data for {ticker} (period={period})")

        try:
            hist = self.yf_collector.get_price_history(
                ticker=ticker,
                period=period,
                interval="1d"
            )

            if hist.empty:
                logger.warning(f"No price data returned for {ticker}")
                return pd.DataFrame()

            # Reset index to make Date a column
            hist = hist.reset_index()

            # Rename columns to match database schema
            hist = hist.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })

            # Add ticker and data source
            hist['ticker'] = ticker
            hist['data_source'] = 'yahoo_finance'

            # For adjusted_close, use 'Close' if 'Adj Close' not available
            if 'Adj Close' in hist.columns:
                hist['adjusted_close'] = hist['Adj Close']
            else:
                hist['adjusted_close'] = hist['close']

            # Select only columns we need
            hist = hist[['ticker', 'date', 'open', 'high', 'low', 'close',
                        'adjusted_close', 'volume', 'data_source']]

            # Convert date to date type (remove time component)
            hist['date'] = pd.to_datetime(hist['date']).dt.date

            logger.info(f"Collected {len(hist)} days of price data for {ticker}")
            return hist

        except Exception as e:
            error_msg = f"Error collecting price data for {ticker}: {e}"
            logger.error(error_msg)
            self.stats['errors'].append({'ticker': ticker, 'error': str(e)})
            return pd.DataFrame()

    def store_price_data(self, price_data: pd.DataFrame) -> Dict[str, int]:
        """
        Store price data in database.

        Uses PostgreSQL UPSERT to handle duplicates gracefully.
        Conflict resolution: Update existing records if (ticker, date) already exists.

        Args:
            price_data: DataFrame with price history

        Returns:
            Dict with counts of inserted and updated records
        """
        if price_data.empty:
            return {'inserted': 0, 'updated': 0}

        ticker = price_data['ticker'].iloc[0]
        records = price_data.to_dict('records')

        inserted = 0
        updated = 0

        with get_db_session() as session:
            try:
                for record in records:
                    # PostgreSQL UPSERT using insert().on_conflict_do_update()
                    stmt = insert(PriceData).values(**record)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['ticker', 'date'],  # Unique constraint
                        set_={
                            'open': stmt.excluded.open,
                            'high': stmt.excluded.high,
                            'low': stmt.excluded.low,
                            'close': stmt.excluded.close,
                            'adjusted_close': stmt.excluded.adjusted_close,
                            'volume': stmt.excluded.volume,
                            'data_source': stmt.excluded.data_source
                        }
                    )

                    result = session.execute(stmt)

                    # Check if insert or update occurred
                    # Note: PostgreSQL doesn't easily expose this, so we'll count total
                    if result.rowcount > 0:
                        inserted += 1

                session.commit()
                logger.info(f"Stored {len(records)} price records for {ticker}")

                return {'inserted': inserted, 'updated': 0}  # Simplified tracking

            except Exception as e:
                session.rollback()
                error_msg = f"Error storing price data for {ticker}: {e}"
                logger.error(error_msg)
                self.stats['errors'].append({'ticker': ticker, 'error': str(e)})
                return {'inserted': 0, 'updated': 0}

    def collect_all_stocks(self, period: str = "1y") -> Dict[str, Any]:
        """
        Collect price data for all active stocks.

        Args:
            period: Time period to collect (default: 1y)

        Returns:
            Statistics about the collection process
        """
        logger.info("=" * 80)
        logger.info("Starting price data collection for all stocks")
        logger.info("=" * 80)

        tickers = self.get_active_stocks()

        for ticker in tickers:
            logger.info(f"\nProcessing {ticker} ({self.stats['stocks_processed'] + 1}/{len(tickers)})")

            # Collect price data
            price_data = self.collect_price_data(ticker, period)

            if not price_data.empty:
                # Store in database
                result = self.store_price_data(price_data)
                self.stats['records_inserted'] += result['inserted']
                self.stats['records_updated'] += result['updated']

            self.stats['stocks_processed'] += 1

        return self.stats

    def print_summary(self):
        """Print collection summary."""
        logger.info("\n" + "=" * 80)
        logger.info("PRICE DATA COLLECTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Stocks processed: {self.stats['stocks_processed']}")
        logger.info(f"Records inserted: {self.stats['records_inserted']}")
        logger.info(f"Records updated: {self.stats['records_updated']}")
        logger.info(f"Errors: {len(self.stats['errors'])}")

        if self.stats['errors']:
            logger.info("\nErrors encountered:")
            for error in self.stats['errors']:
                logger.info(f"  - {error['ticker']}: {error['error']}")

        logger.info("=" * 80)


def main():
    """Main execution function."""
    collector = PriceDataCollector()

    try:
        # Collect 2 years of price data for all stocks
        # Framework Section 4.2: 12-1 month momentum requires 13+ months
        # Using 2y to ensure sufficient data for all momentum calculations
        stats = collector.collect_all_stocks(period="2y")

        # Print summary
        collector.print_summary()

        # Exit with error code if any errors occurred
        if stats['errors']:
            logger.warning(f"\nCompleted with {len(stats['errors'])} errors")
            sys.exit(1)
        else:
            logger.info("\n✅ Price data collection completed successfully!")
            sys.exit(0)

    except KeyboardInterrupt:
        logger.info("\n\nCollection interrupted by user")
        collector.print_summary()
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\nFatal error: {e}")
        collector.print_summary()
        sys.exit(1)


if __name__ == "__main__":
    main()
