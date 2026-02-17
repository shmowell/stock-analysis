"""Unit tests for the ScoreExplainer module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure src/ is on path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from scoring.explainer import ScoreExplainer, _fmt, _score_label


# ------------------------------------------------------------------
# Helper function tests
# ------------------------------------------------------------------

class TestFmt:
    def test_none(self):
        assert _fmt(None) == 'N/A'

    def test_basic(self):
        assert _fmt(14.23) == '14.2'

    def test_pct(self):
        assert _fmt(0.253, 1, pct=True) == '25.3%'

    def test_prefix(self):
        assert _fmt(100, 0, prefix='$') == '$100'

    def test_decimals(self):
        assert _fmt(3.14159, 3) == '3.142'


class TestScoreLabel:
    def test_none(self):
        assert _score_label(None) == 'no data'

    def test_strong(self):
        assert _score_label(80) == 'strong'

    def test_above_average(self):
        assert _score_label(65) == 'above average'

    def test_moderate(self):
        assert _score_label(50) == 'moderate'

    def test_below_average(self):
        assert _score_label(30) == 'below average'

    def test_weak(self):
        assert _score_label(10) == 'weak'


# ------------------------------------------------------------------
# ScoreExplainer tests with mock DB data
# ------------------------------------------------------------------

def _mock_session(fund_data=None, tech_data=None, sent_data=None,
                  market_data=None, price=None, stock=None):
    """Create a mock session that returns specified data from queries."""
    session = MagicMock()

    # Build a flexible query mock
    def make_query_mock(*models):
        qm = MagicMock()

        model = models[0] if models else None
        model_name = model.__name__ if hasattr(model, '__name__') else str(model)

        if model_name == 'FundamentalData':
            qm.filter_by.return_value.first.return_value = fund_data
        elif model_name == 'TechnicalIndicator':
            qm.filter_by.return_value.order_by.return_value.first.return_value = tech_data
        elif model_name == 'SentimentData':
            qm.filter_by.return_value.first.return_value = sent_data
        elif model_name == 'MarketSentiment':
            qm.order_by.return_value.first.return_value = market_data
        elif model_name == 'PriceData':
            qm.filter_by.return_value.order_by.return_value.first.return_value = price
        elif model_name == 'Stock':
            qm.filter_by.return_value.first.return_value = stock
        else:
            qm.filter_by.return_value.first.return_value = None

        return qm

    session.query.side_effect = make_query_mock
    return session


def _make_fund_row(**kwargs):
    row = MagicMock()
    defaults = {
        'pe_ratio': 14.2, 'pb_ratio': 2.1, 'ps_ratio': 3.5,
        'ev_to_ebitda': 11.0, 'dividend_yield': 0.025,
        'roe': 0.253, 'roa': 0.105, 'net_margin': 0.181,
        'operating_margin': 0.22, 'gross_margin': 0.55,
        'revenue_growth_yoy': 0.042, 'eps_growth_yoy': 0.081,
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def _make_tech_row(**kwargs):
    row = MagicMock()
    defaults = {
        'momentum_12_1': 0.183, 'momentum_6m': 0.12, 'momentum_3m': 0.05,
        'momentum_1m': 0.02, 'sma_20': 145.0, 'sma_50': 142.0,
        'sma_200': 131.0, 'mad': 0.084, 'price_vs_200ma': True,
        'relative_volume': 0.95, 'rsi_14': 58.3, 'adx': 25.0,
        'sector_relative_6m': 0.052,
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def _make_sent_row(**kwargs):
    row = MagicMock()
    defaults = {
        'days_to_cover': 2.1, 'consensus_price_target': 165.0,
        'num_buy_ratings': 15, 'num_hold_ratings': 8, 'num_sell_ratings': 2,
        'num_analyst_opinions': 25, 'upgrades_30d': 3, 'downgrades_30d': 1,
        'estimate_revisions_up_90d': 12, 'estimate_revisions_down_90d': 3,
        'insider_buys_6m': 2, 'insider_sells_6m': 5,
        'insider_net_shares_6m': -50000, 'short_interest_pct': 0.032,
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def _make_market_row():
    row = MagicMock()
    row.market_sentiment_score = 52.06
    row.num_indicators_available = 3
    row.vix_score = 55.0
    row.putcall_score = 48.0
    row.fund_flows_score = 53.0
    row.aaii_score = None
    row.vix_value = 18.5
    row.putcall_ratio = 0.92
    row.date = '2026-02-14'
    return row


def _make_price_row(close=150.0):
    row = MagicMock()
    row.close = close
    return row


def _make_stock_row(market_cap=50e9):
    row = MagicMock()
    row.market_cap = market_cap
    row.ticker = 'JNJ'
    return row


SUB_COMPONENTS = {
    'fundamental': {
        'value_score': 56.5, 'quality_score': 57.0, 'growth_score': 48.0,
    },
    'technical': {
        'momentum_score': 75.0, 'trend_score': 87.5,
        'volume_qualified_score': 85.0, 'relative_strength_score': 81.0,
        'rsi_score': 100.0, 'multi_speed_score': 100.0,
    },
    'sentiment': {
        'market_sentiment': 52.0, 'stock_sentiment': 46.3,
        'short_interest_score': 50.0, 'revision_score': 75.0,
        'consensus_score': 35.0, 'insider_score': 40.0,
    },
}


class TestExplainFull:
    """Test the full explain() output with mock data."""

    def test_returns_all_keys(self):
        session = _mock_session(
            fund_data=_make_fund_row(),
            tech_data=_make_tech_row(),
            sent_data=_make_sent_row(),
            market_data=_make_market_row(),
            price=_make_price_row(),
            stock=_make_stock_row(),
        )
        explainer = ScoreExplainer()
        result = explainer.explain('JNJ', SUB_COMPONENTS, session)

        assert 'fundamental' in result
        assert 'technical' in result
        assert 'sentiment' in result
        assert set(result['fundamental'].keys()) == {'value', 'quality', 'growth'}
        assert set(result['technical'].keys()) == {
            'momentum', 'trend', 'volume_qualified',
            'relative_strength', 'rsi', 'multi_speed',
        }
        assert set(result['sentiment'].keys()) == {
            'market', 'stock', 'short_interest',
            'revision', 'consensus', 'insider',
        }

    def test_all_values_are_strings(self):
        session = _mock_session(
            fund_data=_make_fund_row(),
            tech_data=_make_tech_row(),
            sent_data=_make_sent_row(),
            market_data=_make_market_row(),
            price=_make_price_row(),
            stock=_make_stock_row(),
        )
        explainer = ScoreExplainer()
        result = explainer.explain('JNJ', SUB_COMPONENTS, session)

        for pillar, sub in result.items():
            for key, text in sub.items():
                assert isinstance(text, str), f"{pillar}.{key} is not a string: {type(text)}"
                assert len(text) > 0, f"{pillar}.{key} is empty"


class TestFundamentalExplanations:
    def _explain(self, **kwargs):
        explainer = ScoreExplainer()
        fund = _make_fund_row(**kwargs) if kwargs.get('with_data', True) else None
        return explainer._explain_value(
            explainer._load_fundamental.__func__.__get__(None, None) if fund is None else
            {k: float(getattr(fund, k)) if getattr(fund, k) is not None else None
             for k in ['pe_ratio', 'pb_ratio', 'ps_ratio', 'ev_to_ebitda',
                        'dividend_yield', 'roe', 'roa', 'net_margin',
                        'operating_margin', 'gross_margin',
                        'revenue_growth_yoy', 'eps_growth_yoy']},
            56.5,
        )

    def test_value_contains_pe(self):
        explainer = ScoreExplainer()
        data = {
            'pe_ratio': 14.2, 'pb_ratio': 2.1, 'ps_ratio': 3.5,
            'ev_to_ebitda': 11.0, 'dividend_yield': 0.025,
            'roe': 0.253, 'roa': 0.105, 'net_margin': 0.181,
            'operating_margin': 0.22, 'gross_margin': 0.55,
            'revenue_growth_yoy': 0.042, 'eps_growth_yoy': 0.081,
        }
        result = explainer._explain_value(data, 56.5)
        assert 'P/E' in result
        assert '14.2' in result
        assert 'moderate' in result

    def test_value_no_data(self):
        explainer = ScoreExplainer()
        result = explainer._explain_value(None, None)
        assert 'No fundamental data' in result

    def test_quality_contains_roe(self):
        explainer = ScoreExplainer()
        data = {
            'roe': 0.253, 'roa': 0.105, 'net_margin': 0.181,
            'operating_margin': 0.22, 'gross_margin': 0.55,
        }
        result = explainer._explain_quality(data, 57.0)
        assert 'ROE' in result
        assert '25.3%' in result

    def test_growth_contains_revenue(self):
        explainer = ScoreExplainer()
        data = {'revenue_growth_yoy': 0.042, 'eps_growth_yoy': 0.081}
        result = explainer._explain_growth(data, 48.0)
        assert 'Revenue' in result
        assert '4.2%' in result


class TestTechnicalExplanations:
    def test_momentum(self):
        explainer = ScoreExplainer()
        data = {'momentum_12_1': 0.183}
        result = explainer._explain_momentum(data, 75.0)
        assert '18.3%' in result
        assert 'strong' in result

    def test_momentum_negative(self):
        explainer = ScoreExplainer()
        data = {'momentum_12_1': -0.10}
        result = explainer._explain_momentum(data, 20.0)
        assert '-10.0%' in result
        assert 'lost' in result

    def test_trend_uptrend(self):
        explainer = ScoreExplainer()
        data = {
            'price_vs_200ma': True, 'sma_50': 142.0,
            'sma_200': 131.0, 'mad': 0.084,
        }
        result = explainer._explain_trend(data, 87.5)
        assert 'above 200-day MA' in result

    def test_volume_low(self):
        explainer = ScoreExplainer()
        data = {'relative_volume': 0.95}
        result = explainer._explain_volume_qualified(data, 85.0)
        assert 'low' in result
        assert 'bonus' in result

    def test_volume_high(self):
        explainer = ScoreExplainer()
        data = {'relative_volume': 2.5}
        result = explainer._explain_volume_qualified(data, 55.0)
        assert 'high' in result
        assert 'penalty' in result

    def test_rsi_above_50(self):
        explainer = ScoreExplainer()
        data = {'rsi_14': 58.3}
        result = explainer._explain_rsi(data, 100.0)
        assert '58.3' in result
        assert 'uptrend' in result

    def test_rsi_below_50(self):
        explainer = ScoreExplainer()
        data = {'rsi_14': 42.0}
        result = explainer._explain_rsi(data, 0.0)
        assert '42.0' in result
        assert 'no uptrend' in result

    def test_relative_strength_positive(self):
        explainer = ScoreExplainer()
        data = {'sector_relative_6m': 0.052}
        result = explainer._explain_relative_strength(data, 81.0)
        assert 'Outperformed' in result
        assert '5.2pp' in result

    def test_relative_strength_negative(self):
        explainer = ScoreExplainer()
        data = {'sector_relative_6m': -0.03}
        result = explainer._explain_relative_strength(data, 25.0)
        assert 'Underperformed' in result

    def test_multi_speed_both_up(self):
        explainer = ScoreExplainer()
        data = {'sma_20': 150.0, 'sma_50': 145.0, 'sma_200': 130.0}
        result = explainer._explain_multi_speed(data, 100.0)
        assert 'Both' in result

    def test_multi_speed_none(self):
        explainer = ScoreExplainer()
        data = {'sma_20': 130.0, 'sma_50': 145.0, 'sma_200': 150.0}
        result = explainer._explain_multi_speed(data, 0.0)
        assert 'Neither' in result


class TestSentimentExplanations:
    def test_market_sentiment(self):
        explainer = ScoreExplainer()
        data = {
            'market_sentiment_score': 52.06, 'num_indicators_available': 3,
            'vix_value': 18.5, 'putcall_ratio': 0.92,
        }
        result = explainer._explain_market_sentiment(data, 52.0)
        assert '3/4' in result
        assert 'VIX' in result

    def test_short_interest_normal(self):
        explainer = ScoreExplainer()
        data = {'days_to_cover': 2.1, 'short_interest_pct': 0.032}
        result = explainer._explain_short_interest(data, 50.0)
        assert 'normal' in result
        assert '2.1' in result

    def test_short_interest_squeeze(self):
        explainer = ScoreExplainer()
        data = {'days_to_cover': 9.5, 'short_interest_pct': 0.15}
        result = explainer._explain_short_interest(data, 60.0)
        assert 'contrarian' in result

    def test_revision_with_data(self):
        explainer = ScoreExplainer()
        data = {
            'estimate_revisions_up_90d': 12, 'estimate_revisions_down_90d': 3,
            'num_buy_ratings': None, 'num_hold_ratings': None, 'num_sell_ratings': None,
        }
        result = explainer._explain_revision(data, 75.0)
        assert '12' in result
        assert '3' in result
        assert '80%' in result

    def test_revision_fallback(self):
        explainer = ScoreExplainer()
        data = {
            'estimate_revisions_up_90d': None, 'estimate_revisions_down_90d': None,
            'num_buy_ratings': 15, 'num_hold_ratings': 8, 'num_sell_ratings': 2,
        }
        result = explainer._explain_revision(data, 50.0)
        assert 'proxy' in result
        assert '15 Buy' in result

    def test_consensus_large_cap(self):
        explainer = ScoreExplainer()
        data = {'consensus_price_target': 165.0}
        result = explainer._explain_consensus(data, 150.0, 50e9, 35.0)
        assert 'large-cap' in result
        assert '5%' in result
        assert '$165' in result

    def test_consensus_no_target(self):
        explainer = ScoreExplainer()
        data = {'consensus_price_target': None}
        result = explainer._explain_consensus(data, 150.0, 50e9, 50.0)
        assert 'No analyst price target' in result

    def test_insider_selling(self):
        explainer = ScoreExplainer()
        data = {'insider_buys_6m': 2, 'insider_sells_6m': 5, 'insider_net_shares_6m': -50000}
        result = explainer._explain_insider(data, 40.0)
        assert 'selling' in result
        assert '-50,000' in result

    def test_insider_buying(self):
        explainer = ScoreExplainer()
        data = {'insider_buys_6m': 8, 'insider_sells_6m': 1, 'insider_net_shares_6m': 200000}
        result = explainer._explain_insider(data, 75.0)
        assert 'buying' in result
        assert '+200,000' in result

    def test_no_data_fallbacks(self):
        explainer = ScoreExplainer()
        assert 'No sentiment data' in explainer._explain_short_interest(None, 50.0)
        assert 'No sentiment data' in explainer._explain_revision(None, 50.0)
        assert 'No sentiment data' in explainer._explain_consensus(None, 150.0, 50e9, 50.0)
        assert 'No sentiment data' in explainer._explain_insider(None, 50.0)
        assert 'No technical data' in explainer._explain_momentum(None, 50.0)
        assert 'No market sentiment' in explainer._explain_market_sentiment(None, 50.0)
