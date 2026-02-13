# Database Schema Design

## Overview

PostgreSQL database schema for Stock Recommendation Framework v2.0.
Designed to support:
- Stock universe management
- Raw and processed data storage
- Score calculations and tracking
- Override documentation and performance review

## Design Principles

1. **Separate raw from calculated**: Store API responses separately from computed scores
2. **Time-series friendly**: Track historical scores and overrides
3. **Audit trail**: Every override and decision is logged
4. **Percentile-based**: Support universe-wide ranking calculations
5. **Normalize where appropriate**: Avoid data duplication

---

## Schema Tables

### 1. Stocks (Universe Management)

```sql
CREATE TABLE stocks (
    ticker VARCHAR(10) PRIMARY KEY,
    company_name VARCHAR(255),
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap DECIMAL(20, 2),
    is_active BOOLEAN DEFAULT TRUE,
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX idx_stocks_sector ON stocks(sector);
CREATE INDEX idx_stocks_is_active ON stocks(is_active);
```

**Purpose**: Track which stocks are in your universe
**Key Fields**:
- `ticker`: Primary identifier
- `is_active`: Flag to include/exclude from calculations
- `sector/industry`: For relative comparisons

---

### 2. Price Data (Raw Time-Series)

```sql
CREATE TABLE price_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) REFERENCES stocks(ticker),
    date DATE NOT NULL,
    open DECIMAL(10, 2),
    high DECIMAL(10, 2),
    low DECIMAL(10, 2),
    close DECIMAL(10, 2),
    adjusted_close DECIMAL(10, 2),
    volume BIGINT,
    data_source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE INDEX idx_price_ticker_date ON price_data(ticker, date DESC);
CREATE INDEX idx_price_date ON price_data(date DESC);
```

**Purpose**: Store daily price history for technical analysis
**Source**: Yahoo Finance (yfinance)

---

### 3. Fundamental Data (Raw Quarterly/Annual)

```sql
CREATE TABLE fundamental_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) REFERENCES stocks(ticker),
    report_date DATE NOT NULL,
    period_type VARCHAR(10), -- 'quarterly' or 'annual'

    -- Valuation Metrics
    pe_ratio DECIMAL(10, 2),
    forward_pe DECIMAL(10, 2),
    pb_ratio DECIMAL(10, 2),
    ps_ratio DECIMAL(10, 2),
    ev_to_ebitda DECIMAL(10, 2),
    peg_ratio DECIMAL(10, 2),
    dividend_yield DECIMAL(5, 4),

    -- Quality Metrics
    roe DECIMAL(10, 4),
    roa DECIMAL(10, 4),
    net_margin DECIMAL(10, 4),
    operating_margin DECIMAL(10, 4),
    gross_margin DECIMAL(10, 4),
    fcf_to_revenue DECIMAL(10, 4),

    -- Growth Metrics
    revenue_growth_yoy DECIMAL(10, 4),
    eps_growth_yoy DECIMAL(10, 4),
    revenue_growth_3y_cagr DECIMAL(10, 4),
    fcf_growth_yoy DECIMAL(10, 4),
    book_value_growth DECIMAL(10, 4),

    -- Financial Health
    current_ratio DECIMAL(10, 2),
    quick_ratio DECIMAL(10, 2),
    debt_to_equity DECIMAL(10, 2),
    interest_coverage DECIMAL(10, 2),
    cash_to_assets DECIMAL(10, 4),

    -- Other
    beta DECIMAL(10, 4),
    shares_outstanding BIGINT,

    data_source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, report_date, period_type)
);

CREATE INDEX idx_fundamental_ticker_date ON fundamental_data(ticker, report_date DESC);
```

**Purpose**: Store fundamental metrics from financial statements
**Source**: Yahoo Finance, Alpha Vantage
**Note**: Quarterly updates, store historical for backtesting

---

### 4. Technical Indicators (Calculated)

