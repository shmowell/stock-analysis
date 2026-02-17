"""
Calculate and store technical indicators from price data.

Framework Reference: Section 4 (Technical Score)
Purpose: Calculate technical indicators from price_data and store in technical_indicators table
Required for: Technical score calculations

Technical indicators calculated:
- Moving averages (50-day, 200-day, 20-day for multi-speed)
- MAD (Moving Average Distance)
- RSI (14-period)
- Volume averages (20-day, 90-day)
- Returns (1-month, 3-month, 6-month, 12-1 month momentum)

Usage:
    python scripts/calculate_technical_indicators.py
"""

import argparse
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional
import pandas as pd
import numpy as np
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from database import get_db_session
from database.models import Stock, PriceData, TechnicalIndicator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TechnicalIndicatorCalculator:
    """
    Calculates technical indicators from price data.

    Framework Section 4: Technical indicators for cross-sectional
    momentum and trend analysis.
    """

    def __init__(self):
        self.stats = {
            'stocks_processed': 0,
            'indicators_calculated': 0,
            'records_inserted': 0,
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

    def get_price_data(self, ticker: str) -> pd.DataFrame:
        """
        Fetch price history for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            DataFrame with price history sorted by date
        """
        with get_db_session() as session:
            stmt = select(PriceData).where(
                PriceData.ticker == ticker
            ).order_by(PriceData.date)

            result = session.execute(stmt)
            rows = result.scalars().all()

            if not rows:
                logger.warning(f"No price data found for {ticker}")
                return pd.DataFrame()

            # Convert to DataFrame
            data = {
                'date': [row.date for row in rows],
                'open': [float(row.open) if row.open else None for row in rows],
                'high': [float(row.high) if row.high else None for row in rows],
                'low': [float(row.low) if row.low else None for row in rows],
                'close': [float(row.close) if row.close else None for row in rows],
                'volume': [int(row.volume) if row.volume else None for row in rows],
            }

            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df = df.set_index('date')

            logger.info(f"Loaded {len(df)} price records for {ticker}")
            return df

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate RSI (Relative Strength Index).

        Args:
            prices: Series of closing prices
            period: RSI period (default: 14)

        Returns:
            Series of RSI values
        """
        # Calculate price changes
        delta = prices.diff()

        # Separate gains and losses
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        # Calculate average gain and loss
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()

        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_returns(self, prices: pd.Series) -> Dict[str, pd.Series]:
        """
        Calculate various return periods.

        Framework Section 4.2: Return calculations for momentum scoring

        Args:
            prices: Series of closing prices

        Returns:
            Dict with return series for different periods
        """
        returns = {}

        # 1-month return (21 trading days)
        returns['return_1_month'] = prices.pct_change(periods=21)

        # 3-month return (63 trading days)
        returns['return_3_month'] = prices.pct_change(periods=63)

        # 6-month return (126 trading days)
        returns['return_6_month'] = prices.pct_change(periods=126)

        # 12-1 month momentum return
        # Framework Section 4.2: 12 months ago to 1 month ago (excludes recent month)
        # This is: return from 252 days ago to 21 days ago
        prices_12m_ago = prices.shift(252)  # 12 months ago
        prices_1m_ago = prices.shift(21)    # 1 month ago
        returns['return_12_1_month'] = (prices_1m_ago - prices_12m_ago) / prices_12m_ago

        return returns

    def calculate_indicators_for_stock(self, ticker: str) -> List[Dict]:
        """
        Calculate all technical indicators for a stock.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of dicts with indicator data for each date
        """
        logger.info(f"Calculating indicators for {ticker}")

        # Get price data
        df = self.get_price_data(ticker)
        if df.empty:
            logger.warning(f"No price data for {ticker}, skipping")
            return []

        # Calculate moving averages
        df['ma_20'] = df['close'].rolling(window=20, min_periods=20).mean()
        df['ma_50'] = df['close'].rolling(window=50, min_periods=50).mean()
        df['ma_200'] = df['close'].rolling(window=200, min_periods=200).mean()

        # Calculate MAD (Moving Average Distance)
        # Framework Section 4.2: MAD = (50-day MA - 200-day MA) / 200-day MA
        df['mad'] = (df['ma_50'] - df['ma_200']) / df['ma_200']

        # Calculate RSI
        df['rsi'] = self.calculate_rsi(df['close'], period=14)

        # Calculate volume averages
        df['avg_volume_20d'] = df['volume'].rolling(window=20, min_periods=20).mean()
        df['avg_volume_90d'] = df['volume'].rolling(window=90, min_periods=90).mean()

        # Calculate returns
        returns = self.calculate_returns(df['close'])
        for return_name, return_series in returns.items():
            df[return_name] = return_series

        # Only keep the most recent record (latest date)
        # We calculate on full history to get accurate indicators,
        # but only store the latest values
        latest_date = df.index.max()
        latest_row = df.loc[latest_date]

        # Calculate relative volume
        relative_vol = None
        if pd.notna(latest_row['avg_volume_20d']) and pd.notna(latest_row['avg_volume_90d']):
            if latest_row['avg_volume_90d'] > 0:
                relative_vol = float(latest_row['avg_volume_20d'] / latest_row['avg_volume_90d'])

        # Calculate price vs 200-MA boolean
        current_price = float(df['close'].iloc[-1]) if pd.notna(df['close'].iloc[-1]) else None
        price_vs_200ma = None
        if current_price and pd.notna(latest_row['ma_200']):
            price_vs_200ma = current_price > float(latest_row['ma_200'])

        # Prepare record for database (using correct column names from database_schema.md)
        indicator_data = {
            'ticker': ticker,
            'calculation_date': latest_date.date(),
            'sma_20': float(latest_row['ma_20']) if pd.notna(latest_row['ma_20']) else None,
            'sma_50': float(latest_row['ma_50']) if pd.notna(latest_row['ma_50']) else None,
            'sma_200': float(latest_row['ma_200']) if pd.notna(latest_row['ma_200']) else None,
            'mad': float(latest_row['mad']) if pd.notna(latest_row['mad']) else None,
            'momentum_12_1': float(latest_row['return_12_1_month']) if pd.notna(latest_row['return_12_1_month']) else None,
            'momentum_6m': float(latest_row['return_6_month']) if pd.notna(latest_row['return_6_month']) else None,
            'momentum_3m': float(latest_row['return_3_month']) if pd.notna(latest_row['return_3_month']) else None,
            'momentum_1m': float(latest_row['return_1_month']) if pd.notna(latest_row['return_1_month']) else None,
            'rsi_14': float(latest_row['rsi']) if pd.notna(latest_row['rsi']) else None,
            'avg_volume_20d': int(latest_row['avg_volume_20d']) if pd.notna(latest_row['avg_volume_20d']) else None,
            'avg_volume_90d': int(latest_row['avg_volume_90d']) if pd.notna(latest_row['avg_volume_90d']) else None,
            'relative_volume': relative_vol,
            'price_vs_200ma': price_vs_200ma,
            'adx': None,  # Not calculated yet
            'sector_relative_6m': None,  # Will be calculated separately with sector data
        }

        ma200_str = f"{indicator_data['sma_200']:.2f}" if indicator_data['sma_200'] else 'N/A'
        rsi_str = f"{indicator_data['rsi_14']:.1f}" if indicator_data['rsi_14'] else 'N/A'
        return_12_1_str = f"{indicator_data['momentum_12_1']:.2%}" if indicator_data['momentum_12_1'] else 'N/A'

        logger.info(
            f"{ticker}: MA200={ma200_str}, RSI={rsi_str}, 12-1M Return={return_12_1_str}"
        )

        self.stats['indicators_calculated'] += 1
        return [indicator_data]

    def store_indicators(self, indicators: List[Dict]) -> None:
        """
        Store technical indicators in database.

        Uses INSERT ... ON CONFLICT UPDATE to handle duplicates.

        Args:
            indicators: List of indicator dicts
        """
        if not indicators:
            return

        with get_db_session() as session:
            try:
                # Use raw SQL to insert since ORM model doesn't match database schema
                for indicator in indicators:
                    sql = text("""
                        INSERT INTO technical_indicators (
                            ticker, calculation_date, sma_20, sma_50, sma_200,
                            mad, momentum_12_1, momentum_6m, momentum_3m, momentum_1m,
                            rsi_14, avg_volume_20d, avg_volume_90d, relative_volume,
                            price_vs_200ma, adx, sector_relative_6m
                        ) VALUES (
                            :ticker, :calculation_date, :sma_20, :sma_50, :sma_200,
                            :mad, :momentum_12_1, :momentum_6m, :momentum_3m, :momentum_1m,
                            :rsi_14, :avg_volume_20d, :avg_volume_90d, :relative_volume,
                            :price_vs_200ma, :adx, :sector_relative_6m
                        )
                        ON CONFLICT (ticker, calculation_date)
                        DO UPDATE SET
                            sma_20 = EXCLUDED.sma_20,
                            sma_50 = EXCLUDED.sma_50,
                            sma_200 = EXCLUDED.sma_200,
                            mad = EXCLUDED.mad,
                            momentum_12_1 = EXCLUDED.momentum_12_1,
                            momentum_6m = EXCLUDED.momentum_6m,
                            momentum_3m = EXCLUDED.momentum_3m,
                            momentum_1m = EXCLUDED.momentum_1m,
                            rsi_14 = EXCLUDED.rsi_14,
                            avg_volume_20d = EXCLUDED.avg_volume_20d,
                            avg_volume_90d = EXCLUDED.avg_volume_90d,
                            relative_volume = EXCLUDED.relative_volume,
                            price_vs_200ma = EXCLUDED.price_vs_200ma,
                            adx = EXCLUDED.adx,
                            sector_relative_6m = EXCLUDED.sector_relative_6m
                    """)

                    session.execute(sql, indicator)

                session.commit()

                self.stats['records_inserted'] += len(indicators)
                logger.info(f"Stored {len(indicators)} indicator records")

            except Exception as e:
                session.rollback()
                logger.error(f"Error storing indicators: {e}")
                self.stats['errors'].append(str(e))
                raise

    def calculate_sector_relative_returns(self) -> None:
        """
        Calculate sector-relative 6-month returns for all stocks.

        Framework Section 4.2: Relative strength vs sector measures
        how much a stock outperformed/underperformed its sector peers.

        sector_relative_6m = stock's 6m return - sector average 6m return

        Must run AFTER individual indicators are calculated.
        """
        logger.info("Calculating sector-relative 6-month returns...")

        with get_db_session() as session:
            # Get all stocks with their sectors and 6m momentum
            sql = text("""
                SELECT s.ticker, s.sector, ti.momentum_6m
                FROM stocks s
                JOIN technical_indicators ti ON s.ticker = ti.ticker
                WHERE s.is_active = true AND ti.momentum_6m IS NOT NULL
            """)
            result = session.execute(sql)
            rows = result.fetchall()

            if not rows:
                logger.warning("No stocks with 6m momentum data found")
                return

            # Group by sector and calculate averages
            sector_returns: Dict[str, List[float]] = {}
            stock_data: List[Dict] = []
            for ticker, sector, momentum_6m in rows:
                m6m = float(momentum_6m)
                stock_data.append({'ticker': ticker, 'sector': sector, 'momentum_6m': m6m})
                sector_returns.setdefault(sector, []).append(m6m)

            sector_averages = {
                sector: sum(returns) / len(returns)
                for sector, returns in sector_returns.items()
            }

            # Log sector averages
            for sector, avg in sorted(sector_averages.items()):
                count = len(sector_returns[sector])
                logger.info(f"  {sector}: avg 6m return = {avg:.2%} ({count} stocks)")

            # Calculate and update sector_relative_6m for each stock
            updated = 0
            for stock in stock_data:
                sector_avg = sector_averages[stock['sector']]
                relative = stock['momentum_6m'] - sector_avg

                update_sql = text("""
                    UPDATE technical_indicators
                    SET sector_relative_6m = :relative
                    WHERE ticker = :ticker
                """)
                session.execute(update_sql, {
                    'relative': round(relative, 6),
                    'ticker': stock['ticker']
                })

                logger.info(
                    f"  {stock['ticker']}: 6m={stock['momentum_6m']:.2%}, "
                    f"sector avg={sector_avg:.2%}, relative={relative:+.2%}"
                )
                updated += 1

            session.commit()
            logger.info(f"Updated sector_relative_6m for {updated} stocks")

    def process_all_stocks(self, tickers: Optional[List[str]] = None) -> None:
        """Calculate and store indicators for stocks.

        Args:
            tickers: Specific tickers to process. If None, processes all active stocks.
        """
        logger.info("=" * 60)
        logger.info("TECHNICAL INDICATOR CALCULATION")
        logger.info("=" * 60)

        if tickers is None:
            tickers = self.get_active_stocks()

        for ticker in tickers:
            try:
                indicators = self.calculate_indicators_for_stock(ticker)
                if indicators:
                    self.store_indicators(indicators)
                    self.stats['stocks_processed'] += 1

            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                self.stats['errors'].append(f"{ticker}: {str(e)}")
                continue

        # Calculate sector-relative returns after all individual indicators
        # Framework Section 4.2: Requires cross-stock comparison within sectors
        self.calculate_sector_relative_returns()

        self.print_summary()

    def print_summary(self) -> None:
        """Print execution summary."""
        logger.info("=" * 60)
        logger.info("CALCULATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Stocks processed: {self.stats['stocks_processed']}")
        logger.info(f"Indicators calculated: {self.stats['indicators_calculated']}")
        logger.info(f"Records inserted: {self.stats['records_inserted']}")

        if self.stats['errors']:
            logger.warning(f"Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:5]:  # Show first 5 errors
                logger.warning(f"  - {error}")
        else:
            logger.info("✅ No errors!")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Calculate technical indicators")
    parser.add_argument('--ticker', nargs='+', help='Specific ticker(s) to process')
    args = parser.parse_args()

    tickers = [t.upper() for t in args.ticker] if args.ticker else None
    calculator = TechnicalIndicatorCalculator()
    calculator.process_all_stocks(tickers=tickers)


if __name__ == "__main__":
    main()
