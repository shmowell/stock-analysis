# Stock Analysis Project - Development Guidelines

## Project Overview

This is a **Stock Recommendation Framework v2.0** implementation that combines evidence-based quantitative scoring with disciplined human judgment. The system operates on a **Model-First principle**: calculate objective scores using research-backed methodologies, then allow conscious, documented overrides based on intuition.

**Core Philosophy**: Your edge comes from identifying when markets overreact or underreact to information. The framework quantifies this systematically while preserving the ability to override when you see something the models don't.

## Primary Reference Documents

**Specification:** `Stock_Recommendation_Framework_v2_Research_Enhanced.md`
- Complete technical specification
- Research citations and methodology
- Read relevant section BEFORE implementing any feature

**Session Status:** `docs/SESSION_STATUS.md`
- Current project state and progress
- Next session goals and tasks
- **UPDATE THIS AT THE END OF EACH SESSION**

**CRITICAL**: This is SPEC-DRIVEN development - the specification comes first, implementation second.

## Session Workflow

### Starting a Session
1. Read `docs/SESSION_STATUS.md` to understand current state
2. Review "Next Session Goals" section
3. Check "Completed Setup" checklist
4. Begin work on planned tasks

### During a Session
- Follow development principles below
- Reference framework document for implementation details
- Write tests first (TDD)
- Document decisions in code comments

### Ending a Session
**MANDATORY: Update `docs/SESSION_STATUS.md` before closing**

Update the following sections:
1. ✅ **Completed Setup** - Mark new items complete
2. 📋 **Next Session Goals** - Define what comes next
3. 🎯 **Current Environment** - Note any new tools/changes
4. ⚠️ **Known Issues / Notes** - Document blockers or decisions

Template for end-of-session update:
```markdown
## Completed This Session
- [ ] Item 1
- [ ] Item 2

## Ready for Next Session
Primary Objective: [Next major goal]
Tasks: [Specific actionable items]

## Blockers/Decisions
[Any open questions or issues]
```

**Commit and push SESSION_STATUS.md** after updating.

## Architecture Principles

### 1. Model-First, Override Second

**ALWAYS implement in this order:**
1. Calculate the objective, quantitative score first
2. Display the base model output clearly
3. THEN provide interface for human override
4. Document the override with mandatory reasoning

Never build a system where subjective judgment comes first. The model must always run and produce its recommendation before any human override.

### 2. Percentile-Based Scoring

**DO NOT use linear 0-100 scoring**. All metrics must be:
1. Collected as raw values for all stocks in the universe
2. Converted to percentile ranks (0-100) within the universe
3. Averaged within each pillar
4. Combined using weighted averages

Example:
```python
# CORRECT
pe_percentile = percentile_rank_inverted(stock_pe, universe_pe_values)
# Stock at 85th percentile means cheaper than 85% of universe

# WRONG
pe_score = (max_pe - stock_pe) / (max_pe - min_pe) * 100
```

### 3. Research-Backed Weights

**Base Weights (DO NOT change without documented research justification):**
- Fundamental: 45% (range: 35-55%)
- Technical: 35% (range: 25-45%)
- Sentiment: 20% (range: 10-30%)

These weights reflect the empirical evidence hierarchy. See framework Section 1.3 for research citations.

### 4. Separation of Concerns

The codebase should be organized into clear modules:

```
src/
├── data_collection/     # API integrations, data fetching
├── calculators/         # Scoring logic (fundamental, technical, sentiment)
├── models/             # Composite scoring, percentile ranking
├── overrides/          # Override system and documentation
└── utils/              # Helper functions, common utilities
```

Each module should:
- Have a single, well-defined responsibility
- Be independently testable
- Not mix data collection with calculation logic
- Not mix calculation with override logic

## Development Standards

### Code Style

1. **Type Hints**: Use type hints for all function signatures
   ```python
   def percentile_rank(value: float, universe: List[float]) -> float:
       """Calculate percentile rank within universe."""
       pass
   ```

2. **Docstrings**: Required for all public functions
   - Include purpose, parameters, return value
   - Include example if calculation is complex
   - Reference framework section if applicable

3. **Error Handling**:
   - Validate API responses
   - Handle missing data gracefully
   - Log errors with context
   - Never silently fail on bad data

4. **Configuration**:
   - API keys in `.env` (never commit)
   - Weights and thresholds in `config/` YAML files
   - Document why each configuration value is set

### Testing Requirements

**MANDATORY tests before considering any feature complete:**

1. **Unit Tests** for all calculators:
   ```python
   def test_percentile_rank():
       universe = [10, 20, 30, 40, 50]
       assert percentile_rank(35, universe) == 60  # Better than 60%
   ```

2. **Integration Tests** for data pipelines:
   - Test with known stock data
   - Verify calculations against manual computations
   - Test edge cases (missing data, outliers)