```sql
CREATE TABLE technical_indicators (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) REFERENCES stocks(ticker),
    calculation_date DATE NOT NULL,

    -- Moving Averages
    sma_20 DECIMAL(10, 2),
    sma_50 DECIMAL(10, 2),
    sma_200 DECIMAL(10, 2),
    mad DECIMAL(10, 6), -- Moving Average Distance

    -- Momentum
    momentum_12_1 DECIMAL(10, 6), -- 12-1 month return
    momentum_6m DECIMAL(10, 6),
    momentum_3m DECIMAL(10, 6),
    momentum_1m DECIMAL(10, 6),

    -- Volume
    avg_volume_20d BIGINT,
    avg_volume_90d BIGINT,
    relative_volume DECIMAL(10, 4),

    -- Trend
    rsi_14 DECIMAL(10, 2),
    adx DECIMAL(10, 2),
    price_vs_200ma BOOLEAN, -- Above/below 200-day MA

    -- Relative Performance
    sector_relative_6m DECIMAL(10, 6), -- Stock vs sector 6m return

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, calculation_date)
);

CREATE INDEX idx_technical_ticker_date ON technical_indicators(ticker, calculation_date DESC);
```

**Purpose**: Store calculated technical indicators
**Calculation**: Daily, based on price_data
**Framework Reference**: Section 4.2

---

### 5. Sentiment Data (Raw)

```sql
CREATE TABLE sentiment_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) REFERENCES stocks(ticker),
    data_date DATE NOT NULL,

    -- Analyst Data
    consensus_price_target DECIMAL(10, 2),
    num_buy_ratings INTEGER,
    num_hold_ratings INTEGER,
    num_sell_ratings INTEGER,
    num_analyst_opinions INTEGER,

    -- Recent Activity (past 30 days)
    upgrades_30d INTEGER DEFAULT 0,
    downgrades_30d INTEGER DEFAULT 0,
    estimate_revisions_up_90d INTEGER DEFAULT 0,
    estimate_revisions_down_90d INTEGER DEFAULT 0,

    -- Market Sentiment
    short_interest_pct DECIMAL(10, 4),
    days_to_cover DECIMAL(10, 2),

    -- Insider Activity (past 6 months)
    insider_buys_6m INTEGER DEFAULT 0,
    insider_sells_6m INTEGER DEFAULT 0,
    insider_net_shares_6m BIGINT,

    data_source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, data_date)
);

CREATE INDEX idx_sentiment_ticker_date ON sentiment_data(ticker, data_date DESC);
```

**Purpose**: Store stock-specific sentiment indicators
**Source**: Various APIs, SEC EDGAR for insider trading
**Framework Reference**: Section 5.2

---

### 6. Market Sentiment (Broader Market Indicators)

```sql
CREATE TABLE market_sentiment (
    id SERIAL PRIMARY KEY,
    data_date DATE NOT NULL UNIQUE,

    -- VIX
    vix_level DECIMAL(10, 2),
    vix_zscore DECIMAL(10, 4),

    -- AAII Sentiment
    aaii_bull_pct DECIMAL(5, 2),
    aaii_bear_pct DECIMAL(5, 2),
    aaii_neutral_pct DECIMAL(5, 2),
    aaii_bear_bull_spread DECIMAL(5, 2),
    aaii_8week_ma DECIMAL(5, 2),

    -- Put/Call Ratio
    put_call_ratio DECIMAL(10, 4),
    put_call_10d_ma DECIMAL(10, 4),

    -- Fund Flows
    equity_fund_flow DECIMAL(15, 2), -- Weekly, in millions
    fund_flow_category VARCHAR(20), -- 'strong_inflow', 'neutral', 'strong_outflow'

    -- Market Context
    sp500_pe_ratio DECIMAL(10, 2),
    treasury_10y_yield DECIMAL(5, 4),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_market_sentiment_date ON market_sentiment(data_date DESC);
```

**Purpose**: Store market-wide sentiment indicators
**Source**: CBOE (VIX), AAII, ICI
**Framework Reference**: Section 5.2

---

### 7. Stock Scores (Calculated Percentiles)

