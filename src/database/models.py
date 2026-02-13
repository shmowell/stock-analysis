"""
SQLAlchemy ORM models for stock analysis database.

Framework Reference: docs/database_schema.md
"""

from sqlalchemy import (
    Column, String, Numeric, Boolean, DateTime, Date, Text,
    Integer, BigInteger, ForeignKey, UniqueConstraint
)
from sqlalchemy.sql import func
from . import Base


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
    calculation_date = Column(Date, nullable=False)

    # Moving Averages
    sma_20 = Column(Numeric(10, 2))
    sma_50 = Column(Numeric(10, 2))
    sma_200 = Column(Numeric(10, 2))
    mad = Column(Numeric(10, 6))  # Moving Average Distance
    price_vs_200ma = Column(Boolean)  # Price above/below 200-day MA

    # Indicators
    rsi_14 = Column(Numeric(10, 2))
    adx = Column(Numeric(10, 2))

    # Volume
    avg_volume_20d = Column(BigInteger)
    avg_volume_90d = Column(BigInteger)
    relative_volume = Column(Numeric(10, 4))

    # Returns (Momentum)
    momentum_1m = Column(Numeric(10, 6))
    momentum_3m = Column(Numeric(10, 6))
    momentum_6m = Column(Numeric(10, 6))
    momentum_12_1 = Column(Numeric(10, 6))  # 12-1 month momentum
    sector_relative_6m = Column(Numeric(10, 6))

    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<TechnicalIndicator(ticker='{self.ticker}', date='{self.calculation_date}')>"


class SentimentData(Base):
    """
    Stock-specific sentiment indicators.

    Source: Various (Yahoo Finance, Alpha Vantage, others)
    """
    __tablename__ = 'sentiment_data'

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    data_date = Column(Date, nullable=False)

    # Analyst Data
    consensus_price_target = Column(Numeric(10, 2))
    num_buy_ratings = Column(Integer)
    num_hold_ratings = Column(Integer)
    num_sell_ratings = Column(Integer)
    num_analyst_opinions = Column(Integer)
    upgrades_30d = Column(Integer)
    downgrades_30d = Column(Integer)
    estimate_revisions_up_90d = Column(Integer)
    estimate_revisions_down_90d = Column(Integer)

    # Short Interest
    short_interest_pct = Column(Numeric(10, 4))  # % of float
    days_to_cover = Column(Numeric(10, 2))

    # Insider Activity
    insider_buys_6m = Column(Integer)
    insider_sells_6m = Column(Integer)
    insider_net_shares_6m = Column(BigInteger)

    data_source = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<SentimentData(ticker='{self.ticker}', date='{self.data_date}')>"


class MarketSentiment(Base):
    """
    Market-wide sentiment indicators.

    Framework Section 5.1: Market sentiment (40% of sentiment pillar)
    Sources: VIX (yfinance), AAII, Put/Call ratio (CBOE), Fund Flows (ICI)
    """
    __tablename__ = 'market_sentiment'

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True, index=True)

    # VIX data (Fear gauge - contrarian)
    vix_value = Column(Numeric(10, 2))
    vix_mean_1y = Column(Numeric(10, 2))
    vix_std_1y = Column(Numeric(10, 2))
    vix_zscore = Column(Numeric(10, 4))
    vix_score = Column(Numeric(5, 2))  # 0-100 score

    # AAII sentiment (Bulls/Bears - contrarian)
    aaii_bulls = Column(Numeric(5, 2))  # Percentage
    aaii_bears = Column(Numeric(5, 2))  # Percentage
    aaii_neutral = Column(Numeric(5, 2))  # Percentage
    aaii_spread_8w = Column(Numeric(5, 2))  # 8-week MA: Bears - Bulls
    aaii_score = Column(Numeric(5, 2))  # 0-100 score

    # Put/Call ratio (Options sentiment - contrarian)
    putcall_ratio = Column(Numeric(10, 4))
    putcall_ma_10d = Column(Numeric(10, 4))  # 10-day moving average
    putcall_score = Column(Numeric(5, 2))  # 0-100 score

    # Fund flows (Equity fund flows - directional)
    fund_flows_billions = Column(Numeric(10, 2))  # Weekly flows in billions
    fund_flows_zscore = Column(Numeric(10, 4))
    fund_flows_score = Column(Numeric(5, 2))  # 0-100 score

    # Composite market sentiment
    market_sentiment_score = Column(Numeric(5, 2))  # Average of 4 indicators
    num_indicators_available = Column(Integer)  # Track data quality

    data_source = Column(String(100))  # Comma-separated sources
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<MarketSentiment(date='{self.date}', score={self.market_sentiment_score})>"


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


class FMPEstimateSnapshot(Base):
    """
    Snapshots of FMP analyst estimates for revision tracking.

    Framework Section 5.2: Analyst Revision Momentum
    Stores estimate snapshots on each collection run so that revisions
    can be detected by comparing current vs previous values for the
    same fiscal period.

    Source: Financial Modeling Prep /stable/analyst-estimates endpoint
    """
    __tablename__ = 'fmp_estimate_snapshots'

    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    snapshot_date = Column(Date, nullable=False)  # When we collected this
    fiscal_date = Column(Date, nullable=False)     # The quarter being estimated

    # EPS estimates
    eps_avg = Column(Numeric(10, 4))
    eps_high = Column(Numeric(10, 4))
    eps_low = Column(Numeric(10, 4))

    # Revenue estimates
    revenue_avg = Column(Numeric(20, 2))
    revenue_high = Column(Numeric(20, 2))
    revenue_low = Column(Numeric(20, 2))

    # Analyst coverage
    num_analysts_eps = Column(Integer)
    num_analysts_revenue = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('ticker', 'snapshot_date', 'fiscal_date',
                         name='uq_fmp_snapshot_ticker_dates'),
    )

    def __repr__(self):
        return (
            f"<FMPEstimateSnapshot(ticker='{self.ticker}', "
            f"snapshot='{self.snapshot_date}', fiscal='{self.fiscal_date}')>"
        )
