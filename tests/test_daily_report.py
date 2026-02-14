"""
Tests for daily report helper functions.

Tests the pure functions in daily_report.py: compute_movers, format_report,
_get_action_items. Does not test the main() function or DB interaction.
"""

import pytest
from datetime import date
from unittest.mock import MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.composite import CompositeScore, Recommendation
from scoring.pipeline import PipelineResult
from utils.staleness import StalenessResult

# Import from scripts
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.daily_report import compute_movers, format_report, _get_action_items


def _make_pipeline_result(scores_list):
    """Helper to create a PipelineResult from a list of tuples."""
    composite_results = []
    pillar_scores = {}
    for ticker, fund, tech, sent, comp, pct, rec in scores_list:
        composite_results.append(
            CompositeScore(ticker, fund, tech, sent, comp, pct, rec)
        )
        pillar_scores[ticker] = {
            'fundamental': fund, 'technical': tech, 'sentiment': sent
        }
    return PipelineResult(
        composite_results=composite_results,
        pillar_scores=pillar_scores,
        data={'tickers': [s[0] for s in scores_list]},
        weights={'fundamental': 0.45, 'technical': 0.35, 'sentiment': 0.20},
    )


class TestComputeMovers:
    """Tests for compute_movers function."""

    def test_no_previous_scores(self):
        result = _make_pipeline_result([
            ('AAPL', 50.0, 60.0, 55.0, 55.0, 70.0, Recommendation.BUY),
        ])
        movers = compute_movers(result, None)
        assert movers == []

    def test_no_change(self):
        result = _make_pipeline_result([
            ('AAPL', 50.0, 60.0, 55.0, 55.0, 70.0, Recommendation.BUY),
        ])
        previous = {'AAPL': {'composite_score': 55.0, 'recommendation': 'BUY'}}
        movers = compute_movers(result, previous)
        assert movers == []

    def test_small_change_ignored(self):
        """Changes < 1pt should not be reported."""
        result = _make_pipeline_result([
            ('AAPL', 50.0, 60.0, 55.0, 55.5, 70.0, Recommendation.BUY),
        ])
        previous = {'AAPL': {'composite_score': 55.0, 'recommendation': 'BUY'}}
        movers = compute_movers(result, previous)
        assert movers == []

    def test_significant_change_reported(self):
        """Changes >= 1pt should be reported."""
        result = _make_pipeline_result([
            ('AAPL', 50.0, 60.0, 55.0, 58.0, 70.0, Recommendation.BUY),
        ])
        previous = {'AAPL': {'composite_score': 55.0, 'recommendation': 'BUY'}}
        movers = compute_movers(result, previous)
        assert len(movers) == 1
        assert movers[0]['ticker'] == 'AAPL'
        assert movers[0]['change'] == 3.0

    def test_recommendation_change_flagged(self):
        result = _make_pipeline_result([
            ('AAPL', 50.0, 60.0, 55.0, 58.0, 85.0, Recommendation.STRONG_BUY),
        ])
        previous = {'AAPL': {'composite_score': 52.0, 'recommendation': 'BUY'}}
        movers = compute_movers(result, previous)
        assert movers[0]['rec_changed'] is True
        assert movers[0]['old_rec'] == 'BUY'
        assert movers[0]['new_rec'] == 'STRONG BUY'

    def test_sorted_by_abs_change(self):
        result = _make_pipeline_result([
            ('AAPL', 50.0, 60.0, 55.0, 58.0, 70.0, Recommendation.BUY),
            ('GOOGL', 55.0, 65.0, 50.0, 48.0, 30.0, Recommendation.HOLD),
        ])
        previous = {
            'AAPL': {'composite_score': 55.0, 'recommendation': 'BUY'},
            'GOOGL': {'composite_score': 57.0, 'recommendation': 'BUY'},
        }
        movers = compute_movers(result, previous)
        assert len(movers) == 2
        # GOOGL has bigger change (9pt) than AAPL (3pt)
        assert movers[0]['ticker'] == 'GOOGL'

    def test_new_ticker_no_previous(self):
        """New ticker with no previous data should not appear in movers."""
        result = _make_pipeline_result([
            ('TSLA', 50.0, 60.0, 55.0, 55.0, 50.0, Recommendation.HOLD),
        ])
        previous = {'AAPL': {'composite_score': 55.0, 'recommendation': 'BUY'}}
        movers = compute_movers(result, previous)
        assert movers == []