```sql
CREATE TABLE stock_scores (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) REFERENCES stocks(ticker),
    calculation_date DATE NOT NULL,
    universe_size INTEGER, -- Number of stocks ranked

    -- Fundamental Component Scores (percentiles)
    value_score DECIMAL(5, 2),
    quality_score DECIMAL(5, 2),
    growth_score DECIMAL(5, 2),
    fundamental_score DECIMAL(5, 2), -- Composite

    -- Technical Component Scores (percentiles)
    momentum_score DECIMAL(5, 2),
    trend_score DECIMAL(5, 2),
    volume_qualified_score DECIMAL(5, 2),
    relative_strength_score DECIMAL(5, 2),
    rsi_score DECIMAL(5, 2),
    multi_speed_score DECIMAL(5, 2),
    technical_score DECIMAL(5, 2), -- Composite

    -- Sentiment Component Scores
    market_sentiment_score DECIMAL(5, 2),
    stock_sentiment_score DECIMAL(5, 2),
    base_sentiment_score DECIMAL(5, 2), -- Composite

    -- Base Model Output
    base_composite_score DECIMAL(5, 2), -- 45/35/20 weighted
    base_recommendation VARCHAR(20), -- STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL

    -- Metadata
    calculation_version VARCHAR(20), -- Track methodology version
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, calculation_date)
);

CREATE INDEX idx_scores_ticker_date ON stock_scores(ticker, calculation_date DESC);
CREATE INDEX idx_scores_date ON stock_scores(calculation_date DESC);
CREATE INDEX idx_scores_base_composite ON stock_scores(base_composite_score DESC);
```

**Purpose**: Store calculated percentile scores and base recommendations
**Calculation**: Daily/weekly, universe-wide ranking
**Framework Reference**: Sections 3, 4, 5, 7

---

### 8. Override Decisions (Human Adjustments)

```sql
CREATE TABLE override_decisions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) REFERENCES stocks(ticker),
    score_id INTEGER REFERENCES stock_scores(id),
    decision_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    current_price DECIMAL(10, 2),

    -- Base Model Scores (copied from stock_scores for audit)
    base_fundamental_score DECIMAL(5, 2),
    base_technical_score DECIMAL(5, 2),
    base_sentiment_score DECIMAL(5, 2),
    base_composite_score DECIMAL(5, 2),
    base_recommendation VARCHAR(20),

    -- Override Type
    has_weight_override BOOLEAN DEFAULT FALSE,
    has_sentiment_override BOOLEAN DEFAULT FALSE,

    -- Weight Adjustments (if any)
    override_fundamental_weight DECIMAL(5, 4), -- e.g., 0.50 instead of 0.45
    override_technical_weight DECIMAL(5, 4),
    override_sentiment_weight DECIMAL(5, 4),

    -- Sentiment Adjustment (if any)
    sentiment_adjustment DECIMAL(5, 2), -- +/- 15 max
    adjusted_sentiment_score DECIMAL(5, 2),

    -- Final Output
    final_composite_score DECIMAL(5, 2),
    final_recommendation VARCHAR(20),
    composite_impact DECIMAL(5, 2), -- Difference from base

    -- Documentation (REQUIRED)
    what_model_misses TEXT NOT NULL,
    why_view_more_accurate TEXT NOT NULL,
    falsification_criteria TEXT NOT NULL,
    conviction_level VARCHAR(10), -- LOW, MEDIUM, HIGH
    additional_notes TEXT,

    -- 6-Month Review (updated later)
    review_date DATE,
    price_at_review DECIMAL(10, 2),
    return_pct DECIMAL(10, 4),
    sector_return_pct DECIMAL(10, 4),
    market_return_pct DECIMAL(10, 4),
    override_result VARCHAR(10), -- HELPED, HURT, NEUTRAL
    lessons_learned TEXT
);

CREATE INDEX idx_override_ticker_date ON override_decisions(ticker, decision_date DESC);
CREATE INDEX idx_override_review_date ON override_decisions(review_date);
CREATE INDEX idx_override_conviction ON override_decisions(conviction_level);
```

**Purpose**: Store every override decision with mandatory documentation
**Framework Reference**: Section 6.4
**Key**: Links to stock_scores for base model output

---

### 9. Quarterly Reviews (Performance Tracking)

