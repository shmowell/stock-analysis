"""
TechnicalBacktester - Backtest technical scoring model against historical data.

Sets up monthly checkpoints over a date range, scores all stocks using
IndicatorBuilder + TechnicalCalculator at each checkpoint, measures forward
returns, and reports quintile analysis, Spearman correlation, and hit rates.

Framework Reference: Section 10 (Backtesting & Paper Trading)
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
import logging

import numpy as np
import pandas as pd

from backtesting.indicator_builder import IndicatorBuilder
from calculators.technical import TechnicalCalculator

logger = logging.getLogger(__name__)


class BacktestResult:
    """Container for backtest output at a single checkpoint."""

    def __init__(
        self,
        checkpoint_date: date,
        scores: Dict[str, float],
        forward_returns: Dict[str, Dict[str, Optional[float]]],
    ):
        """
        Args:
            checkpoint_date: The as-of date for scoring.
            scores: {ticker: technical_score}.
            forward_returns: {ticker: {period: return}} where period is
                             '1m', '3m', '6m'.
        """
        self.checkpoint_date = checkpoint_date
        self.scores = scores
        self.forward_returns = forward_returns


class BacktestReport:
    """Aggregated backtest metrics across all checkpoints."""

    def __init__(
        self,
        checkpoints: List[BacktestResult],
        quintile_returns: Dict[str, Dict[int, float]],
        spearman_correlations: Dict[str, float],
        hit_rates: Dict[str, float],
        long_short_spread: Dict[str, float],
    ):
        self.checkpoints = checkpoints
        self.quintile_returns = quintile_returns
        self.spearman_correlations = spearman_correlations
        self.hit_rates = hit_rates
        self.long_short_spread = long_short_spread

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 80,
            "TECHNICAL BACKTEST REPORT",
            "=" * 80,
            f"Checkpoints: {len(self.checkpoints)}",
            f"Date range:  {self.checkpoints[0].checkpoint_date} to "
            f"{self.checkpoints[-1].checkpoint_date}",
            "",
        ]

        for period in ['1m', '3m', '6m']:
            lines.append(f"--- Forward {period} Returns ---")

            # Quintile table
            qr = self.quintile_returns.get(period, {})
            if qr:
                lines.append(f"  {'Quintile':<10} {'Avg Return':>12}")
                for q in sorted(qr.keys()):
                    label = {1: 'Q1 (top)', 5: 'Q5 (bot)'}.get(q, f'Q{q}')
                    lines.append(f"  {label:<10} {qr[q]:>12.2%}")

            spread = self.long_short_spread.get(period)
            if spread is not None:
                lines.append(f"  Long-Short:  {spread:>+.2%}")

            corr = self.spearman_correlations.get(period)
            if corr is not None:
                lines.append(f"  Spearman r:  {corr:>+.3f}")

            hr = self.hit_rates.get(period)
            if hr is not None:
                lines.append(f"  Hit rate:    {hr:>.1%}")

            lines.append("")

        lines.append("=" * 80)
        return "\n".join(lines)


class TechnicalBacktester:
    """Backtest the technical scoring model on historical price data.

    Workflow:
    1. Precompute indicators for each ticker using IndicatorBuilder.
    2. Generate monthly checkpoints over the specified date range.
    3. At each checkpoint, build snapshots for all stocks, compute
       sector-relative metrics, then score with TechnicalCalculator.
    4. Measure forward returns at 1m, 3m, 6m horizons.
    5. Aggregate into quintile analysis, Spearman correlation, hit rates.

    Usage:
        backtester = TechnicalBacktester()
        report = backtester.run(
            price_data={'AAPL': df_aapl, 'MSFT': df_msft, ...},
            stock_sectors={'AAPL': 'Technology', 'MSFT': 'Technology', ...},
            start_date=date(2024, 6, 1),
            end_date=date(2025, 12, 1),
        )
        print(report.summary())
    """

    def __init__(self):
        self.indicator_builder = IndicatorBuilder()
        self.technical_calculator = TechnicalCalculator()

    def run(
        self,
        price_data: Dict[str, pd.DataFrame],
        stock_sectors: Dict[str, str],
        start_date: date,
        end_date: date,
    ) -> BacktestReport:
        """Run the full technical backtest.

        Args:
            price_data: {ticker: price_DataFrame} with DatetimeIndex and
                        at least 'close' and 'volume' columns.
            stock_sectors: {ticker: sector_name}.
            start_date: First checkpoint date (inclusive).
            end_date: Last checkpoint date (inclusive).

        Returns:
            BacktestReport with aggregated metrics.
        """
        logger.info(f"Running technical backtest from {start_date} to {end_date}")
        logger.info(f"Universe: {len(price_data)} stocks")

        # Step 1: Precompute indicators for all tickers
        logger.info("Precomputing indicators...")
        indicator_cache: Dict[str, pd.DataFrame] = {}
        for ticker, df in price_data.items():
            indicator_cache[ticker] = self.indicator_builder.compute(df)

        # Step 2: Generate monthly checkpoints
        checkpoints_dates = self._generate_monthly_checkpoints(start_date, end_date)
        logger.info(f"Generated {len(checkpoints_dates)} monthly checkpoints")

        # Step 3: Score at each checkpoint and measure forward returns
        results: List[BacktestResult] = []
        for cp_date in checkpoints_dates:
            result = self._score_checkpoint(
                cp_date, price_data, indicator_cache, stock_sectors,
            )
            if result and len(result.scores) >= 5:
                results.append(result)
            else:
                logger.warning(
                    f"Skipping {cp_date}: insufficient scored stocks "
                    f"({len(result.scores) if result else 0})"
                )

        if not results:
            logger.error("No valid checkpoints produced")
            return BacktestReport(
                checkpoints=[],
                quintile_returns={},
                spearman_correlations={},
                hit_rates={},
                long_short_spread={},
            )

        logger.info(f"Scored {len(results)} valid checkpoints")

        # Step 4: Aggregate metrics
        report = self._aggregate(results)
        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_monthly_checkpoints(
        start_date: date, end_date: date,
    ) -> List[date]:
        """Generate month-end checkpoint dates between start and end."""
        checkpoints = []
        current = date(start_date.year, start_date.month, 1)
        while current <= end_date:
            # Use last day of the month
            if current.month == 12:
                month_end = date(current.year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(current.year, current.month + 1, 1) - timedelta(days=1)

            if start_date <= month_end <= end_date:
                checkpoints.append(month_end)

            # Advance to next month
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)

        return checkpoints

    def _score_checkpoint(
        self,
        cp_date: date,
        price_data: Dict[str, pd.DataFrame],
        indicator_cache: Dict[str, pd.DataFrame],
        stock_sectors: Dict[str, str],
    ) -> Optional[BacktestResult]:
        """Score all stocks at a single checkpoint date.

        Returns:
            BacktestResult, or None if unable to score.
        """
        cp_ts = pd.Timestamp(cp_date)
        max_staleness = pd.Timedelta(days=7)  # Skip if data > 7 days stale

        # Build snapshots for each ticker
        snapshots: Dict[str, Dict] = {}
        for ticker, indicators in indicator_cache.items():
            close_series = price_data[ticker]['close']
            price_df_temp = pd.DataFrame({'close': close_series})
            price_row = self.indicator_builder.get_as_of(price_df_temp, cp_ts)
            if price_row is None:
                continue
            # Reject if the available data is too far from checkpoint
            if cp_ts - price_row.name > max_staleness:
                continue
            current_price = float(price_row['close'])

            snapshot = self.indicator_builder.build_snapshot(
                indicators, cp_ts, current_price,
            )
            if snapshot:
                snapshots[ticker] = snapshot

        if len(snapshots) < 5:
            return BacktestResult(cp_date, {}, {})

        # Compute sector-relative metrics
        self.indicator_builder.compute_sector_relative(snapshots, stock_sectors)

        # Build universe metrics from all snapshots
        universe_metrics = self._build_universe_metrics(snapshots)

        # Score each stock with TechnicalCalculator
        scores: Dict[str, float] = {}
        for ticker, snapshot in snapshots.items():
            result = self.technical_calculator.calculate_technical_score(
                snapshot, universe_metrics,
            )
            tech_score = result.get('technical_score')
            if tech_score is not None:
                scores[ticker] = tech_score

        # Measure forward returns
        forward_returns = self._measure_forward_returns(
            scores.keys(), price_data, cp_date,
        )

        return BacktestResult(cp_date, scores, forward_returns)

    @staticmethod
    def _build_universe_metrics(
        snapshots: Dict[str, Dict],
    ) -> Dict[str, List[float]]:
        """Build universe-wide metric lists from per-stock snapshots."""
        metrics_of_interest = [
            'momentum_12_1', 'momentum_6m', 'momentum_3m', 'momentum_1m',
            'mad', 'relative_volume', 'rsi_14', 'sector_relative_6m',
        ]
        universe: Dict[str, List[float]] = {}
        for metric in metrics_of_interest:
            values = [
                s[metric] for s in snapshots.values()
                if s.get(metric) is not None
            ]
            if values:
                universe[metric] = values
        return universe

    @staticmethod
    def _measure_forward_returns(
        tickers,
        price_data: Dict[str, pd.DataFrame],
        cp_date: date,
    ) -> Dict[str, Dict[str, Optional[float]]]:
        """Measure forward returns from checkpoint date.

        Returns {ticker: {'1m': return, '3m': return, '6m': return}}.
        """
        horizons = {
            '1m': timedelta(days=30),
            '3m': timedelta(days=91),
            '6m': timedelta(days=182),
        }
        results: Dict[str, Dict[str, Optional[float]]] = {}
        cp_ts = pd.Timestamp(cp_date)

        for ticker in tickers:
            df = price_data.get(ticker)
            if df is None or df.empty:
                results[ticker] = {h: None for h in horizons}
                continue

            # Get price at checkpoint
            mask_cp = df.index <= cp_ts
            if not mask_cp.any():
                results[ticker] = {h: None for h in horizons}
                continue
            price_at_cp = float(df.loc[mask_cp, 'close'].iloc[-1])

            fwd: Dict[str, Optional[float]] = {}
            for horizon_name, delta in horizons.items():
                target_ts = cp_ts + delta
                mask_fwd = df.index <= target_ts
                if not mask_fwd.any():
                    fwd[horizon_name] = None
                    continue
                price_fwd = float(df.loc[mask_fwd, 'close'].iloc[-1])
                # Avoid returning 0.0 if the forward date is the same as checkpoint
                if df.loc[mask_fwd].index[-1] <= cp_ts:
                    fwd[horizon_name] = None
                else:
                    fwd[horizon_name] = (price_fwd - price_at_cp) / price_at_cp

            results[ticker] = fwd

        return results

    def _aggregate(self, results: List[BacktestResult]) -> BacktestReport:
        """Aggregate checkpoint results into backtest metrics."""
        periods = ['1m', '3m', '6m']

        # Collect (score, forward_return) pairs across all checkpoints
        pairs: Dict[str, List[Tuple[float, float]]] = {p: [] for p in periods}

        for cp in results:
            for ticker, score in cp.scores.items():
                fwd = cp.forward_returns.get(ticker, {})
                for period in periods:
                    ret = fwd.get(period)
                    if ret is not None:
                        pairs[period].append((score, ret))

        # Calculate metrics for each period
        quintile_returns: Dict[str, Dict[int, float]] = {}
        spearman_correlations: Dict[str, float] = {}
        hit_rates: Dict[str, float] = {}
        long_short_spread: Dict[str, float] = {}

        for period in periods:
            data = pairs[period]
            if len(data) < 10:
                continue

            scores_arr = np.array([d[0] for d in data])
            returns_arr = np.array([d[1] for d in data])

            # Quintile analysis
            qr = self._quintile_analysis(scores_arr, returns_arr)
            quintile_returns[period] = qr

            # Long-short spread
            if 1 in qr and 5 in qr:
                long_short_spread[period] = qr[1] - qr[5]

            # Spearman rank correlation
            spearman_correlations[period] = self._spearman_correlation(
                scores_arr, returns_arr,
            )

            # Hit rate: % of top quintile that beats the median return
            hit_rates[period] = self._hit_rate(scores_arr, returns_arr)

        return BacktestReport(
            checkpoints=results,
            quintile_returns=quintile_returns,
            spearman_correlations=spearman_correlations,
            hit_rates=hit_rates,
            long_short_spread=long_short_spread,
        )

    @staticmethod
    def _quintile_analysis(
        scores: np.ndarray, returns: np.ndarray,
    ) -> Dict[int, float]:
        """Split into 5 quintiles by score and compute average return per quintile.

        Q1 = top scores (highest), Q5 = bottom scores (lowest).
        """
        # Rank by score descending so Q1 = best
        order = np.argsort(-scores)
        n = len(scores)
        quintile_size = n // 5

        result: Dict[int, float] = {}
        for q in range(1, 6):
            start = (q - 1) * quintile_size
            end = q * quintile_size if q < 5 else n
            indices = order[start:end]
            if len(indices) > 0:
                result[q] = float(np.mean(returns[indices]))

        return result

    @staticmethod
    def _spearman_correlation(
        scores: np.ndarray, returns: np.ndarray,
    ) -> float:
        """Compute Spearman rank correlation between scores and returns."""
        n = len(scores)
        if n < 3:
            return 0.0

        # Rank both arrays
        score_ranks = np.argsort(np.argsort(scores)).astype(float) + 1
        return_ranks = np.argsort(np.argsort(returns)).astype(float) + 1

        # Spearman formula: 1 - 6*sum(d^2) / (n*(n^2-1))
        d = score_ranks - return_ranks
        rho = 1 - (6 * np.sum(d ** 2)) / (n * (n ** 2 - 1))
        return float(rho)

    @staticmethod
    def _hit_rate(
        scores: np.ndarray, returns: np.ndarray,
    ) -> float:
        """Fraction of top-quintile stocks that beat the median return."""
        n = len(scores)
        if n < 5:
            return 0.0

        quintile_size = n // 5
        order = np.argsort(-scores)
        top_quintile_indices = order[:quintile_size]

        median_return = float(np.median(returns))
        hits = sum(1 for i in top_quintile_indices if returns[i] > median_return)

        return hits / len(top_quintile_indices) if len(top_quintile_indices) > 0 else 0.0
