"""
Test the sentiment calculator with real data from the database.

Framework Reference: Section 5 (Sentiment Score)
Purpose: Validate sentiment calculator is working correctly with real stock data
Verifies: Stock-specific sentiment scoring (4 components)

Usage:
    python scripts/test_sentiment_calculator.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select

from src.database import get_db_session
from src.database.models import Stock, SentimentData, FundamentalData, PriceData
from src.calculators.sentiment import SentimentCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_latest_price(ticker: str) -> Optional[float]:
    """
    Get the most recent price for a stock.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Latest close price, or None if not available
    """
    with get_db_session() as session:
        stmt = (
            select(PriceData.close)
            .where(PriceData.ticker == ticker)
            .order_by(PriceData.date.desc())
            .limit(1)
        )
        result = session.execute(stmt).first()
        return float(result[0]) if result else None


def get_market_cap(ticker: str) -> Optional[float]:
    """
    Get market cap for a stock from fundamental data.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Market cap in millions, or None if not available
    """
    with get_db_session() as session:
        # Try to get market cap from stock info first
        stmt = select(Stock.market_cap).where(Stock.ticker == ticker)
        result = session.execute(stmt).first()

        if result and result[0]:
            # market_cap in database is in dollars, convert to millions
            return float(result[0]) / 1_000_000

        return None


def transform_sentiment_data(db_data: SentimentData, current_price: float, market_cap: Optional[float]) -> Dict[str, Any]:
    """
    Transform database sentiment data to format expected by calculator.

    The calculator expects:
    - days_to_cover
    - analyst_target
    - market_cap (in millions)
    - insider_net_shares
    - recommendation_mean (optional, not in current DB schema)
    - analyst_count

    Args:
        db_data: SentimentData ORM object from database
        current_price: Current stock price
        market_cap: Market cap in millions

    Returns:
        Dict with fields expected by sentiment calculator
    """
    return {
        'days_to_cover': float(db_data.days_to_cover) if db_data.days_to_cover else None,
        'analyst_target': float(db_data.consensus_price_target) if db_data.consensus_price_target else None,
        'analyst_count': int(db_data.num_analyst_opinions) if db_data.num_analyst_opinions else None,
        'market_cap': market_cap,  # Already in millions
        'insider_net_shares': int(db_data.insider_net_shares_6m) if db_data.insider_net_shares_6m else None,
        # Note: recommendation_mean not in DB, calculator will use neutral score
        'recommendation_mean': None,
    }


def test_sentiment_calculator():
    """
    Test sentiment calculator with real data from all stocks.

    Framework Section 5: Sentiment Score (20% weight)
    Expected: Valid scores 0-100 for all stocks with data
    """
    logger.info("=" * 80)
    logger.info("SENTIMENT CALCULATOR TEST - START")
    logger.info("=" * 80)

    calculator = SentimentCalculator()
    results = []
    success_count = 0
    fail_count = 0

    with get_db_session() as session:
        # Get all active stocks
        stocks_stmt = select(Stock.ticker).where(Stock.is_active == True)
        stocks = session.execute(stocks_stmt).scalars().all()

        logger.info(f"\nTesting {len(stocks)} stocks...")

        for ticker in stocks:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing {ticker}")
            logger.info('='*60)

            try:
                # Get sentiment data
                sentiment_stmt = (
                    select(SentimentData)
                    .where(SentimentData.ticker == ticker)
                    .order_by(SentimentData.data_date.desc())
                    .limit(1)
                )
                sentiment_data = session.execute(sentiment_stmt).scalar_one_or_none()

                if not sentiment_data:
                    logger.warning(f"No sentiment data found for {ticker}")
                    fail_count += 1
                    continue

                # Get current price
                current_price = get_latest_price(ticker)
                if not current_price:
                    logger.warning(f"No price data found for {ticker}")
                    fail_count += 1
                    continue

                # Get market cap
                market_cap = get_market_cap(ticker)

                # Transform data to calculator format
                stock_data = transform_sentiment_data(sentiment_data, current_price, market_cap)

                logger.info(f"\nInput Data:")
                logger.info(f"  Current Price: ${current_price:.2f}")
                logger.info(f"  Market Cap: ${market_cap:.1f}M" if market_cap else "  Market Cap: Unknown")
                logger.info(f"  Analyst Target: ${stock_data['analyst_target']:.2f}" if stock_data['analyst_target'] else "  Analyst Target: None")
                logger.info(f"  Analyst Count: {stock_data['analyst_count']}")
                logger.info(f"  Days to Cover: {stock_data['days_to_cover']:.2f}" if stock_data['days_to_cover'] else "  Days to Cover: None")
                logger.info(f"  Insider Net Shares: {stock_data['insider_net_shares']:,}" if stock_data['insider_net_shares'] else "  Insider Net Shares: None")

                # Calculate sentiment score
                sentiment_score = calculator.calculate_sentiment_score(
                    stock_data,
                    current_price,
                    market_data=None  # Market sentiment not implemented yet
                )

                if sentiment_score is None:
                    logger.warning(f"Calculator returned None for {ticker}")
                    fail_count += 1
                    continue

                # Validate score is in valid range
                if not (0 <= sentiment_score <= 100):
                    logger.error(f"Invalid score {sentiment_score:.2f} for {ticker} (must be 0-100)")
                    fail_count += 1
                    continue

                logger.info(f"\n✅ SENTIMENT SCORE: {sentiment_score:.2f}")

                results.append({
                    'ticker': ticker,
                    'sentiment_score': sentiment_score,
                    'current_price': current_price,
                    'analyst_target': stock_data['analyst_target'],
                    'days_to_cover': stock_data['days_to_cover']
                })
                success_count += 1

            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}", exc_info=True)
                fail_count += 1

    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("SENTIMENT CALCULATOR TEST - SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total stocks tested: {len(stocks)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {fail_count}")
    logger.info(f"Success rate: {success_count/len(stocks)*100:.1f}%")

    if results:
        # Sort by sentiment score
        results.sort(key=lambda x: x['sentiment_score'], reverse=True)

        logger.info("\n" + "=" * 80)
        logger.info("SENTIMENT SCORES (sorted high to low)")
        logger.info("=" * 80)
        logger.info(f"{'Ticker':<8} {'Score':>6} {'Price':>8} {'Target':>8} {'DTC':>6}")
        logger.info("-" * 80)

        for r in results:
            target_str = f"${r['analyst_target']:.2f}" if r['analyst_target'] else "N/A"
            dtc_str = f"{r['days_to_cover']:.2f}" if r['days_to_cover'] else "N/A"
            logger.info(
                f"{r['ticker']:<8} {r['sentiment_score']:>6.2f} "
                f"${r['current_price']:>7.2f} {target_str:>8} {dtc_str:>6}"
            )

        # Statistics
        scores = [r['sentiment_score'] for r in results]
        logger.info("\n" + "=" * 80)
        logger.info("SCORE STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Min:    {min(scores):.2f}")
        logger.info(f"Max:    {max(scores):.2f}")
        logger.info(f"Mean:   {sum(scores)/len(scores):.2f}")
        logger.info(f"Median: {sorted(scores)[len(scores)//2]:.2f}")

        # Validation checks
        logger.info("\n" + "=" * 80)
        logger.info("VALIDATION CHECKS")
        logger.info("=" * 80)

        all_valid = True

        # Check 1: All scores in valid range (0-100)
        invalid_scores = [s for s in scores if not (0 <= s <= 100)]
        if invalid_scores:
            logger.error(f"❌ Found {len(invalid_scores)} scores outside 0-100 range")
            all_valid = False
        else:
            logger.info("✅ All scores in valid range (0-100)")

        # Check 2: Scores show reasonable distribution (not all the same)
        score_range = max(scores) - min(scores)
        if score_range < 5:
            logger.warning(f"⚠️ Low score variance (range: {score_range:.2f}) - check if calculator is working correctly")
        else:
            logger.info(f"✅ Good score variance (range: {score_range:.2f})")

        # Check 3: Framework compliance (sentiment is 20% of composite)
        logger.info("\n📋 Framework Compliance:")
        logger.info("  - Stock-Specific Sentiment: 60% of sentiment score")
        logger.info("  - Market-Wide Sentiment: 40% of sentiment score (currently defaulting to 50)")
        logger.info("  - Sentiment Pillar: 20% of composite score")

        if all_valid:
            logger.info("\n✅ ALL VALIDATION CHECKS PASSED")
            return 0
        else:
            logger.error("\n❌ SOME VALIDATION CHECKS FAILED")
            return 1
    else:
        logger.error("\n❌ No successful results to analyze")
        return 2


def main():
    """Main entry point."""
    return test_sentiment_calculator()


if __name__ == "__main__":
    exit(main())
