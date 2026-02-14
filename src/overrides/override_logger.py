"""
Override Logger - Persistence and statistics for override tracking.

Framework Reference: Section 6.4, Section 8 (Override Tracking & Learning)

Logs overrides as JSON files in logs/overrides/ directory.
Provides statistics calculation for quarterly review.

Author: Stock Analysis Framework v2.0
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .models import OverrideResult, OverrideType

logger = logging.getLogger(__name__)


class OverrideLogger:
    """Log and retrieve override records for tracking and learning.

    Framework Section 8: Override Tracking & Learning

    File naming convention:
    - Individual overrides: logs/overrides/{ticker}_{YYYY-MM-DD}_{HH-MM-SS-ffffff}.json
    """

    def __init__(self, log_dir: Optional[str] = None):
        """Initialize override logger.

        Args:
            log_dir: Directory for override log files.
                     Defaults to project_root/logs/overrides/
        """
        if log_dir is None:
            log_dir = Path(__file__).parent.parent.parent / 'logs' / 'overrides'
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_override(self, result: OverrideResult) -> str:
        """Log an override result to a JSON file.

        Creates individual JSON file for the override.

        Args:
            result: OverrideResult to log

        Returns:
            Path to the created log file
        """
        timestamp_str = result.timestamp.strftime("%Y-%m-%d_%H-%M-%S-%f")
        filename = f"{result.ticker}_{timestamp_str}.json"
        file_path = self.log_dir / filename

        data = result.to_dict()

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Override logged to {file_path}")
        return str(file_path)

    def load_override(self, file_path: str) -> Dict:
        """Load a single override from a JSON file.

        Args:
            file_path: Path to the override JSON file

        Returns:
            Override record as dict
        """
        with open(file_path, 'r') as f:
            return json.load(f)

    def load_all_overrides(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        ticker: Optional[str] = None,
    ) -> List[Dict]:
        """Load all override records, optionally filtered.

        Args:
            start_date: Filter overrides after this date
            end_date: Filter overrides before this date
            ticker: Filter to specific ticker

        Returns:
            List of override record dicts
        """
        overrides = []

        for file_path in sorted(self.log_dir.glob("*.json")):
            try:
                data = self.load_override(str(file_path))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load override file {file_path}: {e}")
                continue

            # Filter by ticker
            if ticker and data.get('ticker') != ticker:
                continue

            # Filter by date
            try:
                override_date = datetime.fromisoformat(data['timestamp'])
            except (KeyError, ValueError):
                continue

            if start_date and override_date < start_date:
                continue
            if end_date and override_date > end_date:
                continue

            overrides.append(data)

        return overrides

    def calculate_override_statistics(
        self,
        overrides: Optional[List[Dict]] = None,
    ) -> Dict:
        """Calculate override statistics for quarterly review.

        Framework Section 8.1: Quarterly Override Review

        Metrics calculated:
        - Total overrides count
        - Breakdown by type (weight/sentiment/both)
        - Breakdown by conviction level
        - Average percentile impact
        - Recommendation change count
        - Extreme override count
        - Guardrail violation count

        Note: Override alpha and hit rate require future price data,
        deferred to Phase 4 (backtesting).

        Args:
            overrides: List of override dicts to analyze.
                      If None, loads all from disk.

        Returns:
            Dict of statistics
        """
        if overrides is None:
            overrides = self.load_all_overrides()

        if not overrides:
            return {
                'total_overrides': 0,
                'by_type': {},
                'by_conviction': {},
                'avg_percentile_impact': 0.0,
                'recommendation_changes': 0,
                'extreme_overrides': 0,
                'guardrail_violations': 0,
            }

        # Count by type
        by_type: Dict[str, int] = {}
        for o in overrides:
            otype = o.get('override_type', 'unknown')
            by_type[otype] = by_type.get(otype, 0) + 1

        # Count by conviction
        by_conviction: Dict[str, int] = {}
        for o in overrides:
            doc = o.get('documentation') or {}
            conviction = doc.get('conviction', 'unknown')
            by_conviction[conviction] = by_conviction.get(conviction, 0) + 1

        # Impact statistics
        impacts = []
        for o in overrides:
            result = o.get('result', {})
            impact = result.get('percentile_impact')
            if impact is not None:
                impacts.append(abs(impact))

        avg_impact = sum(impacts) / len(impacts) if impacts else 0.0

        # Recommendation changes
        rec_changes = sum(
            1 for o in overrides
            if o.get('result', {}).get('recommendation_changed', False)
        )

        # Extreme overrides
        extreme_count = sum(
            1 for o in overrides
            if o.get('result', {}).get('extreme_override', False)
        )

        # Guardrail violations
        violation_count = sum(
            1 for o in overrides
            if len(o.get('result', {}).get('guardrail_violations', [])) > 0
        )

        return {
            'total_overrides': len(overrides),
            'by_type': by_type,
            'by_conviction': by_conviction,
            'avg_percentile_impact': round(avg_impact, 2),
            'recommendation_changes': rec_changes,
            'extreme_overrides': extreme_count,
            'guardrail_violations': violation_count,
        }

    def generate_quarterly_summary(
        self,
        quarter: str,
        total_stocks_evaluated: int,
    ) -> str:
        """Generate a quarterly summary report string.

        Framework Section 8.2: Learning Template

        Args:
            quarter: Quarter identifier (e.g., "Q1 2026")
            total_stocks_evaluated: Total universe size

        Returns:
            Formatted summary report string
        """
        overrides = self.load_all_overrides()
        stats = self.calculate_override_statistics(overrides)

        override_frequency = (
            stats['total_overrides'] / total_stocks_evaluated * 100
            if total_stocks_evaluated > 0 else 0.0
        )

        lines = [
            "=" * 80,
            f"QUARTERLY OVERRIDE REVIEW: {quarter}",
            "=" * 80,
            "",
            f"Total Stocks Evaluated: {total_stocks_evaluated}",
            f"Total Overrides: {stats['total_overrides']}",
            f"Override Frequency: {override_frequency:.1f}% "
            f"(target: <30%)",
            "",
            "By Override Type:",
        ]

        for otype, count in stats['by_type'].items():
            lines.append(f"  {otype}: {count}")

        lines.extend([
            "",
            "By Conviction Level:",
        ])
        for conv, count in stats['by_conviction'].items():
            lines.append(f"  {conv}: {count}")

        lines.extend([
            "",
            f"Average Percentile Impact: {stats['avg_percentile_impact']:.1f}pt",
            f"Recommendation Changes: {stats['recommendation_changes']}",
            f"Extreme Overrides: {stats['extreme_overrides']}",
            f"Guardrail Violations: {stats['guardrail_violations']}",
            "",
            "=" * 80,
            "NOTE: Override alpha and hit rate require price performance data",
            "(available after Phase 4 backtesting implementation)",
            "=" * 80,
        ])

        return "\n".join(lines)
