"""
Collect and store sentiment data for all stocks in the universe.

Framework Reference: Section 2.3 (Sentiment Data), Section 5 (Sentiment Score)
Purpose: Populate sentiment_data table with latest sentiment indicators
Required for: Sentiment score calculations (stock-specific sentiment component)

Usage:
    python scripts/collect_sentiment_data.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, date
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
import yfinance as yf

from src.database import get_db_session
from src.database.models import Stock, SentimentData
from src.data_collection.yahoo_finance import YahooFinanceCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SentimentDataCollector:
    """
    Collects and stores sentiment metrics for the stock universe.

    Framework Section 5: Sentiment Score Components
    Stock-Specific Sentiment:
    - Analyst consensus and recommendations
    - Short interest data
    - Insider activity
    """

    def __init__(self):
        self.yf_collector = YahooFinanceCollector()
        self.stats = {
            'stocks_processed': 0,
            'stocks_success': 0,
            'stocks_failed': 0,
            'metrics_collected': {},
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

    def collect_short_interest_data(self, ticker: str) -> Dict[str, Optional[float]]:
        """
        Collect short interest data for a ticker.

        Framework Section 5.2: Short Interest (contrarian with threshold)

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with short interest metrics
        """
        short_data = {}

        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Short interest as % of float
            short_ratio = info.get('shortRatio')  # Days to cover
            short_percent_float = info.get('shortPercentOfFloat')

            short_data['short_interest'] = short_percent_float
            short_data['days_to_cover'] = short_ratio

            if short_ratio is not None:
                logger.info(f"{ticker}: Days to cover = {short_ratio:.2f}")
            else:
                logger.debug(f"{ticker}: No short interest data available")

        except Exception as e:
            logger.warning(f"Error collecting short interest for {ticker}: {e}")
            short_data['short_interest'] = None
            short_data['days_to_cover'] = None

        return short_data

    def collect_insider_activity_data(self, ticker: str) -> Optional[int]:
        """
        Collect insider trading activity for a ticker.

        Framework Section 5.2: Insider Activity (past 6 months)

        Note: Yahoo Finance provides limited insider data. This is a simplified
        implementation that tries to extract net insider shares from available data.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Net insider shares (positive = buying, negative = selling), or None
        """
        try:
            stock = yf.Ticker(ticker)

            # Try to get insider transactions
            # Note: yfinance insider data is limited and inconsistent
            insider_transactions = stock.insider_transactions

            if insider_transactions is not None and not insider_transactions.empty:
                # Calculate net shares from recent transactions (past 6 months)
                # Positive value = net buying, negative = net selling
                recent_transactions = insider_transactions.head(20)  # Get recent transactions

                # Sum up shares (negative for sales, positive for purchases)
                net_shares = 0
                for _, row in recent_transactions.iterrows():
                    transaction_type = row.get('Transaction', '').lower()
                    shares = row.get('Shares', 0)

                    if 'sale' in transaction_type or 'sold' in transaction_type:
                        net_shares -= abs(shares)
                    elif 'purchase' in transaction_type or 'bought' in transaction_type:
                        net_shares += abs(shares)

                logger.info(f"{ticker}: Net insider shares = {net_shares:,}")
                return int(net_shares)
            else:
                logger.debug(f"{ticker}: No insider transaction data available")
                return None

        except Exception as e:
            logger.warning(f"Error collecting insider activity for {ticker}: {e}")
            return None

    def collect_sentiment_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Collect sentiment metrics for a ticker.

        Framework Section 5.2: Stock-Specific Sentiment
        - Analyst consensus and recommendations
        - Short interest
        - Insider activity

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with sentiment metrics, or None if collection fails
        """
        logger.info(f"Collecting sentiment data for {ticker}")

        try:
            # Get analyst data from Yahoo Finance collector
            stock_data = self.yf_collector.get_stock_data(ticker)
            analyst_data = stock_data.get('analyst', {})

            if not analyst_data:
                logger.warning(f"No analyst data returned for {ticker}")

            # Get short interest data
            short_data = self.collect_short_interest_data(ticker)

            # Get insider activity data
            insider_net_shares = self.collect_insider_activity_data(ticker)

            # Track metrics collected
            metrics_count = 0
            if analyst_data.get('target_price') is not None:
                metrics_count += 1
            if analyst_data.get('recommendation_mean') is not None:
                metrics_count += 1
            if short_data.get('days_to_cover') is not None:
                metrics_count += 1
            if insider_net_shares is not None:
                metrics_count += 1

            logger.info(f"{ticker}: Collected {metrics_count}/4 sentiment metrics")

            # Prepare data for database (matching database schema)
            data = {
                'ticker': ticker,
                'data_date': date.today(),

                # Analyst Data (Framework Section 5.2 - Sentiment #2, #3)
                'consensus_price_target': analyst_data.get('target_price'),
                'num_analyst_opinions': analyst_data.get('num_analysts'),
                # Note: recommendation_mean (1-5 scale) will be calculated from ratings if available
                # For now, we'll store the analyst count and target price

                # Short Interest (Framework Section 5.2 - Sentiment #1)
                'short_interest_pct': short_data.get('short_interest'),
                'days_to_cover': short_data.get('days_to_cover'),

                # Insider Activity (Framework Section 5.2 - Sentiment #4)
                # Store as net shares in 6-month period
                'insider_net_shares_6m': insider_net_shares,
                'insider_buys_6m': None,  # Not available from current data source
                'insider_sells_6m': None,  # Not available from current data source

                # Additional analyst data (not collected yet)
                'num_buy_ratings': None,
                'num_hold_ratings': None,
                'num_sell_ratings': None,
                'upgrades_30d': None,
                'downgrades_30d': None,
                'estimate_revisions_up_90d': None,
                'estimate_revisions_down_90d': None,

                'data_source': 'yahoo_finance'
            }

            # Track which metrics were collected
            self.stats['metrics_collected'][ticker] = {
                'analyst_target': data['consensus_price_target'] is not None,
                'num_analysts': data['num_analyst_opinions'] is not None,
                'short_interest': data['days_to_cover'] is not None,
                'insider_activity': data['insider_net_shares_6m'] is not None,
                'total': metrics_count
            }

            return data

        except Exception as e:
            logger.error(f"Error collecting sentiment data for {ticker}: {e}")
            self.stats['errors'].append({
                'ticker': ticker,
                'error': str(e)
            })
            return None

    def store_sentiment_data(self, data: Dict[str, Any]) -> bool:
        """
        Store sentiment data in database.

        Uses INSERT ... ON CONFLICT UPDATE to handle duplicates
        (same ticker + data_date).

        Args:
            data: Dict with sentiment data

        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_session() as session:
                # Use PostgreSQL INSERT ... ON CONFLICT UPDATE
                stmt = insert(SentimentData).values(**data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['ticker', 'data_date'],
                    set_={
                        'consensus_price_target': stmt.excluded.consensus_price_target,
                        'num_analyst_opinions': stmt.excluded.num_analyst_opinions,
                        'short_interest_pct': stmt.excluded.short_interest_pct,
                        'days_to_cover': stmt.excluded.days_to_cover,
                        'insider_net_shares_6m': stmt.excluded.insider_net_shares_6m,
                        'data_source': stmt.excluded.data_source
                    }
                )

                session.execute(stmt)
                session.commit()

                logger.info(f"Stored sentiment data for {data['ticker']}")
                return True

        except Exception as e:
            logger.error(f"Error storing sentiment data for {data['ticker']}: {e}")
            return False

    def run(self) -> Dict[str, Any]:
        """
        Main execution: collect and store sentiment data for all active stocks.

        Returns:
            Dict with execution statistics
        """
        logger.info("=" * 80)
        logger.info("SENTIMENT DATA COLLECTION - START")
        logger.info("=" * 80)

        tickers = self.get_active_stocks()
        self.stats['stocks_processed'] = len(tickers)

        for ticker in tickers:
            logger.info(f"\nProcessing {ticker}...")

            # Collect sentiment data
            data = self.collect_sentiment_data(ticker)

            if data:
                # Store in database
                success = self.store_sentiment_data(data)
                if success:
                    self.stats['stocks_success'] += 1
                else:
                    self.stats['stocks_failed'] += 1
            else:
                self.stats['stocks_failed'] += 1

        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("SENTIMENT DATA COLLECTION - SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total stocks processed: {self.stats['stocks_processed']}")
        logger.info(f"Successfully collected: {self.stats['stocks_success']}")
        logger.info(f"Failed: {self.stats['stocks_failed']}")

        # Detailed metrics breakdown
        logger.info("\nMetrics Coverage by Stock:")
        for ticker, metrics in self.stats['metrics_collected'].items():
            logger.info(f"  {ticker}: {metrics['total']}/4 metrics")
            logger.info(f"    - Analyst Target: {'✓' if metrics['analyst_target'] else '✗'}")
            logger.info(f"    - Num Analysts: {'✓' if metrics['num_analysts'] else '✗'}")
            logger.info(f"    - Short Interest: {'✓' if metrics['short_interest'] else '✗'}")
            logger.info(f"    - Insider Activity: {'✓' if metrics['insider_activity'] else '✗'}")

        if self.stats['errors']:
            logger.info("\nErrors encountered:")
            for error in self.stats['errors']:
                logger.info(f"  {error['ticker']}: {error['error']}")

        return self.stats


def main():
    """Main entry point."""
    collector = SentimentDataCollector()
    stats = collector.run()

    # Exit with appropriate code
    if stats['stocks_failed'] == 0:
        logger.info("\n✅ All stocks processed successfully!")
        return 0
    elif stats['stocks_success'] > 0:
        logger.warning(f"\n⚠️ Partial success: {stats['stocks_success']}/{stats['stocks_processed']} stocks")
        return 1
    else:
        logger.error("\n❌ All stocks failed!")
        return 2


if __name__ == "__main__":
    exit(main())
