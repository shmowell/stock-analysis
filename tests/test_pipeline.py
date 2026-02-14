"""
Tests for ScoringPipeline.

Tests data preparation methods and PipelineResult container.
Scoring logic is tested via existing calculator tests;
these tests focus on the pipeline orchestration layer.
"""

import pytest
from unittest.mock import MagicMock, patch

from scoring.pipeline import ScoringPipeline, PipelineResult
from models.composite import CompositeScore, Recommendation


class TestPipelineDataPreparation:
    """Tests for the static data preparation methods."""

    def test_prepare_fundamental_maps_field_names(self):
        """Verify field name mapping from DB format to calculator format."""
        records = {
            'AAPL': {
                'pe_ratio': 28.5,
                'pb_ratio': 10.0,
                'ps_ratio': 7.0,
                'ev_to_ebitda': 22.0,
                'dividend_yield': 0.005,
                'roe': 0.80,
                'roa': 0.25,
                'net_margin': 0.25,
                'operating_margin': 0.30,
                'gross_margin': 0.45,
                'revenue_growth_yoy': 0.08,
                'eps_growth_yoy': 0.12,
            }
        }
        stock_data, universe = ScoringPipeline._prepare_fundamental(records)
        assert 'AAPL' in stock_data
        # ev_to_ebitda -> ev_ebitda
        assert stock_data['AAPL']['ev_ebitda'] == 22.0
        # revenue_growth_yoy -> revenue_growth
        assert stock_data['AAPL']['revenue_growth'] == 0.08
        # Universe should have values
        assert 'pe_ratio' in universe

    def test_prepare_fundamental_handles_none(self):
        records = {
            'AAPL': {'pe_ratio': None, 'pb_ratio': 10.0,
                     'ps_ratio': None, 'ev_to_ebitda': None,
                     'dividend_yield': None, 'roe': None, 'roa': None,
                     'net_margin': None, 'operating_margin': None,
                     'gross_margin': None, 'revenue_growth_yoy': None,
                     'eps_growth_yoy': None}
        }
        stock_data, universe = ScoringPipeline._prepare_fundamental(records)
        assert stock_data['AAPL']['pe_ratio'] is None
        # pe_ratio should not appear in universe (no valid values)
        assert 'pe_ratio' not in universe
        # pb_ratio has a value
        assert 'pb_ratio' in universe

    def test_prepare_technical_computes_uptrends(self):
        records = {
            'AAPL': {
                'current_price': 185.0,
                'sma_20': 180.0,
                'sma_50': 175.0,
                'sma_200': 170.0,
                'momentum_12_1': 0.15,
                'momentum_6m': 0.10,
                'momentum_3m': 0.05,
                'momentum_1m': 0.02,
                'mad': 0.05,
                'rsi_14': 55.0,
                'adx': 25.0,
                'avg_volume_20d': 50000000.0,
                'relative_volume': 1.2,
                'sector_relative_6m': 0.03,
            }
        }
        stock_data, universe = ScoringPipeline._prepare_technical(records)

        # Price > SMA20 > SMA50 => short_term_uptrend
        assert stock_data['AAPL']['short_term_uptrend'] is True
        # Price > SMA50 > SMA200 => long_term_uptrend
        assert stock_data['AAPL']['long_term_uptrend'] is True

    def test_prepare_technical_downtrend(self):
        records = {
            'AAPL': {
                'current_price': 160.0,
                'sma_20': 170.0,
                'sma_50': 175.0,
                'sma_200': 180.0,
            }
        }
        stock_data, _ = ScoringPipeline._prepare_technical(records)
        assert stock_data['AAPL']['short_term_uptrend'] is False
        assert stock_data['AAPL']['long_term_uptrend'] is False

    def test_prepare_technical_missing_sma(self):
        records = {
            'AAPL': {
                'current_price': 185.0,
                'sma_20': None,
                'sma_50': None,
                'sma_200': None,
            }
        }
        stock_data, _ = ScoringPipeline._prepare_technical(records)
        assert stock_data['AAPL']['short_term_uptrend'] is None
        assert stock_data['AAPL']['long_term_uptrend'] is None

    def test_prepare_sentiment_computes_recommendation_mean(self):
        records = {
            'AAPL': {
                'num_buy_ratings': 30,
                'num_hold_ratings': 10,
                'num_sell_ratings': 5,
                'consensus_price_target': 200.0,
                'num_analyst_opinions': 45,
                'market_cap': 3000000000000,
                'insider_net_shares_6m': -500000,
                'upgrades_30d': 3,
                'downgrades_30d': 1,
                'estimate_revisions_up_90d': 5,
                'estimate_revisions_down_90d': 2,
                'days_to_cover': 2.5,
                'short_interest_pct': 0.01,
                'insider_buys_6m': 2,
                'insider_sells_6m': 5,
            }
        }
        stock_data, universe = ScoringPipeline._prepare_sentiment(records)
        # recommendation_mean = (30*1 + 10*3 + 5*5) / 45 = (30+30+25)/45 = 85/45 ≈ 1.889
        assert abs(stock_data['AAPL']['recommendation_mean'] - 1.889) < 0.01

    def test_prepare_sentiment_no_ratings(self):
        records = {
            'AAPL': {
                'num_buy_ratings': 0,
                'num_hold_ratings': 0,
                'num_sell_ratings': 0,
                'consensus_price_target': None,
                'num_analyst_opinions': None,
                'market_cap': None,
                'insider_net_shares_6m': None,
                'upgrades_30d': None,
                'downgrades_30d': None,
                'estimate_revisions_up_90d': None,
                'estimate_revisions_down_90d': None,
                'days_to_cover': None,
                'short_interest_pct': None,
                'insider_buys_6m': None,
                'insider_sells_6m': None,
            }
        }
        stock_data, _ = ScoringPipeline._prepare_sentiment(records)
        assert stock_data['AAPL']['recommendation_mean'] is None

    def test_prepare_sentiment_field_mapping(self):
        records = {
            'AAPL': {
                'num_buy_ratings': 10,
                'num_hold_ratings': 5,
                'num_sell_ratings': 2,
                'consensus_price_target': 200.0,
                'num_analyst_opinions': 17,
                'market_cap': 3e12,
                'insider_net_shares_6m': -100000,
                'upgrades_30d': 2,
                'downgrades_30d': 1,
                'estimate_revisions_up_90d': 4,
                'estimate_revisions_down_90d': 1,
                'days_to_cover': 2.0,
                'short_interest_pct': 0.01,
                'insider_buys_6m': 1,
                'insider_sells_6m': 3,
            }
        }
        stock_data, _ = ScoringPipeline._prepare_sentiment(records)
        # Verify field mapping
        assert stock_data['AAPL']['analyst_target'] == 200.0
        assert stock_data['AAPL']['analyst_count'] == 17
        assert stock_data['AAPL']['insider_net_shares'] == -100000


