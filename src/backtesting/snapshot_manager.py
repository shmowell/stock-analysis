"""
SnapshotManager - Save and load point-in-time pipeline data as JSON snapshots.

Enables forward-looking backtest validation by persisting the complete state
of the scoring pipeline at a given date, so scores can later be compared
against actual forward returns.

Framework Reference: Section 10 (Backtesting & Paper Trading)
"""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class SnapshotManager:
    """Save and load point-in-time scoring snapshots.

    Each snapshot captures:
    - Date of the snapshot
    - All pillar scores for each stock
    - Composite scores and recommendations
    - Model weights used
    - Raw pillar data (optional, for debugging)

    Snapshots are stored as JSON files in a configurable directory.

    Usage:
        manager = SnapshotManager(snapshot_dir='data/snapshots')
        manager.save(pipeline_result, snapshot_date=date.today())
        snapshot = manager.load(date(2025, 6, 30))
    """

    def __init__(self, snapshot_dir: Optional[str] = None):
        """Initialize SnapshotManager.

        Args:
            snapshot_dir: Directory for snapshot storage.
                          Defaults to data/snapshots/ from project root.
        """
        if snapshot_dir:
            self.snapshot_dir = Path(snapshot_dir)
        else:
            self.snapshot_dir = Path(__file__).parent.parent.parent / 'data' / 'snapshots'

    def _snapshot_path(self, snapshot_date: date) -> Path:
        """Get the file path for a snapshot date."""
        return self.snapshot_dir / f"snapshot_{snapshot_date.isoformat()}.json"

    def save(self, pipeline_result, snapshot_date: Optional[date] = None) -> Path:
        """Save a pipeline result as a dated snapshot.

        Args:
            pipeline_result: PipelineResult from ScoringPipeline.run().
            snapshot_date: Date label for the snapshot. Defaults to today.

        Returns:
            Path to the saved snapshot file.
        """
        snap_date = snapshot_date or date.today()
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        data = {
            'snapshot_date': snap_date.isoformat(),
            'generated_at': datetime.now().isoformat(),
            'universe_size': len(pipeline_result.composite_results),
            'weights': pipeline_result.weights,
            'scores': [],
        }

        for cr in pipeline_result.composite_results:
            pillars = pipeline_result.pillar_scores.get(cr.ticker, {})
            data['scores'].append({
                'ticker': cr.ticker,
                'fundamental_score': cr.fundamental_score,
                'technical_score': cr.technical_score,
                'sentiment_score': cr.sentiment_score,
                'composite_score': cr.composite_score,
                'composite_percentile': cr.composite_percentile,
                'recommendation': cr.recommendation.value,
                'pillar_detail': pillars,
            })

        path = self._snapshot_path(snap_date)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Saved snapshot for {snap_date} to {path}")
        return path

    def load(self, snapshot_date: date) -> Optional[Dict]:
        """Load a snapshot for a given date.

        Args:
            snapshot_date: The date of the snapshot to load.

        Returns:
            Dict with snapshot data, or None if not found.
        """
        path = self._snapshot_path(snapshot_date)
        if not path.exists():
            logger.warning(f"No snapshot found for {snapshot_date}")
            return None

        with open(path, 'r') as f:
            data = json.load(f)

        logger.info(f"Loaded snapshot for {snapshot_date} ({data['universe_size']} stocks)")
        return data

    def list_snapshots(self) -> List[date]:
        """List all available snapshot dates, sorted ascending.

        Returns:
            List of dates for which snapshots exist.
        """
        if not self.snapshot_dir.exists():
            return []

        dates = []
        for p in sorted(self.snapshot_dir.glob('snapshot_*.json')):
            try:
                date_str = p.stem.replace('snapshot_', '')
                dates.append(date.fromisoformat(date_str))
            except ValueError:
                continue

        return dates

    def delete(self, snapshot_date: date) -> bool:
        """Delete a snapshot file.

        Args:
            snapshot_date: Date of the snapshot to delete.

        Returns:
            True if deleted, False if file didn't exist.
        """
        path = self._snapshot_path(snapshot_date)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted snapshot for {snapshot_date}")
            return True
        return False
