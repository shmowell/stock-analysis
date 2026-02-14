"""
Alpha Vantage data collection module.

Framework Reference: Section 9.2
Collects:
- Additional fundamental data (backup/verification)
- Technical indicators (RSI, ADX, SMA)
- Earnings data

IMPORTANT: Free tier has 5 calls/minute rate limit - must use rate limiter!
"""

import requests
import os
from typing import Dict, Optional, Any
from datetime import datetime
import logging

from utils.rate_limiter import RateLimiter
from utils.validators import (
    validate_numeric,
    validate_api_response,
    is_valid_ticker,
    DataValidationError
)

logger = logging.getLogger(__name__)


class AlphaVantageCollector:
    """
    Collects stock data from Alpha Vantage API.

    Framework Section 9.2: Alpha Vantage provides technical indicators
    and additional fundamental data.

    Rate Limit: 5 calls/minute (free tier)
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Alpha Vantage collector.

        Args:
            api_key: Alpha Vantage API key (defaults to env var)
        """
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_API_KEY')
        if not self.api_key:
            raise ValueError("Alpha Vantage API key not provided")

        # Rate limiter: 5 calls per 60 seconds
        self.rate_limiter = RateLimiter(calls=5, period=60)
        self.logger = logger

    def _make_request(self, params: Dict[str, str]) -> Dict:
        """
        Make rate-limited API request.

        Args:
            params: API request parameters

        Returns:
            API response as dict

        Raises:
            DataValidationError: If request fails
        """
        # Add API key to params
        params['apikey'] = self.api_key

        # Apply rate limiting
        with self.rate_limiter:
            try:
                response = requests.get(self.BASE_URL, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Check for API error messages
                if 'Error Message' in data:
                    raise DataValidationError(f"API Error: {data['Error Message']}")

                if 'Note' in data:
                    # Rate limit message
                    raise DataValidationError(f"Rate limit: {data['Note']}")

                return data

            except requests.exceptions.RequestException as e:
                self.logger.error(f"API request failed: {e}")
                raise DataValidationError(f"API request failed: {e}")

    def get_company_overview(self, ticker: str) -> Dict[str, Any]:
        """
        Get company overview and fundamental data.

        Framework Section 2.1: Fundamental data backup/verification.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict of fundamental metrics
        """
        if not is_valid_ticker(ticker):
            raise DataValidationError(f"Invalid ticker: {ticker}")

        self.logger.info(f"Fetching company overview for {ticker}")

        params = {
            'function': 'OVERVIEW',
            'symbol': ticker
        }

        data = self._make_request(params)

        # Validate response has data
        if not data or 'Symbol' not in data:
            raise DataValidationError(f"No overview data for {ticker}")

        # Extract and validate metrics
        overview = {
            'ticker': ticker,
            'collected_at': datetime.now(),
            'pe_ratio': validate_numeric(data.get('PERatio'), max_value=1000),
            'pb_ratio': validate_numeric(data.get('PriceToBookRatio'), max_value=100),
            'ps_ratio': validate_numeric(data.get('PriceToSalesRatioTTM'), max_value=100),
            'peg_ratio': validate_numeric(data.get('PEGRatio'), max_value=10),
            'dividend_yield': validate_numeric(data.get('DividendYield'), min_value=0, max_value=1),
            'roe': validate_numeric(data.get('ReturnOnEquityTTM'), max_value=1),
            'roa': validate_numeric(data.get('ReturnOnAssetsTTM'), max_value=1),
            'profit_margin': validate_numeric(data.get('ProfitMargin'), max_value=1),
            'operating_margin': validate_numeric(data.get('OperatingMarginTTM'), max_value=1),
            'revenue_growth_yoy': validate_numeric(data.get('QuarterlyRevenueGrowthYOY')),
            'earnings_growth_yoy': validate_numeric(data.get('QuarterlyEarningsGrowthYOY')),
            'beta': validate_numeric(data.get('Beta')),
            '52_week_high': validate_numeric(data.get('52WeekHigh'), min_value=0),
            '52_week_low': validate_numeric(data.get('52WeekLow'), min_value=0),
            'shares_outstanding': validate_numeric(data.get('SharesOutstanding'), min_value=0),
            'eps': validate_numeric(data.get('EPS')),
            'analyst_target': validate_numeric(data.get('AnalystTargetPrice'), min_value=0),
        }

        self.logger.info(f"Successfully fetched overview for {ticker}")
        return overview

    def get_rsi(self, ticker: str, time_period: int = 14) -> Dict[str, Any]:
        """
        Get RSI (Relative Strength Index).

        Framework Section 4: Technical indicators
        Note: RSI used for trend confirmation, not overbought/oversold signals

        Args:
            ticker: Stock ticker
            time_period: RSI calculation period (default 14)

        Returns:
            Dict with latest RSI value and history
        """
        if not is_valid_ticker(ticker):
            raise DataValidationError(f"Invalid ticker: {ticker}")

        self.logger.info(f"Fetching RSI for {ticker}")

        params = {
            'function': 'RSI',
            'symbol': ticker,
            'interval': 'daily',
            'time_period': str(time_period),
            'series_type': 'close'
        }

        data = self._make_request(params)

        # Validate response
        if 'Technical Analysis: RSI' not in data:
            raise DataValidationError(f"No RSI data for {ticker}")

        rsi_data = data['Technical Analysis: RSI']

        # Get latest RSI value
        latest_date = sorted(rsi_data.keys(), reverse=True)[0]
        latest_rsi = validate_numeric(
            rsi_data[latest_date]['RSI'],
            min_value=0,
            max_value=100
        )

        return {
            'ticker': ticker,
            'collected_at': datetime.now(),
            'rsi': latest_rsi,
            'date': latest_date,
            'time_period': time_period
        }

    def get_sma(self, ticker: str, time_period: int = 200) -> Dict[str, Any]:
        """
        Get SMA (Simple Moving Average).

        Framework Section 2.2: Moving averages for trend analysis

        Args:
            ticker: Stock ticker
            time_period: SMA period (50 or 200 typical)

        Returns:
            Dict with latest SMA value
        """
        if not is_valid_ticker(ticker):
            raise DataValidationError(f"Invalid ticker: {ticker}")

        self.logger.info(f"Fetching SMA{time_period} for {ticker}")

        params = {
            'function': 'SMA',
            'symbol': ticker,
            'interval': 'daily',
            'time_period': str(time_period),
            'series_type': 'close'
        }

        data = self._make_request(params)

        # Validate response
        if 'Technical Analysis: SMA' not in data:
            raise DataValidationError(f"No SMA data for {ticker}")

        sma_data = data['Technical Analysis: SMA']

        # Get latest SMA value
        latest_date = sorted(sma_data.keys(), reverse=True)[0]
        latest_sma = validate_numeric(
            sma_data[latest_date]['SMA'],
            min_value=0
        )

        return {
            'ticker': ticker,
            'collected_at': datetime.now(),
            'sma': latest_sma,
            'date': latest_date,
            'time_period': time_period
        }

    def get_adx(self, ticker: str, time_period: int = 14) -> Dict[str, Any]:
        """
        Get ADX (Average Directional Index) for trend strength.

        Framework Section 2.2: ADX measures trend strength (not direction)
        - ADX > 25: Strong trend
        - ADX < 20: Weak/no trend

        Args:
            ticker: Stock ticker
            time_period: ADX calculation period (default 14)

        Returns:
            Dict with latest ADX value
        """
        if not is_valid_ticker(ticker):
            raise DataValidationError(f"Invalid ticker: {ticker}")

        self.logger.info(f"Fetching ADX for {ticker}")

        params = {
            'function': 'ADX',
            'symbol': ticker,
            'interval': 'daily',
            'time_period': str(time_period)
        }

        data = self._make_request(params)

        # Validate response
        if 'Technical Analysis: ADX' not in data:
            raise DataValidationError(f"No ADX data for {ticker}")

        adx_data = data['Technical Analysis: ADX']

        # Get latest ADX value
        latest_date = sorted(adx_data.keys(), reverse=True)[0]
        latest_adx = validate_numeric(
            adx_data[latest_date]['ADX'],
            min_value=0,
            max_value=100
        )

        return {
            'ticker': ticker,
            'collected_at': datetime.now(),
            'adx': latest_adx,
            'date': latest_date,
            'time_period': time_period,
            'strong_trend': latest_adx > 25 if latest_adx else None
        }

    def get_earnings(self, ticker: str) -> Dict[str, Any]:
        """
        Get earnings data and estimates.

        Args:
            ticker: Stock ticker

        Returns:
            Dict with earnings history and estimates
        """
        if not is_valid_ticker(ticker):
            raise DataValidationError(f"Invalid ticker: {ticker}")

        self.logger.info(f"Fetching earnings for {ticker}")

        params = {
            'function': 'EARNINGS',
            'symbol': ticker
        }

        data = self._make_request(params)

        # Validate response
        if 'quarterlyEarnings' not in data:
            raise DataValidationError(f"No earnings data for {ticker}")

        return {
            'ticker': ticker,
            'collected_at': datetime.now(),
            'quarterly_earnings': data.get('quarterlyEarnings', []),
            'annual_earnings': data.get('annualEarnings', [])
        }

    def get_technical_indicators(self, ticker: str) -> Dict[str, Any]:
        """
        Get all technical indicators for a ticker.

        Combines RSI, SMA, and ADX into single dict.
        Uses 3 API calls - be mindful of rate limits!

        Args:
            ticker: Stock ticker

        Returns:
            Dict with all technical indicators
        """
        self.logger.info(f"Fetching all technical indicators for {ticker}")

        indicators = {
            'ticker': ticker,
            'collected_at': datetime.now()
        }

        try:
            # RSI (1 call)
            rsi_data = self.get_rsi(ticker)
            indicators['rsi'] = rsi_data['rsi']

            # SMA 200 (1 call)
            sma_data = self.get_sma(ticker, time_period=200)
            indicators['sma_200'] = sma_data['sma']

            # ADX (1 call)
            adx_data = self.get_adx(ticker)
            indicators['adx'] = adx_data['adx']
            indicators['strong_trend'] = adx_data['strong_trend']

        except DataValidationError as e:
            self.logger.error(f"Error fetching indicators for {ticker}: {e}")
            # Return partial data if some calls fail

        return indicators