class TestGetActionItems:
    """Tests for _get_action_items function."""

    def test_strong_buy_signals(self):
        result = _make_pipeline_result([
            ('JNJ', 53.0, 86.0, 48.0, 64.0, 93.0, Recommendation.STRONG_BUY),
        ])
        items = _get_action_items(result, [])
        assert any("STRONG BUY" in i for i in items)

    def test_strong_sell_signals(self):
        result = _make_pipeline_result([
            ('PG', 36.0, 29.0, 48.0, 36.0, 13.0, Recommendation.STRONG_SELL),
        ])
        items = _get_action_items(result, [])
        assert any("STRONG SELL" in i for i in items)

    def test_recommendation_change_in_actions(self):
        movers = [{
            'ticker': 'AAPL', 'old_score': 50.0, 'new_score': 58.0,
            'change': 8.0, 'old_rec': 'HOLD', 'new_rec': 'BUY', 'rec_changed': True,
        }]
        result = _make_pipeline_result([
            ('AAPL', 50.0, 60.0, 55.0, 58.0, 70.0, Recommendation.BUY),
        ])
        items = _get_action_items(result, movers)
        assert any("HOLD" in i and "BUY" in i for i in items)

    def test_big_mover_flagged(self):
        """Moves >= 3pt should be flagged for review."""
        movers = [{
            'ticker': 'NVDA', 'old_score': 50.0, 'new_score': 55.0,
            'change': 5.0, 'old_rec': 'HOLD', 'new_rec': 'HOLD', 'rec_changed': False,
        }]
        result = _make_pipeline_result([
            ('NVDA', 62.0, 67.0, 55.0, 55.0, 73.0, Recommendation.BUY),
        ])
        items = _get_action_items(result, movers)
        assert any("review" in i.lower() for i in items)


class TestFormatReport:
    """Tests for format_report output structure."""

    def test_report_contains_header(self):
        result = _make_pipeline_result([
            ('AAPL', 50.0, 60.0, 55.0, 55.0, 70.0, Recommendation.BUY),
        ])
        staleness = [
            StalenessResult("price_data", date(2026, 2, 13), 1, 1, False, 7000),
        ]
        report = format_report(result, staleness, [], {})
        assert "DAILY STOCK ANALYSIS REPORT" in report

    def test_report_contains_ranked_list(self):
        result = _make_pipeline_result([
            ('AAPL', 50.0, 60.0, 55.0, 55.0, 70.0, Recommendation.BUY),
            ('PG', 40.0, 30.0, 45.0, 38.0, 20.0, Recommendation.SELL),
        ])
        staleness = []
        report = format_report(result, staleness, [], {})
        assert "RANKED STOCK LIST" in report
        assert "AAPL" in report
        assert "PG" in report

    def test_report_contains_data_freshness(self):
        result = _make_pipeline_result([
            ('AAPL', 50.0, 60.0, 55.0, 55.0, 70.0, Recommendation.BUY),
        ])
        staleness = [
            StalenessResult("price_data", date(2026, 2, 13), 1, 1, False, 7000),
        ]
        report = format_report(result, staleness, [], {})
        assert "DATA FRESHNESS" in report

    def test_report_movers_section(self):
        result = _make_pipeline_result([
            ('AAPL', 50.0, 60.0, 55.0, 58.0, 70.0, Recommendation.BUY),
        ])
        movers = [{
            'ticker': 'AAPL', 'old_score': 55.0, 'new_score': 58.0,
            'change': 3.0, 'old_rec': 'BUY', 'new_rec': 'BUY', 'rec_changed': False,
        }]
        report = format_report(result, [], movers, {})
        assert "SIGNIFICANT MOVERS" in report

    def test_report_weights_footer(self):
        result = _make_pipeline_result([
            ('AAPL', 50.0, 60.0, 55.0, 55.0, 70.0, Recommendation.BUY),
        ])
        report = format_report(result, [], [], {})
        assert "F=45%" in report
        assert "T=35%" in report
        assert "S=20%" in report