3. **Validation Tests**:
   - Verify percentile ranks sum correctly
   - Ensure weights always sum to 100%
   - Check override limits are enforced

### Data Quality

1. **Always validate API responses**:
   - Check for null/missing values
   - Verify data types match expectations
   - Log when data is unavailable

2. **Handle missing data**:
   - Document how each metric handles missing data
   - Options: skip stock, use sector average, use previous value
   - NEVER use arbitrary defaults like 0 or 50

3. **Store raw data**:
   - Keep original API responses in `data/raw/`
   - Store processed/calculated values in `data/processed/`
   - Enables recalculation and debugging

## Implementation Phases

Follow the roadmap in Framework Section 10:

### Phase 1: Foundation (Current)
- ✅ Directory structure created
- ✅ CLAUDE.md established
- ⏳ API setup and testing
- ⏳ Database/storage design
- ⏳ Basic data collection scripts

### Phase 2: Core Model
- Calculate fundamental scores (value, quality, growth)
- Calculate technical scores (momentum, trend, volume)
- Calculate base sentiment scores
- Implement percentile ranking engine

### Phase 3: Override System
- Build override input interface
- Implement weight adjustment logic
- Implement sentiment override logic
- Create documentation templates

### Phase 4-6: Testing & Production
- Backtesting on historical data
- Paper trading validation
- Live deployment with monitoring

**RULE**: Do not move to next phase until current phase is complete and tested.

## Key Implementation Requirements

### Percentile Ranking (CRITICAL)

Reference: Framework Section 1.2

```python
# Must handle both directions:
# 1. Higher is better (ROE, revenue growth)
percentile_rank(value, universe)

# 2. Lower is better (P/E, P/B)
percentile_rank_inverted(value, universe)
```

### Fundamental Scoring

Reference: Framework Section 3

**Sub-components (equal weight within fundamental):**
- Value: 33% (P/E, P/B, P/S, EV/EBITDA, Div Yield)
- Quality: 33% (ROE, ROA, margins, earnings stability)
- Growth: 34% (Revenue, EPS, FCF growth)

Each component:
1. Rank each metric as percentile
2. Average the percentile ranks
3. Combine using sub-component weights

### Technical Scoring

Reference: Framework Section 4

**Changes from typical technical analysis:**
- ❌ NO MACD (redundant)
- ❌ NO RSI overbought/oversold signals (weak predictor)
- ✅ YES cross-sectional momentum (strongest academic support)
- ✅ YES Moving Average Distance (MAD)
- ✅ YES volume-qualified momentum

**Sub-components:**
- Cross-sectional momentum: 35%
- Trend strength: 25%
- Volume-qualified momentum: 20%
- Relative strength vs sector: 10%
- RSI trend confirmation: 5%
- Multi-speed trend: 5%

### Sentiment Scoring

Reference: Framework Section 5

**MUST be rules-based FIRST, then override:**

Market-wide sentiment (40%):
- VIX z-score (contrarian)
- AAII Bear-Bull spread (contrarian)
- Put/Call ratio (contrarian)
- Equity fund flows (directional)

Stock-specific sentiment (60%):
- Short interest (contrarian with threshold)
- Analyst revision momentum
- Analyst consensus (with systematic discount)
- Insider activity

### Override System

Reference: Framework Section 6

**Non-negotiable requirements:**

1. **Override ONLY after base score is calculated**
   - User must see base recommendation first
   - No "start with blank slate" interface

2. **Mandatory documentation for every override**
   - What does model miss?
   - Why is your view more accurate?
   - What would prove you wrong?
   - Must fill out template (Section 6.4)

3. **Enforced limits**:
   - Weight adjustment: ±10% per pillar
   - Sentiment adjustment: ±15 points
   - Combined impact: ≤12 percentile points

4. **Tracking**:
   - Store every override in logs/overrides/
   - Enable quarterly review
   - Calculate override alpha

## Common Pitfalls to Avoid

### ❌ DON'T:
- Use linear scoring instead of percentile ranking
- Calculate scores in isolation (need full universe for percentiles)
- Allow overrides without documentation
- Hard-code weights in calculation functions
- Mix API calls with calculation logic
- Skip validation of API data
- Use equal weights (33/33/33) - not research-backed

### ✅ DO:
- Always rank within universe using percentiles
- Separate data collection, calculation, and override
- Validate all inputs and handle missing data
- Make weights configurable but with clear defaults
- Document why each decision was made
- Write tests for every calculator
- Reference framework sections in code comments

## API Integration Guidelines

Reference: Framework Section 9

### Required Data Sources

1. **Yahoo Finance** (yfinance):
   - Fundamental metrics (P/E, ROE, margins)
   - Price history (for moving averages, momentum)
   - Basic analyst data

