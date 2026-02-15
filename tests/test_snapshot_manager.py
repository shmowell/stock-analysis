"""
Tests for SnapshotManager — save/load point-in-time scoring snapshots.
"""

import pytest
import json
from datetime import date
from pathlib import Path

from backtesting.snapshot_manager import SnapshotManager


# ---------------------------------------------------------------------------
# Mock PipelineResult
# ---------------------------------------------------------------------------

class _MockRecommendation:
    def __init__(self, value):
        self.value = value


class _MockCompositeScore:
    def __init__(self, ticker, fund, tech, sent, comp, pctile, rec):
        self.ticker = ticker
        self.fundamental_score = fund
        self.technical_score = tech
        self.sentiment_score = sent
        self.composite_score = comp
        self.composite_percentile = pctile
        self.recommendation = _MockRecommendation(rec)


class _MockPipelineResult:
    def __init__(self, scores, pillar_scores, weights):
        self.composite_results = scores
        self.pillar_scores = pillar_scores
        self.weights = weights


@pytest.fixture
def mock_result():
    scores = [
        _MockCompositeScore('AAPL', 60.0, 75.0, 55.0, 63.5, 86.7, 'STRONG BUY'),
        _MockCompositeScore('MSFT', 55.0, 70.0, 50.0, 58.0, 60.0, 'HOLD'),
    ]
    pillar_scores = {
        'AAPL': {'fundamental': 60.0, 'technical': 75.0, 'sentiment': 55.0},
        'MSFT': {'fundamental': 55.0, 'technical': 70.0, 'sentiment': 50.0},
    }
    weights = {'fundamental': 0.45, 'technical': 0.35, 'sentiment': 0.20}
    return _MockPipelineResult(scores, pillar_scores, weights)


@pytest.fixture
def manager(tmp_path):
    return SnapshotManager(snapshot_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSave:

    def test_creates_file(self, manager, mock_result, tmp_path):
        path = manager.save(mock_result, snapshot_date=date(2025, 6, 15))
        assert path.exists()
        assert path.name == 'snapshot_2025-06-15.json'

    def test_file_contents_valid_json(self, manager, mock_result):
        path = manager.save(mock_result, snapshot_date=date(2025, 6, 15))
        with open(path) as f:
            data = json.load(f)
        assert data['snapshot_date'] == '2025-06-15'
        assert data['universe_size'] == 2
        assert len(data['scores']) == 2

    def test_score_fields(self, manager, mock_result):
        path = manager.save(mock_result, snapshot_date=date(2025, 6, 15))
        with open(path) as f:
            data = json.load(f)
        score = data['scores'][0]
        assert score['ticker'] == 'AAPL'
        assert score['fundamental_score'] == 60.0
        assert score['recommendation'] == 'STRONG BUY'
        assert 'pillar_detail' in score

    def test_creates_directory(self, tmp_path, mock_result):
        deep_dir = tmp_path / 'a' / 'b' / 'c'
        mgr = SnapshotManager(snapshot_dir=str(deep_dir))
        path = mgr.save(mock_result, snapshot_date=date(2025, 1, 1))
        assert path.exists()


class TestLoad:

    def test_round_trip(self, manager, mock_result):
        manager.save(mock_result, snapshot_date=date(2025, 6, 15))
        data = manager.load(date(2025, 6, 15))
        assert data is not None
        assert data['snapshot_date'] == '2025-06-15'
        assert data['universe_size'] == 2

    def test_missing_returns_none(self, manager):
        data = manager.load(date(2099, 1, 1))
        assert data is None


class TestListSnapshots:

    def test_empty_directory(self, manager):
        assert manager.list_snapshots() == []

    def test_lists_sorted(self, manager, mock_result):
        manager.save(mock_result, snapshot_date=date(2025, 3, 1))
        manager.save(mock_result, snapshot_date=date(2025, 1, 1))
        manager.save(mock_result, snapshot_date=date(2025, 2, 1))

        dates = manager.list_snapshots()
        assert dates == [date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)]

    def test_non_existent_dir(self, tmp_path):
        mgr = SnapshotManager(snapshot_dir=str(tmp_path / 'nope'))
        assert mgr.list_snapshots() == []


class TestDelete:

    def test_delete_existing(self, manager, mock_result):
        manager.save(mock_result, snapshot_date=date(2025, 6, 15))
        assert manager.delete(date(2025, 6, 15)) is True
        assert manager.load(date(2025, 6, 15)) is None

    def test_delete_non_existing(self, manager):
        assert manager.delete(date(2099, 1, 1)) is False
