"""
Collect and store fundamental data for all stocks in the universe.

Framework Reference: Section 2.1 (Fundamental Data), Section 3 (Fundamental Score)
Purpose: Populate fundamental_data table with latest fundamental metrics
Required for: Fundamental score calculations (value, quality, growth components)

Usage:
    python scripts/collect_fundamental_data.py
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from datetime import datetime, date
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from database import get_db_session
from database.models import Stock, FundamentalData
from data_collection.yahoo_finance import YahooFinanceCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FundamentalDataCollector:
    """
    Collects and stores fundamental metrics for the stock universe.

    Framework Section 3: Fundamental Score Components
    - Value: P/E, P/B, P/S, EV/EBITDA, Dividend Yield
    - Quality: ROE, ROA, Net/Operating/Gross Margins
    - Growth: Revenue, Earnings, FCF growth
    - Financial Health: Current/Quick Ratios, Debt/Equity
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

    def collect_fundamental_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Collect fundamental metrics for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with fundamental metrics, or None if collection fails
        """
        logger.info(f"Collecting fundamental data for {ticker}")

        try:
            # Get comprehensive stock data from Yahoo Finance
            stock_data = self.yf_collector.get_stock_data(ticker)
            fundamentals = stock_data.get('fundamental', {})

            if not fundamentals:
                logger.warning(f"No fundamental data returned for {ticker}")
                return None

            # Track which metrics were successfully collected
            metrics_count = sum(1 for v in fundamentals.values() if v is not None)
            total_metrics = len(fundamentals)
            logger.info(f"{ticker}: Collected {metrics_count}/{total_metrics} metrics")

            # Prepare data for database
            # Note: Yahoo Finance provides trailing/current data, not historical quarters
            # report_date is set to today since this is the latest available data
            data = {
                'ticker': ticker,
                'report_date': date.today(),
                'period_type': 'current',  # Latest available metrics

                # Valuation Metrics (Framework Section 3.2 - Value Component)
                'pe_ratio': fundamentals.get('pe_ratio'),
                'forward_pe': fundamentals.get('pe_ratio'),  # Yahoo returns forward or trailing
                'pb_ratio': fundamentals.get('pb_ratio'),
                'ps_ratio': fundamentals.get('ps_ratio'),
                'ev_to_ebitda': fundamentals.get('ev_ebitda'),
                'peg_ratio': fundamentals.get('peg_ratio'),
                'dividend_yield': fundamentals.get('dividend_yield'),

                # Quality Metrics (Framework Section 3.2 - Quality Component)
                'roe': fundamentals.get('roe'),
                'roa': fundamentals.get('roa'),
                'net_margin': fundamentals.get('net_margin'),
                'operating_margin': fundamentals.get('operating_margin'),
                'gross_margin': fundamentals.get('gross_margin'),

                # Growth Metrics (Framework Section 3.2 - Growth Component)
                'revenue_growth_yoy': fundamentals.get('revenue_growth'),
                'eps_growth_yoy': fundamentals.get('earnings_growth'),

                # Financial Health
                'current_ratio': fundamentals.get('current_ratio'),
                'quick_ratio': fundamentals.get('quick_ratio'),
                'debt_to_equity': fundamentals.get('debt_to_equity'),

                # Market Data
                'beta': fundamentals.get('beta'),

                'data_source': 'yahoo_finance'
            }

            return data

        except Exception as e:
            logger.error(f"Error collecting fundamental data for {ticker}: {e}")
            self.stats['errors'].append({
                'ticker': ticker,
                'error': str(e)
            })
            return None

    def store_fundamental_data(self, data: Dict[str, Any]) -> bool:
        """
        Store fundamental data in database.

        Uses INSERT ... ON CONFLICT UPDATE to handle duplicates
        (same ticker + report_date).

        Args:
            data: Fundamental data dict

        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_session() as session:
                # Use upsert to handle existing data
                # If ticker + report_date + period_type exists, update the metrics
                stmt = insert(FundamentalData).values(**data)

                # Create update dict excluding the conflict keys
                update_data = {
                    key: value
                    for key, value in data.items()
                    if key not in ['ticker', 'report_date', 'period_type']
                }

                stmt = stmt.on_conflict_do_update(
                    index_elements=['ticker', 'report_date', 'period_type'],
                    set_=update_data
                )

                session.execute(stmt)
                session.commit()

                logger.info(f"Stored fundamental data for {data['ticker']}")
                return True

        except Exception as e:
            logger.error(f"Error storing data for {data['ticker']}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.stats['errors'].append({
                'ticker': data['ticker'],
                'error': f"Storage error: {str(e)}"
            })
            return False

    def run(self):
        """
        Main execution: Collect and store fundamental data for all active stocks.
        """
        logger.info("=" * 80)
        logger.info("FUNDAMENTAL DATA COLLECTION - START")
        logger.info("=" * 80)

        # Get active stocks
        tickers = self.get_active_stocks()

        if not tickers:
            logger.warning("No active stocks found in database")
            return

        logger.info(f"Processing {len(tickers)} stocks...")

        # Process each stock
        for ticker in tickers:
            self.stats['stocks_processed'] += 1

            # Collect data
            data = self.collect_fundamental_data(ticker)

            if data is None:
                self.stats['stocks_failed'] += 1
                continue

            # Store data
            if self.store_fundamental_data(data):
                self.stats['stocks_success'] += 1

                # Track metrics availability
                for key, value in data.items():
                    if key not in ['ticker', 'report_date', 'period_type', 'data_source', 'created_at']:
                        if key not in self.stats['metrics_collected']:
                            self.stats['metrics_collected'][key] = 0
                        if value is not None:
                            self.stats['metrics_collected'][key] += 1
            else:
                self.stats['stocks_failed'] += 1

        # Print summary
        self._print_summary(tickers)

    def _print_summary(self, tickers: List[str]):
        """Print collection summary statistics."""
        logger.info("=" * 80)
        logger.info("FUNDAMENTAL DATA COLLECTION - SUMMARY")
        logger.info("=" * 80)

        logger.info(f"Stocks processed: {self.stats['stocks_processed']}")
        logger.info(f"  ✓ Success: {self.stats['stocks_success']}")
        logger.info(f"  ✗ Failed: {self.stats['stocks_failed']}")

        if self.stats['metrics_collected']:
            logger.info("\nMetrics Availability (across all stocks):")
            total_stocks = self.stats['stocks_success']

            # Group metrics by category
            value_metrics = ['pe_ratio', 'forward_pe', 'pb_ratio', 'ps_ratio',
                           'ev_to_ebitda', 'peg_ratio', 'dividend_yield']
            quality_metrics = ['roe', 'roa', 'net_margin', 'operating_margin', 'gross_margin']
            growth_metrics = ['revenue_growth_yoy', 'eps_growth_yoy']
            health_metrics = ['current_ratio', 'quick_ratio', 'debt_to_equity']

            categories = [
                ("VALUE", value_metrics),
                ("QUALITY", quality_metrics),
                ("GROWTH", growth_metrics),
                ("FINANCIAL HEALTH", health_metrics),
                ("MARKET", ['beta'])
            ]

            for category_name, metrics in categories:
                logger.info(f"\n  {category_name}:")
                for metric in metrics:
                    count = self.stats['metrics_collected'].get(metric, 0)
                    pct = (count / total_stocks * 100) if total_stocks > 0 else 0
                    status = "✓" if pct >= 80 else "⚠" if pct >= 50 else "✗"
                    logger.info(f"    {status} {metric}: {count}/{total_stocks} ({pct:.0f}%)")

        if self.stats['errors']:
            logger.warning(f"\nErrors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:5]:  # Show first 5
                logger.warning(f"  - {error['ticker']}: {error['error']}")
            if len(self.stats['errors']) > 5:
                logger.warning(f"  ... and {len(self.stats['errors']) - 5} more")

        logger.info("\n" + "=" * 80)

        # Data quality assessment
        if self.stats['stocks_success'] > 0:
            coverage = (self.stats['stocks_success'] / self.stats['stocks_processed']) * 100
            logger.info(f"Data Quality: {coverage:.1f}% stock coverage")

            if coverage >= 90:
                logger.info("✓ EXCELLENT - Ready for fundamental calculations")
            elif coverage >= 75:
                logger.info("⚠ GOOD - Usable but some stocks missing data")
            else:
                logger.warning("✗ POOR - Significant data gaps, investigate errors")


if __name__ == '__main__':
    collector = FundamentalDataCollector()
    collector.run()
