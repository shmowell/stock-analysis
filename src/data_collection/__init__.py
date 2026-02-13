"""
Data collection modules for stock analysis framework.

Framework Reference: Section 2, 9
Provides collectors for:
- Yahoo Finance (fundamental, technical, analyst data)
- Alpha Vantage (technical indicators, additional fundamental)
- Financial Modeling Prep (analyst estimates, stock grades)

Usage:
    from src.data_collection import YahooFinanceCollector, AlphaVantageCollector, FMPCollector

    yf = YahooFinanceCollector()
    data = yf.get_stock_data('AAPL')

    av = AlphaVantageCollector(api_key='your_key')
    overview = av.get_company_overview('AAPL')

    fmp = FMPCollector()
    grades = fmp.get_stock_grades('AAPL')
"""

from src.data_collection.yahoo_finance import YahooFinanceCollector
from src.data_collection.alpha_vantage import AlphaVantageCollector
from src.data_collection.fmp import FMPCollector

__all__ = [
    'YahooFinanceCollector',
    'AlphaVantageCollector',
    'FMPCollector'
]
