# Session Status - Current State

**Last Updated:** 2026-02-16 (None propagation for missing data)
**Current Phase:** Phase 6 — Web GUI & Refinement (IN PROGRESS)
**Status:** Phases 1-5 complete. Web GUI live. Missing data now shows N/A instead of fake 50.0 scores. Recalculate auto-detects stocks needing data collection.

> **Session History:** Detailed past session notes are in [SESSION_HISTORY.md](SESSION_HISTORY.md) (only load when needed)

---

## Completed Infrastructure

### Phase 1 Week 1: Data Infrastructure COMPLETE
- Yahoo Finance & Alpha Vantage integrations working
- Rate limiting & data validation implemented
- 15 stocks loaded across 7 sectors (100% data quality)
- Database schema & ORM models created

### Phase 1 Week 2: Calculation Engine COMPLETE
- Percentile engine: 36 tests passing
- Fundamental calculator: all 15 stocks scoring (32.1 to 64.8)
- Technical calculator: all 6 sub-components implemented
- Sentiment calculator: all 4 stock-specific components, 39 unit tests
- Composite score calculator: 45/35/20 weights, 62 unit tests

### Phase 2: Calculator Integration & Data Quality COMPLETE
- Technical calculator field mapping fixed
- Sentiment calculator fully integrated with market data
- Market sentiment: 3/4 indicators operational (VIX, Put/Call, Fund Flows)
- Price data extended to 2 years (7,545 records)
- momentum_12_1 operational for all 15 stocks
- sector_relative_6m operational for all 15 stocks (7 sectors)
- All 6 technical sub-components now active
- ✅ FMP API integration: analyst estimates & stock grades (13/15 stocks)
- ✅ Real analyst revision tracking via estimate snapshots
- ✅ Sentiment calculator upgraded with real FMP revision data + proxy fallback

### Phase 3: Override System COMPLETE
- ✅ Override data models, OverrideManager with guardrails, OverrideLogger
- ✅ CLI script: `scripts/apply_override.py`
- ✅ End-to-end verified: calculate_scores → apply_override → JSON log output

### Phase 4: User-Facing Tools COMPLETE
- ✅ `ScoringPipeline` extracted to `src/scoring/pipeline.py` (reusable class)
- ✅ `StalenessChecker` at `src/utils/staleness.py` (configurable cadences)
- ✅ `scripts/daily_report.py` — primary daily tool (refresh, score, compare, report)
- ✅ `scripts/manage_universe.py` — add/remove/list/reactivate stocks
- ✅ `scripts/review_overrides.py` — list/summary/detail override views
- ✅ Import cleanup: standardized all `from src.xxx` → `from xxx` across codebase
- ✅ `stock_scores` DB table schema aligned with ORM model
- ✅ 54 new tests (staleness, pipeline, daily report) — all passing
- ✅ `conftest.py` for consistent test imports

### Phase 5: Backtesting Framework COMPLETE
- ✅ `IndicatorBuilder` — reusable indicator calculation from price DataFrames for any date
- ✅ `TechnicalBacktester` — monthly checkpoint scoring, forward returns, quintile analysis
- ✅ `SnapshotManager` — save/load point-in-time pipeline snapshots as JSON
- ✅ `scripts/run_backtest.py` — CLI entry point with custom date ranges
- ✅ `scripts/daily_report.py` — automatic snapshot saving after scoring
- ✅ 61 new tests (30 indicator builder + 20 backtester + 11 snapshot manager)
- ✅ End-to-end verified: backtest ran on 15 stocks, 11 checkpoints, report generated

### Phase 6: Web GUI & Refinement (IN PROGRESS)
- ✅ Flask web app with dashboard, scores, universe, overrides, backtest, data status pages
- ✅ Background task system for score calculation
- ✅ Score explainability: sub-component breakdowns (fundamental: value/quality/growth, technical: 6 sub-scores, sentiment: market/stock + 4 sub-scores)
- ✅ Data status visibility: `no_data` warnings for stocks missing DB data
- ✅ Sentiment calculator returns dict with sub-components
- ✅ Pipeline preserves sub-component data through to JSON and DB persistence
- ✅ 24 web route tests
- ✅ Weekend-aware staleness checking for price_data and technical_indicators
- ✅ Partial-success exit code in price collector (no longer fails on single ticker error)
- ✅ Subprocess error logging in refresh task results
- ✅ None propagation for missing data (no more fake 50.0 scores)
- ✅ Per-stock coverage detection in StalenessChecker (auto-triggers data collection for new stocks)
- ✅ Unscored stocks shown as INSUFFICIENT DATA with N/A in GUI
- ⏳ Auto-collect data when adding a stock (CLI + web UI)

**Current Database:**
- 16 active stocks across 7 sectors (AMD added but no data yet — will auto-collect on next Recalculate)
- Price data: 7,545 records (2 years x 15 stocks)
- Fundamental data: 15 records
- Technical indicators: 15 records (all fields populated)
- Sentiment data: 15 records (13 with FMP data, 2 Yahoo-only)
- Market sentiment: 1 record (3/4 indicators)
- FMP estimate snapshots: 130 records (baseline for revision tracking)
- Stock scores: 15 records (persisted to DB + JSON)

---

