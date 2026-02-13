-- Stock Analysis Framework - Database Initialization
-- PostgreSQL Schema Creation Script
-- Version: 2.0
-- Reference: docs/database_schema.md

-- ============================================================
-- 1. STOCKS (Universe Management)
-- ============================================================

CREATE TABLE IF NOT EXISTS stocks (
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

CREATE INDEX IF NOT EXISTS idx_stocks_sector ON stocks(sector);
CREATE INDEX IF NOT EXISTS idx_stocks_is_active ON stocks(is_active);

-- ============================================================
-- 2. PRICE DATA (Raw Time-Series)
-- ============================================================

CREATE TABLE IF NOT EXISTS price_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) REFERENCES stocks(ticker) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_price_ticker_date ON price_data(ticker, date DESC);
CREATE INDEX IF NOT EXISTS idx_price_date ON price_data(date DESC);

-- ============================================================
-- 3. FUNDAMENTAL DATA (Raw Quarterly/Annual)
-- ============================================================

CREATE TABLE IF NOT EXISTS fundamental_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) REFERENCES stocks(ticker) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_fundamental_ticker_date ON fundamental_data(ticker, report_date DESC);

-- ============================================================
-- 4. TECHNICAL INDICATORS (Calculated)
-- ============================================================

CREATE TABLE IF NOT EXISTS technical_indicators (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) REFERENCES stocks(ticker) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_technical_ticker_date ON technical_indicators(ticker, calculation_date DESC);

-- ============================================================
-- 5. SENTIMENT DATA (Raw)
-- ============================================================

CREATE TABLE IF NOT EXISTS sentiment_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) REFERENCES stocks(ticker) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_sentiment_ticker_date ON sentiment_data(ticker, data_date DESC);

-- ============================================================
-- 6. MARKET SENTIMENT (Broader Market Indicators)
-- ============================================================
-- Framework Section 5.1: Market sentiment (40% of sentiment pillar)
-- Sources: VIX (yfinance), AAII, Put/Call ratio (CBOE), Fund Flows (ICI)

CREATE TABLE IF NOT EXISTS market_sentiment (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,

    -- VIX data (Fear gauge - contrarian)
    vix_value DECIMAL(10, 2),
    vix_mean_1y DECIMAL(10, 2),
    vix_std_1y DECIMAL(10, 2),
    vix_zscore DECIMAL(10, 4),
    vix_score DECIMAL(5, 2), -- 0-100 score

    -- AAII sentiment (Bulls/Bears - contrarian)
    aaii_bulls DECIMAL(5, 2), -- Percentage
    aaii_bears DECIMAL(5, 2), -- Percentage
    aaii_neutral DECIMAL(5, 2), -- Percentage
    aaii_spread_8w DECIMAL(5, 2), -- 8-week MA: Bears - Bulls
    aaii_score DECIMAL(5, 2), -- 0-100 score

    -- Put/Call ratio (Options sentiment - contrarian)
    putcall_ratio DECIMAL(10, 4),
    putcall_ma_10d DECIMAL(10, 4), -- 10-day moving average
    putcall_score DECIMAL(5, 2), -- 0-100 score

    -- Fund flows (Equity fund flows - directional)
    fund_flows_billions DECIMAL(10, 2), -- Weekly flows in billions
    fund_flows_zscore DECIMAL(10, 4),
    fund_flows_score DECIMAL(5, 2), -- 0-100 score

    -- Composite market sentiment
    market_sentiment_score DECIMAL(5, 2), -- Average of 4 indicators
    num_indicators_available INTEGER, -- Track data quality

    data_source VARCHAR(100), -- Comma-separated sources
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_market_sentiment_date ON market_sentiment(date DESC);

-- ============================================================
-- 7. STOCK SCORES (Calculated Percentiles)
-- ============================================================

CREATE TABLE IF NOT EXISTS stock_scores (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) REFERENCES stocks(ticker) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_scores_ticker_date ON stock_scores(ticker, calculation_date DESC);
CREATE INDEX IF NOT EXISTS idx_scores_date ON stock_scores(calculation_date DESC);
CREATE INDEX IF NOT EXISTS idx_scores_base_composite ON stock_scores(base_composite_score DESC);

-- ============================================================
-- 8. OVERRIDE DECISIONS (Human Adjustments)
-- ============================================================

CREATE TABLE IF NOT EXISTS override_decisions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) REFERENCES stocks(ticker) ON DELETE CASCADE,
    score_id INTEGER REFERENCES stock_scores(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_override_ticker_date ON override_decisions(ticker, decision_date DESC);
CREATE INDEX IF NOT EXISTS idx_override_review_date ON override_decisions(review_date);
CREATE INDEX IF NOT EXISTS idx_override_conviction ON override_decisions(conviction_level);

-- ============================================================
-- 9. QUARTERLY REVIEWS (Performance Tracking)
-- ============================================================

CREATE TABLE IF NOT EXISTS quarterly_reviews (
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

CREATE INDEX IF NOT EXISTS idx_quarterly_quarter ON quarterly_reviews(quarter);

-- ============================================================
-- 10. API CALL LOG (Rate Limiting & Debugging)
-- ============================================================

CREATE TABLE IF NOT EXISTS api_call_log (
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

CREATE INDEX IF NOT EXISTS idx_api_log_timestamp ON api_call_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_api_log_source ON api_call_log(api_source, timestamp DESC);

-- ============================================================
-- 11. CALCULATION LOG (Audit Trail)
-- ============================================================

CREATE TABLE IF NOT EXISTS calculation_log (
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

CREATE INDEX IF NOT EXISTS idx_calc_log_timestamp ON calculation_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_calc_log_type ON calculation_log(calculation_type);

-- ============================================================
-- INITIALIZATION COMPLETE
-- ============================================================

-- Grant permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO stock_analysis_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO stock_analysis_user;
