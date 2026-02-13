"""
Data collection modules for stock analysis framework.

Framework Reference: Section 2, 9
Provides collectors for:
- Yahoo Finance (fundamental, technical, analyst data)
- Alpha Vantage (technical indicators, additional fundamental)

Usage:
    from src.data_collection import YahooFinanceCollector, AlphaVantageCollector

    yf = YahooFinanceCollector()
    data = yf.get_stock_data('AAPL')

    av = AlphaVantageCollector(api_key='your_key')
    overview = av.get_company_overview('AAPL')
"""

from src.data_collection.yahoo_finance import YahooFinanceCollector
from src.data_collection.alpha_vantage import AlphaVantageCollector

__all__ = [
    'YahooFinanceCollector',
    'AlphaVantageCollector'
]
