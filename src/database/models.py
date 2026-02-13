"""
SQLAlchemy ORM models for stock analysis database.

Framework Reference: docs/database_schema.md
"""

from sqlalchemy import (
    Column, String, Numeric, Boolean, DateTime, Date, Text,
    Integer, BigInteger, ForeignKey
)
from sqlalchemy.sql import func
from src.database import Base


class Stock(Base):
    """
    Stock universe management table.

    Tracks which stocks are in the analysis universe.
    """
    __tablename__ = 'stocks'

    ticker = Column(String(10), primary_key=True)
    company_name = Column(String(255))
    sector = Column(String(100))
    industry = Column(String(100))
    market_cap = Column(Numeric(20, 2))
    is_active = Column(Boolean, default=True)
    added_date = Column(DateTime, server_default=func.now())
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())
    notes = Column(Text)

    def __repr__(self):
        return f"<Stock(ticker='{self.ticker}', name='{self.company_name}')>"


class PriceData(Base):
    """
    Daily price history for technical analysis.

    Source: Yahoo Finance (yfinance)
    """
    __tablename__ = 'price_data'

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    date = Column(Date, nullable=False)
    open = Column(Numeric(10, 2))
    high = Column(Numeric(10, 2))
    low = Column(Numeric(10, 2))
    close = Column(Numeric(10, 2))
    adjusted_close = Column(Numeric(10, 2))
    volume = Column(BigInteger)
    data_source = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<PriceData(ticker='{self.ticker}', date='{self.date}', close={self.close})>"


class FundamentalData(Base):
    """
    Fundamental metrics from financial reports.

    Source: Yahoo Finance, Alpha Vantage
    """
    __tablename__ = 'fundamental_data'

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    report_date = Column(Date, nullable=False)
    period_type = Column(String(10))  # 'quarterly' or 'annual'

    # Valuation Metrics
    pe_ratio = Column(Numeric(10, 2))
    forward_pe = Column(Numeric(10, 2))
    pb_ratio = Column(Numeric(10, 2))
    ps_ratio = Column(Numeric(10, 2))
    ev_to_ebitda = Column(Numeric(10, 2))
    peg_ratio = Column(Numeric(10, 2))
    dividend_yield = Column(Numeric(5, 4))

    # Quality Metrics
    roe = Column(Numeric(10, 4))
    roa = Column(Numeric(10, 4))
    net_margin = Column(Numeric(10, 4))
    operating_margin = Column(Numeric(10, 4))
    gross_margin = Column(Numeric(10, 4))
    fcf_to_revenue = Column(Numeric(10, 4))

    # Growth Metrics
    revenue_growth_yoy = Column(Numeric(10, 4))
    eps_growth_yoy = Column(Numeric(10, 4))
    revenue_growth_3y_cagr = Column(Numeric(10, 4))
    fcf_growth_yoy = Column(Numeric(10, 4))
    book_value_growth = Column(Numeric(10, 4))

    # Financial Health
    current_ratio = Column(Numeric(10, 2))
    quick_ratio = Column(Numeric(10, 2))
    debt_to_equity = Column(Numeric(10, 2))
    interest_coverage = Column(Numeric(10, 2))
    cash_to_assets = Column(Numeric(10, 4))

    # Market Data
    beta = Column(Numeric(10, 4))
    shares_outstanding = Column(BigInteger)

    data_source = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<FundamentalData(ticker='{self.ticker}', date='{self.report_date}')>"


class TechnicalIndicator(Base):
    """
    Calculated technical indicators.

    Source: Calculated from price_data or Alpha Vantage
    """
    __tablename__ = 'technical_indicators'

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    date = Column(Date, nullable=False)

    # Moving Averages
    ma_50 = Column(Numeric(10, 2))
    ma_200 = Column(Numeric(10, 2))
    mad = Column(Numeric(10, 4))  # Moving Average Distance

    # Indicators
    rsi = Column(Numeric(5, 2))
    adx = Column(Numeric(5, 2))

    # Volume
    avg_volume_20d = Column(BigInteger)
    avg_volume_90d = Column(BigInteger)

    # Returns
    return_1_month = Column(Numeric(10, 4))
    return_3_month = Column(Numeric(10, 4))
    return_6_month = Column(Numeric(10, 4))
    return_12_1_month = Column(Numeric(10, 4))  # Momentum return

    data_source = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<TechnicalIndicator(ticker='{self.ticker}', date='{self.date}')>"


class SentimentData(Base):
    """
    Stock-specific sentiment indicators.

    Source: Various (Yahoo Finance, Alpha Vantage, others)
    """
    __tablename__ = 'sentiment_data'

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    date = Column(Date, nullable=False)

    # Analyst Data
    analyst_target = Column(Numeric(10, 2))
    analyst_count = Column(Integer)
    recommendation_mean = Column(Numeric(3, 2))

    # Short Interest
    short_interest = Column(Numeric(10, 4))  # % of float
    days_to_cover = Column(Numeric(10, 2))

    # Other
    insider_net_shares = Column(BigInteger)  # Net insider buying (shares)

    data_source = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<SentimentData(ticker='{self.ticker}', date='{self.date}')>"


class StockScore(Base):
    """
    Calculated percentile scores.

    Framework Section 1.2: Percentile ranking system
    """
    __tablename__ = 'stock_scores'

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    calculation_date = Column(Date, nullable=False)

    # Pillar Scores (0-100 percentile)
    fundamental_score = Column(Numeric(5, 2))
    technical_score = Column(Numeric(5, 2))
    sentiment_score = Column(Numeric(5, 2))

    # Sub-component Scores
    value_score = Column(Numeric(5, 2))
    quality_score = Column(Numeric(5, 2))
    growth_score = Column(Numeric(5, 2))

    # Composite Score
    base_composite_score = Column(Numeric(5, 2))
    final_composite_score = Column(Numeric(5, 2))

    # Recommendation
    recommendation = Column(String(20))  # 'Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell'

    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<StockScore(ticker='{self.ticker}', date='{self.calculation_date}', score={self.final_composite_score})>"