2. **Alpha Vantage**:
   - Technical indicators (RSI, SMA)
   - Additional fundamental data
   - Earnings data

3. **Sentiment Sources**:
   - Short interest data
   - Insider trading (SEC EDGAR)
   - VIX, Put/Call ratios
   - AAII sentiment

### API Best Practices

1. **Rate Limiting**:
   - Respect API rate limits
   - Implement backoff/retry logic
   - Cache responses appropriately

2. **Error Handling**:
   ```python
   try:
       data = fetch_stock_data(ticker)
   except APIError as e:
       log.error(f"Failed to fetch {ticker}: {e}")
       # Decide: skip stock, use cached data, or raise
   ```

3. **Data Validation**:
   - Check for None/NaN values
   - Verify data freshness
   - Log anomalies

## Documentation Standards

### Code Comments

Reference framework sections in code:
```python
# Calculate 12-1 month momentum
# Framework Section 4.2: Excludes most recent month to avoid reversal effect
momentum_return = (price_1m_ago - price_12m_ago) / price_12m_ago
```

### README Files

Each module should have a README explaining:
- Purpose and scope
- Key functions and their usage
- Dependencies
- Testing approach

### Override Documentation

Use templates from `templates/` directory:
- `override_log_template.md` (Section 6.4)
- `quarterly_review_template.md` (Section 8.2)

## Version Control Guidelines

### Commit Messages

Follow conventional commits:
```
feat: Add percentile ranking engine
fix: Handle missing P/E data in fundamental calculator
docs: Update API integration guide
test: Add unit tests for momentum calculator
```

### Branching Strategy

- `main`: Production-ready code
- `develop`: Integration branch
- `feature/*`: Individual features
- `fix/*`: Bug fixes

### What to Commit

✅ Commit:
- Source code
- Tests
- Documentation
- Configuration templates
- Requirements files

❌ Never commit:
- API keys (.env files)
- Raw data files
- Personal override logs
- Temporary files

## Monitoring and Logging

### Required Logs

1. **Data Collection Logs**:
   - API calls made
   - Errors encountered
   - Data quality issues

2. **Calculation Logs**:
   - Stocks processed
   - Scores calculated
   - Warnings for edge cases

3. **Override Logs**:
   - Every override decision
   - Reasoning and documentation
   - Performance tracking

### Performance Metrics

Track and log:
- API response times
- Calculation execution time
- Data coverage (% of stocks with complete data)
- Override frequency and performance

## Questions and Decisions

When you encounter an ambiguous situation:

1. **Check the framework document first**
   - Is this addressed in the spec?
   - What do the research citations suggest?

2. **Follow the principle of least surprise**
   - What would a user expect?
   - What's the simplest correct implementation?

3. **Document the decision**
   - Add comment explaining why
   - Update CLAUDE.md if it's a pattern
   - Reference in commit message

4. **Ask before making major changes**
   - New dependencies
   - Architecture changes
   - Weight adjustments
   - Override system modifications

## Success Criteria

A feature is "done" when:

✅ Implementation matches framework specification
✅ Unit tests pass with >90% coverage
✅ Integration tests verify end-to-end flow
✅ Documentation is complete
✅ Error handling is robust
✅ Logging is comprehensive
✅ Code review is complete

## Contact and Resources

- **Framework Document**: `Stock_Recommendation_Framework_v2_Research_Enhanced.md`
- **Override Templates**: `templates/`
- **Configuration**: `config/`
- **Research Citations**: Framework Appendix C

---

## Development Workflow

### During Development
1. Read relevant framework section
2. Design implementation approach
3. Write tests first (TDD)
4. Implement feature
5. Validate against framework
6. Document and commit
7. Update this CLAUDE.md if needed

### End-of-Session Checklist

**MANDATORY before ending any work session:**

- [ ] **Update `docs/SESSION_STATUS.md`**
  - Mark completed tasks as ✅
  - Update "Completed This Session" section
  - Define "Next Session Goals"
  - Document any blockers or decisions

- [ ] **Commit all changes**
  - Stage all modified files
  - Write clear commit message
  - Reference framework sections if applicable

- [ ] **Push to GitHub**
  - Verify all commits pushed
  - Check GitHub for successful push

- [ ] **Update environment notes**
  - Document any new dependencies added
  - Note any configuration changes
  - Record any issues encountered

**SESSION_STATUS.md Template:**
```markdown
## Completed This Session (YYYY-MM-DD)
- [x] Task completed
- [x] Another task completed

## Blockers/Decisions
- [Issue or decision made]

## Next Session Goals
Primary Objective: [What to accomplish next]
Tasks:
1. [Specific task]
2. [Specific task]
```

**Remember**: The framework is the specification. Code is the implementation. When in doubt, refer to the spec.

---

*Last Updated: Review and update SESSION_STATUS.md at the end of EVERY session.*
