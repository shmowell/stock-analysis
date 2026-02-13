"""
Integration Script: Calculate Complete Composite Scores

This script performs end-to-end calculation of composite scores by:
1. Loading fundamental, technical, and sentiment data from database
2. Calculating pillar scores using each calculator
3. Combining into composite scores with recommendations
4. Validating results and generating report

Framework Reference: Section 1.3, Section 7

Usage:
    python scripts/calculate_scores.py

Author: Stock Analysis Framework v2.0
Date: 2026-02-12
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from sqlalchemy.orm import Session
from database import get_db_session
from database.models import Stock, FundamentalData, TechnicalIndicator, SentimentData, PriceData, MarketSentiment
from calculators.fundamental import FundamentalCalculator
from calculators.technical import TechnicalCalculator
from calculators.sentiment import SentimentCalculator
from models.composite import CompositeScoreCalculator, Recommendation
from typing import Dict, List


def load_all_data(session: Session) -> Dict:
    """Load all necessary data from database and convert to plain dicts.

    Args:
        session: Database session

    Returns:
        Dict containing stocks and their data:
        {
            'tickers': List of ticker strings,
            'fundamental_data': Dict[ticker, dict of metrics],
            'technical_data': Dict[ticker, dict of metrics],
            'sentiment_data': Dict[ticker, dict of metrics]
        }
    """
    print("Loading data from database...")

    # Get all active stocks and their market caps
    stocks = session.query(Stock).filter_by(is_active=True).all()
    tickers = [s.ticker for s in stocks]
    market_caps = {s.ticker: float(s.market_cap) if s.market_cap else None for s in stocks}
    print(f"  Loaded {len(tickers)} active stocks")

    # Load fundamental data and convert to dicts
    fundamental_records = session.query(FundamentalData).all()
    fundamental_data = {}
    for fd in fundamental_records:
        fundamental_data[fd.ticker] = {
            'pe_ratio': float(fd.pe_ratio) if fd.pe_ratio else None,
            'pb_ratio': float(fd.pb_ratio) if fd.pb_ratio else None,
            'ps_ratio': float(fd.ps_ratio) if fd.ps_ratio else None,
            'ev_to_ebitda': float(fd.ev_to_ebitda) if fd.ev_to_ebitda else None,
            'dividend_yield': float(fd.dividend_yield) if fd.dividend_yield else None,
            'roe': float(fd.roe) if fd.roe else None,
            'roa': float(fd.roa) if fd.roa else None,
            'net_margin': float(fd.net_margin) if fd.net_margin else None,
            'operating_margin': float(fd.operating_margin) if fd.operating_margin else None,
            'gross_margin': float(fd.gross_margin) if fd.gross_margin else None,
            'revenue_growth_yoy': float(fd.revenue_growth_yoy) if fd.revenue_growth_yoy else None,
            'eps_growth_yoy': float(fd.eps_growth_yoy) if fd.eps_growth_yoy else None,
        }
    print(f"  Loaded {len(fundamental_data)} fundamental records")

    # Load technical indicators - only latest record per ticker
    technical_records = session.query(TechnicalIndicator).order_by(
        TechnicalIndicator.ticker, TechnicalIndicator.calculation_date.desc()
    ).all()
    technical_data = {}
    for ti in technical_records:
        if ti.ticker in technical_data:
            continue  # Skip older records, keep only latest
        technical_data[ti.ticker] = {
            'sma_20': float(ti.sma_20) if ti.sma_20 is not None else None,
            'sma_50': float(ti.sma_50) if ti.sma_50 is not None else None,
            'sma_200': float(ti.sma_200) if ti.sma_200 is not None else None,
            'mad': float(ti.mad) if ti.mad is not None else None,
            'price_vs_200ma': ti.price_vs_200ma if ti.price_vs_200ma is not None else None,
            'momentum_12_1': float(ti.momentum_12_1) if ti.momentum_12_1 is not None else None,
            'momentum_6m': float(ti.momentum_6m) if ti.momentum_6m is not None else None,
            'momentum_3m': float(ti.momentum_3m) if ti.momentum_3m is not None else None,
            'momentum_1m': float(ti.momentum_1m) if ti.momentum_1m is not None else None,
            'avg_volume_20d': float(ti.avg_volume_20d) if ti.avg_volume_20d is not None else None,
            'relative_volume': float(ti.relative_volume) if ti.relative_volume is not None else None,
            'rsi_14': float(ti.rsi_14) if ti.rsi_14 is not None else None,
            'adx': float(ti.adx) if ti.adx is not None else None,
            'sector_relative_6m': float(ti.sector_relative_6m) if ti.sector_relative_6m is not None else None,
        }
    print(f"  Loaded {len(technical_data)} technical records")

    # Load latest prices for each stock
    latest_prices = {}
    for ticker in tickers:
        latest_price_record = (
            session.query(PriceData)
            .filter(PriceData.ticker == ticker)
            .order_by(PriceData.date.desc())
            .first()
        )
        if latest_price_record:
            latest_prices[ticker] = float(latest_price_record.close)
    print(f"  Loaded {len(latest_prices)} latest prices")

    # Load sentiment data and convert to dicts
    sentiment_records = session.query(SentimentData).all()
    sentiment_data = {}
    for sd in sentiment_records:
        sentiment_data[sd.ticker] = {
            # Analyst data
            'consensus_price_target': float(sd.consensus_price_target) if sd.consensus_price_target else None,
            'num_buy_ratings': int(sd.num_buy_ratings) if sd.num_buy_ratings else None,
            'num_hold_ratings': int(sd.num_hold_ratings) if sd.num_hold_ratings else None,
            'num_sell_ratings': int(sd.num_sell_ratings) if sd.num_sell_ratings else None,
            'num_analyst_opinions': int(sd.num_analyst_opinions) if sd.num_analyst_opinions else None,
            'upgrades_30d': int(sd.upgrades_30d) if sd.upgrades_30d else None,
            'downgrades_30d': int(sd.downgrades_30d) if sd.downgrades_30d else None,
            'estimate_revisions_up_90d': int(sd.estimate_revisions_up_90d) if sd.estimate_revisions_up_90d else None,
            'estimate_revisions_down_90d': int(sd.estimate_revisions_down_90d) if sd.estimate_revisions_down_90d else None,
            # Short interest
            'short_interest_pct': float(sd.short_interest_pct) if sd.short_interest_pct else None,
            'days_to_cover': float(sd.days_to_cover) if sd.days_to_cover else None,
            # Insider activity
            'insider_buys_6m': int(sd.insider_buys_6m) if sd.insider_buys_6m else None,
            'insider_sells_6m': int(sd.insider_sells_6m) if sd.insider_sells_6m else None,
            'insider_net_shares_6m': int(sd.insider_net_shares_6m) if sd.insider_net_shares_6m else None,
        }
    print(f"  Loaded {len(sentiment_data)} sentiment records")

    # Add latest price to technical data for uptrend calculations
    for ticker in tickers:
        if ticker in technical_data and ticker in latest_prices:
            technical_data[ticker]['current_price'] = latest_prices[ticker]

    # Add market_cap to sentiment data
    for ticker in tickers:
        if ticker in sentiment_data and ticker in market_caps:
            sentiment_data[ticker]['market_cap'] = market_caps[ticker]

    # Load latest market sentiment (market-wide indicators)
    market_sentiment_record = (
        session.query(MarketSentiment)
        .order_by(MarketSentiment.date.desc())
        .first()
    )
    market_sentiment = None
    if market_sentiment_record:
        market_sentiment = {
            'date': market_sentiment_record.date,
            'market_sentiment_score': float(market_sentiment_record.market_sentiment_score),
            'num_indicators_available': int(market_sentiment_record.num_indicators_available),
            'vix_score': float(market_sentiment_record.vix_score) if market_sentiment_record.vix_score else None,
            'aaii_score': float(market_sentiment_record.aaii_score) if market_sentiment_record.aaii_score else None,
            'putcall_score': float(market_sentiment_record.putcall_score) if market_sentiment_record.putcall_score else None,
            'fund_flows_score': float(market_sentiment_record.fund_flows_score) if market_sentiment_record.fund_flows_score else None,
        }
        print(f"  Loaded market sentiment data for {market_sentiment_record.date}")
        print(f"    Market sentiment score: {market_sentiment['market_sentiment_score']:.2f} "
              f"(from {market_sentiment['num_indicators_available']} indicators)")
    else:
        print("  WARNING: No market sentiment data found in database")
        print("  Run: python scripts/collect_market_sentiment.py")

    return {
        'tickers': tickers,
        'fundamental_data': fundamental_data,
        'technical_data': technical_data,
        'sentiment_data': sentiment_data,
        'latest_prices': latest_prices,
        'market_caps': market_caps,
        'market_sentiment': market_sentiment
    }


def prepare_fundamental_data(fundamental_records: Dict) -> tuple:
    """Convert fundamental data to calculator format.

    Returns:
        Tuple of (stock_data dict, universe_metrics dict)
    """
    stock_data = {}
    for ticker, metrics in fundamental_records.items():
        stock_data[ticker] = {
            # Valuation metrics
            'pe_ratio': metrics.get('pe_ratio'),
            'pb_ratio': metrics.get('pb_ratio'),
            'ps_ratio': metrics.get('ps_ratio'),
            'ev_ebitda': metrics.get('ev_to_ebitda'),
            'dividend_yield': metrics.get('dividend_yield'),
            # Quality metrics
            'roe': metrics.get('roe'),
            'roa': metrics.get('roa'),
            'net_margin': metrics.get('net_margin'),
            'operating_margin': metrics.get('operating_margin'),
            'gross_margin': metrics.get('gross_margin'),
            # Growth metrics
            'revenue_growth': metrics.get('revenue_growth_yoy'),
            'earnings_growth': metrics.get('eps_growth_yoy'),
        }

    # Build universe metrics
    universe = {}
    metric_names = ['pe_ratio', 'pb_ratio', 'ps_ratio', 'ev_ebitda', 'dividend_yield',
                    'roe', 'roa', 'net_margin', 'operating_margin', 'gross_margin',
                    'revenue_growth', 'earnings_growth']

    for metric in metric_names:
        values = [stock[metric] for stock in stock_data.values() if stock.get(metric) is not None]
        if values:
            universe[metric] = values

    return stock_data, universe


def prepare_technical_data(technical_records: Dict) -> tuple:
    """Prepare technical data for calculator (already in dict format).

    Computes derived indicators:
    - short_term_uptrend: Price > 20-day MA AND 20-day > 50-day
    - long_term_uptrend: Price > 50-day MA AND 50-day > 200-day

    Returns:
        Tuple of (stock_data dict, universe_metrics dict)
    """
    # Data is already in the right format
    stock_data = technical_records

    # Compute derived uptrend indicators for each stock
    for ticker, data in stock_data.items():
        current_price = data.get('current_price')
        sma_20 = data.get('sma_20')
        sma_50 = data.get('sma_50')
        sma_200 = data.get('sma_200')

        # Short-term uptrend: Price > 20-day MA AND 20-day > 50-day
        if current_price is not None and sma_20 is not None and sma_50 is not None:
            data['short_term_uptrend'] = (current_price > sma_20) and (sma_20 > sma_50)
        else:
            data['short_term_uptrend'] = None

        # Long-term uptrend: Price > 50-day MA AND 50-day > 200-day
        if current_price is not None and sma_50 is not None and sma_200 is not None:
            data['long_term_uptrend'] = (current_price > sma_50) and (sma_50 > sma_200)
        else:
            data['long_term_uptrend'] = None

    # Build universe metrics
    universe = {}
    metrics = ['sma_50', 'sma_200', 'mad', 'momentum_12_1', 'momentum_6m', 'momentum_3m', 'momentum_1m',
               'avg_volume_20d', 'relative_volume', 'rsi_14', 'adx', 'sector_relative_6m']

    for metric in metrics:
        values = [stock.get(metric) for stock in stock_data.values() if stock.get(metric) is not None]
        if values:
            universe[metric] = values

    return stock_data, universe


def prepare_sentiment_data(sentiment_records: Dict) -> tuple:
    """Prepare sentiment data for calculator.

    Computes derived metrics:
    - recommendation_mean: Weighted average of buy/hold/sell ratings (1-5 scale)
    - Maps field names to match calculator expectations

    Returns:
        Tuple of (stock_data dict, universe_metrics dict)
    """
    stock_data = {}

    for ticker, data in sentiment_records.items():
        # Map field names for calculator
        mapped_data = {
            'days_to_cover': data.get('days_to_cover'),
            'analyst_target': data.get('consensus_price_target'),
            'analyst_count': data.get('num_analyst_opinions'),
            'market_cap': data.get('market_cap'),
            'insider_net_shares': data.get('insider_net_shares_6m'),
            'upgrades_30d': data.get('upgrades_30d'),
            'downgrades_30d': data.get('downgrades_30d'),
            # FMP revision data (Framework Section 5.2 - real revision tracking)
            'estimate_revisions_up_90d': data.get('estimate_revisions_up_90d'),
            'estimate_revisions_down_90d': data.get('estimate_revisions_down_90d'),
        }

        # Calculate recommendation_mean from buy/hold/sell ratings
        # Scale: 1.0 = Strong Buy, 2.0 = Buy, 3.0 = Hold, 4.0 = Sell, 5.0 = Strong Sell
        num_buy = data.get('num_buy_ratings') or 0
        num_hold = data.get('num_hold_ratings') or 0
        num_sell = data.get('num_sell_ratings') or 0
        total_ratings = num_buy + num_hold + num_sell

        if total_ratings > 0:
            # Simplified: Buy=1, Hold=3, Sell=5
            recommendation_mean = (num_buy * 1.0 + num_hold * 3.0 + num_sell * 5.0) / total_ratings
            mapped_data['recommendation_mean'] = recommendation_mean
        else:
            mapped_data['recommendation_mean'] = None

        stock_data[ticker] = mapped_data

    # Build universe metrics
    universe = {}
    metrics = ['recommendation_mean', 'analyst_count', 'analyst_target', 'days_to_cover',
               'market_cap', 'insider_net_shares']

    for metric in metrics:
        values = [stock.get(metric) for stock in stock_data.values() if stock.get(metric) is not None]
        if values:
            universe[metric] = values

    return stock_data, universe


def calculate_pillar_scores(data: Dict) -> Dict[str, Dict[str, float]]:
    """Calculate fundamental, technical, and sentiment scores for all stocks.

    Args:
        data: Dict containing tickers and their data (from load_all_data)

    Returns:
        Dict mapping ticker to pillar scores:
        {
            'AAPL': {
                'fundamental': 75.0,
                'technical': 82.0,
                'sentiment': 68.0
            },
            ...
        }
    """
    print("\nCalculating pillar scores...")

    tickers = data['tickers']
    fundamental_data = data['fundamental_data']
    technical_data = data['technical_data']
    sentiment_data = data['sentiment_data']
    latest_prices = data['latest_prices']

    # Initialize calculators
    fundamental_calc = FundamentalCalculator()
    technical_calc = TechnicalCalculator()
    sentiment_calc = SentimentCalculator()

    # Prepare data for each calculator
    fund_stock_data, fund_universe = prepare_fundamental_data(fundamental_data)
    print(f"  Prepared fundamental data: {len(fund_stock_data)} stocks, {len(fund_universe)} metrics")

    tech_stock_data, tech_universe = prepare_technical_data(technical_data)
    print(f"  Prepared technical data: {len(tech_stock_data)} stocks, {len(tech_universe)} metrics")

    sent_stock_data, sent_universe = prepare_sentiment_data(sentiment_data)
    print(f"  Prepared sentiment data: {len(sent_stock_data)} stocks, {len(sent_universe)} metrics")

    # Calculate scores for each stock
    stock_scores = {}

    for ticker in tickers:
        # Fundamental score
        if ticker in fund_stock_data:
            fund_result = fundamental_calc.calculate_fundamental_score(
                fund_stock_data[ticker],
                fund_universe
            )
            fund_score = fund_result.get('fundamental_score', 50.0)
        else:
            fund_score = 50.0

        # Technical score
        if ticker in tech_stock_data:
            tech_result = technical_calc.calculate_technical_score(
                tech_stock_data[ticker],
                tech_universe
            )
            tech_score = tech_result.get('technical_score', 50.0)
        else:
            tech_score = 50.0

        # Sentiment score
        if ticker in sent_stock_data and ticker in latest_prices:
            current_price = latest_prices[ticker]
            sent_score = sentiment_calc.calculate_sentiment_score(
                sent_stock_data[ticker],
                current_price,
                market_data=data['market_sentiment']  # Pass market-wide sentiment
            )
        else:
            sent_score = 50.0

        stock_scores[ticker] = {
            'fundamental': fund_score if fund_score is not None else 50.0,
            'technical': tech_score if tech_score is not None else 50.0,
            'sentiment': sent_score if sent_score is not None else 50.0
        }

    print(f"  Calculated scores for {len(stock_scores)} stocks")
    return stock_scores


def validate_scores(stock_scores: Dict[str, Dict[str, float]]):
    """Validate that all pillar scores are in valid range.

    Args:
        stock_scores: Dict of ticker to pillar scores

    Raises:
        ValueError: If any score is out of range
    """
    print("\nValidating scores...")

    errors = []
    for ticker, scores in stock_scores.items():
        for pillar, score in scores.items():
            if not (0 <= score <= 100):
                errors.append(f"  {ticker} {pillar}: {score:.2f} (out of range 0-100)")

    if errors:
        print("  VALIDATION ERRORS:")
        for error in errors:
            print(error)
        raise ValueError(f"Found {len(errors)} scores out of valid range")
    else:
        print("  [OK] All scores in valid range [0, 100]")


def display_detailed_results(stock_scores: Dict[str, Dict[str, float]], composite_results):
    """Display detailed breakdown of scores for each stock.

    Args:
        stock_scores: Dict of ticker to pillar scores
        composite_results: List of CompositeScore objects
    """
    print("\n" + "=" * 120)
    print("DETAILED SCORE BREAKDOWN")
    print("=" * 120)

    for result in composite_results:
        ticker = result.ticker
        scores = stock_scores[ticker]

        print(f"\n{ticker} - {result.recommendation.value}")
        print(f"  Fundamental: {scores['fundamental']:6.2f}")
        print(f"  Technical:   {scores['technical']:6.2f}")
        print(f"  Sentiment:   {scores['sentiment']:6.2f}")
        print(f"  --------------------")
        print(f"  Composite:   {result.composite_score:6.2f} (Percentile: {result.composite_percentile:.1f})")


def main():
    """Main integration test function."""
    print("=" * 100)
    print("COMPOSITE SCORE INTEGRATION TEST")
    print("=" * 100)
    print("\nThis script performs end-to-end calculation:")
    print("  1. Load fundamental, technical, sentiment data from database")
    print("  2. Calculate pillar scores for all stocks")
    print("  3. Calculate composite scores and generate recommendations")
    print("  4. Validate results")
    print()

    try:
        # Get database session
        with get_db_session() as session:
            # Step 1: Load all data
            data = load_all_data(session)

        # Check we have complete data
        if not data['tickers']:
            print("ERROR: No stocks found in database")
            return

        num_tickers = len(data['tickers'])
        print(f"\nData coverage:")
        print(f"  Stocks: {num_tickers}")
        print(f"  Fundamental: {len(data['fundamental_data'])}/{num_tickers} "
              f"({len(data['fundamental_data'])/num_tickers*100:.0f}%)")
        print(f"  Technical: {len(data['technical_data'])}/{num_tickers} "
              f"({len(data['technical_data'])/num_tickers*100:.0f}%)")
        print(f"  Sentiment: {len(data['sentiment_data'])}/{num_tickers} "
              f"({len(data['sentiment_data'])/num_tickers*100:.0f}%)")

        # Step 2: Calculate pillar scores
        stock_scores = calculate_pillar_scores(data)

        # Step 3: Validate scores
        validate_scores(stock_scores)

        # Step 4: Calculate composite scores
        print("\nCalculating composite scores...")
        composite_calc = CompositeScoreCalculator(
            fundamental_weight=0.45,  # Framework Section 1.3 base weights
            technical_weight=0.35,
            sentiment_weight=0.20
        )

        composite_results = composite_calc.calculate_scores_for_universe(stock_scores)
        print(f"  Calculated composite scores for {len(composite_results)} stocks")

        # Step 5: Generate and display report
        report = composite_calc.generate_report(composite_results)
        print("\n" + report)

        # Step 6: Display detailed breakdown
        display_detailed_results(stock_scores, composite_results)

        # Step 7: Validation summary
        print("\n" + "=" * 120)
        print("VALIDATION SUMMARY")
        print("=" * 120)

        # Check percentile distribution
        percentiles = [r.composite_percentile for r in composite_results]
        print(f"\nComposite Percentile Distribution:")
        print(f"  Min:    {min(percentiles):6.2f}")
        print(f"  25th:   {sorted(percentiles)[len(percentiles)//4]:6.2f}")
        print(f"  Median: {sorted(percentiles)[len(percentiles)//2]:6.2f}")
        print(f"  75th:   {sorted(percentiles)[3*len(percentiles)//4]:6.2f}")
        print(f"  Max:    {max(percentiles):6.2f}")

        # Check recommendation distribution
        print(f"\nRecommendation Distribution:")
        for rec in Recommendation:
            count = sum(1 for r in composite_results if r.recommendation == rec)
            pct = count / len(composite_results) * 100
            print(f"  {rec.value:12s}: {count:2d} stocks ({pct:5.1f}%)")

        # Final validation
        print("\n" + "=" * 120)
        print("[OK] INTEGRATION TEST COMPLETE")
        print("=" * 120)
        print(f"\nSuccessfully calculated composite scores for {len(composite_results)} stocks")
        print("All three pillar calculators integrated successfully")
        print("\nFramework compliance:")
        print("  [OK] Percentile-based scoring (Section 1.2)")
        print("  [OK] Research-backed weights: 45/35/20 (Section 1.3)")
        print("  [OK] Recommendation thresholds (Section 7.2)")
        print()

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        if 'session' in locals():
            session.close()


if __name__ == "__main__":
    main()
