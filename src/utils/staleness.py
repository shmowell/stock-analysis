"""
Data Staleness Checker - Determines which data tables need refreshing.

Queries MAX(date) per table and compares against expected update cadences
to identify stale data that should be refreshed before scoring.

Usage:
    from utils.staleness import StalenessChecker

    checker = StalenessChecker()
    with get_db_session() as session:
        report = checker.check_all(session)
        for item in report:
            print(f"{item['table']}: {'STALE' if item['stale'] else 'OK'}")

Author: Stock Analysis Framework v2.0
Date: 2026-02-14
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import (
    PriceData, FundamentalData, TechnicalIndicator,
    SentimentData, MarketSentiment, FMPEstimateSnapshot,
)


@dataclass
class StalenessResult:
    """Result of a staleness check for one data table."""
    table: str
    latest_date: Optional[date]
    max_age_days: int
    age_days: Optional[int]
    stale: bool
    record_count: int

    @property
    def status(self) -> str:
        if self.latest_date is None:
            return "NO DATA"
        return "STALE" if self.stale else "OK"

    def __str__(self) -> str:
        if self.latest_date is None:
            return f"{self.table:25s}  NO DATA  (0 records)"
        age_str = f"{self.age_days}d old" if self.age_days is not None else "?"
        limit_str = f"max {self.max_age_days}d"
        flag = " << NEEDS REFRESH" if self.stale else ""
        return f"{self.table:25s}  {self.latest_date}  ({age_str}, {limit_str}, {self.record_count} records){flag}"


# Default cadences: how many days old data can be before it's "stale"
DEFAULT_CADENCES = {
    'price_data': 1,             # Daily — should have yesterday's close
    'technical_indicators': 3,   # Recalculate after price refresh
    'fundamental_data': 30,      # Monthly is fine
    'sentiment_data': 7,         # Weekly refresh
    'market_sentiment': 3,       # Every few days
    'fmp_estimate_snapshots': 14, # Bi-weekly
}


class StalenessChecker:
    """Check data freshness across all tables.

    Args:
        cadences: Optional dict overriding default max-age-days per table.
        today: Override for testing (defaults to date.today()).
    """

    # Maps table key to (model_class, date_column)
    TABLE_CONFIG = {
        'price_data': (PriceData, PriceData.date),
        'technical_indicators': (TechnicalIndicator, TechnicalIndicator.calculation_date),
        'fundamental_data': (FundamentalData, FundamentalData.report_date),
        'sentiment_data': (SentimentData, SentimentData.data_date),
        'market_sentiment': (MarketSentiment, MarketSentiment.date),
        'fmp_estimate_snapshots': (FMPEstimateSnapshot, FMPEstimateSnapshot.snapshot_date),
    }

    # Tables whose data only arrives on market trading days (Mon-Fri).
    # Staleness thresholds are automatically widened over weekends so that
    # Friday's data isn't incorrectly flagged as stale on Saturday-Monday.
    MARKET_DATA_TABLES = {'price_data', 'technical_indicators'}

    def __init__(
        self,
        cadences: Optional[Dict[str, int]] = None,
        today: Optional[date] = None,
    ):
        self.cadences = cadences or DEFAULT_CADENCES.copy()
        self._today = today

    @property
    def today(self) -> date:
        return self._today or date.today()

    def _effective_max_age(self, table_key: str) -> int:
        """Get effective max age in calendar days, widening for weekends on market data.

        For market data tables, Friday's close is the latest available data
        until Monday's close.  Without adjustment the 1-day cadence would
        wrongly flag Friday data as stale on Saturday (age 1 is fine, but
        Sunday = 2, Monday = 3).  We add the weekend gap so the threshold
        stays meaningful.
        """
        base = self.cadences.get(table_key, 7)
        if table_key in self.MARKET_DATA_TABLES:
            weekday = self.today.weekday()  # 0=Mon … 6=Sun
            if weekday == 0:      # Monday: Fri data is 3 calendar days old
                return base + 2
            elif weekday == 6:    # Sunday: Fri data is 2 calendar days old
                return base + 1
            elif weekday == 5:    # Saturday: Fri data is 1 calendar day old
                return base + 1
        return base

    def check_table(self, session: Session, table_key: str) -> StalenessResult:
        """Check staleness for a single table.

        Args:
            session: Database session.
            table_key: Key from TABLE_CONFIG (e.g. 'price_data').

        Returns:
            StalenessResult for that table.
        """
        model_cls, date_col = self.TABLE_CONFIG[table_key]
        max_age = self._effective_max_age(table_key)

        # Query latest date and count
        result = session.query(
            func.max(date_col),
            func.count(date_col),
        ).one()

        latest_date = result[0]
        count = result[1]

        if latest_date is None:
            return StalenessResult(
                table=table_key,
                latest_date=None,
                max_age_days=max_age,
                age_days=None,
                stale=True,
                record_count=0,
            )

        age_days = (self.today - latest_date).days
        stale = age_days > max_age

        return StalenessResult(
            table=table_key,
            latest_date=latest_date,
            max_age_days=max_age,
            age_days=age_days,
            stale=stale,
            record_count=count,
        )

    def check_all(self, session: Session) -> List[StalenessResult]:
        """Check staleness for all configured tables.

        Returns:
            List of StalenessResult, one per table.
        """
        results = []
        for key in self.TABLE_CONFIG:
            results.append(self.check_table(session, key))
        return results

    def get_stale_tables(self, session: Session) -> List[StalenessResult]:
        """Return only the tables that need refreshing."""
        return [r for r in self.check_all(session) if r.stale]

    def format_report(self, results: List[StalenessResult]) -> str:
        """Format staleness results as a readable report."""
        lines = ["DATA FRESHNESS", "-" * 80]
        for r in results:
            lines.append(str(r))
        stale_count = sum(1 for r in results if r.stale)
        lines.append("-" * 80)
        if stale_count:
            lines.append(f"{stale_count} table(s) need refresh")
        else:
            lines.append("All data is fresh")
        return "\n".join(lines)
