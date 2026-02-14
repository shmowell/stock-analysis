"""
Test fundamental calculator with real data from database.

This script loads fundamental data and calculates scores to verify the calculator works correctly.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import logging
from typing import Dict, List
from sqlalchemy import select

from database import get_db_session
from database.models import FundamentalData
from calculators.fundamental import FundamentalCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_fundamental_data() -> Dict[str, Dict]:
    """
    Load fundamental data from database.

    Returns:
        Dict mapping ticker to fundamental metrics
    """
    data = {}

    with get_db_session() as session:
        stmt = select(FundamentalData).order_by(FundamentalData.ticker)
        results = session.execute(stmt).scalars().all()

        for record in results:
            data[record.ticker] = {
                # Valuation metrics
                'pe_ratio': float(record.pe_ratio) if record.pe_ratio else None,
                'pb_ratio': float(record.pb_ratio) if record.pb_ratio else None,
                'ps_ratio': float(record.ps_ratio) if record.ps_ratio else None,
                'ev_ebitda': float(record.ev_to_ebitda) if record.ev_to_ebitda else None,
                'dividend_yield': float(record.dividend_yield) if record.dividend_yield else None,

                # Quality metrics
                'roe': float(record.roe) if record.roe else None,
                'roa': float(record.roa) if record.roa else None,
                'net_margin': float(record.net_margin) if record.net_margin else None,
                'operating_margin': float(record.operating_margin) if record.operating_margin else None,
                'gross_margin': float(record.gross_margin) if record.gross_margin else None,

                # Growth metrics
                'revenue_growth': float(record.revenue_growth_yoy) if record.revenue_growth_yoy else None,
                'earnings_growth': float(record.eps_growth_yoy) if record.eps_growth_yoy else None,
            }

    logger.info(f"Loaded fundamental data for {len(data)} stocks")
    return data


def prepare_universe_metrics(stock_data: Dict[str, Dict]) -> Dict[str, List[float]]:
    """
    Prepare universe metrics for percentile ranking.

    Args:
        stock_data: Dict mapping ticker to metrics

    Returns:
        Dict mapping metric name to list of all universe values
    """
    universe = {}
    metrics = [
        'pe_ratio', 'pb_ratio', 'ps_ratio', 'ev_ebitda', 'dividend_yield',
        'roe', 'roa', 'net_margin', 'operating_margin', 'gross_margin',
        'revenue_growth', 'earnings_growth'
    ]

    for metric in metrics:
        values = [
            stock[metric]
            for stock in stock_data.values()
            if stock.get(metric) is not None
        ]
        if values:
            universe[metric] = values
            logger.debug(f"{metric}: {len(values)} stocks with data")

    return universe


def main():
    logger.info("=" * 80)
    logger.info("FUNDAMENTAL CALCULATOR TEST")
    logger.info("=" * 80)

    # Load data
    stock_data = load_fundamental_data()

    if not stock_data:
        logger.error("No fundamental data found in database")
        return

    # Prepare universe metrics
    universe = prepare_universe_metrics(stock_data)
    logger.info(f"Universe prepared with {len(universe)} metric types\n")

    # Initialize calculator
    calculator = FundamentalCalculator()

    # Calculate scores for each stock
    results = []

    for ticker, metrics in sorted(stock_data.items()):
        logger.info(f"Calculating scores for {ticker}...")

        # Calculate all scores (returns dict with value, quality, growth, fundamental)
        scores = calculator.calculate_fundamental_score(metrics, universe)

        results.append({
            'ticker': ticker,
            'value': scores.get('value_score'),
            'quality': scores.get('quality_score'),
            'growth': scores.get('growth_score'),
            'fundamental': scores.get('fundamental_score')
        })

        value = scores.get('value_score')
        quality = scores.get('quality_score')
        growth = scores.get('growth_score')
        fundamental = scores.get('fundamental_score')

        logger.info(
            f"  Value: {f'{value:.1f}' if value else 'N/A':>5} | "
            f"Quality: {f'{quality:.1f}' if quality else 'N/A':>5} | "
            f"Growth: {f'{growth:.1f}' if growth else 'N/A':>5} | "
            f"Fundamental: {f'{fundamental:.1f}' if fundamental else 'N/A':>5}"
        )

    # Print summary table
    print("\n" + "=" * 80)
    print("FUNDAMENTAL SCORES SUMMARY")
    print("=" * 80)
    print(f"{'Ticker':<8} {'Value':>8} {'Quality':>8} {'Growth':>8} {'Fundamental':>12}")
    print("-" * 80)

    for result in sorted(results, key=lambda x: x['fundamental'] or 0, reverse=True):
        val = result['value']
        qual = result['quality']
        grw = result['growth']
        fund = result['fundamental']

        print(
            f"{result['ticker']:<8} "
            f"{f'{val:.1f}' if val else 'N/A':>8} "
            f"{f'{qual:.1f}' if qual else 'N/A':>8} "
            f"{f'{grw:.1f}' if grw else 'N/A':>8} "
            f"{f'{fund:.1f}' if fund else 'N/A':>12}"
        )

    print("=" * 80)

    # Validation checks
    print("\nVALIDATION CHECKS:")
    scores_calculated = sum(1 for r in results if r['fundamental'] is not None)
    print(f"- Stocks with complete fundamental scores: {scores_calculated}/{len(results)}")

    if scores_calculated > 0:
        fund_scores = [r['fundamental'] for r in results if r['fundamental'] is not None]
        print(f"- Score range: {min(fund_scores):.1f} to {max(fund_scores):.1f}")
        print(f"- All scores in 0-100 range: {all(0 <= s <= 100 for s in fund_scores)}")

    logger.info("\nTest complete!")


if __name__ == '__main__':
    main()
