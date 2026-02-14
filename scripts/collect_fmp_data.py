"""
Collect and store FMP analyst data for all stocks in the universe.

Framework Reference: Section 5.2 (Analyst Revision Momentum), Section 9.3
Purpose: Populate upgrades_30d, downgrades_30d, estimate_revisions_up_90d,
         estimate_revisions_down_90d in the sentiment_data table.

Must run AFTER collect_sentiment_data.py (which creates base sentiment records).

Usage:
    python scripts/collect_fmp_data.py
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from datetime import date
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from database import get_db_session
from database.models import Stock, SentimentData, FMPEstimateSnapshot
from data_collection.fmp import FMPCollector
from utils.validators import DataValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FMPDataCollector:
    """
    Collects FMP analyst data and updates sentiment records.

    Framework Section 5.2: Analyst Revision Momentum & Consensus
    - Stock grades: upgrades/downgrades in past 30 days
    - Analyst estimates: track revisions over time
    """

    def __init__(self):
        self.fmp = FMPCollector()
        self.stats = {
            'stocks_processed': 0,
            'stocks_success': 0,
            'stocks_failed': 0,
            'upgrades_populated': 0,
            'revisions_populated': 0,
            'snapshots_stored': 0,
            'errors': []
        }

    def get_active_stocks(self) -> List[str]:
        """Fetch all active stocks from database."""
        with get_db_session() as session:
            stmt = select(Stock.ticker).where(Stock.is_active == True)
            result = session.execute(stmt)
            tickers = [row[0] for row in result]
            logger.info(f"Found {len(tickers)} active stocks")
            return tickers

    def load_previous_snapshots(self, ticker: str) -> Dict[str, Dict]:
        """
        Load the most recent estimate snapshots for a ticker.

        Returns:
            Dict keyed by fiscal_date string, each value containing
            'eps_avg' and 'revenue_avg' from the most recent prior snapshot.
        """
        with get_db_session() as session:
            # Get the most recent snapshot_date for this ticker (before today)
            from sqlalchemy import func
            latest_date_stmt = (
                select(func.max(FMPEstimateSnapshot.snapshot_date))
                .where(FMPEstimateSnapshot.ticker == ticker)
                .where(FMPEstimateSnapshot.snapshot_date < date.today())
            )
            result = session.execute(latest_date_stmt).scalar()

            if result is None:
                return {}

            # Load all snapshots from that date
            snapshots_stmt = (
                select(FMPEstimateSnapshot)
                .where(FMPEstimateSnapshot.ticker == ticker)
                .where(FMPEstimateSnapshot.snapshot_date == result)
            )
            rows = session.execute(snapshots_stmt).scalars().all()

            snapshots = {}
            for row in rows:
                fiscal_key = row.fiscal_date.isoformat()
                snapshots[fiscal_key] = {
                    'eps_avg': float(row.eps_avg) if row.eps_avg is not None else None,
                    'revenue_avg': float(row.revenue_avg) if row.revenue_avg is not None else None,
                }

            logger.info(f"{ticker}: Loaded {len(snapshots)} previous snapshots from {result}")
            return snapshots

    def store_estimate_snapshots(self, ticker: str, estimates: List[Dict]) -> int:
        """
        Store current estimate snapshots for future revision comparison.

        Args:
            ticker: Stock ticker
            estimates: List of estimate dicts from FMP API

        Returns:
            Number of snapshots stored
        """
        today = date.today()
        stored = 0

        with get_db_session() as session:
            for est in estimates:
                fiscal_date = est.get('date')
                if not fiscal_date:
                    continue

                values = {
                    'ticker': ticker,
                    'snapshot_date': today,
                    'fiscal_date': fiscal_date,
                    'eps_avg': est.get('estimatedEpsAvg'),
                    'eps_high': est.get('estimatedEpsHigh'),
                    'eps_low': est.get('estimatedEpsLow'),
                    'revenue_avg': est.get('estimatedRevenueAvg'),
                    'revenue_high': est.get('estimatedRevenueHigh'),
                    'revenue_low': est.get('estimatedRevenueLow'),
                    'num_analysts_eps': int(est['numberAnalystEstimatedEps']) if est.get('numberAnalystEstimatedEps') is not None else None,
                    'num_analysts_revenue': int(est['numberAnalystEstimatedRevenue']) if est.get('numberAnalystEstimatedRevenue') is not None else None,
                }

                stmt = insert(FMPEstimateSnapshot).values(**values)
                stmt = stmt.on_conflict_do_update(
                    constraint='uq_fmp_snapshot_ticker_dates',
                    set_={
                        'eps_avg': stmt.excluded.eps_avg,
                        'eps_high': stmt.excluded.eps_high,
                        'eps_low': stmt.excluded.eps_low,
                        'revenue_avg': stmt.excluded.revenue_avg,
                        'revenue_high': stmt.excluded.revenue_high,
                        'revenue_low': stmt.excluded.revenue_low,
                        'num_analysts_eps': stmt.excluded.num_analysts_eps,
                        'num_analysts_revenue': stmt.excluded.num_analysts_revenue,
                    }
                )
                session.execute(stmt)
                stored += 1

            session.commit()

        logger.info(f"{ticker}: Stored {stored} estimate snapshots")
        return stored

    def update_sentiment_record(self, ticker: str, fmp_data: Dict) -> bool:
        """
        Update the most recent SentimentData record with FMP fields.

        Only updates FMP-sourced fields; leaves Yahoo data intact.
        Finds the latest record for this ticker (any date).

        Args:
            ticker: Stock ticker
            fmp_data: Dict with upgrades_30d, downgrades_30d,
                      estimate_revisions_up_90d, estimate_revisions_down_90d
        """
        try:
            with get_db_session() as session:
                # Build update values (only non-None FMP fields)
                update_values = {}

                if fmp_data.get('upgrades_30d') is not None:
                    update_values['upgrades_30d'] = fmp_data['upgrades_30d']
                if fmp_data.get('downgrades_30d') is not None:
                    update_values['downgrades_30d'] = fmp_data['downgrades_30d']
                if fmp_data.get('estimate_revisions_up_90d') is not None:
                    update_values['estimate_revisions_up_90d'] = fmp_data['estimate_revisions_up_90d']
                if fmp_data.get('estimate_revisions_down_90d') is not None:
                    update_values['estimate_revisions_down_90d'] = fmp_data['estimate_revisions_down_90d']

                if not update_values:
                    logger.info(f"{ticker}: No FMP data to update")
                    return True

                # Update data_source to include FMP
                update_values['data_source'] = 'yahoo_finance,fmp'

                # Find the most recent sentiment record for this ticker
                from sqlalchemy import func
                latest_date_stmt = (
                    select(func.max(SentimentData.data_date))
                    .where(SentimentData.ticker == ticker)
                )
                latest_date = session.execute(latest_date_stmt).scalar()

                if latest_date is None:
                    logger.warning(
                        f"{ticker}: No sentiment record found. "
                        f"Run collect_sentiment_data.py first."
                    )
                    return False

                stmt = (
                    update(SentimentData)
                    .where(SentimentData.ticker == ticker)
                    .where(SentimentData.data_date == latest_date)
                    .values(**update_values)
                )
                session.execute(stmt)
                session.commit()

                logger.info(
                    f"{ticker}: Updated sentiment record ({latest_date}) with FMP data"
                )
                return True

        except Exception as e:
            logger.error(f"Error updating sentiment for {ticker}: {e}")
            return False

    def collect_for_ticker(self, ticker: str) -> Optional[Dict]:
        """
        Collect all FMP data for a single ticker.

        Returns:
            Dict with FMP data fields, or None on failure
        """
        fmp_data = {}

        try:
            # 1. Upgrades/downgrades (30-day window)
            grades = self.fmp.calculate_upgrades_downgrades(ticker, lookback_days=30)
            fmp_data['upgrades_30d'] = grades['upgrades']
            fmp_data['downgrades_30d'] = grades['downgrades']
            self.stats['upgrades_populated'] += 1

        except DataValidationError as e:
            logger.warning(f"{ticker}: Failed to get grades: {e}")
            fmp_data['upgrades_30d'] = None
            fmp_data['downgrades_30d'] = None

        try:
            # 2. Estimate revisions
            previous = self.load_previous_snapshots(ticker)
            revisions = self.fmp.calculate_estimate_revisions(ticker, previous)

            # Store current snapshots for future comparison
            if revisions['current_estimates']:
                stored = self.store_estimate_snapshots(
                    ticker, revisions['current_estimates']
                )
                self.stats['snapshots_stored'] += stored

            fmp_data['estimate_revisions_up_90d'] = revisions['revisions_up']
            fmp_data['estimate_revisions_down_90d'] = revisions['revisions_down']

            if revisions['revisions_up'] is not None:
                self.stats['revisions_populated'] += 1

        except DataValidationError as e:
            logger.warning(f"{ticker}: Failed to get estimates: {e}")
            fmp_data['estimate_revisions_up_90d'] = None
            fmp_data['estimate_revisions_down_90d'] = None

        return fmp_data

    def run(self) -> Dict[str, Any]:
        """
        Main execution: collect FMP data for all active stocks.

        Returns:
            Dict with execution statistics
        """
        logger.info("=" * 80)
        logger.info("FMP DATA COLLECTION - START")
        logger.info("=" * 80)

        tickers = self.get_active_stocks()
        self.stats['stocks_processed'] = len(tickers)

        for ticker in tickers:
            logger.info(f"\nProcessing {ticker}...")

            fmp_data = self.collect_for_ticker(ticker)

            if fmp_data:
                success = self.update_sentiment_record(ticker, fmp_data)
                if success:
                    self.stats['stocks_success'] += 1
                else:
                    self.stats['stocks_failed'] += 1
            else:
                self.stats['stocks_failed'] += 1

        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("FMP DATA COLLECTION - SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total stocks processed: {self.stats['stocks_processed']}")
        logger.info(f"Successfully updated: {self.stats['stocks_success']}")
        logger.info(f"Failed: {self.stats['stocks_failed']}")
        logger.info(f"Grades populated: {self.stats['upgrades_populated']}")
        logger.info(f"Revisions populated: {self.stats['revisions_populated']}")
        logger.info(f"Estimate snapshots stored: {self.stats['snapshots_stored']}")

        if self.stats['errors']:
            logger.info("\nErrors encountered:")
            for error in self.stats['errors']:
                logger.info(f"  {error}")

        return self.stats


def main():
    """Main entry point."""
    collector = FMPDataCollector()
    stats = collector.run()

    if stats['stocks_failed'] == 0:
        logger.info("\nAll stocks processed successfully!")
        return 0
    elif stats['stocks_success'] > 0:
        logger.warning(
            f"\nPartial success: {stats['stocks_success']}/{stats['stocks_processed']} stocks"
        )
        return 1
    else:
        logger.error("\nAll stocks failed!")
        return 2


if __name__ == "__main__":
    exit(main())
