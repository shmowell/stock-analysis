"""
Tests for data staleness checker.

Tests StalenessChecker with mocked database queries.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from utils.staleness import StalenessChecker, StalenessResult, DEFAULT_CADENCES


class TestStalenessResult:
    """Tests for the StalenessResult dataclass."""

    def test_status_no_data(self):
        r = StalenessResult(
            table="test", latest_date=None, max_age_days=7,
            age_days=None, stale=True, record_count=0
        )
        assert r.status == "NO DATA"

    def test_status_stale(self):
        r = StalenessResult(
            table="test", latest_date=date(2026, 1, 1), max_age_days=7,
            age_days=10, stale=True, record_count=100
        )
        assert r.status == "STALE"

    def test_status_ok(self):
        r = StalenessResult(
            table="test", latest_date=date(2026, 2, 13), max_age_days=7,
            age_days=1, stale=False, record_count=100
        )
        assert r.status == "OK"

    def test_str_no_data(self):
        r = StalenessResult(
            table="price_data", latest_date=None, max_age_days=1,
            age_days=None, stale=True, record_count=0
        )
        assert "NO DATA" in str(r)

    def test_str_stale(self):
        r = StalenessResult(
            table="price_data", latest_date=date(2026, 1, 1), max_age_days=1,
            age_days=44, stale=True, record_count=7000
        )
        s = str(r)
        assert "NEEDS REFRESH" in s
        assert "44d old" in s

    def test_str_ok(self):
        r = StalenessResult(
            table="price_data", latest_date=date(2026, 2, 13), max_age_days=1,
            age_days=1, stale=False, record_count=7000
        )
        s = str(r)
        assert "NEEDS REFRESH" not in s


class TestStalenessChecker:
    """Tests for StalenessChecker logic (without DB)."""

    def test_default_cadences(self):
        checker = StalenessChecker()
        assert checker.cadences == DEFAULT_CADENCES

    def test_custom_cadences(self):
        custom = {'price_data': 5}
        checker = StalenessChecker(cadences=custom)
        assert checker.cadences['price_data'] == 5

    def test_today_override(self):
        checker = StalenessChecker(today=date(2026, 3, 1))
        assert checker.today == date(2026, 3, 1)

    def test_today_default(self):
        checker = StalenessChecker()
        assert checker.today == date.today()

    def test_check_table_stale(self):
        """Mock a DB query returning a stale date."""
        checker = StalenessChecker(today=date(2026, 2, 14))

        session = MagicMock()
        # Mock the query chain: session.query().one() returns (date, count)
        session.query.return_value.one.return_value = (date(2026, 2, 10), 7000)

        result = checker.check_table(session, 'price_data')
        assert result.stale is True
        assert result.age_days == 4
        assert result.max_age_days == 1
        assert result.record_count == 7000

    def test_check_table_fresh(self):
        """Mock a DB query returning a fresh date."""
        checker = StalenessChecker(today=date(2026, 2, 14))

        session = MagicMock()
        session.query.return_value.one.return_value = (date(2026, 2, 13), 7000)

        result = checker.check_table(session, 'price_data')
        assert result.stale is False
        assert result.age_days == 1

    def test_check_table_no_data(self):
        """Mock a DB query returning no data."""
        checker = StalenessChecker(today=date(2026, 2, 14))

        session = MagicMock()
        session.query.return_value.one.return_value = (None, 0)

        result = checker.check_table(session, 'price_data')
        assert result.stale is True
        assert result.latest_date is None
        assert result.record_count == 0

    def test_check_table_exactly_at_limit(self):
        """Data exactly at the max age should not be stale."""
        checker = StalenessChecker(today=date(2026, 2, 14))

        session = MagicMock()
        # price_data cadence is 1 day; 1 day old = not stale
        session.query.return_value.one.return_value = (date(2026, 2, 13), 100)

        result = checker.check_table(session, 'price_data')
        assert result.stale is False

    def test_check_all(self):
        """check_all should return one result per table."""
        checker = StalenessChecker(today=date(2026, 2, 14))

        session = MagicMock()
        session.query.return_value.one.return_value = (date(2026, 2, 13), 100)

        results = checker.check_all(session)
        assert len(results) == len(checker.TABLE_CONFIG)

    def test_get_stale_tables(self):
        """get_stale_tables should only return stale ones."""
        checker = StalenessChecker(today=date(2026, 2, 14))

        session = MagicMock()
        # Everything is 5 days old
        session.query.return_value.one.return_value = (date(2026, 2, 9), 100)

        stale = checker.get_stale_tables(session)
        # price_data (cadence 1), technical_indicators (3), market_sentiment (3)
        # should be stale. fundamental_data (30), fmp_estimate_snapshots (14) should not.
        stale_names = [r.table for r in stale]
        assert 'price_data' in stale_names
        assert 'technical_indicators' in stale_names
        assert 'market_sentiment' in stale_names
        assert 'fundamental_data' not in stale_names

    def test_format_report(self):
        checker = StalenessChecker()
        results = [
            StalenessResult("price_data", date(2026, 2, 13), 1, 1, False, 7000),
            StalenessResult("sentiment_data", None, 7, None, True, 0),
        ]
        report = checker.format_report(results)
        assert "DATA FRESHNESS" in report
        assert "1 table(s) need refresh" in report

    def test_format_report_all_fresh(self):
        checker = StalenessChecker()
        results = [
            StalenessResult("price_data", date(2026, 2, 13), 1, 1, False, 7000),
        ]
        report = checker.format_report(results)
        assert "All data is fresh" in report
