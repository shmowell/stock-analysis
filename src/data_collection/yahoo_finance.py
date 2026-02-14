"""
Yahoo Finance data collection module.

Framework Reference: Section 2.1, 9.1
Collects:
- Fundamental data (valuation, quality, growth, financial health)
- Price history and technical data
- Analyst data

Uses yfinance library - no strict rate limits but respect fair use.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import logging

from utils.validators import (
    validate_numeric,
    validate_percentage,
    validate_ratio,
    is_valid_ticker,
    DataValidationError
)

logger = logging.getLogger(__name__)


class YahooFinanceCollector:
    """
    Collects stock data from Yahoo Finance.

    Framework Section 9.1: Yahoo Finance provides most fundamental
    and technical data needed for the analysis.
    """

    def __init__(self):
        """Initialize Yahoo Finance collector."""
        self.logger = logger

    def get_stock_data(self, ticker: str) -> Dict[str, Any]:
        """
        Get comprehensive stock data for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with all collected data

        Raises:
            DataValidationError: If ticker is invalid or data cannot be fetched
        """
        if not is_valid_ticker(ticker):
            raise DataValidationError(f"Invalid ticker: {ticker}")

        self.logger.info(f"Fetching data for {ticker}")

        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Collect all data
            data = {
                'ticker': ticker,
                'collected_at': datetime.now(),
                'fundamental': self._get_fundamental_data(info),
                'technical': self._get_technical_data(stock),
                'analyst': self._get_analyst_data(info),
                'company_info': self._get_company_info(info)
            }

            self.logger.info(f"Successfully collected data for {ticker}")
            return data

        except Exception as e:
            self.logger.error(f"Error fetching data for {ticker}: {e}")
            raise DataValidationError(f"Failed to fetch data for {ticker}: {e}")

    def _get_fundamental_data(self, info: Dict) -> Dict[str, Optional[float]]:
        """
        Extract fundamental metrics from Yahoo Finance info.

        Framework Section 2.1: Fundamental Data
        - Valuation: P/E, P/B, P/S, EV/EBITDA, PEG, Dividend Yield
        - Quality: ROE, ROA, Margins, FCF/Revenue
        - Growth: Revenue, EPS, Book Value, FCF growth
        - Financial Health: Ratios

        Args:
            info: Yahoo Finance info dict

        Returns:
            Dict of fundamental metrics
        """
        fundamentals = {}

        # Valuation Metrics
        fundamentals['pe_ratio'] = validate_ratio(
            info.get('forwardPE') or info.get('trailingPE'),
            max_value=1000  # Sanity check
        )
        fundamentals['pb_ratio'] = validate_ratio(
            info.get('priceToBook'),
            max_value=100
        )
        fundamentals['ps_ratio'] = validate_ratio(
            info.get('priceToSalesTrailing12Months'),
            max_value=100
        )
        fundamentals['ev_ebitda'] = validate_ratio(
            info.get('enterpriseToEbitda'),
            max_value=1000
        )
        fundamentals['peg_ratio'] = validate_ratio(
            info.get('pegRatio'),
            max_value=10
        )
        fundamentals['dividend_yield'] = validate_percentage(
            info.get('dividendYield'),
            as_decimal=True
        )

        # Quality Metrics
        fundamentals['roe'] = validate_percentage(
            info.get('returnOnEquity'),
            as_decimal=True
        )
        fundamentals['roa'] = validate_percentage(
            info.get('returnOnAssets'),
            as_decimal=True
        )
        fundamentals['net_margin'] = validate_percentage(
            info.get('profitMargins'),
            as_decimal=True
        )
        fundamentals['operating_margin'] = validate_percentage(
            info.get('operatingMargins'),
            as_decimal=True
        )
        fundamentals['gross_margin'] = validate_percentage(
            info.get('grossMargins'),
            as_decimal=True
        )

        # Growth Metrics
        fundamentals['revenue_growth'] = validate_percentage(
            info.get('revenueGrowth'),
            as_decimal=True
        )
        fundamentals['earnings_growth'] = validate_percentage(
            info.get('earningsGrowth'),
            as_decimal=True
        )

        # Financial Health
        fundamentals['current_ratio'] = validate_ratio(
            info.get('currentRatio'),
            max_value=20
        )
        fundamentals['quick_ratio'] = validate_ratio(
            info.get('quickRatio'),
            max_value=20
        )
        fundamentals['debt_to_equity'] = validate_ratio(
            info.get('debtToEquity'),
            max_value=1000  # Some companies have high leverage
        )

        # Market data
        fundamentals['market_cap'] = validate_numeric(
            info.get('marketCap'),
            min_value=0
        )
        fundamentals['beta'] = validate_numeric(
            info.get('beta')
        )

        return fundamentals

    def _get_technical_data(self, stock: yf.Ticker) -> Dict[str, Any]:
        """
        Calculate technical indicators from price history.

        Framework Section 2.2: Technical Data
        - Price history (1 year minimum)
        - Moving averages (50-day, 200-day)
        - MAD (Moving Average Distance)
        - Volume metrics
        - Return metrics (1M, 3M, 6M, 12M)

        Args:
            stock: yfinance Ticker object

        Returns:
            Dict of technical metrics
        """
        technical = {}

        try:
            # Get 1 year of price history
            hist = stock.history(period="1y")

            if hist.empty:
                self.logger.warning(f"No price history available for {stock.ticker}")
                return technical

            # Current price
            technical['current_price'] = validate_numeric(
                hist['Close'].iloc[-1],
                min_value=0
            )

            # Moving averages
            hist['MA_50'] = hist['Close'].rolling(window=50).mean()
            hist['MA_200'] = hist['Close'].rolling(window=200).mean()

            technical['ma_50'] = validate_numeric(
                hist['MA_50'].iloc[-1],
                min_value=0
            )
            technical['ma_200'] = validate_numeric(
                hist['MA_200'].iloc[-1],
                min_value=0
            )

            # Moving Average Distance (MAD)
            # Framework Section 2.2: MAD = (50-day - 200-day) / 200-day
            if technical['ma_50'] and technical['ma_200']:
                technical['mad'] = (technical['ma_50'] - technical['ma_200']) / technical['ma_200']
            else:
                technical['mad'] = None

            # Price position vs 200-day MA
            if technical['current_price'] and technical['ma_200']:
                technical['above_ma_200'] = technical['current_price'] > technical['ma_200']
            else:
                technical['above_ma_200'] = None

            # Volume metrics
            technical['avg_volume_20d'] = validate_numeric(
                hist['Volume'].tail(20).mean(),
                min_value=0
            )
            technical['avg_volume_90d'] = validate_numeric(
                hist['Volume'].tail(90).mean(),
                min_value=0
            )
            technical['current_volume'] = validate_numeric(
                hist['Volume'].iloc[-1],
                min_value=0
            )

            # Return calculations
            # Framework Section 4.2: 12-1 month momentum (excludes most recent month)
            if len(hist) >= 252:  # ~1 year of trading days
                price_12m_ago = hist['Close'].iloc[-252]
                price_1m_ago = hist['Close'].iloc[-21]
                current_price = hist['Close'].iloc[-1]

                technical['return_12_1_month'] = validate_numeric(
                    (price_1m_ago - price_12m_ago) / price_12m_ago
                )
                technical['return_6_month'] = validate_numeric(
                    (current_price - hist['Close'].iloc[-126]) / hist['Close'].iloc[-126]
                )
                technical['return_3_month'] = validate_numeric(
                    (current_price - hist['Close'].iloc[-63]) / hist['Close'].iloc[-63]
                )
                technical['return_1_month'] = validate_numeric(
                    (current_price - price_1m_ago) / price_1m_ago
                )
            else:
                self.logger.warning(f"Insufficient history for return calculations")
                technical['return_12_1_month'] = None
                technical['return_6_month'] = None
                technical['return_3_month'] = None
                technical['return_1_month'] = None

            # Store price history for later use
            technical['price_history'] = hist[['Close', 'Volume']].tail(252).to_dict()

        except Exception as e:
            self.logger.error(f"Error calculating technical data: {e}")

        return technical

    def _get_analyst_data(self, info: Dict) -> Dict[str, Any]:
        """
        Extract analyst data.

        Framework Section 2.3: Sentiment Data
        - Consensus price target
        - Number of analyst opinions
        - Recommendations

        Args:
            info: Yahoo Finance info dict

        Returns:
            Dict of analyst metrics
        """
        analyst = {}

        analyst['target_price'] = validate_numeric(
            info.get('targetMeanPrice'),
            min_value=0
        )
        analyst['target_high'] = validate_numeric(
            info.get('targetHighPrice'),
            min_value=0
        )
        analyst['target_low'] = validate_numeric(
            info.get('targetLowPrice'),
            min_value=0
        )
        analyst['num_analysts'] = validate_numeric(
            info.get('numberOfAnalystOpinions'),
            min_value=0,
            allow_zero=True
        )

        # Recommendation (1=Strong Buy, 5=Strong Sell)
        analyst['recommendation_mean'] = validate_numeric(
            info.get('recommendationMean'),
            min_value=1,
            max_value=5
        )

        return analyst

    def _get_company_info(self, info: Dict) -> Dict[str, Any]:
        """
        Extract company information.

        Args:
            info: Yahoo Finance info dict

        Returns:
            Dict of company info
        """
        return {
            'name': info.get('longName') or info.get('shortName'),
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'country': info.get('country'),
            'website': info.get('website'),
            'description': info.get('longBusinessSummary')
        }

    def get_price_history(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Get historical price data.

        Args:
            ticker: Stock ticker
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)

        Returns:
            DataFrame with price history
        """
        if not is_valid_ticker(ticker):
            raise DataValidationError(f"Invalid ticker: {ticker}")

        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval=interval)

            if hist.empty:
                raise DataValidationError(f"No price history for {ticker}")

            return hist

        except Exception as e:
            self.logger.error(f"Error fetching price history for {ticker}: {e}")
            raise DataValidationError(f"Failed to fetch price history: {e}")
