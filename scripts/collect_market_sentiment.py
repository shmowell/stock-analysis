"""
Market Sentiment Data Collection Script

Collects and scores 4 market-wide sentiment indicators:
1. VIX z-score (fear gauge - contrarian)
2. AAII Bull/Bear spread (investor sentiment - contrarian)
3. Put/Call ratio (options sentiment - contrarian)
4. Equity fund flows (directional)

Framework Reference: Section 5.1 (Market Sentiment - 40% of sentiment pillar)

Usage:
    python scripts/collect_market_sentiment.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import numpy as np
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import yfinance as yf
from dotenv import load_dotenv
from loguru import logger
from database import get_db_session
from database.models import MarketSentiment

# Load environment variables
load_dotenv(project_root / '.env')

# Configure logger
logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


class MarketSentimentCollector:
    """
    Collects market-wide sentiment data from multiple sources.

    Framework Section 5.1: Market sentiment indicators (40% of sentiment pillar)
    """

    def __init__(self):
        self.today = datetime.now().date()
        self.data_sources = []

    # ========================================================================
    # 1. VIX Z-Score (EASY - Yahoo Finance)
    # ========================================================================

    def collect_vix_data(self) -> Optional[Dict]:
        """
        Collect VIX data and calculate z-score.

        Framework Section 5.1: VIX measures market fear/volatility
        High VIX (fear) → Low score → Contrarian bullish
        Low VIX (complacency) → High score → Contrarian bearish

        Returns:
            Dict with vix_value, vix_mean_1y, vix_std_1y, vix_zscore, vix_score
        """
        logger.info("Collecting VIX data from Yahoo Finance...")

        try:
            vix = yf.Ticker("^VIX")

            # Get 1 year of history for z-score calculation
            vix_history = vix.history(period="1y")

            if vix_history.empty:
                logger.error("No VIX data returned from Yahoo Finance")
                return None

            # Get current VIX value (most recent close)
            current_vix = float(vix_history['Close'].iloc[-1])

            # Calculate 1-year statistics
            vix_mean = float(vix_history['Close'].mean())
            vix_std = float(vix_history['Close'].std())

            # Calculate z-score
            if vix_std == 0:
                logger.warning("VIX std deviation is 0, cannot calculate z-score")
                vix_zscore = 0.0
            else:
                vix_zscore = (current_vix - vix_mean) / vix_std

            # Calculate score (Framework Section 5.1)
            # Score = 50 + (Z × 15) [capped at 0-100]
            # High VIX (Z > 0) → Score > 50 → Bullish (contrarian)
            # Low VIX (Z < 0) → Score < 50 → Bearish (contrarian)
            vix_score = 50.0 + (vix_zscore * 15.0)
            vix_score = max(0.0, min(100.0, vix_score))  # Cap at 0-100

            logger.success(f"VIX data collected: current={current_vix:.2f}, mean={vix_mean:.2f}, "
                          f"std={vix_std:.2f}, z-score={vix_zscore:.2f}, score={vix_score:.2f}")

            self.data_sources.append("Yahoo Finance (VIX)")

            return {
                'vix_value': round(current_vix, 2),
                'vix_mean_1y': round(vix_mean, 2),
                'vix_std_1y': round(vix_std, 2),
                'vix_zscore': round(vix_zscore, 4),
                'vix_score': round(vix_score, 2)
            }

        except Exception as e:
            logger.error(f"Error collecting VIX data: {e}")
            return None

    # ========================================================================
    # 2. AAII Sentiment Survey (MODERATE - Scraping/API)
    # ========================================================================

    def collect_aaii_data(self) -> Optional[Dict]:
        """
        Collect AAII sentiment survey data (Bulls/Bears/Neutral).

        Framework Section 5.1: AAII survey measures retail investor sentiment
        Uses Nasdaq Data Link (formerly Quandl) AAII/AAII_SENTIMENT dataset.

        Scoring (contrarian - 8-week MA of Bears-Bulls spread):
        - Spread > 20: Score = 75 (extreme pessimism → bullish)
        - Spread 10-20: Score = 60
        - Spread -10 to 10: Score = 50 (neutral)
        - Spread -20 to -10: Score = 40
        - Spread < -20: Score = 25 (extreme optimism → bearish)

        Returns:
            Dict with aaii_bulls, aaii_bears, aaii_neutral, aaii_spread_8w, aaii_score
            None if data unavailable
        """
        api_key = os.getenv('NASDAQ_DATA_LINK_API_KEY')
        if not api_key:
            logger.warning("NASDAQ_DATA_LINK_API_KEY not set in .env, skipping AAII")
            return None

        logger.info("Collecting AAII sentiment data from Nasdaq Data Link...")

        try:
            import nasdaqdatalink
            nasdaqdatalink.ApiConfig.api_key = api_key

            # Fetch last 10 weeks of data (need 8 for MA calculation)
            start_date = (datetime.now() - timedelta(weeks=12)).strftime('%Y-%m-%d')
            data = nasdaqdatalink.get(
                'AAII/AAII_SENTIMENT',
                start_date=start_date
            )

            if data.empty:
                logger.error("No AAII data returned from Nasdaq Data Link")
                return None

            # Latest reading
            latest = data.iloc[-1]

            # AAII data comes as decimals (0.35 = 35%) or percentages
            # Check if values are > 1 (percentage) or < 1 (decimal)
            bulls_raw = float(latest.get('Bullish', 0))
            bears_raw = float(latest.get('Bearish', 0))
            neutral_raw = float(latest.get('Neutral', 0))

            # Normalize to percentages (0-100)
            if bulls_raw <= 1.0 and bears_raw <= 1.0:
                bulls = bulls_raw * 100
                bears = bears_raw * 100
                neutral = neutral_raw * 100
            else:
                bulls = bulls_raw
                bears = bears_raw
                neutral = neutral_raw

            # Calculate 8-week MA of Bear-Bull spread (Framework Section 5.1)
            # Spread = % Bears - % Bulls
            if 'Bullish' in data.columns and 'Bearish' in data.columns:
                bull_col = data['Bullish']
                bear_col = data['Bearish']
                if bull_col.iloc[0] <= 1.0:
                    bull_col = bull_col * 100
                    bear_col = bear_col * 100
                spread_series = bear_col - bull_col
                spread_8w = float(spread_series.tail(8).mean())
            else:
                spread_8w = bears - bulls

            # Score based on 8-week MA spread (Framework Section 5.1)
            if spread_8w > 20:
                aaii_score = 75.0  # Extreme pessimism → bullish
            elif spread_8w > 10:
                aaii_score = 60.0
            elif spread_8w >= -10:
                aaii_score = 50.0  # Neutral
            elif spread_8w >= -20:
                aaii_score = 40.0
            else:
                aaii_score = 25.0  # Extreme optimism → bearish

            logger.success(
                f"AAII data collected: Bulls={bulls:.1f}%, Bears={bears:.1f}%, "
                f"Neutral={neutral:.1f}%, 8w Spread={spread_8w:.1f}, Score={aaii_score:.1f}"
            )

            self.data_sources.append("Nasdaq Data Link (AAII)")

            return {
                'aaii_bulls': round(bulls, 2),
                'aaii_bears': round(bears, 2),
                'aaii_neutral': round(neutral, 2),
                'aaii_spread_8w': round(spread_8w, 2),
                'aaii_score': round(aaii_score, 2)
            }

        except Exception as e:
            logger.error(f"Error collecting AAII data: {e}")
            return None

    # ========================================================================
    # 3. Put/Call Ratio (MODERATE - CBOE/MacroMicro)
    # ========================================================================

    def collect_putcall_data(self) -> Optional[Dict]:
        """
        Collect Put/Call ratio using SPY/QQQ/IWM options chain data.

        Framework Section 5.1: Options sentiment indicator (contrarian)
        Uses yfinance to compute aggregate put/call volume ratio from
        the most liquid equity ETF options as a proxy for CBOE equity P/C.

        Scoring (10-day MA, but uses raw ratio until history accumulates):
        - P/C > 1.0: Score = 70 (fear → bullish)
        - P/C 0.8-1.0: Score = 55
        - P/C 0.6-0.8: Score = 45
        - P/C < 0.6: Score = 30 (greed → bearish)

        Returns:
            Dict with putcall_ratio, putcall_ma_10d, putcall_score
            None if data unavailable
        """
        logger.info("Collecting Put/Call ratio from options chain data (SPY/QQQ/IWM)...")

        try:
            total_put_volume = 0
            total_call_volume = 0
            etfs_processed = []

            for ticker_symbol in ['SPY', 'QQQ', 'IWM']:
                try:
                    ticker = yf.Ticker(ticker_symbol)
                    expirations = ticker.options

                    if not expirations:
                        logger.warning(f"No options data for {ticker_symbol}")
                        continue

                    # Use nearest 3 expirations for a representative sample
                    for exp_date in expirations[:3]:
                        chain = ticker.option_chain(exp_date)
                        put_vol = chain.puts['volume'].sum()
                        call_vol = chain.calls['volume'].sum()

                        # Handle NaN volumes
                        if pd.isna(put_vol):
                            put_vol = 0
                        if pd.isna(call_vol):
                            call_vol = 0

                        total_put_volume += int(put_vol)
                        total_call_volume += int(call_vol)

                    etfs_processed.append(ticker_symbol)

                except Exception as e:
                    logger.warning(f"Error fetching options for {ticker_symbol}: {e}")
                    continue

            if not etfs_processed or total_call_volume == 0:
                logger.error("No valid options data collected")
                return None

            # Calculate aggregate put/call ratio
            putcall_ratio = total_put_volume / total_call_volume

            # For 10-day MA: check database for historical readings
            # If insufficient history, use raw ratio
            putcall_ma_10d = self._get_putcall_ma_10d(putcall_ratio)

            # Score based on 10-day MA (or raw ratio if no history)
            scoring_ratio = putcall_ma_10d if putcall_ma_10d is not None else putcall_ratio

            # Framework Section 5.1: Contrarian scoring
            if scoring_ratio > 1.0:
                putcall_score = 70.0  # Fear → bullish
            elif scoring_ratio > 0.8:
                putcall_score = 55.0
            elif scoring_ratio > 0.6:
                putcall_score = 45.0
            else:
                putcall_score = 30.0  # Greed → bearish

            logger.success(
                f"Put/Call data collected from {', '.join(etfs_processed)}: "
                f"ratio={putcall_ratio:.3f}, 10d MA={putcall_ma_10d or 'N/A'}, "
                f"score={putcall_score:.1f}"
            )

            self.data_sources.append(f"yfinance Options ({', '.join(etfs_processed)})")

            return {
                'putcall_ratio': round(putcall_ratio, 4),
                'putcall_ma_10d': round(putcall_ma_10d, 4) if putcall_ma_10d else None,
                'putcall_score': round(putcall_score, 2)
            }

        except Exception as e:
            logger.error(f"Error collecting Put/Call data: {e}")
            return None

    def _get_putcall_ma_10d(self, current_ratio: float) -> Optional[float]:
        """
        Calculate 10-day moving average of Put/Call ratio from stored history.

        Returns None if insufficient history (< 5 readings).
        """
        try:
            with get_db_session() as session:
                # Get last 10 days of Put/Call data from database
                recent = session.query(MarketSentiment.putcall_ratio).filter(
                    MarketSentiment.putcall_ratio.isnot(None)
                ).order_by(MarketSentiment.date.desc()).limit(9).all()

                ratios = [float(r[0]) for r in recent if r[0] is not None]
                ratios.insert(0, current_ratio)  # Add today's reading

                if len(ratios) < 5:
                    logger.debug(
                        f"Only {len(ratios)} P/C readings, need 5+ for MA. "
                        f"Using raw ratio."
                    )
                    return None

                ma_10d = float(np.mean(ratios[:10]))
                return ma_10d

        except Exception as e:
            logger.debug(f"Could not calculate P/C 10d MA: {e}")
            return None

    # ========================================================================
    # 4. Equity Fund Flows (COMPLEX - ICI/GitHub Dataset)
    # ========================================================================

    def collect_fund_flows_data(self) -> Optional[Dict]:
        """
        Collect equity fund flow data from DataHub.io (ICI dataset).

        Framework Section 5.1: Fund flows are DIRECTIONAL (not contrarian)
        Strong inflows → Score < 50 → Bearish (chasing returns)
        Strong outflows → Score > 50 → Bullish (capitulation)

        Data source: DataHub.io mirror of ICI monthly net equity fund flows.
        Uses z-score against trailing 12 months to classify flow strength.

        Returns:
            Dict with fund_flows_billions, fund_flows_zscore, fund_flows_score
            None if data unavailable
        """
        logger.info("Collecting equity fund flow data from DataHub.io (ICI)...")

        MONTHLY_URL = (
            "https://r2.datahub.io/cm20e8rbw0005l30ch82su75o/main/raw/data/monthly.csv"
        )

        try:
            df = pd.read_csv(MONTHLY_URL, parse_dates=['Date'])

            if df.empty:
                logger.error("No fund flow data returned from DataHub.io")
                return None

            # Use 'Total Equity' column (net new cash flow in millions USD)
            if 'Total Equity' not in df.columns:
                logger.error(f"Expected 'Total Equity' column not found. Columns: {df.columns.tolist()}")
                return None

            # Sort by date and drop NaN values
            df = df.sort_values('Date').dropna(subset=['Total Equity'])

            if len(df) < 12:
                logger.error(f"Insufficient fund flow data: {len(df)} months (need 12+)")
                return None

            # Latest reading (in millions USD)
            latest_flow = float(df['Total Equity'].iloc[-1])
            latest_flow_billions = latest_flow / 1000  # Convert to billions

            # Calculate z-score against trailing 12 months
            trailing_12m = df['Total Equity'].tail(12)
            flow_mean = float(trailing_12m.mean())
            flow_std = float(trailing_12m.std())

            if flow_std == 0:
                fund_flows_zscore = 0.0
            else:
                fund_flows_zscore = (latest_flow - flow_mean) / flow_std

            # Scoring: DIRECTIONAL (not contrarian like other indicators)
            # Framework Section 5.1:
            # Strong inflows (z > 1.0) → Score = 30 (chasing → bearish)
            # Moderate inflows (z 0.25-1.0) → Score = 40
            # Neutral (z -0.25 to 0.25) → Score = 50
            # Moderate outflows (z -1.0 to -0.25) → Score = 60
            # Strong outflows (z < -1.0) → Score = 70 (capitulation → bullish)
            if fund_flows_zscore > 1.0:
                fund_flows_score = 30.0  # Strong inflows → bearish
            elif fund_flows_zscore > 0.25:
                fund_flows_score = 40.0
            elif fund_flows_zscore >= -0.25:
                fund_flows_score = 50.0  # Neutral
            elif fund_flows_zscore >= -1.0:
                fund_flows_score = 60.0
            else:
                fund_flows_score = 70.0  # Strong outflows → bullish

            latest_date = df['Date'].iloc[-1].strftime('%Y-%m-%d')
            logger.success(
                f"Fund flow data collected (latest: {latest_date}): "
                f"flow={latest_flow_billions:+.2f}B, z-score={fund_flows_zscore:.2f}, "
                f"score={fund_flows_score:.1f}"
            )

            self.data_sources.append("DataHub.io (ICI Fund Flows)")

            return {
                'fund_flows_billions': round(latest_flow_billions, 2),
                'fund_flows_zscore': round(fund_flows_zscore, 4),
                'fund_flows_score': round(fund_flows_score, 2)
            }

        except Exception as e:
            logger.error(f"Error collecting fund flow data: {e}")
            return None

    # ========================================================================
    # Composite Market Sentiment Score
    # ========================================================================

    def calculate_market_sentiment_score(
        self,
        vix_score: Optional[float],
        aaii_score: Optional[float],
        putcall_score: Optional[float],
        fund_flows_score: Optional[float]
    ) -> Tuple[float, int]:
        """
        Calculate composite market sentiment score from available indicators.

        Framework Section 5.1: Average of 4 indicators (equal weight)
        If <2 indicators available, return neutral 50.0

        Args:
            vix_score: VIX z-score (0-100)
            aaii_score: AAII sentiment (0-100)
            putcall_score: Put/Call ratio (0-100)
            fund_flows_score: Fund flows (0-100)

        Returns:
            Tuple of (composite_score, num_indicators_available)
        """
        scores = []

        if vix_score is not None:
            scores.append(vix_score)
        if aaii_score is not None:
            scores.append(aaii_score)
        if putcall_score is not None:
            scores.append(putcall_score)
        if fund_flows_score is not None:
            scores.append(fund_flows_score)

        num_indicators = len(scores)

        if num_indicators < 2:
            logger.warning(f"Only {num_indicators} indicator(s) available. Using neutral 50.0")
            return 50.0, num_indicators

        composite_score = float(np.mean(scores))

        logger.info(f"Market sentiment score: {composite_score:.2f} "
                   f"(from {num_indicators} indicators)")

        return round(composite_score, 2), num_indicators

    # ========================================================================
    # Main Collection Method
    # ========================================================================

    def collect_all_data(self) -> Optional[Dict]:
        """
        Collect all market sentiment indicators and calculate composite score.

        Returns:
            Dict with all market sentiment data ready for database insertion
        """
        logger.info("=" * 70)
        logger.info("Market Sentiment Data Collection")
        logger.info(f"Date: {self.today}")
        logger.info("=" * 70)

        # Collect each indicator
        vix_data = self.collect_vix_data()
        aaii_data = self.collect_aaii_data()
        putcall_data = self.collect_putcall_data()
        fund_flows_data = self.collect_fund_flows_data()

        # Extract scores (handle None values)
        vix_score = vix_data.get('vix_score') if vix_data else None
        aaii_score = aaii_data.get('aaii_score') if aaii_data else None
        putcall_score = putcall_data.get('putcall_score') if putcall_data else None
        fund_flows_score = fund_flows_data.get('fund_flows_score') if fund_flows_data else None

        # Calculate composite score
        composite_score, num_indicators = self.calculate_market_sentiment_score(
            vix_score, aaii_score, putcall_score, fund_flows_score
        )

        # Combine all data
        market_data = {
            'date': self.today,
            'market_sentiment_score': composite_score,
            'num_indicators_available': num_indicators,
            'data_source': ', '.join(self.data_sources) if self.data_sources else 'None',
        }

        # Add VIX data
        if vix_data:
            market_data.update(vix_data)

        # Add AAII data
        if aaii_data:
            market_data.update(aaii_data)

        # Add Put/Call data
        if putcall_data:
            market_data.update(putcall_data)

        # Add Fund Flows data
        if fund_flows_data:
            market_data.update(fund_flows_data)

        return market_data

    # ========================================================================
    # Database Storage
    # ========================================================================

    def store_to_database(self, market_data: Dict) -> bool:
        """
        Store market sentiment data to database.

        Args:
            market_data: Dict containing all market sentiment data

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Storing market sentiment data to database for {market_data['date']}")

        try:
            with get_db_session() as session:
                # Check if record already exists for this date
                existing = session.query(MarketSentiment).filter_by(
                    date=market_data['date']
                ).first()

                if existing:
                    logger.warning(f"Market sentiment data already exists for {market_data['date']}")
                    logger.info("Updating existing record...")

                    # Update existing record
                    for key, value in market_data.items():
                        if key != 'date':  # Don't update the date field
                            setattr(existing, key, value)

                    existing.updated_at = datetime.now()

                else:
                    # Create new record
                    sentiment_record = MarketSentiment(**market_data)
                    session.add(sentiment_record)

                session.commit()
                logger.success("Market sentiment data stored successfully!")
                return True

        except Exception as e:
            logger.error(f"Error storing market sentiment data: {e}")
            return False


def main():
    """Main execution function"""
    collector = MarketSentimentCollector()

    # Collect all market sentiment data
    market_data = collector.collect_all_data()

    if not market_data:
        logger.error("Failed to collect market sentiment data")
        return False

    # Store to database
    success = collector.store_to_database(market_data)

    if success:
        logger.info("=" * 70)
        logger.success("Market Sentiment Collection Complete!")
        logger.info("=" * 70)
        logger.info("\nSummary:")
        logger.info(f"  Date: {market_data['date']}")
        logger.info(f"  Market Sentiment Score: {market_data['market_sentiment_score']:.2f}")
        logger.info(f"  Indicators Available: {market_data['num_indicators_available']}/4")
        if market_data.get('vix_score') is not None:
            logger.info(f"  VIX Score: {market_data['vix_score']:.2f}")
        if market_data.get('aaii_score') is not None:
            logger.info(f"  AAII Score: {market_data['aaii_score']:.2f}")
        if market_data.get('putcall_score') is not None:
            logger.info(f"  Put/Call Score: {market_data['putcall_score']:.2f}")
        if market_data.get('fund_flows_score') is not None:
            logger.info(f"  Fund Flows Score: {market_data['fund_flows_score']:.2f}")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
