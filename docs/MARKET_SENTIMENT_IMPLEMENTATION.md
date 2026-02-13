# Market Sentiment Implementation Guide

**Status:** Ready for implementation (research complete)
**Priority:** MEDIUM (Phase 2, Task #1)
**Framework Reference:** Section 5.1

---

## Overview

Implement all 4 market-wide sentiment indicators to complete the sentiment pillar (currently defaults to 50.0 neutral).

**Current State:** Market sentiment = 50.0 (placeholder)
**Target State:** Market sentiment = dynamic score based on 4 real indicators
**Impact:** Sentiment scores will show greater variation (currently 45.5-54.5)

---

## 1. VIX Z-Score (EASY) ✅

### Data Source
- **Provider:** Yahoo Finance (via yfinance)
- **Ticker:** `^VIX`
- **Availability:** FREE, historical data since 1990
- **URL:** https://finance.yahoo.com/quote/%5EVIX/history/

### Implementation
```python
import yfinance as yf

# Fetch VIX data
vix = yf.Ticker("^VIX")
vix_history = vix.history(period="1y")  # Get 1 year for z-score calculation
```

### Scoring Formula (Framework Section 5.1)
```
Z = (Current VIX - 1-year mean) / 1-year std dev
Score = 50 + (Z × 15)  [capped at 0-100]

High VIX (fear) → Low score → Contrarian bullish
Low VIX (complacency) → High score → Contrarian bearish
```

### Example Calculation
- Current VIX: 20
- 1-year mean: 18
- 1-year std: 4
- Z-score: (20 - 18) / 4 = 0.5
- Score: 50 + (0.5 × 15) = 57.5

---

## 2. AAII Sentiment Survey (MODERATE) ⚠️

### Data Sources
**Option A - Quandl API (Recommended):**
- Requires free API key registration
- Programmatic access via Python
- URL: https://data.nasdaq.com/ (search "AAII")

**Option B - Direct Scraping:**
- URL: https://www.aaii.com/sentimentsurvey/sent_results
- Weekly data publicly available
- Requires web scraping (BeautifulSoup/Selenium)

**Option C - MacroMicro:**
- URL: https://en.macromicro.me/charts/20828/us-aaii-sentimentsurvey
- May have API or downloadable CSV

### Scoring Formula (Framework Section 5.1)
```
Spread = % Bears - % Bulls (using 8-week moving average)

If Spread > 20: Score = 75 (extreme pessimism → bullish)
If Spread 10-20: Score = 60
If Spread -10 to 10: Score = 50 (neutral)
If Spread -20 to -10: Score = 40
If Spread < -20: Score = 25 (extreme optimism → bearish)
```

### Example Calculation
- Bulls: 30%, Bears: 40%, Neutral: 30%
- 8-week MA Spread: 40 - 30 = +10
- Score: 60 (mild pessimism → mildly bullish)

---

## 3. Put/Call Ratio (MODERATE) ⚠️

### Data Sources
**Option A - CBOE Direct:**
- Official source: Chicago Board Options Exchange
- URL: http://www.cboe.com/data/PutCallRatio.aspx
- Historical data available for download
- GitHub example: https://gist.github.com/breeko/6210432

**Option B - MacroMicro:**
- URL: https://en.macromicro.me/charts/449/us-cboe-options-put-call-ratio
- May have CSV export or API

**Option C - YCharts (Paid):**
- URL: https://ycharts.com/indicators/cboe_equity_put_call_ratio
- Not recommended (requires subscription)

### Scoring Formula (Framework Section 5.1)
```
Use 10-day moving average of equity Put/Call ratio

If P/C > 1.0: Score = 70 (fear → bullish)
If P/C 0.8-1.0: Score = 55
If P/C 0.6-0.8: Score = 45
If P/C < 0.6: Score = 30 (greed → bearish)
```

### Example Calculation
- 10-day MA Put/Call ratio: 0.85
- Score: 55 (moderate fear → mildly bullish)

---

## 4. Equity Fund Flows (COMPLEX) ⚠️⚠️

### Data Sources
**Option A - ICI Website:**
- Investment Company Institute
- URL: https://www.ici.org/research/stats/flows
- Weekly reports on estimated long-term mutual fund flows
- Manual download or web scraping required

**Option B - GitHub Dataset:**
- URL: https://github.com/datasets/investor-flow-of-funds-us
- Monthly data from 2007 onwards
- CSV format, easy to integrate
- May be outdated (check last update)

**Option C - Nasdaq Data Link (ICI1):**
- URL: https://data.nasdaq.com/databases/ICI1
- May require paid subscription for API access

### Scoring Formula (Framework Section 5.1)
```
Directional (NOT contrarian like other indicators)

Strong inflows: Score = 30 (chasing → bearish)
Neutral: Score = 50
Strong outflows: Score = 70 (capitulation → bullish)

Note: "Strong" needs to be defined based on historical percentiles
Suggestion: Use z-score similar to VIX
```

### Example Calculation
- Weekly inflows: +$5B (above average)
- Score: 35 (strong inflows → bearish signal)

---

## Implementation Plan

### Step 1: Database Schema
Create `MarketSentiment` table in `src/database/models.py`:

```python
class MarketSentiment(Base):
    __tablename__ = 'market_sentiment'

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True, index=True)

    # VIX data
    vix_value = Column(Float)
    vix_zscore = Column(Float)
    vix_score = Column(Float)

    # AAII data
    aaii_bulls = Column(Float)  # Percentage
    aaii_bears = Column(Float)
    aaii_neutral = Column(Float)
    aaii_spread = Column(Float)  # Bears - Bulls
    aaii_score = Column(Float)

    # Put/Call data
    putcall_ratio = Column(Float)
    putcall_score = Column(Float)

    # Fund flows data
    fund_flows = Column(Float)  # Billions of dollars
    fund_flows_score = Column(Float)

    # Composite
    market_sentiment_score = Column(Float)  # Average of 4 indicators

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

### Step 2: Data Collection Script
Create `scripts/collect_market_sentiment.py`:

1. Fetch VIX data (easy - yfinance)
2. Fetch AAII sentiment (Quandl or scraping)
3. Fetch Put/Call ratio (CBOE scraping or API)
4. Fetch Fund Flows (ICI or GitHub dataset)
5. Calculate scores for each indicator
6. Calculate composite market sentiment score
7. Store in database

### Step 3: Update Sentiment Calculator
Modify `src/calculators/sentiment.py`:

Update `calculate_market_sentiment()` method from placeholder to:

```python
def calculate_market_sentiment(self, market_data: Dict[str, any]) -> float:
    """Calculate market-wide sentiment from 4 indicators."""

    scores = []

    # 1. VIX z-score (contrarian)
    vix_score = self.calculate_vix_score(market_data.get('vix_zscore'))
    scores.append(vix_score)

    # 2. AAII Bear-Bull spread (contrarian)
    aaii_score = self.calculate_aaii_score(market_data.get('aaii_spread'))
    scores.append(aaii_score)

    # 3. Put/Call ratio (contrarian)
    putcall_score = self.calculate_putcall_score(market_data.get('putcall_ratio'))
    scores.append(putcall_score)

    # 4. Equity fund flows (directional)
    flows_score = self.calculate_flows_score(market_data.get('fund_flows'))
    scores.append(flows_score)

    # Average the 4 components
    market_sentiment = np.mean(scores)

    return market_sentiment
```

### Step 4: Integration
Update `scripts/calculate_scores.py`:

1. Load latest market sentiment data from database
2. Pass to sentiment calculator in `calculate_sentiment_score()` call
3. Verify sentiment scores show variation (not all ~50)

### Step 5: Testing
1. Run data collection: `python scripts/collect_market_sentiment.py`
2. Verify database populated correctly
3. Run score calculation: `python scripts/calculate_scores.py`
4. Verify sentiment scores vary based on market conditions
5. Add unit tests for new scoring methods

---

## Success Criteria

- ✅ MarketSentiment table created in database
- ✅ VIX data collected and z-score calculated
- ✅ AAII sentiment data collected (via Quandl or scraping)
- ✅ Put/Call ratio data collected
- ✅ Fund flows data collected
- ✅ All 4 scoring methods implemented in sentiment calculator
- ✅ Market sentiment score calculated (average of 4 indicators)
- ✅ Sentiment scores show variation (not defaulting to 50.0)
- ✅ Integration test with calculate_scores.py passes
- ✅ Documentation updated in SESSION_HISTORY.md

---

## Expected Impact

**Before:**
- Market sentiment: 50.0 (neutral placeholder)
- Sentiment pillar: 60% stock-specific only
- Sentiment scores: 45.5-54.5 (narrow range)

**After:**
- Market sentiment: Dynamic (varies with market conditions)
- Sentiment pillar: 40% market + 60% stock (complete)
- Sentiment scores: Wider variation based on market regime

**Example Scenarios:**
- High VIX + High AAII bears + High Put/Call + Outflows → Market Score ~70 (contrarian bullish)
- Low VIX + High AAII bulls + Low Put/Call + Inflows → Market Score ~30 (contrarian bearish)

---

## Notes & Considerations

1. **Data Frequency:**
   - VIX: Daily (real-time)
   - AAII: Weekly (Thursday release)
   - Put/Call: Daily
   - Fund Flows: Weekly (Wednesday release from ICI)

   **Recommendation:** Update market sentiment weekly (Thursday after AAII release)

2. **Historical Backfill:**
   - VIX: Can backfill to 1990 (via yfinance)
   - AAII: May have limited free historical data
   - Put/Call: CBOE has extensive historical data
   - Fund Flows: ICI has weekly data going back years

   **Recommendation:** Start with recent data (1 year), backfill if needed

3. **Error Handling:**
   - If any indicator is missing: Still calculate with available indicators
   - If <2 indicators available: Return neutral 50.0
   - Log warnings for missing data

4. **API Keys Required:**
   - Quandl/Nasdaq Data Link (free tier)
   - Consider rate limiting for web scraping

5. **Alternative Approaches:**
   - **Phase 1 (MVP):** VIX only (quick win)
   - **Phase 2:** VIX + Put/Call (moderate effort)
   - **Phase 3:** Add AAII + Fund Flows (complete)

   User chose full implementation (all 4) for next session.

---

## References

**Framework Document:** `docs/Stock_Recommendation_Framework_v2_Research_Enhanced.md` Section 5.1

**Research Sources:**
- [Yahoo Finance VIX Historical Data](https://finance.yahoo.com/quote/%5EVIX/history/)
- [AAII Sentiment Survey](https://www.aaii.com/sentimentsurvey/sent_results)
- [CBOE Put/Call Ratio Data](https://en.macromicro.me/charts/449/us-cboe-options-put-call-ratio)
- [ICI Fund Flows Data](https://www.ici.org/research/stats/flows)
- [GitHub Investor Flows Dataset](https://github.com/datasets/investor-flow-of-funds-us)

**Code References:**
- Sentiment Calculator: `src/calculators/sentiment.py` (line 320-357)
- Database Models: `src/database/models.py`
- Score Calculation: `scripts/calculate_scores.py`

---

**Last Updated:** 2026-02-13
**Status:** Ready for implementation in next session
**User Choice:** Option B (Full Implementation - all 4 indicators)
