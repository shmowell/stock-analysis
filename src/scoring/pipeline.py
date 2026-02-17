"""
Scoring Pipeline - Reusable orchestration of the complete scoring workflow.

Extracts the scoring logic from calculate_scores.py into a reusable class
that can be called by daily_report.py, calculate_scores.py, and other tools.

Workflow:
    1. Load fundamental, technical, sentiment data from database
    2. Prepare data for each calculator
    3. Calculate pillar scores (fundamental, technical, sentiment)
    4. Calculate composite scores with recommendations
    5. Persist results to database and/or JSON

Framework Reference: Section 1.3 (Base Weighting), Section 7 (Final Recommendation)

Author: Stock Analysis Framework v2.0
Date: 2026-02-14
"""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from calculators.fundamental import FundamentalCalculator
from calculators.technical import TechnicalCalculator
from calculators.sentiment import SentimentCalculator
from database.models import (
    Stock, FundamentalData, TechnicalIndicator, SentimentData,
    PriceData, MarketSentiment, StockScore
)
from models.composite import CompositeScoreCalculator, CompositeScore, Recommendation


class ScoringPipeline:
    """Reusable scoring pipeline for stock analysis.

    Orchestrates the complete scoring workflow from data loading through
    composite score calculation and persistence.

    Usage:
        from scoring import ScoringPipeline

        pipeline = ScoringPipeline()
        with get_db_session() as session:
            results = pipeline.run(session)
            # results.composite_results: List[CompositeScore]
            # results.pillar_scores: Dict[str, Dict[str, float]]
    """

    # Default weights from Framework Section 1.3
    DEFAULT_WEIGHTS = {
        'fundamental': 0.45,
        'technical': 0.35,
        'sentiment': 0.20,
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None, verbose: bool = True):
        """Initialize the scoring pipeline.

        Args:
            weights: Optional weight overrides. Keys: fundamental, technical, sentiment.
                     Must sum to 1.0. Defaults to 45/35/20.
            verbose: If True, print progress messages during execution.
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.verbose = verbose

        # Initialize calculators
        self._fundamental_calc = FundamentalCalculator()
        self._technical_calc = TechnicalCalculator()
        self._sentiment_calc = SentimentCalculator()
        self._composite_calc = CompositeScoreCalculator(
            fundamental_weight=self.weights['fundamental'],
            technical_weight=self.weights['technical'],
            sentiment_weight=self.weights['sentiment'],
        )

    def _log(self, msg: str) -> None:
        """Print a message if verbose mode is on."""
        if self.verbose:
            print(msg)

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def load_data(self, session: Session, tickers: Optional[List[str]] = None) -> Dict:
        """Load all data from database, optionally filtered by tickers.

        Args:
            session: Database session.
            tickers: Optional list of tickers to load. If None, loads all active stocks.

        Returns:
            Dict with keys: tickers, fundamental_data, technical_data,
            sentiment_data, latest_prices, market_caps, market_sentiment.
        """
        self._log("Loading data from database...")

        # Get stocks
        query = session.query(Stock).filter_by(is_active=True)
        if tickers:
            query = query.filter(Stock.ticker.in_(tickers))
        stocks = query.all()
        stock_tickers = [s.ticker for s in stocks]
        market_caps = {
            s.ticker: float(s.market_cap) if s.market_cap else None
            for s in stocks
        }
        self._log(f"  Loaded {len(stock_tickers)} active stocks")

        # Fundamental data
        fund_query = session.query(FundamentalData)
        if tickers:
            fund_query = fund_query.filter(FundamentalData.ticker.in_(tickers))
        fundamental_data = {}
        for fd in fund_query.all():
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
        self._log(f"  Loaded {len(fundamental_data)} fundamental records")

        # Technical indicators - latest record per ticker
        tech_query = session.query(TechnicalIndicator).order_by(
            TechnicalIndicator.ticker, TechnicalIndicator.calculation_date.desc()
        )
        if tickers:
            tech_query = tech_query.filter(TechnicalIndicator.ticker.in_(tickers))
        technical_data = {}
        for ti in tech_query.all():
            if ti.ticker in technical_data:
                continue  # Keep only latest
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
        self._log(f"  Loaded {len(technical_data)} technical records")

        # Latest prices
        latest_prices = {}
        for ticker in stock_tickers:
            latest = (
                session.query(PriceData)
                .filter(PriceData.ticker == ticker)
                .order_by(PriceData.date.desc())
                .first()
            )
            if latest:
                latest_prices[ticker] = float(latest.close)
        self._log(f"  Loaded {len(latest_prices)} latest prices")

        # Sentiment data
        sent_query = session.query(SentimentData)
        if tickers:
            sent_query = sent_query.filter(SentimentData.ticker.in_(tickers))
        sentiment_data = {}
        for sd in sent_query.all():
            sentiment_data[sd.ticker] = {
                'consensus_price_target': float(sd.consensus_price_target) if sd.consensus_price_target else None,
                'num_buy_ratings': int(sd.num_buy_ratings) if sd.num_buy_ratings else None,
                'num_hold_ratings': int(sd.num_hold_ratings) if sd.num_hold_ratings else None,
                'num_sell_ratings': int(sd.num_sell_ratings) if sd.num_sell_ratings else None,
                'num_analyst_opinions': int(sd.num_analyst_opinions) if sd.num_analyst_opinions else None,
                'upgrades_30d': int(sd.upgrades_30d) if sd.upgrades_30d else None,
                'downgrades_30d': int(sd.downgrades_30d) if sd.downgrades_30d else None,
                'estimate_revisions_up_90d': int(sd.estimate_revisions_up_90d) if sd.estimate_revisions_up_90d else None,
                'estimate_revisions_down_90d': int(sd.estimate_revisions_down_90d) if sd.estimate_revisions_down_90d else None,
                'short_interest_pct': float(sd.short_interest_pct) if sd.short_interest_pct else None,
                'days_to_cover': float(sd.days_to_cover) if sd.days_to_cover else None,
                'insider_buys_6m': int(sd.insider_buys_6m) if sd.insider_buys_6m else None,
                'insider_sells_6m': int(sd.insider_sells_6m) if sd.insider_sells_6m else None,
                'insider_net_shares_6m': int(sd.insider_net_shares_6m) if sd.insider_net_shares_6m else None,
            }
        self._log(f"  Loaded {len(sentiment_data)} sentiment records")

        # Enrich: add current_price to technical data
        for ticker in stock_tickers:
            if ticker in technical_data and ticker in latest_prices:
                technical_data[ticker]['current_price'] = latest_prices[ticker]

        # Enrich: add market_cap to sentiment data
        for ticker in stock_tickers:
            if ticker in sentiment_data and ticker in market_caps:
                sentiment_data[ticker]['market_cap'] = market_caps[ticker]

        # Market sentiment (market-wide indicators)
        ms_record = (
            session.query(MarketSentiment)
            .order_by(MarketSentiment.date.desc())
            .first()
        )
        market_sentiment = None
        if ms_record:
            market_sentiment = {
                'date': ms_record.date,
                'market_sentiment_score': float(ms_record.market_sentiment_score),
                'num_indicators_available': int(ms_record.num_indicators_available),
                'vix_score': float(ms_record.vix_score) if ms_record.vix_score else None,
                'aaii_score': float(ms_record.aaii_score) if ms_record.aaii_score else None,
                'putcall_score': float(ms_record.putcall_score) if ms_record.putcall_score else None,
                'fund_flows_score': float(ms_record.fund_flows_score) if ms_record.fund_flows_score else None,
            }
            self._log(
                f"  Loaded market sentiment for {ms_record.date} "
                f"(score: {market_sentiment['market_sentiment_score']:.2f}, "
                f"{market_sentiment['num_indicators_available']} indicators)"
            )
        else:
            self._log("  WARNING: No market sentiment data found")

        return {
            'tickers': stock_tickers,
            'fundamental_data': fundamental_data,
            'technical_data': technical_data,
            'sentiment_data': sentiment_data,
            'latest_prices': latest_prices,
            'market_caps': market_caps,
            'market_sentiment': market_sentiment,
        }

    # ------------------------------------------------------------------
    # Data Preparation (convert DB dicts to calculator format)
    # ------------------------------------------------------------------

    @staticmethod
    def _prepare_fundamental(records: Dict) -> Tuple[Dict, Dict]:
        """Convert fundamental data to calculator format.

        Returns:
            (stock_data, universe_metrics) tuple.
        """
        stock_data = {}
        for ticker, metrics in records.items():
            stock_data[ticker] = {
                'pe_ratio': metrics.get('pe_ratio'),
                'pb_ratio': metrics.get('pb_ratio'),
                'ps_ratio': metrics.get('ps_ratio'),
                'ev_ebitda': metrics.get('ev_to_ebitda'),
                'dividend_yield': metrics.get('dividend_yield'),
                'roe': metrics.get('roe'),
                'roa': metrics.get('roa'),
                'net_margin': metrics.get('net_margin'),
                'operating_margin': metrics.get('operating_margin'),
                'gross_margin': metrics.get('gross_margin'),
                'revenue_growth': metrics.get('revenue_growth_yoy'),
                'earnings_growth': metrics.get('eps_growth_yoy'),
            }

        universe = {}
        metric_names = [
            'pe_ratio', 'pb_ratio', 'ps_ratio', 'ev_ebitda', 'dividend_yield',
            'roe', 'roa', 'net_margin', 'operating_margin', 'gross_margin',
            'revenue_growth', 'earnings_growth',
        ]
        for metric in metric_names:
            values = [s[metric] for s in stock_data.values() if s.get(metric) is not None]
            if values:
                universe[metric] = values

        return stock_data, universe

    @staticmethod
    def _prepare_technical(records: Dict) -> Tuple[Dict, Dict]:
        """Prepare technical data, computing derived uptrend indicators.

        Returns:
            (stock_data, universe_metrics) tuple.
        """
        stock_data = records  # Already in dict form

        for _ticker, data in stock_data.items():
            price = data.get('current_price')
            sma_20 = data.get('sma_20')
            sma_50 = data.get('sma_50')
            sma_200 = data.get('sma_200')

            if price is not None and sma_20 is not None and sma_50 is not None:
                data['short_term_uptrend'] = (price > sma_20) and (sma_20 > sma_50)
            else:
                data['short_term_uptrend'] = None

            if price is not None and sma_50 is not None and sma_200 is not None:
                data['long_term_uptrend'] = (price > sma_50) and (sma_50 > sma_200)
            else:
                data['long_term_uptrend'] = None

        universe = {}
        metrics = [
            'sma_50', 'sma_200', 'mad', 'momentum_12_1', 'momentum_6m',
            'momentum_3m', 'momentum_1m', 'avg_volume_20d', 'relative_volume',
            'rsi_14', 'adx', 'sector_relative_6m',
        ]
        for metric in metrics:
            values = [s.get(metric) for s in stock_data.values() if s.get(metric) is not None]
            if values:
                universe[metric] = values

        return stock_data, universe

    @staticmethod
    def _prepare_sentiment(records: Dict) -> Tuple[Dict, Dict]:
        """Prepare sentiment data, computing recommendation_mean.

        Returns:
            (stock_data, universe_metrics) tuple.
        """
        stock_data = {}
        for ticker, data in records.items():
            mapped = {
                'days_to_cover': data.get('days_to_cover'),
                'analyst_target': data.get('consensus_price_target'),
                'analyst_count': data.get('num_analyst_opinions'),
                'market_cap': data.get('market_cap'),
                'insider_net_shares': data.get('insider_net_shares_6m'),
                'upgrades_30d': data.get('upgrades_30d'),
                'downgrades_30d': data.get('downgrades_30d'),
                'estimate_revisions_up_90d': data.get('estimate_revisions_up_90d'),
                'estimate_revisions_down_90d': data.get('estimate_revisions_down_90d'),
            }

            # Calculate recommendation_mean from buy/hold/sell ratings
            # Scale: 1.0 = Strong Buy, 3.0 = Hold, 5.0 = Strong Sell
            num_buy = data.get('num_buy_ratings') or 0
            num_hold = data.get('num_hold_ratings') or 0
            num_sell = data.get('num_sell_ratings') or 0
            total = num_buy + num_hold + num_sell
            if total > 0:
                mapped['recommendation_mean'] = (
                    num_buy * 1.0 + num_hold * 3.0 + num_sell * 5.0
                ) / total
            else:
                mapped['recommendation_mean'] = None

            stock_data[ticker] = mapped

        universe = {}
        metrics = [
            'recommendation_mean', 'analyst_count', 'analyst_target',
            'days_to_cover', 'market_cap', 'insider_net_shares',
        ]
        for metric in metrics:
            values = [s.get(metric) for s in stock_data.values() if s.get(metric) is not None]
            if values:
                universe[metric] = values

        return stock_data, universe

    # ------------------------------------------------------------------
    # Score Calculation
    # ------------------------------------------------------------------

    def calculate_scores(
        self, data: Dict
    ) -> Tuple[Dict[str, Dict[str, float]], List[CompositeScore]]:
        """Calculate pillar scores and composite scores for the universe.

        Args:
            data: Dict from load_data().

        Returns:
            Tuple of:
                - pillar_scores: {ticker: {fundamental, technical, sentiment}}
                - composite_results: List[CompositeScore] sorted by percentile desc.
        """
        self._log("\nCalculating pillar scores...")
        tickers = data['tickers']

        # Prepare data
        fund_stock, fund_universe = self._prepare_fundamental(data['fundamental_data'])
        tech_stock, tech_universe = self._prepare_technical(data['technical_data'])
        sent_stock, sent_universe = self._prepare_sentiment(data['sentiment_data'])

        self._log(f"  Prepared: {len(fund_stock)} fundamental, "
                  f"{len(tech_stock)} technical, {len(sent_stock)} sentiment")

        # Calculate per-stock pillar scores (with sub-component detail)
        pillar_scores: Dict[str, Dict] = {}
        for ticker in tickers:
            fund_detail = {}
            tech_detail = {}
            sent_detail = {}
            data_status = {}

            # Fundamental
            if ticker in fund_stock:
                fund_result = self._fundamental_calc.calculate_fundamental_score(
                    fund_stock[ticker], fund_universe
                )
                fund_score = fund_result.get('fundamental_score')
                fund_detail = {
                    'value_score': fund_result.get('value_score'),
                    'quality_score': fund_result.get('quality_score'),
                    'growth_score': fund_result.get('growth_score'),
                }
                data_status['fundamental'] = 'calculated'
            else:
                fund_score = None
                data_status['fundamental'] = 'no_data'

            # Technical
            if ticker in tech_stock:
                tech_result = self._technical_calc.calculate_technical_score(
                    tech_stock[ticker], tech_universe
                )
                tech_score = tech_result.get('technical_score')
                tech_detail = {
                    'momentum_score': tech_result.get('momentum_score'),
                    'trend_score': tech_result.get('trend_score'),
                    'volume_qualified_score': tech_result.get('volume_qualified_score'),
                    'relative_strength_score': tech_result.get('relative_strength_score'),
                    'rsi_score': tech_result.get('rsi_score'),
                    'multi_speed_score': tech_result.get('multi_speed_score'),
                }
                data_status['technical'] = 'calculated'
            else:
                tech_score = None
                data_status['technical'] = 'no_data'

            # Sentiment (returns dict with sub-components)
            if ticker in sent_stock and ticker in data['latest_prices']:
                sent_result = self._sentiment_calc.calculate_sentiment_score(
                    sent_stock[ticker],
                    data['latest_prices'][ticker],
                    market_data=data['market_sentiment'],
                )
                sent_score = sent_result.get('sentiment_score')
                sent_detail = {
                    'market_sentiment': sent_result.get('market_sentiment'),
                    'stock_sentiment': sent_result.get('stock_sentiment'),
                    'short_interest_score': sent_result.get('short_interest_score'),
                    'revision_score': sent_result.get('revision_score'),
                    'consensus_score': sent_result.get('consensus_score'),
                    'insider_score': sent_result.get('insider_score'),
                }
                data_status['sentiment'] = 'calculated'
            else:
                sent_score = None
                data_status['sentiment'] = 'no_data'

            pillar_scores[ticker] = {
                'fundamental': fund_score,
                'technical': tech_score,
                'sentiment': sent_score,
                'fundamental_detail': fund_detail,
                'technical_detail': tech_detail,
                'sentiment_detail': sent_detail,
                'data_status': data_status,
            }

        self._log(f"  Calculated pillar scores for {len(pillar_scores)} stocks")

        # Separate fully-scored stocks from those missing data
        scorable = {
            ticker: scores for ticker, scores in pillar_scores.items()
            if scores['fundamental'] is not None
            and scores['technical'] is not None
            and scores['sentiment'] is not None
        }
        unscored = [t for t in pillar_scores if t not in scorable]
        if unscored:
            self._log(f"  Excluding {len(unscored)} stock(s) with missing data: {', '.join(unscored)}")

        # Validate only scorable stocks
        self._validate_scores(scorable)

        # Composite scores (only for fully-scored stocks)
        self._log("\nCalculating composite scores...")
        composite_results = self._composite_calc.calculate_scores_for_universe(scorable)
        self._log(f"  Calculated composite scores for {len(composite_results)} stocks")

        return pillar_scores, composite_results

    _PILLAR_KEYS = ('fundamental', 'technical', 'sentiment')

    def _validate_scores(self, pillar_scores: Dict[str, Dict]) -> None:
        """Validate all pillar scores are within [0, 100]."""
        errors = []
        for ticker, scores in pillar_scores.items():
            for pillar in self._PILLAR_KEYS:
                score = scores.get(pillar)
                if score is not None and not (0 <= score <= 100):
                    errors.append(f"  {ticker} {pillar}: {score:.2f}")
        if errors:
            self._log("  VALIDATION ERRORS:")
            for e in errors:
                self._log(e)
            raise ValueError(f"{len(errors)} scores out of valid range [0, 100]")
        self._log("  [OK] All scores in valid range [0, 100]")

    # ------------------------------------------------------------------
    # Full Pipeline
    # ------------------------------------------------------------------

    def run(
        self,
        session: Session,
        tickers: Optional[List[str]] = None,
    ) -> 'PipelineResult':
        """Run the complete scoring pipeline.

        Args:
            session: Database session.
            tickers: Optional list of tickers (default: all active stocks).

        Returns:
            PipelineResult with composite_results, pillar_scores, and data.
        """
        data = self.load_data(session, tickers=tickers)

        if not data['tickers']:
            self._log("ERROR: No stocks found in database")
            return PipelineResult(
                composite_results=[],
                pillar_scores={},
                data=data,
                weights=self.weights,
            )

        self._log_coverage(data)

        pillar_scores, composite_results = self.calculate_scores(data)

        return PipelineResult(
            composite_results=composite_results,
            pillar_scores=pillar_scores,
            data=data,
            weights=self.weights,
        )

    def _log_coverage(self, data: Dict) -> None:
        """Log data coverage statistics."""
        n = len(data['tickers'])
        self._log(f"\nData coverage:")
        self._log(f"  Stocks:      {n}")
        self._log(f"  Fundamental: {len(data['fundamental_data'])}/{n} "
                  f"({len(data['fundamental_data'])/n*100:.0f}%)")
        self._log(f"  Technical:   {len(data['technical_data'])}/{n} "
                  f"({len(data['technical_data'])/n*100:.0f}%)")
        self._log(f"  Sentiment:   {len(data['sentiment_data'])}/{n} "
                  f"({len(data['sentiment_data'])/n*100:.0f}%)")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def persist_to_db(
        self,
        session: Session,
        result: 'PipelineResult',
        calculation_date: Optional[date] = None,
    ) -> int:
        """Save scores to the stock_scores table.

        Args:
            session: Database session.
            result: PipelineResult from run().
            calculation_date: Date for the scores. Defaults to today.

        Returns:
            Number of records saved.
        """
        calc_date = calculation_date or date.today()
        count = 0

        # Delete existing scores for this date to avoid duplicates
        tickers_to_save = [cr.ticker for cr in result.composite_results]
        if tickers_to_save:
            session.query(StockScore).filter(
                StockScore.calculation_date == calc_date,
                StockScore.ticker.in_(tickers_to_save),
            ).delete(synchronize_session='fetch')

        for cr in result.composite_results:
            pillars = result.pillar_scores.get(cr.ticker, {})
            fund_detail = pillars.get('fundamental_detail', {})

            score_record = StockScore(
                ticker=cr.ticker,
                calculation_date=calc_date,
                fundamental_score=float(cr.fundamental_score),
                technical_score=float(cr.technical_score),
                sentiment_score=float(cr.sentiment_score),
                base_composite_score=float(cr.composite_score),
                final_composite_score=float(cr.composite_score),
                recommendation=cr.recommendation.value,
                value_score=float(fund_detail['value_score']) if fund_detail.get('value_score') is not None else None,
                quality_score=float(fund_detail['quality_score']) if fund_detail.get('quality_score') is not None else None,
                growth_score=float(fund_detail['growth_score']) if fund_detail.get('growth_score') is not None else None,
            )
            session.add(score_record)
            count += 1

        session.flush()
        self._log(f"  Persisted {count} scores to database (date: {calc_date})")
        return count

    def persist_to_json(
        self,
        result: 'PipelineResult',
        output_path: Optional[Path] = None,
    ) -> Path:
        """Save scores to JSON file for the override system.

        Args:
            result: PipelineResult from run().
            output_path: Target path. Defaults to data/processed/latest_scores.json.

        Returns:
            Path to the saved file.
        """
        if output_path is None:
            output_path = Path(__file__).parent.parent.parent / 'data' / 'processed' / 'latest_scores.json'
        output_path.parent.mkdir(parents=True, exist_ok=True)

        scores_list = []
        scored_tickers = set()
        for r in result.composite_results:
            pillars = result.pillar_scores.get(r.ticker, {})
            entry = {
                'ticker': r.ticker,
                'fundamental_score': r.fundamental_score,
                'technical_score': r.technical_score,
                'sentiment_score': r.sentiment_score,
                'composite_score': r.composite_score,
                'composite_percentile': r.composite_percentile,
                'recommendation': r.recommendation.value,
                'sub_components': {
                    'fundamental': pillars.get('fundamental_detail', {}),
                    'technical': pillars.get('technical_detail', {}),
                    'sentiment': pillars.get('sentiment_detail', {}),
                },
                'data_status': pillars.get('data_status', {}),
            }
            scores_list.append(entry)
            scored_tickers.add(r.ticker)

        # Include unscored stocks (missing data) with null scores
        for ticker, pillars in result.pillar_scores.items():
            if ticker in scored_tickers:
                continue
            entry = {
                'ticker': ticker,
                'fundamental_score': pillars.get('fundamental'),
                'technical_score': pillars.get('technical'),
                'sentiment_score': pillars.get('sentiment'),
                'composite_score': None,
                'composite_percentile': None,
                'recommendation': 'INSUFFICIENT DATA',
                'sub_components': {
                    'fundamental': pillars.get('fundamental_detail', {}),
                    'technical': pillars.get('technical_detail', {}),
                    'sentiment': pillars.get('sentiment_detail', {}),
                },
                'data_status': pillars.get('data_status', {}),
            }
            scores_list.append(entry)

        scores_data = {
            'generated_at': str(datetime.now()),
            'universe_size': len(result.composite_results),
            'scored_count': len(result.composite_results),
            'unscored_count': len(result.pillar_scores) - len(result.composite_results),
            'weights': result.weights,
            'scores': scores_list,
        }
        with open(output_path, 'w') as f:
            json.dump(scores_data, f, indent=2)

        self._log(f"  Saved scores to {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Previous Scores (for change comparison)
    # ------------------------------------------------------------------

    def load_previous_scores(self, session: Session) -> Optional[Dict[str, Dict]]:
        """Load the most recent set of scores from the database.

        Returns:
            Dict mapping ticker to score dict, or None if no previous scores exist.
            Each score dict has: fundamental_score, technical_score, sentiment_score,
            composite_score, recommendation.
        """
        # Find the latest calculation_date
        latest = (
            session.query(StockScore.calculation_date)
            .order_by(StockScore.calculation_date.desc())
            .first()
        )
        if not latest:
            return None

        latest_date = latest[0]
        records = (
            session.query(StockScore)
            .filter(StockScore.calculation_date == latest_date)
            .all()
        )

        result = {}
        for r in records:
            result[r.ticker] = {
                'calculation_date': r.calculation_date,
                'fundamental_score': float(r.fundamental_score) if r.fundamental_score else None,
                'technical_score': float(r.technical_score) if r.technical_score else None,
                'sentiment_score': float(r.sentiment_score) if r.sentiment_score else None,
                'composite_score': float(r.final_composite_score) if r.final_composite_score else None,
                'recommendation': r.recommendation,
            }

        self._log(f"  Loaded {len(result)} previous scores from {latest_date}")
        return result


class PipelineResult:
    """Container for scoring pipeline output."""

    def __init__(
        self,
        composite_results: List[CompositeScore],
        pillar_scores: Dict[str, Dict[str, float]],
        data: Dict,
        weights: Dict[str, float],
    ):
        self.composite_results = composite_results
        self.pillar_scores = pillar_scores
        self.data = data
        self.weights = weights

    @property
    def tickers(self) -> List[str]:
        return [r.ticker for r in self.composite_results]

    def get_score(self, ticker: str) -> Optional[CompositeScore]:
        """Get composite score for a specific ticker."""
        for r in self.composite_results:
            if r.ticker == ticker:
                return r
        return None

    def as_ranked_list(self) -> List[Dict]:
        """Return scores as a ranked list of dicts (rank 1 = best)."""
        return [
            {
                'rank': i + 1,
                'ticker': r.ticker,
                'recommendation': r.recommendation.value,
                'composite_score': r.composite_score,
                'composite_percentile': r.composite_percentile,
                'fundamental': r.fundamental_score,
                'technical': r.technical_score,
                'sentiment': r.sentiment_score,
            }
            for i, r in enumerate(self.composite_results)
        ]