## Next Session Goals

**Priority:**
1. Auto-collect data + score when adding a stock (both `manage_universe.py add` and web UI `/universe/add`)
   - After inserting Stock row, run data collection scripts for that ticker
   - Optionally trigger a scoring run afterward
2. Expand stock universe (add more stocks for better percentile ranking)

**Potential tasks:**
3. Extend price data history (more backtest coverage)
4. Full-model backtest (once snapshots accumulate over daily runs)
5. Paper trading simulation with real-time tracking
6. Override alpha calculation (track override performance vs base model)
7. Metric-level data availability (show "3/5 metrics" alongside each sub-component score)

### Deferred Items
- AAII Sentiment (requires premium API)
- Override alpha calculation (requires price performance tracking)
- Full-model backtest (requires accumulated snapshots over time)

---

## Quick Reference

### Daily Workflow Commands
```bash
# Daily pre-market analysis (primary command)
python scripts/daily_report.py

# Score without refreshing data
python scripts/daily_report.py --skip-refresh

# Force full data refresh
python scripts/daily_report.py --force-refresh

# Single ticker report
python scripts/daily_report.py --ticker AAPL

# Run technical backtest
python scripts/run_backtest.py
python scripts/run_backtest.py --start 2024-06-01 --end 2025-06-30

# Manage universe
python scripts/manage_universe.py list
python scripts/manage_universe.py add TSLA META
python scripts/manage_universe.py remove DIS
python scripts/manage_universe.py reactivate DIS

# Review overrides
python scripts/review_overrides.py summary
python scripts/review_overrides.py list
python scripts/review_overrides.py detail GOOGL

# Apply override
python scripts/apply_override.py

# Calculate scores (verbose)
python scripts/calculate_scores.py
```

### Current Environment
- **Database:** PostgreSQL, stock_analysis
  - 16 stocks (15 with data, AMD pending), 7,545 price records
  - 130 FMP estimate snapshots (baseline for future revision detection)
- **APIs:** Yahoo Finance (unlimited), Alpha Vantage (5/min), FMP (250/day), DataHub.io (free)
- **Python:** 3.12.9
- **Tests:** pytest (467 passing)

### Latest Scores (2026-02-14)
| Rank | Ticker | Recommendation | Composite | Fund | Tech | Sent |
|------|--------|---------------|-----------|------|------|------|
| 1 | JNJ | STRONG BUY | 64.0 | 53.5 | 86.5 | 48.2 |
| 2 | CAT | STRONG BUY | 62.8 | 47.4 | 92.3 | 46.0 |
| 3 | GOOGL | BUY | 62.5 | 49.0 | 85.5 | 52.7 |
| 4 | NVDA | BUY | 62.4 | 62.3 | 66.8 | 55.0 |
| 5 | XOM | HOLD | 55.4 | 48.5 | 68.5 | 48.2 |
| -- | AMD | INSUFFICIENT DATA | N/A | N/A | N/A | N/A |

### Key Module Files
- `src/web/` — Flask web GUI (dashboard, scores, universe, overrides, backtest, data status)
- `src/scoring/pipeline.py` — ScoringPipeline (reusable scoring orchestration, sub-component data)
- `src/backtesting/indicator_builder.py` — IndicatorBuilder (indicator math for any date)
- `src/backtesting/technical_backtest.py` — TechnicalBacktester (quintile analysis, correlations)
- `src/backtesting/snapshot_manager.py` — SnapshotManager (point-in-time snapshots)
- `src/utils/staleness.py` — StalenessChecker (data freshness + per-stock coverage)
- `src/overrides/override_manager.py` — Core override logic + guardrails
- `src/overrides/override_logger.py` — JSON persistence
- `src/models/composite.py` — CompositeScoreCalculator

### Known Limitations

1. **AAII sentiment data unavailable (premium API)**
   - Free Nasdaq Data Link key returns 403
   - System works well with 3/4 indicators

2. **Fund flows data lags ~2 months**
   - ICI dataset updates monthly with delay

3. **FMP free tier limitations**
   - CAT and PG return 402 (premium-only tickers)
   - Quarterly estimates require premium (annual only on free tier)
   - Revision detection requires 2+ collection runs (first run = baseline)

4. **Market holidays not handled in staleness checker**
   - Weekend adjustment works (Sat/Sun/Mon), but holidays (e.g. President's Day) can still cause false stale flags
   - Would require a trading calendar to fully solve

5. **Backtest limited by data history**
   - Only 2 years of price data → ~12 months of testable checkpoints
   - 15-stock universe too small for robust quintile analysis
   - Full-model backtest requires accumulated daily snapshots

6. **Adding stocks doesn't auto-collect data**
   - `manage_universe.py add` and web UI only insert Stock row
   - Data collection requires separate Recalculate or daily_report.py run
   - Next session: make add auto-trigger collection + scoring

---

**Phase 1 Progress: 100% COMPLETE**
**Phase 2 Progress: 100% COMPLETE**
**Phase 3 Progress: 100% COMPLETE**
**Phase 4 Progress: 100% COMPLETE**
**Phase 5 Progress: 100% COMPLETE**
**Phase 6 Progress: Web GUI + Explainability + None propagation COMPLETE, auto-collect on add pending**
