"""
IndicatorBuilder - Reusable technical indicator calculation from price DataFrames.

Extracts the indicator math from scripts/calculate_technical_indicators.py
into a pure-data class that can compute indicators for any historical date,
enabling backtesting without database dependency.

Framework Reference: Section 4 (Technical Score)
"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class IndicatorBuilder:
    """Calculate technical indicators from a price DataFrame.

    Unlike TechnicalIndicatorCalculator (which reads from DB and stores the
    latest date), IndicatorBuilder is a pure calculation engine:
    - Input: a price DataFrame with DatetimeIndex and OHLCV columns
    - Output: a DataFrame with all indicators computed for every date

    This enables point-in-time indicator retrieval for backtesting.

    Usage:
        builder = IndicatorBuilder()
        indicators_df = builder.compute(price_df)

        # Get indicators as of a specific date
        row = builder.get_as_of(indicators_df, date(2025, 6, 30))
    """

    # Standard trading day counts
    DAYS_1M = 21
    DAYS_3M = 63
    DAYS_6M = 126
    DAYS_12M = 252

    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Compute all technical indicators from a price DataFrame.

        Args:
            prices: DataFrame with DatetimeIndex and columns:
                    close (required), volume (optional), open, high, low.

        Returns:
            DataFrame with same index and columns for every indicator:
            sma_20, sma_50, sma_200, mad, rsi_14,
            avg_volume_20d, avg_volume_90d, relative_volume,
            momentum_1m, momentum_3m, momentum_6m, momentum_12_1,
            price_vs_200ma.
        """
        if prices.empty:
            return pd.DataFrame()

        df = prices.copy()

        # Moving averages
        df['sma_20'] = df['close'].rolling(window=20, min_periods=20).mean()
        df['sma_50'] = df['close'].rolling(window=50, min_periods=50).mean()
        df['sma_200'] = df['close'].rolling(window=200, min_periods=200).mean()

        # MAD: (50-day MA - 200-day MA) / 200-day MA
        # Framework Section 4.2
        df['mad'] = (df['sma_50'] - df['sma_200']) / df['sma_200']

        # RSI (14-period)
        df['rsi_14'] = self._calculate_rsi(df['close'], period=14)

        # Volume averages (only if volume column exists)
        if 'volume' in df.columns:
            df['avg_volume_20d'] = df['volume'].rolling(window=20, min_periods=20).mean()
            df['avg_volume_90d'] = df['volume'].rolling(window=90, min_periods=90).mean()
            df['relative_volume'] = df['avg_volume_20d'] / df['avg_volume_90d']
        else:
            df['avg_volume_20d'] = np.nan
            df['avg_volume_90d'] = np.nan
            df['relative_volume'] = np.nan

        # Momentum returns
        df['momentum_1m'] = df['close'].pct_change(periods=self.DAYS_1M)
        df['momentum_3m'] = df['close'].pct_change(periods=self.DAYS_3M)
        df['momentum_6m'] = df['close'].pct_change(periods=self.DAYS_6M)

        # 12-1 month momentum: return from 12 months ago to 1 month ago
        # Framework Section 4.2: excludes most recent month to avoid reversal
        prices_12m_ago = df['close'].shift(self.DAYS_12M)
        prices_1m_ago = df['close'].shift(self.DAYS_1M)
        df['momentum_12_1'] = (prices_1m_ago - prices_12m_ago) / prices_12m_ago

        # Price vs 200-MA boolean
        df['price_vs_200ma'] = df['close'] > df['sma_200']

        # Select only indicator columns
        indicator_cols = [
            'sma_20', 'sma_50', 'sma_200', 'mad', 'rsi_14',
            'avg_volume_20d', 'avg_volume_90d', 'relative_volume',
            'momentum_1m', 'momentum_3m', 'momentum_6m', 'momentum_12_1',
            'price_vs_200ma',
        ]
        return df[indicator_cols]

    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI (Relative Strength Index).

        Uses the simple moving average method (same as existing calculator).
        """
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def get_as_of(
        self,
        indicators: pd.DataFrame,
        as_of_date: pd.Timestamp,
    ) -> Optional[pd.Series]:
        """Get the indicator values as of a specific date.

        Returns the row on or before as_of_date (latest available data).

        Args:
            indicators: DataFrame from compute().
            as_of_date: Target date.

        Returns:
            Series with indicator values, or None if no data available.
        """
        if indicators.empty:
            return None

        as_of_ts = pd.Timestamp(as_of_date)
        mask = indicators.index <= as_of_ts
        if not mask.any():
            return None

        return indicators.loc[mask].iloc[-1]

    def build_snapshot(
        self,
        indicators: pd.DataFrame,
        as_of_date: pd.Timestamp,
        current_price: float,
    ) -> Optional[Dict[str, float]]:
        """Build a dict of indicator values suitable for TechnicalCalculator.

        Returns values in the same format as the scoring pipeline expects
        (matching the keys used by _prepare_technical in pipeline.py).

        Args:
            indicators: DataFrame from compute().
            as_of_date: Target date.
            current_price: Closing price on as_of_date.

        Returns:
            Dict with all technical metrics, or None if data unavailable.
        """
        row = self.get_as_of(indicators, as_of_date)
        if row is None:
            return None

        sma_20 = _safe_float(row.get('sma_20'))
        sma_50 = _safe_float(row.get('sma_50'))
        sma_200 = _safe_float(row.get('sma_200'))

        # Compute uptrend signals
        short_term_uptrend = None
        if current_price and sma_20 is not None and sma_50 is not None:
            short_term_uptrend = (current_price > sma_20) and (sma_20 > sma_50)

        long_term_uptrend = None
        if current_price and sma_50 is not None and sma_200 is not None:
            long_term_uptrend = (current_price > sma_50) and (sma_50 > sma_200)

        return {
            'sma_20': sma_20,
            'sma_50': sma_50,
            'sma_200': sma_200,
            'mad': _safe_float(row.get('mad')),
            'rsi_14': _safe_float(row.get('rsi_14')),
            'avg_volume_20d': _safe_float(row.get('avg_volume_20d')),
            'avg_volume_90d': _safe_float(row.get('avg_volume_90d')),
            'relative_volume': _safe_float(row.get('relative_volume')),
            'momentum_1m': _safe_float(row.get('momentum_1m')),
            'momentum_3m': _safe_float(row.get('momentum_3m')),
            'momentum_6m': _safe_float(row.get('momentum_6m')),
            'momentum_12_1': _safe_float(row.get('momentum_12_1')),
            'price_vs_200ma': bool(row.get('price_vs_200ma')) if pd.notna(row.get('price_vs_200ma')) else None,
            'current_price': current_price,
            'short_term_uptrend': short_term_uptrend,
            'long_term_uptrend': long_term_uptrend,
            # sector_relative_6m is computed cross-sectionally in the backtester
            'sector_relative_6m': None,
        }

    def compute_sector_relative(
        self,
        stock_snapshots: Dict[str, Dict],
        stock_sectors: Dict[str, str],
    ) -> None:
        """Compute sector_relative_6m for all stocks in-place.

        Framework Section 4.2: sector_relative_6m = stock's 6m return - sector avg 6m return.

        Args:
            stock_snapshots: Dict of {ticker: snapshot_dict} from build_snapshot().
            stock_sectors: Dict of {ticker: sector_name}.
        """
        # Group 6m momentum by sector
        sector_returns: Dict[str, List[float]] = {}
        for ticker, snapshot in stock_snapshots.items():
            mom_6m = snapshot.get('momentum_6m')
            sector = stock_sectors.get(ticker)
            if mom_6m is not None and sector:
                sector_returns.setdefault(sector, []).append(mom_6m)

        # Compute sector averages
        sector_avgs = {
            sector: sum(vals) / len(vals)
            for sector, vals in sector_returns.items()
            if vals
        }

        # Update each snapshot
        for ticker, snapshot in stock_snapshots.items():
            mom_6m = snapshot.get('momentum_6m')
            sector = stock_sectors.get(ticker)
            if mom_6m is not None and sector and sector in sector_avgs:
                snapshot['sector_relative_6m'] = mom_6m - sector_avgs[sector]


def _safe_float(val) -> Optional[float]:
    """Convert a value to float, returning None for NaN/None."""
    if val is None:
        return None
    try:
        f = float(val)
        if np.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None