class TestPipelineResult:
    """Tests for the PipelineResult container."""

    def _make_result(self):
        scores = [
            CompositeScore('AAPL', 50.0, 60.0, 55.0, 55.0, 70.0, Recommendation.BUY),
            CompositeScore('GOOGL', 55.0, 65.0, 50.0, 57.0, 80.0, Recommendation.BUY),
            CompositeScore('PG', 40.0, 30.0, 45.0, 38.0, 20.0, Recommendation.SELL),
        ]
        pillar = {
            'AAPL': {'fundamental': 50.0, 'technical': 60.0, 'sentiment': 55.0},
            'GOOGL': {'fundamental': 55.0, 'technical': 65.0, 'sentiment': 50.0},
            'PG': {'fundamental': 40.0, 'technical': 30.0, 'sentiment': 45.0},
        }
        return PipelineResult(
            composite_results=scores,
            pillar_scores=pillar,
            data={'tickers': ['AAPL', 'GOOGL', 'PG']},
            weights={'fundamental': 0.45, 'technical': 0.35, 'sentiment': 0.20},
        )

    def test_tickers_property(self):
        result = self._make_result()
        assert result.tickers == ['AAPL', 'GOOGL', 'PG']

    def test_get_score_found(self):
        result = self._make_result()
        score = result.get_score('AAPL')
        assert score is not None
        assert score.ticker == 'AAPL'

    def test_get_score_not_found(self):
        result = self._make_result()
        assert result.get_score('TSLA') is None

    def test_as_ranked_list(self):
        result = self._make_result()
        ranked = result.as_ranked_list()
        assert len(ranked) == 3
        assert ranked[0]['rank'] == 1
        assert ranked[0]['ticker'] == 'AAPL'
        assert 'composite_score' in ranked[0]
        assert 'recommendation' in ranked[0]

    def test_weights_preserved(self):
        result = self._make_result()
        assert result.weights['fundamental'] == 0.45


class TestPipelineInit:
    """Tests for ScoringPipeline initialization."""

    def test_default_weights(self):
        pipeline = ScoringPipeline(verbose=False)
        assert pipeline.weights == {'fundamental': 0.45, 'technical': 0.35, 'sentiment': 0.20}

    def test_custom_weights(self):
        w = {'fundamental': 0.50, 'technical': 0.30, 'sentiment': 0.20}
        pipeline = ScoringPipeline(weights=w, verbose=False)
        assert pipeline.weights == w

    def test_verbose_flag(self):
        pipeline = ScoringPipeline(verbose=False)
        assert pipeline.verbose is False


class TestPipelineValidation:
    """Tests for score validation."""

    def test_validate_scores_valid(self):
        pipeline = ScoringPipeline(verbose=False)
        scores = {'AAPL': {'fundamental': 50.0, 'technical': 75.0, 'sentiment': 60.0}}
        # Should not raise
        pipeline._validate_scores(scores)

    def test_validate_scores_out_of_range(self):
        pipeline = ScoringPipeline(verbose=False)
        scores = {'AAPL': {'fundamental': 105.0, 'technical': 75.0, 'sentiment': 60.0}}
        with pytest.raises(ValueError, match="out of valid range"):
            pipeline._validate_scores(scores)

    def test_validate_scores_negative(self):
        pipeline = ScoringPipeline(verbose=False)
        scores = {'AAPL': {'fundamental': -5.0, 'technical': 75.0, 'sentiment': 60.0}}
        with pytest.raises(ValueError, match="out of valid range"):
            pipeline._validate_scores(scores)

    def test_validate_scores_boundary_values(self):
        pipeline = ScoringPipeline(verbose=False)
        scores = {'AAPL': {'fundamental': 0.0, 'technical': 100.0, 'sentiment': 50.0}}
        # Should not raise
        pipeline._validate_scores(scores)