```sql
CREATE TABLE quarterly_reviews (
    id SERIAL PRIMARY KEY,
    quarter VARCHAR(10) NOT NULL UNIQUE, -- e.g., 'Q1_2026'
    review_date DATE NOT NULL,

    -- Summary Statistics
    total_stocks_evaluated INTEGER,
    total_stocks_overridden INTEGER,
    override_frequency DECIMAL(5, 4),

    -- Breakdown
    weight_adjustments_only INTEGER,
    sentiment_adjustments_only INTEGER,
    both_adjustments INTEGER,

    -- Performance Metrics
    override_hit_rate DECIMAL(5, 4),
    override_alpha DECIMAL(10, 4),

    -- Best/Worst
    best_override_ticker VARCHAR(10),
    best_override_outperformance DECIMAL(10, 4),
    worst_override_ticker VARCHAR(10),
    worst_override_underperformance DECIMAL(10, 4),

    -- Insights (structured as JSON for flexibility)
    patterns_discovered JSONB,
    action_items JSONB,

    -- Documentation
    full_review_path TEXT, -- Path to markdown review file

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_quarterly_quarter ON quarterly_reviews(quarter);
```

**Purpose**: Aggregate quarterly performance reviews
**Framework Reference**: Section 8.2
**Note**: Detailed review in markdown, summary stats in DB

---

## Utility Tables

### 10. API Call Log (Rate Limiting & Debugging)

```sql
CREATE TABLE api_call_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    api_source VARCHAR(50), -- 'yahoo_finance', 'alpha_vantage', etc.
    endpoint VARCHAR(255),
    ticker VARCHAR(10),
    status_code INTEGER,
    response_time_ms INTEGER,
    error_message TEXT,
    rate_limit_remaining INTEGER
);

CREATE INDEX idx_api_log_timestamp ON api_call_log(timestamp DESC);
CREATE INDEX idx_api_log_source ON api_call_log(api_source, timestamp DESC);
```

**Purpose**: Track API usage, debug failures, respect rate limits

---

### 11. Calculation Log (Audit Trail)

```sql
CREATE TABLE calculation_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    calculation_type VARCHAR(50), -- 'fundamental_score', 'technical_score', etc.
    calculation_date DATE,
    universe_size INTEGER,
    stocks_processed INTEGER,
    stocks_failed INTEGER,
    execution_time_seconds DECIMAL(10, 2),
    version VARCHAR(20),
    warnings TEXT,
    error_summary TEXT
);

CREATE INDEX idx_calc_log_timestamp ON calculation_log(timestamp DESC);
CREATE INDEX idx_calc_log_type ON calculation_log(calculation_type);
```

**Purpose**: Track when calculations run, performance, errors

---

## Database Initialization Script

See `scripts/init_db.sql` for full table creation.
See `src/database/models.py` for SQLAlchemy ORM models.

---

## Migration Strategy

Using Alembic for schema migrations:

1. **Initial**: Create all tables
2. **Ongoing**: Track schema changes in version control
3. **Rollback**: Support if methodology changes

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## Data Retention Policy

- **Price Data**: Keep all historical (for backtesting)
- **Fundamental Data**: Keep all quarterly reports
- **Technical Indicators**: Keep 2 years, then aggregate monthly
- **Scores**: Keep all (enables performance review)
- **Overrides**: Keep all (learning from mistakes)
- **API Logs**: Keep 90 days
- **Calculation Logs**: Keep 1 year

---

## Backup Strategy

1. **Daily**: Automated PostgreSQL backup
2. **Weekly**: Export override decisions to CSV
3. **Monthly**: Full database dump before migrations
4. **Critical**: Override logs backed up immediately

---

## Performance Considerations

### Indexes
- All date-based queries have DESC indexes
- Ticker + date composite indexes for time-series
- Composite score index for ranking

### Partitioning (Future)
If data grows large:
- Partition `price_data` by year
- Partition `stock_scores` by quarter

### Materialized Views (Future)
For expensive queries:
- Latest scores for active stocks
- Universe rankings by sector
- Override performance summaries

---

## Connection Pooling

Use SQLAlchemy with connection pooling:

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600
)
```

---

## Security

- ✅ Passwords in .env (not version controlled)
- ✅ Read-only user for analysis/reporting
- ✅ Write user only for data collection scripts
- ✅ Admin user for migrations
- ✅ SSL connection in production

---

## Next Steps

1. Create PostgreSQL database
2. Run `scripts/init_db.sql`
3. Set up Alembic migrations
4. Create SQLAlchemy ORM models
5. Write database utility functions
6. Test connection and basic CRUD

**Status**: Schema designed, ready for implementation
