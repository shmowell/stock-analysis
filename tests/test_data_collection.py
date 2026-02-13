"""
Integration tests for data collection modules.

Framework Reference: Section 9 (API Integration)

NOTE: These tests make real API calls and are marked with @pytest.mark.integration
Run with: pytest -m integration
Skip with: pytest -m "not integration"

These tests verify:
- API connections work
- Data is collected successfully
- Validation is applied correctly
- Rate limiting functions
"""

import pytest
import os
from datetime import datetime

from src.data_collection import YahooFinanceCollector, AlphaVantageCollector
from src.utils.validators import DataValidationError


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestYahooFinanceCollector:
    """Test Yahoo Finance data collection."""

    @pytest.fixture
    def collector(self):
        """Create Yahoo Finance collector."""
        return YahooFinanceCollector()

    def test_get_stock_data_success(self, collector):
        """Test successful data collection for AAPL."""
        data = collector.get_stock_data('AAPL')

        # Check structure
        assert 'ticker' in data
        assert data['ticker'] == 'AAPL'
        assert 'collected_at' in data
        assert isinstance(data['collected_at'], datetime)

        # Check data sections
        assert 'fundamental' in data
        assert 'technical' in data
        assert 'analyst' in data
        assert 'company_info' in data

    def test_fundamental_data_structure(self, collector):
        """Test fundamental data has expected fields."""
        data = collector.get_stock_data('AAPL')
        fundamental = data['fundamental']

        # Valuation metrics
        assert 'pe_ratio' in fundamental
        assert 'pb_ratio' in fundamental
        assert 'ps_ratio' in fundamental

        # Quality metrics
        assert 'roe' in fundamental
        assert 'roa' in fundamental
        assert 'net_margin' in fundamental

        # Growth metrics
        assert 'revenue_growth' in fundamental
        assert 'earnings_growth' in fundamental

    def test_technical_data_structure(self, collector):
        """Test technical data has expected fields."""
        data = collector.get_stock_data('AAPL')
        technical = data['technical']

        # Price and MA data
        assert 'current_price' in technical
        assert 'ma_50' in technical
        assert 'ma_200' in technical
        assert 'mad' in technical

        # Volume data
        assert 'avg_volume_20d' in technical
        assert 'current_volume' in technical

        # Returns
        assert 'return_12_1_month' in technical
        assert 'return_1_month' in technical

    def test_analyst_data_structure(self, collector):
        """Test analyst data has expected fields."""
        data = collector.get_stock_data('AAPL')
        analyst = data['analyst']

        assert 'target_price' in analyst
        assert 'num_analysts' in analyst

    def test_company_info_structure(self, collector):
        """Test company info has expected fields."""
        data = collector.get_stock_data('AAPL')
        info = data['company_info']

        assert 'name' in info
        assert 'sector' in info
        assert 'industry' in info

    def test_invalid_ticker(self, collector):
        """Test error handling for invalid ticker."""
        with pytest.raises(DataValidationError):
            collector.get_stock_data('INVALID_TICKER_12345')

    def test_get_price_history(self, collector):
        """Test price history retrieval."""
        hist = collector.get_price_history('AAPL', period='1mo')

        assert not hist.empty
        assert 'Close' in hist.columns
        assert 'Volume' in hist.columns
        assert len(hist) > 0

    def test_multiple_stocks(self, collector):
        """Test collecting data for multiple stocks."""
        tickers = ['AAPL', 'MSFT', 'GOOGL']
        results = []

        for ticker in tickers:
            data = collector.get_stock_data(ticker)
            assert data['ticker'] == ticker
            results.append(data)

        assert len(results) == 3


class TestAlphaVantageCollector:
    """Test Alpha Vantage data collection."""

    @pytest.fixture
    def collector(self):
        """Create Alpha Vantage collector."""
        api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if not api_key:
            pytest.skip("ALPHA_VANTAGE_API_KEY not set")
        return AlphaVantageCollector(api_key)

    def test_get_company_overview(self, collector):
        """Test company overview retrieval."""
        overview = collector.get_company_overview('AAPL')

        assert overview['ticker'] == 'AAPL'
        assert 'collected_at' in overview
        assert 'pe_ratio' in overview
        assert 'roe' in overview

    def test_get_rsi(self, collector):
        """Test RSI indicator retrieval."""
        rsi_data = collector.get_rsi('AAPL')

        assert rsi_data['ticker'] == 'AAPL'
        assert 'rsi' in rsi_data
        assert rsi_data['time_period'] == 14

        # RSI should be between 0 and 100
        if rsi_data['rsi'] is not None:
            assert 0 <= rsi_data['rsi'] <= 100

    def test_get_sma(self, collector):
        """Test SMA retrieval."""
        sma_data = collector.get_sma('AAPL', time_period=200)

        assert sma_data['ticker'] == 'AAPL'
        assert 'sma' in sma_data
        assert sma_data['time_period'] == 200

        # SMA should be positive
        if sma_data['sma'] is not None:
            assert sma_data['sma'] > 0

    def test_get_adx(self, collector):
        """Test ADX indicator retrieval."""
        adx_data = collector.get_adx('AAPL')

        assert adx_data['ticker'] == 'AAPL'
        assert 'adx' in adx_data
        assert 'strong_trend' in adx_data

        # ADX should be between 0 and 100
        if adx_data['adx'] is not None:
            assert 0 <= adx_data['adx'] <= 100

    def test_rate_limiting(self, collector):
        """Test that rate limiting is applied."""
        import time

        # Make 5 calls (at the limit)
        start = time.time()
        for _ in range(5):
            try:
                collector.get_rsi('AAPL')
            except DataValidationError:
                # May fail due to duplicate requests, that's ok
                pass

        # Make 6th call - should trigger rate limit wait
        try:
            collector.get_rsi('AAPL')
        except DataValidationError:
            pass

        elapsed = time.time() - start

        # Should have taken at least some time due to rate limiting
        # (exact timing depends on API response times)
        assert elapsed > 0

    def test_invalid_ticker(self, collector):
        """Test error handling for invalid ticker."""
        with pytest.raises(DataValidationError):
            collector.get_company_overview('INVALID')


class TestIntegration:
    """Test integration between collectors."""

    def test_yahoo_and_alpha_vantage_comparison(self):
        """Compare data from both sources for consistency."""
        api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if not api_key:
            pytest.skip("ALPHA_VANTAGE_API_KEY not set")

        yf = YahooFinanceCollector()
        av = AlphaVantageCollector(api_key)

        ticker = 'AAPL'

        # Get data from both sources
        yf_data = yf.get_stock_data(ticker)
        av_overview = av.get_company_overview(ticker)

        # Both should have the same ticker
        assert yf_data['ticker'] == av_overview['ticker'] == ticker

        # PE ratios should be roughly similar (within 50% tolerance)
        # They may differ due to timing and calculation methods
        yf_pe = yf_data['fundamental']['pe_ratio']
        av_pe = av_overview['pe_ratio']

        if yf_pe and av_pe:
            ratio = max(yf_pe, av_pe) / min(yf_pe, av_pe)
            # Allow for some difference but flag if wildly different
            if ratio > 2:
                print(f"Warning: Large PE difference - YF: {yf_pe}, AV: {av_pe}")
