"""
Test technical calculator with real data from database.

Framework Reference: Section 4 (Technical Score)
Purpose: Verify technical score calculations work correctly with actual data
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from typing import Dict, List
from sqlalchemy import select, text

from src.database import get_db_session
from src.database.models import Stock, PriceData
from src.calculators.technical import TechnicalCalculator, extract_technical_metrics_from_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_current_price(ticker: str) -> float:
    """Get most recent closing price for a ticker."""
    with get_db_session() as session:
        stmt = select(PriceData).where(
            PriceData.ticker == ticker
        ).order_by(PriceData.date.desc()).limit(1)

        result = session.execute(stmt)
        price_row = result.scalar_one_or_none()

        if price_row:
            return float(price_row.close)
        return None


def get_technical_indicators(ticker: str):
    """Get latest technical indicators for a ticker using raw SQL."""
    with get_db_session() as session:
        # Use raw SQL since ORM model doesn't match database schema
        sql = text("""
            SELECT *
            FROM technical_indicators
            WHERE ticker = :ticker
            ORDER BY calculation_date DESC
            LIMIT 1
        """)

        result = session.execute(sql, {'ticker': ticker})
        row = result.fetchone()

        return row


def calculate_sector_return_6m(sector: str) -> float:
    """Calculate average 6-month return for a sector."""
    with get_db_session() as session:
        sql = text("""
            SELECT AVG(ti.momentum_6m) as sector_return
            FROM technical_indicators ti
            JOIN stocks s ON ti.ticker = s.ticker
            WHERE s.sector = :sector
            AND ti.momentum_6m IS NOT NULL
        """)

        result = session.execute(sql, {'sector': sector})
        row = result.fetchone()

        if row and row[0]:
            return float(row[0])
        return None


def get_all_stocks() -> List[tuple]:
    """Get all active stocks with their sectors."""
    with get_db_session() as session:
        stmt = select(Stock.ticker, Stock.company_name, Stock.sector).where(
            Stock.is_active == True
        )
        result = session.execute(stmt)
        return result.all()


def build_universe_metrics() -> Dict[str, List[float]]:
    """Build universe-wide metrics for percentile ranking."""
    universe_metrics = {
        'return_12_1_month': [],
        'mad': [],
        'relative_strength_spread': [],
    }

    stocks = get_all_stocks()

    for ticker, _, sector in stocks:
        indicator_row = get_technical_indicators(ticker)
        if not indicator_row:
            continue

        current_price = get_current_price(ticker)
        if not current_price:
            continue

        sector_return_6m = calculate_sector_return_6m(sector)

        # Extract metrics
        metrics = extract_technical_metrics_from_db(
            indicator_row,
            current_price,
            sector_return_6m
        )

        # Add to universe lists (only if not None)
        if metrics['return_12_1_month'] is not None:
            universe_metrics['return_12_1_month'].append(metrics['return_12_1_month'])

        if metrics['mad'] is not None:
            universe_metrics['mad'].append(metrics['mad'])

        if metrics['relative_strength_spread'] is not None:
            universe_metrics['relative_strength_spread'].append(metrics['relative_strength_spread'])

    return universe_metrics


def test_technical_calculator():
    """Test technical calculator with real data."""
    logger.info("=" * 60)
    logger.info("TESTING TECHNICAL CALCULATOR")
    logger.info("=" * 60)

    # Initialize calculator
    calculator = TechnicalCalculator()

    # Build universe metrics for percentile ranking
    logger.info("\nBuilding universe metrics...")
    universe_metrics = build_universe_metrics()

    logger.info(f"Universe metrics collected:")
    logger.info(f"  - 12-1M returns: {len(universe_metrics['return_12_1_month'])} stocks")
    logger.info(f"  - MAD values: {len(universe_metrics['mad'])} stocks")
    logger.info(f"  - Relative strength: {len(universe_metrics['relative_strength_spread'])} stocks")

    # Get all stocks
    stocks = get_all_stocks()

    logger.info(f"\nTesting calculator on {len(stocks)} stocks:")
    logger.info("=" * 60)

    successful = 0
    failed = 0

    for ticker, company_name, sector in stocks:
        try:
            # Get technical indicators
            indicator_row = get_technical_indicators(ticker)
            if not indicator_row:
                logger.warning(f"{ticker}: No technical indicators found")
                failed += 1
                continue

            # Get current price
            current_price = get_current_price(ticker)
            if not current_price:
                logger.warning(f"{ticker}: No current price found")
                failed += 1
                continue

            # Get sector return
            sector_return_6m = calculate_sector_return_6m(sector)

            # Extract metrics
            stock_metrics = extract_technical_metrics_from_db(
                indicator_row,
                current_price,
                sector_return_6m
            )

            # Calculate technical score
            scores = calculator.calculate_technical_score(stock_metrics, universe_metrics)

            # Display results (format None values properly)
            def format_score(score):
                return f"{score:.1f}" if score is not None else "N/A"

            logger.info(f"\n{ticker} ({company_name}) - Sector: {sector}")
            logger.info(f"  Component Scores:")
            logger.info(f"    Momentum:          {format_score(scores['momentum_score'])}")
            logger.info(f"    Trend:             {format_score(scores['trend_score'])}")
            logger.info(f"    Volume-Qualified:  {format_score(scores['volume_qualified_score'])}")
            logger.info(f"    Relative Strength: {format_score(scores['relative_strength_score'])}")
            logger.info(f"    RSI:               {format_score(scores['rsi_score'])}")
            logger.info(f"    Multi-Speed:       {format_score(scores['multi_speed_score'])}")
            logger.info(f"  TECHNICAL SCORE:   {format_score(scores['technical_score'])}")

            if scores['technical_score'] is not None:
                successful += 1
            else:
                failed += 1

        except Exception as e:
            logger.error(f"{ticker}: Error calculating technical score: {e}")
            failed += 1
            continue

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total stocks tested: {len(stocks)}")
    logger.info(f"Successful calculations: {successful}")
    logger.info(f"Failed calculations: {failed}")
    logger.info(f"Success rate: {successful / len(stocks) * 100:.1f}%")

    if successful == len(stocks):
        logger.info("\n✅ All technical scores calculated successfully!")
    elif successful > 0:
        logger.info(f"\n⚠️  {failed} stocks failed to calculate")
    else:
        logger.error("\n❌ All calculations failed!")


def main():
    """Main execution function."""
    test_technical_calculator()


if __name__ == "__main__":
    main()
