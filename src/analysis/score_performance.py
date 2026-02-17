"""
Score vs. Price Performance Analyzer.

Correlates historical composite scores from snapshots with subsequent
stock price performance (forward returns) to validate whether the
scoring model has predictive power.

Framework Reference: Section 10 (Backtesting & Paper Trading)
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import bisect
import logging

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ScoreReturnPair:
    """A single (score, forward_return) observation."""
    ticker: str
    snapshot_date: date
    composite_score: float
    composite_percentile: float
    recommendation: str
    fundamental_score: Optional[float]
    technical_score: Optional[float]
    sentiment_score: Optional[float]
    forward_returns: Dict[str, Optional[float]]  # {'1m': 0.05, '3m': 0.12}


@dataclass
class RecommendationBucket:
    """Aggregated stats for one recommendation category."""
    recommendation: str
    count: int
    avg_score: float
    avg_return_1m: Optional[float]
    avg_return_3m: Optional[float]
    median_return_1m: Optional[float]
    median_return_3m: Optional[float]
    win_rate_1m: Optional[float]
    win_rate_3m: Optional[float]


@dataclass
class UniverseAnalysis:
    """Universe-level analysis results."""
    total_observations: int
    observations_with_1m: int
    observations_with_3m: int
    snapshot_dates: List[str]

    recommendation_buckets: List[RecommendationBucket]

    quintile_returns_1m: Dict[int, float]
    quintile_returns_3m: Dict[int, float]

    spearman_1m: Optional[float]
    spearman_3m: Optional[float]

    long_short_1m: Optional[float]
    long_short_3m: Optional[float]

    hit_rate_1m: Optional[float]
    hit_rate_3m: Optional[float]

    monthly_long_short: List[Dict]


@dataclass
class StockAnalysis:
    """Per-stock analysis results."""
    ticker: str
    observations: int
    scores: List[Dict]
    avg_score: Optional[float]
    avg_return_1m: Optional[float]
    avg_return_3m: Optional[float]
    score_return_correlation: Optional[float]
    score_dates: List[str]
    composite_scores: List[float]
    forward_returns_1m: List[Optional[float]]
    forward_returns_3m: List[Optional[float]]


class ScorePerformanceAnalyzer:
    """Analyze whether composite scores predict forward price performance.

    Loads snapshots from data/snapshots/ and price data from DB,
    then computes universe-level and per-stock correlation metrics.

    Usage:
        analyzer = ScorePerformanceAnalyzer()
        with get_db_session() as session:
            pairs = analyzer.load_data(snapshot_dir, session)
        universe = analyzer.analyze_universe(pairs)
        stock = analyzer.analyze_stock(pairs, 'AAPL')
    """

    FORWARD_HORIZONS = {
        '1m': timedelta(days=30),
        '3m': timedelta(days=91),
    }

    RECOMMENDATION_ORDER = ['STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL']

    def load_data(
        self,
        snapshot_dir: str,
        session,
    ) -> List[ScoreReturnPair]:
        """Load all snapshots and pair each score with forward returns.

        Args:
            snapshot_dir: Path to data/snapshots/ directory.
            session: SQLAlchemy database session.

        Returns:
            List of ScoreReturnPair objects.
        """
        from backtesting.snapshot_manager import SnapshotManager

        mgr = SnapshotManager(snapshot_dir=snapshot_dir)
        snapshot_dates = mgr.list_snapshots()

        if not snapshot_dates:
            logger.warning("No snapshots found")
            return []

        price_cache = self._build_price_cache(session)

        pairs = []
        for snap_date in snapshot_dates:
            snapshot = mgr.load(snap_date)
            if not snapshot:
                continue

            for stock_data in snapshot.get('scores', []):
                ticker = stock_data['ticker']
                composite = stock_data.get('composite_score')
                if composite is None:
                    continue

                rec = stock_data.get('recommendation', 'HOLD')
                if rec == 'INSUFFICIENT DATA':
                    continue

                fwd_returns = self._get_forward_returns_from_cache(
                    ticker, snap_date, price_cache,
                )

                pairs.append(ScoreReturnPair(
                    ticker=ticker,
                    snapshot_date=snap_date,
                    composite_score=composite,
                    composite_percentile=stock_data.get('composite_percentile', 0),
                    recommendation=rec,
                    fundamental_score=stock_data.get('fundamental_score'),
                    technical_score=stock_data.get('technical_score'),
                    sentiment_score=stock_data.get('sentiment_score'),
                    forward_returns=fwd_returns,
                ))

        logger.info(
            f"Loaded {len(pairs)} score-return pairs from "
            f"{len(snapshot_dates)} snapshots"
        )
        return pairs

    def analyze_universe(
        self,
        pairs: List[ScoreReturnPair],
    ) -> UniverseAnalysis:
        """Compute universe-level metrics from all score-return pairs."""
        if not pairs:
            return UniverseAnalysis(
                total_observations=0,
                observations_with_1m=0,
                observations_with_3m=0,
                snapshot_dates=[],
                recommendation_buckets=[],
                quintile_returns_1m={},
                quintile_returns_3m={},
                spearman_1m=None,
                spearman_3m=None,
                long_short_1m=None,
                long_short_3m=None,
                hit_rate_1m=None,
                hit_rate_3m=None,
                monthly_long_short=[],
            )

        snapshot_dates = sorted({p.snapshot_date.isoformat() for p in pairs})

        # Filter pairs that have forward returns for each horizon
        pairs_1m = [p for p in pairs if p.forward_returns.get('1m') is not None]
        pairs_3m = [p for p in pairs if p.forward_returns.get('3m') is not None]

        # Recommendation bucket analysis
        rec_buckets = self._compute_recommendation_buckets(pairs_1m, pairs_3m)

        # Quintile and correlation analysis
        quintile_1m, spearman_1m, hit_1m, ls_1m = self._compute_score_metrics(
            pairs_1m, '1m',
        )
        quintile_3m, spearman_3m, hit_3m, ls_3m = self._compute_score_metrics(
            pairs_3m, '3m',
        )

        # Monthly long-short time series
        monthly_ls = self._compute_monthly_long_short(pairs)

        return UniverseAnalysis(
            total_observations=len(pairs),
            observations_with_1m=len(pairs_1m),
            observations_with_3m=len(pairs_3m),
            snapshot_dates=snapshot_dates,
            recommendation_buckets=rec_buckets,
            quintile_returns_1m=quintile_1m,
            quintile_returns_3m=quintile_3m,
            spearman_1m=spearman_1m,
            spearman_3m=spearman_3m,
            long_short_1m=ls_1m,
            long_short_3m=ls_3m,
            hit_rate_1m=hit_1m,
            hit_rate_3m=hit_3m,
            monthly_long_short=monthly_ls,
        )

    def analyze_stock(
        self,
        pairs: List[ScoreReturnPair],
        ticker: str,
    ) -> Optional[StockAnalysis]:
        """Compute per-stock analysis for a single ticker."""
        stock_pairs = [p for p in pairs if p.ticker == ticker]
        if not stock_pairs:
            return None

        stock_pairs.sort(key=lambda p: p.snapshot_date)

        scores_list = []
        score_dates = []
        composite_scores = []
        fwd_1m = []
        fwd_3m = []

        for p in stock_pairs:
            scores_list.append({
                'date': p.snapshot_date.isoformat(),
                'composite': p.composite_score,
                'fundamental': p.fundamental_score,
                'technical': p.technical_score,
                'sentiment': p.sentiment_score,
                'fwd_1m': p.forward_returns.get('1m'),
                'fwd_3m': p.forward_returns.get('3m'),
            })
            score_dates.append(p.snapshot_date.isoformat())
            composite_scores.append(p.composite_score)
            fwd_1m.append(p.forward_returns.get('1m'))
            fwd_3m.append(p.forward_returns.get('3m'))

        # Average returns where available
        valid_1m = [r for r in fwd_1m if r is not None]
        valid_3m = [r for r in fwd_3m if r is not None]

        avg_return_1m = float(np.mean(valid_1m)) if valid_1m else None
        avg_return_3m = float(np.mean(valid_3m)) if valid_3m else None

        # Score-return correlation (Spearman) for this stock
        correlation = None
        if len(valid_1m) >= 4:
            scores_with_ret = [
                (p.composite_score, p.forward_returns['1m'])
                for p in stock_pairs
                if p.forward_returns.get('1m') is not None
            ]
            if len(scores_with_ret) >= 4:
                s_arr = np.array([x[0] for x in scores_with_ret])
                r_arr = np.array([x[1] for x in scores_with_ret])
                correlation = float(self._spearman_correlation(s_arr, r_arr))

        return StockAnalysis(
            ticker=ticker,
            observations=len(stock_pairs),
            scores=scores_list,
            avg_score=float(np.mean(composite_scores)),
            avg_return_1m=avg_return_1m,
            avg_return_3m=avg_return_3m,
            score_return_correlation=correlation,
            score_dates=score_dates,
            composite_scores=composite_scores,
            forward_returns_1m=fwd_1m,
            forward_returns_3m=fwd_3m,
        )

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_price_cache(session) -> Dict[str, Tuple[List[date], List[float]]]:
        """Load all price data into {ticker: (sorted_dates, prices)}.

        Uses sorted lists for efficient bisect-based lookups.
        """
        from database.models import PriceData

        raw: Dict[str, Dict[date, float]] = {}
        all_prices = (
            session.query(PriceData.ticker, PriceData.date, PriceData.close)
            .order_by(PriceData.ticker, PriceData.date)
            .all()
        )

        for row in all_prices:
            if row.ticker not in raw:
                raw[row.ticker] = {}
            raw[row.ticker][row.date] = float(row.close)

        # Convert to sorted parallel lists for bisect lookups
        cache = {}
        for ticker, date_price_map in raw.items():
            sorted_dates = sorted(date_price_map.keys())
            prices = [date_price_map[d] for d in sorted_dates]
            cache[ticker] = (sorted_dates, prices)

        return cache

    def _get_forward_returns_from_cache(
        self,
        ticker: str,
        snapshot_date: date,
        price_cache: Dict[str, Tuple[List[date], List[float]]],
    ) -> Dict[str, Optional[float]]:
        """Calculate forward returns using in-memory price cache."""
        if ticker not in price_cache:
            return {h: None for h in self.FORWARD_HORIZONS}

        sorted_dates, prices = price_cache[ticker]

        base_price = self._find_price_on_or_before(
            snapshot_date, sorted_dates, prices, tolerance_days=5,
        )
        if base_price is None:
            return {h: None for h in self.FORWARD_HORIZONS}

        results = {}
        for horizon_name, delta in self.FORWARD_HORIZONS.items():
            target_date = snapshot_date + delta
            fwd_price = self._find_price_on_or_before(
                target_date, sorted_dates, prices, tolerance_days=5,
            )
            if fwd_price is not None and fwd_price != base_price:
                results[horizon_name] = (fwd_price - base_price) / base_price
            else:
                results[horizon_name] = None

        return results

    @staticmethod
    def _find_price_on_or_before(
        target: date,
        sorted_dates: List[date],
        prices: List[float],
        tolerance_days: int = 5,
    ) -> Optional[float]:
        """Find the closest price on or before target date within tolerance."""
        if not sorted_dates:
            return None

        idx = bisect.bisect_right(sorted_dates, target) - 1
        if idx < 0:
            return None

        actual_date = sorted_dates[idx]
        if (target - actual_date).days > tolerance_days:
            return None

        return prices[idx]

    # ------------------------------------------------------------------
    # Statistical analysis helpers
    # ------------------------------------------------------------------

    def _compute_recommendation_buckets(
        self,
        pairs_1m: List[ScoreReturnPair],
        pairs_3m: List[ScoreReturnPair],
    ) -> List[RecommendationBucket]:
        """Group observations by recommendation and compute stats."""
        # Build lookup for 3m returns by (ticker, date)
        ret_3m_lookup = {
            (p.ticker, p.snapshot_date): p.forward_returns['3m']
            for p in pairs_3m
        }

        # Use 1m pairs as the base (more complete), augment with 3m
        by_rec: Dict[str, List[ScoreReturnPair]] = {}
        for p in pairs_1m:
            rec = p.recommendation
            if rec not in by_rec:
                by_rec[rec] = []
            by_rec[rec].append(p)

        # Also include pairs that only have 3m returns
        for p in pairs_3m:
            if p.forward_returns.get('1m') is None:
                rec = p.recommendation
                if rec not in by_rec:
                    by_rec[rec] = []
                by_rec[rec].append(p)

        buckets = []
        for rec in self.RECOMMENDATION_ORDER:
            rec_pairs = by_rec.get(rec, [])
            if not rec_pairs:
                buckets.append(RecommendationBucket(
                    recommendation=rec, count=0, avg_score=0,
                    avg_return_1m=None, avg_return_3m=None,
                    median_return_1m=None, median_return_3m=None,
                    win_rate_1m=None, win_rate_3m=None,
                ))
                continue

            scores = [p.composite_score for p in rec_pairs]
            returns_1m = [
                p.forward_returns['1m'] for p in rec_pairs
                if p.forward_returns.get('1m') is not None
            ]
            returns_3m = [
                ret_3m_lookup.get((p.ticker, p.snapshot_date))
                for p in rec_pairs
            ]
            returns_3m = [r for r in returns_3m if r is not None]

            buckets.append(RecommendationBucket(
                recommendation=rec,
                count=len(rec_pairs),
                avg_score=round(float(np.mean(scores)), 1),
                avg_return_1m=round(float(np.mean(returns_1m)), 4) if returns_1m else None,
                avg_return_3m=round(float(np.mean(returns_3m)), 4) if returns_3m else None,
                median_return_1m=round(float(np.median(returns_1m)), 4) if returns_1m else None,
                median_return_3m=round(float(np.median(returns_3m)), 4) if returns_3m else None,
                win_rate_1m=round(sum(1 for r in returns_1m if r > 0) / len(returns_1m), 2) if returns_1m else None,
                win_rate_3m=round(sum(1 for r in returns_3m if r > 0) / len(returns_3m), 2) if returns_3m else None,
            ))

        return buckets

    def _compute_score_metrics(
        self,
        pairs: List[ScoreReturnPair],
        horizon: str,
    ) -> Tuple[Dict[int, float], Optional[float], Optional[float], Optional[float]]:
        """Compute quintile returns, Spearman, hit rate, long-short for one horizon."""
        if len(pairs) < 10:
            return {}, None, None, None

        scores = np.array([p.composite_score for p in pairs])
        returns = np.array([p.forward_returns[horizon] for p in pairs])

        quintiles = self._quintile_analysis(scores, returns)
        spearman = self._spearman_correlation(scores, returns)
        hit = self._hit_rate(scores, returns)

        ls = None
        if 1 in quintiles and 5 in quintiles:
            ls = round(quintiles[1] - quintiles[5], 4)

        # Round quintile values
        quintiles = {k: round(v, 4) for k, v in quintiles.items()}

        return quintiles, round(spearman, 3), round(hit, 2), ls

    def _compute_monthly_long_short(
        self,
        pairs: List[ScoreReturnPair],
    ) -> List[Dict]:
        """Compute per-snapshot top-half vs bottom-half spread."""
        by_date: Dict[date, List[ScoreReturnPair]] = {}
        for p in pairs:
            if p.snapshot_date not in by_date:
                by_date[p.snapshot_date] = []
            by_date[p.snapshot_date].append(p)

        results = []
        for snap_date in sorted(by_date.keys()):
            date_pairs = by_date[snap_date]

            # Need at least 4 stocks for meaningful top/bottom split
            pairs_with_1m = [
                p for p in date_pairs
                if p.forward_returns.get('1m') is not None
            ]
            if len(pairs_with_1m) < 4:
                results.append({
                    'date': snap_date.isoformat(),
                    'spread_1m': None,
                    'n_stocks': len(date_pairs),
                })
                continue

            pairs_with_1m.sort(key=lambda p: p.composite_score, reverse=True)
            mid = len(pairs_with_1m) // 2
            top_half = pairs_with_1m[:mid]
            bottom_half = pairs_with_1m[mid:]

            top_avg = np.mean([p.forward_returns['1m'] for p in top_half])
            bot_avg = np.mean([p.forward_returns['1m'] for p in bottom_half])

            results.append({
                'date': snap_date.isoformat(),
                'spread_1m': round(float(top_avg - bot_avg), 4),
                'n_stocks': len(date_pairs),
            })

        return results

    # ------------------------------------------------------------------
    # Reusable statistical methods (from TechnicalBacktester)
    # ------------------------------------------------------------------

    @staticmethod
    def _quintile_analysis(
        scores: np.ndarray, returns: np.ndarray,
    ) -> Dict[int, float]:
        """Split into 5 quintiles by score, compute avg return per quintile.

        Q1 = top scores (highest), Q5 = bottom scores (lowest).
        """
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

        score_ranks = np.argsort(np.argsort(scores)).astype(float) + 1
        return_ranks = np.argsort(np.argsort(returns)).astype(float) + 1

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
        top_indices = order[:quintile_size]

        median_return = float(np.median(returns))
        hits = sum(1 for i in top_indices if returns[i] > median_return)

        return hits / len(top_indices) if len(top_indices) > 0 else 0.0
