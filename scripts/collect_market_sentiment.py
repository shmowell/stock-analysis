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

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yfinance as yf
from loguru import logger
from src.database import get_db_session
from src.database.models import MarketSentiment

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
        High bear spread → Contrarian bullish
        High bull spread → Contrarian bearish

        TODO: Implement one of:
        - Option A: Quandl/Nasdaq Data Link API (requires API key)
        - Option B: Web scraping from AAII.com
        - Option C: MacroMicro.me API

        Returns:
            Dict with aaii_bulls, aaii_bears, aaii_neutral, aaii_spread_8w, aaii_score
        """
        logger.warning("AAII sentiment collection not yet implemented")
        logger.info("Placeholder: Using neutral AAII sentiment (50.0)")

        # Placeholder data - will be replaced with real implementation
        return {
            'aaii_bulls': None,
            'aaii_bears': None,
            'aaii_neutral': None,
            'aaii_spread_8w': None,
            'aaii_score': 50.0  # Neutral placeholder
        }

    # ========================================================================
    # 3. Put/Call Ratio (MODERATE - CBOE/MacroMicro)
    # ========================================================================

    def collect_putcall_data(self) -> Optional[Dict]:
        """
        Collect CBOE Put/Call ratio data.

        Framework Section 5.1: Options sentiment indicator
        High Put/Call (fear) → Contrarian bullish
        Low Put/Call (greed) → Contrarian bearish

        TODO: Implement one of:
        - Option A: CBOE website scraping
        - Option B: MacroMicro.me API
        - Option C: Alternative data provider

        Returns:
            Dict with putcall_ratio, putcall_ma_10d, putcall_score
        """
        logger.warning("Put/Call ratio collection not yet implemented")
        logger.info("Placeholder: Using neutral Put/Call sentiment (50.0)")

        # Placeholder data - will be replaced with real implementation
        return {
            'putcall_ratio': None,
            'putcall_ma_10d': None,
            'putcall_score': 50.0  # Neutral placeholder
        }

    # ========================================================================
    # 4. Equity Fund Flows (COMPLEX - ICI/GitHub Dataset)
    # ========================================================================

    def collect_fund_flows_data(self) -> Optional[Dict]:
        """
        Collect equity fund flow data (weekly).

        Framework Section 5.1: Fund flows are DIRECTIONAL (not contrarian)
        Strong inflows → Score < 50 → Bearish (chasing)
        Strong outflows → Score > 50 → Bullish (capitulation)

        TODO: Implement one of:
        - Option A: ICI website (Investment Company Institute)
        - Option B: GitHub dataset (https://github.com/datasets/investor-flow-of-funds-us)
        - Option C: Nasdaq Data Link (ICI1)

        Returns:
            Dict with fund_flows_billions, fund_flows_zscore, fund_flows_score
        """
        logger.warning("Fund flows collection not yet implemented")
        logger.info("Placeholder: Using neutral fund flows sentiment (50.0)")

        # Placeholder data - will be replaced with real implementation
        return {
            'fund_flows_billions': None,
            'fund_flows_zscore': None,
            'fund_flows_score': 50.0  # Neutral placeholder
        }

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
        if market_data.get('vix_score'):
            logger.info(f"  VIX Score: {market_data['vix_score']:.2f}")
        logger.info(f"\nNext steps:")
        logger.info("  1. Implement AAII sentiment collection")
        logger.info("  2. Implement Put/Call ratio collection")
        logger.info("  3. Implement fund flows collection")
        logger.info("  4. Update sentiment calculator to use market sentiment")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
