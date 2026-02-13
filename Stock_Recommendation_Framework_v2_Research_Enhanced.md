# Stock Recommendation Methodology Framework v2.0
## Research-Enhanced with Model-First Intuitive Override

**Version 2.0 - Research Enhanced**  
**Last Updated:** February 2026

---

## Executive Summary

This framework combines evidence-based quantitative scoring with disciplined human judgment. The system operates on a **Model-First principle**: calculate objective scores using research-backed methodologies, then allow conscious, documented overrides based on your intuition. This approach preserves the benefits of systematic analysis while capturing insights that models miss.

**Core Innovation:** Your edge comes from identifying when markets overreact or underreact to information. The framework quantifies this systematically while preserving your ability to override when you see something the models don't.

**Key Changes from v1.0:**
- Updated weighting from 40/30/30 to **45/35/20** (Fundamental/Technical/Sentiment) based on academic research
- Replaced linear 0-100 scoring with **percentile ranking** across investment universe
- Restructured technical indicators: elevated cross-sectional momentum, replaced MACD and RSI overbought/oversold signals
- Converted subjective sentiment slider to **rules-based sentiment score + documented override**
- Added systematic override tracking and performance review

---

## Table of Contents

1. [Scoring Architecture Overview](#1-scoring-architecture-overview)
2. [Data Collection & Sources](#2-data-collection--sources)
3. [Fundamental Score (45% weight)](#3-fundamental-score-45-weight)
4. [Technical Score (35% weight)](#4-technical-score-35-weight)
5. [Sentiment Score (20% weight)](#5-sentiment-score-20-weight)
6. [Model-First Override System](#6-model-first-override-system)
7. [Final Recommendation Logic](#7-final-recommendation-logic)
8. [Override Tracking & Learning](#8-override-tracking--learning)
9. [API Integration Guide](#9-api-integration-guide)
10. [Implementation Roadmap](#10-implementation-roadmap)

---

## 1. Scoring Architecture Overview

### 1.1 The Two-Phase Process

**Phase 1: Model Calculation (Objective)**
```
Step 1: Calculate raw metrics for all stocks in universe
Step 2: Convert to percentile ranks (0-100) within universe
Step 3: Average percentile ranks within each pillar
Step 4: Apply base weights: 45% Fundamental + 35% Technical + 20% Sentiment
Step 5: Generate Base Composite Score (0-100 percentile)
```

**Phase 2: Intuitive Override (Subjective)**
```
Step 6: Review Base Composite Score
Step 7: Decide if override is warranted
Step 8: Document reasoning for any override
Step 9: Apply weight adjustments (±10 points max per pillar)
Step 10: Apply sentiment score adjustment (±15 points max)
Step 11: Calculate Final Composite Score
```

### 1.2 Why Percentile Ranking?

**Research Finding:** Gu, Kelly & Xiu (2020) showed that methods allowing nonlinear predictor interactions achieved out-of-sample Sharpe ratios of **1.35-1.45 vs 0.61 for linear models**.

**Implementation:** 
- Rank each metric within your universe (e.g., all S&P 500 stocks, or your watchlist of 50 stocks)
- A stock at 85th percentile for P/E means it's cheaper than 85% of universe
- Average ranks within each pillar to get pillar score
- Robust to outliers, handles skewed distributions naturally

**Example:**
```
Stock ABC:
- P/E rank: 78th percentile (cheaper than 78% of stocks)
- P/B rank: 82nd percentile  
- EV/EBITDA rank: 71st percentile
- ROE rank: 88th percentile
- Revenue growth rank: 65th percentile

Fundamental Score = Average(78, 82, 71, 88, 65) = 76.8
```

### 1.3 Base Weighting Rationale

| Factor | Base Weight | Range | Research Support |
|--------|------------|-------|------------------|
| **Fundamental** | 45% | 35-55% | Fama-French factors explain most long-term cross-sectional variation. AQR's diversified value metrics generate t-stats >2.0 across 30+ years. |
| **Technical** | 35% | 25-45% | Jegadeesh-Titman momentum: 1-1.5% monthly alpha for 3 decades. Asness et al.: momentum negatively correlated with value (-0.5 to -0.7), making combination powerful. |
| **Sentiment** | 20% | 10-30% | Baker-Wurgler: high sentiment predicts lower returns but concentrated in hard-to-value stocks. Weaker standalone predictive power but adds diversification. |

**Why not equal weights?** Equal weighting (33/33/33) would give sentiment the same influence as fundamentals despite weaker empirical support. The 45/35/20 split matches the evidence hierarchy.

---

## 2. Data Collection & Sources

### 2.1 Fundamental Data (Yahoo Finance, Alpha Vantage)

**Valuation Metrics:**
- P/E ratio (trailing and forward)
- P/B ratio
- P/S ratio  
- EV/EBITDA
- PEG ratio
- Dividend yield

**Quality Metrics:**
- ROE (Return on Equity)
- ROA (Return on Assets)
- Net profit margin
- Operating margin
- Gross margin
- Free cash flow / Revenue

**Growth Metrics:**
- Revenue growth (YoY, QoQ)
- EPS growth (YoY, 3-year CAGR)
- Book value growth
- Free cash flow growth

**Financial Health:**
- Current ratio
- Quick ratio
- Debt-to-Equity
- Interest coverage ratio
- Cash / Total assets

**Sector & Market Context:**
- Sector average metrics (for relative valuation)
- S&P 500 P/E ratio (market valuation)
- Risk-free rate (10-year Treasury)

### 2.2 Technical Data

**Price & Return Data:**
- Daily closing prices (1-year minimum)
- Total returns including dividends
- 12-month, 6-month, 3-month, 1-month returns

**Moving Averages:**
- 50-day Simple Moving Average (SMA)
- 200-day Simple Moving Average
- Moving Average Distance (MAD) = (50-day SMA - 200-day SMA) / 200-day SMA

**Volume Data:**
- Daily volume
- 20-day average volume
- 90-day average volume
- Relative volume (today vs. 20-day avg)

**Trend Indicators:**
- ADX (Average Directional Index) for trend strength
- Price position vs. 200-day MA (binary: above/below)

### 2.3 Sentiment Data

**Analyst Data:**
- Consensus price target (12-month)
- Number of Buy/Hold/Sell ratings
- Recent rating changes (upgrades/downgrades in past 30 days)
- Earnings estimate revisions (past 3 months)

**Market Sentiment:**
- Short interest as % of float
- Days to cover (short interest / avg daily volume)
- Put/Call ratio (10-day moving average)
- Insider transactions (past 6 months)

**Broader Market Sentiment:**
- VIX level and z-score vs. 1-year average
- AAII Bull-Bear spread (8-week MA)
- Equity fund flows (weekly)

---

## 3. Fundamental Score (45% weight)

### 3.1 Research Foundation

**Key Finding:** AQR's "Craftsmanship Alpha" research (Israel, Jiang & Ross 2017) showed that **diversified composite factors outperformed single metrics** in nearly every 5-year period since 1990. Use multiple measures per category.

### 3.2 Sub-Factor Calculation

**Value Component (33% of Fundamental Score)**

Metrics to rank (percentile within universe):
1. P/E ratio (lower is better → invert rank)
2. P/B ratio (lower is better → invert rank)
3. P/S ratio (lower is better → invert rank)
4. EV/EBITDA (lower is better → invert rank)
5. Dividend yield (higher is better)

```
Value Score = Average of 5 percentile ranks
Example: If stock ranks at 82, 76, 88, 71, 65 → Value = 76.4
```

**Quality Component (33% of Fundamental Score)**

Metrics to rank:
1. ROE (higher is better)
2. ROA (higher is better)
3. Net margin (higher is better)
4. Operating margin (higher is better)
5. Earnings stability (lower std dev of earnings → higher rank)

```
Quality Score = Average of 5 percentile ranks
```

**Growth Component (34% of Fundamental Score)**

Metrics to rank:
1. Revenue growth YoY (higher is better)
2. EPS growth YoY (higher is better)
3. Revenue growth 3-year CAGR (higher is better)
4. Free cash flow growth (higher is better)

```
Growth Score = Average of 4 percentile ranks
```

### 3.3 Fundamental Pillar Score

```
Fundamental Score = (Value × 0.33) + (Quality × 0.33) + (Growth × 0.34)

Example:
Value: 76.4
Quality: 88.2  
Growth: 62.5

Fundamental Score = (76.4 × 0.33) + (88.2 × 0.33) + (62.5 × 0.34)
                  = 25.2 + 29.1 + 21.3
                  = 75.6
```

This 75.6 means the stock ranks at the 76th percentile for fundamentals in your universe.

---

## 4. Technical Score (35% weight)

### 4.1 Research Foundation

**Key Changes from v1.0:**
- **Dropped:** MACD (redundant with MA signals), RSI overbought/oversold (weak predictive power)
- **Elevated:** Cross-sectional momentum (strongest academic support), MAD (cleaner trend signal)
- **Retained:** Moving average position (trend filter), volume qualification (momentum life cycle)

**Core Evidence:** Jegadeesh & Titman documented momentum across 30+ years and dozens of countries. Blitz et al. (2023) confirmed short-term momentum signals produce alpha uncorrelated with Fama-French factors.

### 4.2 Sub-Factor Calculation

**Cross-Sectional Momentum (35% of Technical Score)**

```
12-1 Month Return = Total return from 12 months ago to 1 month ago
                    (Excludes most recent month to avoid reversal effect)

Rank across universe: Percentile of this return
Higher rank = stronger momentum

Example: Stock returned 18% over 12-1 month period
         85% of universe had lower returns
         → Momentum Score = 85
```

**Trend Strength (25% of Technical Score)**

```
Two components:

1. Price vs. 200-day MA (Binary):
   - Above 200-day: 100 points
   - Below 200-day: 0 points

2. MAD (Moving Average Distance):
   MAD = (50-day MA - 200-day MA) / 200-day MA
   
   Rank MAD across universe: Higher MAD = stronger uptrend
   
Trend Score = (Binary × 0.5) + (MAD_rank × 0.5)

Example:
- Price at $105, 200-day MA at $98 → Binary = 100
- MAD = +4.5% → Ranks at 78th percentile
- Trend = (100 × 0.5) + (78 × 0.5) = 89
```

**Volume-Qualified Momentum (20% of Technical Score)**

Research (Lee & Swaminathan 2000): High-volume winners = late-stage momentum (reversal risk). Low-volume winners = early-stage momentum (more persistent).

```
Volume Qualifier:
- Calculate momentum score (as above)
- Calculate relative volume: Current avg volume / 90-day avg volume

If relative volume < 1.2 (low volume):
  → Volume-Qualified Score = Momentum Score + 10 (early stage bonus)
  
If relative volume 1.2 to 1.8 (normal):
  → Volume-Qualified Score = Momentum Score
  
If relative volume > 1.8 (high volume):
  → Volume-Qualified Score = Momentum Score - 10 (late stage penalty)

Cap at 0-100 range
```

**Relative Strength vs. Sector (10% of Technical Score)**

```
6-month return of stock vs. 6-month return of sector
Rank this spread across universe
Higher relative outperformance = higher score
```

**RSI Trend Confirmation (5% of Technical Score)**

Note: RSI is retained ONLY as binary trend confirmation, not overbought/oversold.

```
RSI(14):
- Above 50 → Bullish trend → 100 points
- Below 50 → Bearish trend → 0 points
```

**Multi-Speed Trend Blend (5% of Technical Score)**

```
Combine two trend signals:
1. Price > 20-day MA AND 20-day > 50-day → Short-term uptrend
2. Price > 50-day MA AND 50-day > 200-day → Long-term uptrend

Score:
- Both uptrends: 100
- One uptrend: 50  
- No uptrends: 0
```

### 4.3 Technical Pillar Score

```
Technical Score = (Momentum × 0.35) + (Trend × 0.25) + 
                  (Volume-Qualified × 0.20) + (Relative Strength × 0.10) + 
                  (RSI × 0.05) + (Multi-Speed × 0.05)

Example:
Momentum: 85
Trend: 89
Volume-Qualified: 75 (85 - 10 for high volume)
Relative Strength: 72
RSI: 100 (above 50)
Multi-Speed: 100 (both uptrends)

Technical = (85×0.35) + (89×0.25) + (75×0.20) + (72×0.10) + (100×0.05) + (100×0.05)
          = 29.75 + 22.25 + 15 + 7.2 + 5 + 5
          = 84.2
```

---

## 5. Sentiment Score (20% weight)

### 5.1 Research Foundation

**Key Change from v1.0:** Replace subjective ±15% adjustment with rules-based scoring, THEN allow documented override.

**Evidence:** 
- Rapach, Ringgenberg & Zhou (2016): Short interest has R² of 13% for aggregate returns - "arguably the strongest known predictor"
- Baker & Wurgler: Sentiment effects concentrated in hard-to-value stocks
- Hong & Kubik: Analysts systematically optimistic (career incentives)

### 5.2 Rules-Based Sentiment Score (Base)

**Market-Wide Sentiment Component (40% of Sentiment Score)**

```
Four indicators, each scored 0-100 then averaged:

1. VIX Z-Score (contrarian):
   Z = (Current VIX - 1-year mean) / 1-year std dev
   Score = 50 + (Z × 15)  [caps at 0-100]
   High VIX (fear) → Low score → Contrarian bullish
   
2. AAII Bear-Bull Spread (8-week MA, contrarian):
   Spread = % Bears - % Bulls
   If Spread > 20: Score = 75 (extreme pessimism → bullish)
   If Spread 10-20: Score = 60
   If Spread -10 to 10: Score = 50 (neutral)
   If Spread -20 to -10: Score = 40
   If Spread < -20: Score = 25 (extreme optimism → bearish)
   
3. Put/Call Ratio (10-day MA, contrarian):
   If P/C > 1.0: Score = 70 (fear → bullish)
   If P/C 0.8-1.0: Score = 55
   If P/C 0.6-0.8: Score = 45
   If P/C < 0.6: Score = 30 (greed → bearish)
   
4. Equity Fund Flows (directional):
   Strong inflows: Score = 30 (chasing → bearish)
   Neutral: Score = 50
   Strong outflows: Score = 70 (capitulation → bullish)

Market Sentiment = Average of 4 scores
```

**Stock-Specific Sentiment Component (60% of Sentiment Score)**

```
Four indicators, each scored 0-100 then averaged:

1. Short Interest (contrarian with threshold):
   Days to Cover < 3: Score = 50 (normal)
   Days to Cover 3-5: Score = 40 (mild concern)
   Days to Cover 5-8: Score = 30 (significant shorts)
   Days to Cover > 8: Score = 60 (potential contrarian opportunity)
   
   Note: Very high short interest can be either informed bearishness 
   OR setup for squeeze. Use 60 not 70+ to reflect ambiguity.
   
2. Analyst Revision Momentum (past 3 months):
   % of estimates revised UP in past 90 days:
   > 60%: Score = 75 (bullish)
   40-60%: Score = 60
   20-40%: Score = 40
   < 20%: Score = 25 (bearish)
   
3. Analyst Consensus vs. Fair Value (with systematic discount):
   
   Step 1: Apply discount to consensus target:
   - Large cap, low volatility: Discount 5%
   - Mid cap, moderate volatility: Discount 8%
   - Small cap, high volatility: Discount 12%
   
   Discounted Target = Consensus Target × (1 - Discount)
   
   Step 2: Calculate implied return:
   Return = (Discounted Target - Current Price) / Current Price
   
   Step 3: Score:
   > 20%: Score = 80
   10-20%: Score = 65
   0-10%: Score = 50
   -10 to 0%: Score = 35
   < -10%: Score = 20
   
4. Insider Activity (past 6 months):
   Cluster buying (3+ insiders within 1 month): Score = 75
   Single insider buying: Score = 60
   No activity: Score = 50
   Single insider selling: Score = 40
   Cluster selling: Score = 25

Stock Sentiment = Average of 4 scores
```

### 5.3 Base Sentiment Pillar Score

```
Base Sentiment Score = (Market Sentiment × 0.40) + (Stock Sentiment × 0.60)

Example:
Market Sentiment = 58 (mildly bearish VIX, neutral AAII, etc.)
Stock Sentiment = 42 (high short interest, downgrades, insider selling)

Base Sentiment = (58 × 0.40) + (42 × 0.60)
                = 23.2 + 25.2
                = 48.4
```

**This is what the model says. Now you decide if you agree or want to override.**

---

## 6. Model-First Override System

### 6.1 The Override Philosophy

**You see the base score first.** Then you ask yourself: "Do I see something the model doesn't?"

The model captures:
- Quantifiable fundamentals
- Price patterns
- Observable sentiment indicators

You might see:
- Management quality changes
- Industry shifts before they show in data
- Temporary vs. structural problems
- Market narrative vs. reality gaps

### 6.2 Two Types of Override

**Override Type 1: Weight Adjustment**

Adjust pillar weights based on market regime or stock characteristics.

```
Base Weights: 45% Fundamental / 35% Technical / 20% Sentiment

Your Permissible Ranges:
- Fundamental: 35-55% (±10 from base)
- Technical: 25-45% (±10 from base)
- Sentiment: 10-30% (±10 from base)

Must sum to 100%
```

**When to adjust weights:**

*Increase Fundamental (→ 50-55%):*
- Company undergoing structural improvement not yet in metrics
- Industry tailwinds just beginning
- Strong earnings quality vs. reported earnings
- Rangebound/choppy market (technicals less reliable)

*Increase Technical (→ 40-45%):*
- Strong momentum regime across market
- Breakout from consolidation pattern
- Sector rotation favoring stock's momentum
- Fundamentals are stable/neutral (not driving story)

*Increase Sentiment (→ 25-30%):*
- High volatility environment (your contrarian edge matters more)
- Obvious market overreaction to news
- Stock in "hard to value" category (small cap, unprofitable, high growth)
- Divergence between fundamentals and sentiment is extreme

**Override Type 2: Sentiment Score Adjustment**

After seeing the base sentiment score (0-100), you can adjust it by ±15 points.

```
Base Sentiment Score: 48 (calculated from rules)

Your View: "The short interest is informed BUT the insider selling 
was tax-related and the analyst downgrades are based on outdated 
supply chain concerns that were resolved last week. Sentiment too negative."

Adjustment: +12 points
Final Sentiment Score: 60

Impact: Will increase overall composite score
```

### 6.3 Override Decision Tree

```
START: Review Base Composite Score

Question 1: Is the score directionally wrong?
├─ NO → No override needed, proceed to recommendation
└─ YES → Continue to Question 2

Question 2: Can you articulate SPECIFIC information the model missed?
├─ NO → Do not override (you're second-guessing, not correcting)
└─ YES → Continue to Question 3

Question 3: Is this information:
├─ Public but not yet in data (recent news, mgmt change) → Override warranted
├─ Your private research/analysis → Override warranted  
├─ Gut feel/emotional reaction → Do NOT override
└─ Sector/macro view → Consider weight adjustment instead

Question 4: How would you explain this to a skeptic?
├─ Can articulate clearly → Proceed with override
└─ Can't articulate → Do NOT override
```

### 6.4 Override Documentation Template

**MANDATORY for every override. No override without documentation.**

```
═══════════════════════════════════════════════════════════
STOCK OVERRIDE LOG
═══════════════════════════════════════════════════════════
Stock: [Ticker]
Date: [Date]
Current Price: $[X]

─────────────────────────────────────────────────────────
BASE MODEL OUTPUT
─────────────────────────────────────────────────────────
Fundamental Score: [X]/100
Technical Score: [X]/100  
Base Sentiment Score: [X]/100

Base Weights: 45/35/20
Base Composite: [X]/100 percentile
Base Recommendation: [STRONG BUY/BUY/HOLD/SELL/STRONG SELL]

─────────────────────────────────────────────────────────
YOUR OVERRIDE
─────────────────────────────────────────────────────────
Override Type: [Weight Adjustment / Sentiment Adjustment / Both]

Weight Adjustment (if any):
  Fundamental: 45% → [X]%
  Technical: 35% → [X]%
  Sentiment: 20% → [X]%
  
Sentiment Score Adjustment (if any):
  Base Sentiment: [X] → Adjusted: [X]
  Change: [+/- X] points

Adjusted Composite: [X]/100 percentile
Final Recommendation: [STRONG BUY/BUY/HOLD/SELL/STRONG SELL]

─────────────────────────────────────────────────────────
REASONING (REQUIRED)
─────────────────────────────────────────────────────────
What does the model miss?
[Your explanation]

Why is your view more accurate?
[Your explanation]

What would prove you wrong?
[Your falsification criteria]

Conviction Level: [Low/Medium/High]

─────────────────────────────────────────────────────────
6-MONTH REVIEW (Update after 6 months)
─────────────────────────────────────────────────────────
Stock Price Then: $[X]
Stock Price Now: $[X]
Return: [X]%

Sector Return: [X]%
Market Return: [X]%

Override Result: [Helped / Hurt / Neutral]

What did you learn?
[Your reflection]

═══════════════════════════════════════════════════════════
```

### 6.5 Override Guardrails

**Maximum Impact Rules:**

1. **Single Override Limit:**
   - Weight adjustment alone: Max ±10 percentile impact on composite
   - Sentiment adjustment alone: Max ±3 percentile impact on composite
   - Combined overrides: Max ±12 percentile impact on composite

2. **Extreme Override Flag:**
   - If final score differs from base by >15 percentiles → REQUIRES HIGH CONVICTION
   - Document 3 specific pieces of evidence supporting override
   - Consider reducing position size even if conviction is high

3. **Override Frequency Target:**
   - Aim for overrides on <30% of stocks evaluated
   - If you're overriding >50%, the base model weights may need adjustment
   - Track quarterly: Are you systematically disagreeing with one pillar?

4. **Forbidden Overrides:**
   - Cannot override to move from SELL to BUY (or vice versa) without extraordinary justification
   - Cannot use override to "make the numbers work" for a predetermined decision
   - Cannot override based on emotional attachment to a position

---

## 7. Final Recommendation Logic

### 7.1 Calculate Final Composite Score

```
Step 1: Apply your weight overrides (or use base 45/35/20)

Step 2: Apply sentiment score override (or use base sentiment)

Step 3: Calculate Final Composite
Final Composite = (Fundamental × Weight_F) + 
                  (Technical × Weight_T) + 
                  (Adjusted_Sentiment × Weight_S)

Step 4: Determine percentile rank of Final Composite
```

### 7.2 Recommendation Thresholds (Percentile-Based)

| Final Percentile | Recommendation | Expected Behavior | Position Size |
|-----------------|----------------|-------------------|---------------|
| **≥85th** | **STRONG BUY** | Top 15% of universe; highest conviction | 8-10% of portfolio |
| **70th-84th** | **BUY** | Above-average expected returns | 5-7% of portfolio |
| **30th-69th** | **HOLD** | Insufficient edge to act | Maintain current (or 3-4% if new) |
| **16th-29th** | **SELL** | Below-average expected returns | Reduce to <3% |
| **≤15th** | **STRONG SELL** | Bottom 15%; highest negative conviction | Exit completely |

### 7.3 Conviction Modifiers

**Signal Agreement Score:**
Calculate what % of individual sub-signals agree on direction.

```
Example:
Fundamental sub-factors: Value=82, Quality=88, Growth=62
→ 3 out of 3 are above 50 (bullish) = 100% agreement

Technical sub-factors: Momentum=85, Trend=89, Volume-Qual=75, Rel Strength=72
→ 4 out of 4 above 50 = 100% agreement

Sentiment sub-factors: Market=58, Stock=42
→ 1 out of 2 above 50 = 50% agreement

Overall Agreement = (100 + 100 + 50) / 3 = 83% agreement

High agreement (>75%): Increase conviction → Increase position size by 20%
Low agreement (<50%): Decrease conviction → Reduce position size by 30%
```

### 7.4 Risk Adjustments

**Downgrade by one level if:**
- Beta > 1.5 (high volatility)
- Debt/Equity > 2.0 (financial risk)  
- Negative free cash flow for 3+ quarters
- Sector under regulatory pressure
- Low liquidity (avg daily volume < $10M)

**Upgrade by one level if:**
- Insider buying >5% of shares in past 3 months
- Short interest >15% (potential squeeze if fundamentals/technicals bullish)
- Stock breaking out after 6+ month consolidation
- Sector with strong demonstrable tailwinds

---

## 8. Override Tracking & Learning

### 8.1 Quarterly Override Review

Every quarter, analyze your override performance:

**Metrics to Calculate:**

1. **Override Hit Rate**
```
Overrides that improved outcome / Total overrides

Improved = Final return beat what base model would have recommended
```

2. **Override Alpha**
```
Average return of overridden positions 
MINUS 
Average return of non-overridden positions with same base score

Positive = your overrides add value
Negative = you're destroying value vs. model
```

3. **Override Pattern Analysis**
```
Category analysis:
- Weight adjustments: Win rate by type (increase Fundamental, etc.)
- Sentiment adjustments: Win rate by direction (+adjustment vs. -adjustment)
- Sector: Which sectors do you override well vs. poorly?
- Market regime: Do overrides work better in bull vs. bear markets?
```

### 8.2 Learning Template

```
═══════════════════════════════════════════════════════════
QUARTERLY OVERRIDE REVIEW
═══════════════════════════════════════════════════════════
Quarter: [Q1 2026]

─────────────────────────────────────────────────────────
SUMMARY STATISTICS
─────────────────────────────────────────────────────────
Total stocks evaluated: [X]
Stocks overridden: [X] ([X]%)
Weight adjustments: [X]
Sentiment adjustments: [X]
Both: [X]

─────────────────────────────────────────────────────────
PERFORMANCE
─────────────────────────────────────────────────────────
Override hit rate: [X]% (target: >55%)
Override alpha: [+/-X]% (target: >0%)

Best override: [Stock, +X% outperformance]
Worst override: [Stock, -X% underperformance]

─────────────────────────────────────────────────────────
PATTERNS DISCOVERED
─────────────────────────────────────────────────────────
What types of overrides worked?
[Your findings]

What types of overrides failed?
[Your findings]

Sectors where you have edge:
[List]

Sectors where you should trust model:
[List]

─────────────────────────────────────────────────────────
ACTION ITEMS
─────────────────────────────────────────────────────────
1. [Specific change to approach]
2. [Specific change to approach]
3. [Specific change to approach]

─────────────────────────────────────────────────────────
BASE MODEL CALIBRATION
─────────────────────────────────────────────────────────
Should base weights change?
[Yes/No - if yes, propose new base weights]

Should any sub-factors be added/removed?
[Your recommendations]

═══════════════════════════════════════════════════════════
```

### 8.3 Continuous Improvement Cycle

```
Quarter 1: Run system with 45/35/20 base
         → Track overrides
         
Quarter 2: Review override patterns
         → Identify systematic adjustments you make
         
Quarter 3: Test if systematic adjustments should become base model changes
         → Example: "I always increase Technical in momentum markets"
         → Solution: Add momentum regime detector to auto-adjust weights
         
Quarter 4: Implement improvements
         → Your intuition becomes systematized
         → Model gets better, you override less frequently
         → Your remaining overrides capture higher-quality insights
```

---

## 9. API Integration Guide

### 9.1 Yahoo Finance (yfinance Python library)

```python
import yfinance as yf
import pandas as pd
import numpy as np

ticker = yf.Ticker("AAPL")

# Fundamental data
info = ticker.info
pe_ratio = info.get('forwardPE')
pb_ratio = info.get('priceToBook')
roe = info.get('returnOnEquity')
profit_margin = info.get('profitMargins')
revenue_growth = info.get('revenueGrowth')
debt_to_equity = info.get('debtToEquity')

# Price and technical data
hist = ticker.history(period="1y")
current_price = hist['Close'].iloc[-1]

# Calculate moving averages
hist['MA_50'] = hist['Close'].rolling(window=50).mean()
hist['MA_200'] = hist['Close'].rolling(window=200).mean()

# Calculate MAD
mad = (hist['MA_50'].iloc[-1] - hist['MA_200'].iloc[-1]) / hist['MA_200'].iloc[-1]

# Calculate momentum (12-1 month return)
price_12m_ago = hist['Close'].iloc[-252] if len(hist) > 252 else hist['Close'].iloc[0]
price_1m_ago = hist['Close'].iloc[-21]
momentum_return = (price_1m_ago - price_12m_ago) / price_12m_ago

# Analyst data
analyst_price_target = info.get('targetMeanPrice')
num_buy = info.get('numberOfAnalystOpinions')  # May need to parse recommendations
```

### 9.2 Alpha Vantage API

```python
import requests

API_KEY = 'your_alpha_vantage_key'
symbol = 'AAPL'

# Fundamental data
url = f'https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={API_KEY}'
response = requests.get(url)
data = response.json()

pe_ratio = float(data.get('PERatio', 0))
pb_ratio = float(data.get('PriceToBookRatio', 0))
profit_margin = float(data.get('ProfitMargin', 0))
roe = float(data.get('ReturnOnEquityTTM', 0))

# Technical indicators
# RSI
url = f'https://www.alphavantage.co/query?function=RSI&symbol={symbol}&interval=daily&time_period=14&series_type=close&apikey={API_KEY}'
response = requests.get(url)
rsi_data = response.json()
current_rsi = float(list(rsi_data['Technical Analysis: RSI'].values())[0]['RSI'])

# SMA
url = f'https://www.alphavantage.co/query?function=SMA&symbol={symbol}&interval=daily&time_period=200&series_type=close&apikey={API_KEY}'
response = requests.get(url)
sma_data = response.json()
sma_200 = float(list(sma_data['Technical Analysis: SMA'].values())[0]['SMA'])
```

### 9.3 Additional Data Sources

**For Short Interest:**
- Finviz API or web scraping
- Yahoo Finance (basic short % of float)
- FINRA short interest data (twice monthly)

**For Insider Trading:**
- SEC Form 4 filings via SEC EDGAR API
- OpenInsider.com (for aggregated data)
- Yahoo Finance insider transactions tab

**For Analyst Data:**
- FinancialModelingPrep API
- Alpha Vantage earnings endpoints
- Benzinga API (paid)

**For Sentiment Indicators:**
- CBOE for VIX and Put/Call ratio
- AAII.com for Bull-Bear spread (subscription)
- Fund flow data from ICI.org or Bloomberg

---

## 10. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Week 1: Data Infrastructure**
- Set up API access (Yahoo Finance, Alpha Vantage, others)
- Create database or spreadsheet to store stock universe
- Build data collection scripts
- Test data retrieval for 10-20 stocks

**Week 2: Calculation Engine**
- Implement percentile ranking function
- Build calculators for each sub-factor
- Test on sample stocks
- Validate calculations against known values

### Phase 2: Core Model (Weeks 3-4)

**Week 3: Pillar Scoring**
- Implement Fundamental score calculation (value, quality, growth)
- Implement Technical score calculation (momentum, trend, volume)
- Implement base Sentiment score calculation (rules-based)
- Test end-to-end on 20 stocks

**Week 4: Composite & Recommendations**
- Implement weighted composite calculation
- Create percentile-based recommendation logic
- Build risk adjustment rules
- Generate sample recommendations

### Phase 3: Override System (Weeks 5-6)

**Week 5: Override Interface**
- Design override input form/interface
- Implement weight adjustment logic
- Implement sentiment override logic
- Create documentation templates

**Week 6: Tracking System**
- Build override log database/spreadsheet
- Create tracking dashboards
- Set up quarterly review templates
- Test override workflow

### Phase 4: Backtesting (Weeks 7-8)

**Week 7: Historical Testing**
- Collect 12 months of historical data for 50 stocks
- Run model on historical data (simulate base scores)
- Calculate hypothetical returns
- Identify any obvious issues

**Week 8: Refinement**
- Adjust sub-factor weights if needed
- Calibrate thresholds
- Test sensitivity to different market regimes
- Document findings

### Phase 5: Live Testing (Weeks 9-12)

**Week 9: Paper Trading**
- Run model weekly on live data
- Generate recommendations
- Track performance (no real money)
- Practice override documentation

**Weeks 10-12: Continued Paper Trading**
- Build confidence in model
- Refine override decision process
- Accumulate override examples
- Prepare for real capital deployment

### Phase 6: Production (Week 13+)

**Week 13: Go Live**
- Start with small positions (1-3% each)
- Limit to 5-10 positions initially
- Document every decision
- Review weekly

**Month 2-3: Scale Up**
- Increase position sizes gradually
- Expand to more stocks
- Continue documenting overrides
- First quarterly review at end of month 3

**Ongoing:**
- Weekly: Update scores for existing positions
- Monthly: Full scan of universe for new opportunities
- Quarterly: Override performance review and model calibration
- Annually: Comprehensive methodology review

---

## Appendix A: Calculation Quick Reference

### Percentile Rank Function
```python
def percentile_rank(value, universe_values):
    """
    Calculate percentile rank of value within universe.
    Higher value = higher rank (for metrics like ROE)
    Lower value = higher rank needs INVERTING (for P/E)
    """
    rank = (np.sum(universe_values < value) / len(universe_values)) * 100
    return rank

# For "lower is better" metrics like P/E, use:
def percentile_rank_inverted(value, universe_values):
    rank = (np.sum(universe_values > value) / len(universe_values)) * 100
    return rank
```

### Base Composite Score
```python
def calculate_base_composite(fundamental_score, technical_score, base_sentiment_score):
    """
    Calculate base composite using research-backed weights.
    """
    composite = (fundamental_score * 0.45 + 
                 technical_score * 0.35 + 
                 base_sentiment_score * 0.20)
    return composite
```

### Override Application
```python
def apply_override(fundamental_score, technical_score, base_sentiment_score,
                   weight_f=0.45, weight_t=0.35, weight_s=0.20,
                   sentiment_adjustment=0):
    """
    Apply weight and sentiment overrides.
    """
    # Apply sentiment adjustment (±15 max)
    adjusted_sentiment = base_sentiment_score + sentiment_adjustment
    adjusted_sentiment = np.clip(adjusted_sentiment, 0, 100)
    
    # Calculate final composite with custom weights
    final_composite = (fundamental_score * weight_f + 
                       technical_score * weight_t + 
                       adjusted_sentiment * weight_s)
    
    return final_composite, adjusted_sentiment
```

### Recommendation from Percentile
```python
def get_recommendation(percentile_score):
    """
    Convert percentile score to recommendation.
    """
    if percentile_score >= 85:
        return "STRONG BUY"
    elif percentile_score >= 70:
        return "BUY"
    elif percentile_score >= 30:
        return "HOLD"
    elif percentile_score >= 15:
        return "SELL"
    else:
        return "STRONG SELL"
```

---

## Appendix B: Example Stock Evaluation with Override

### Stock: XYZ Technology Corp

**Step 1: Collect Data**
- Current Price: $142.50
- Sector: Technology
- Universe: S&P 500 (500 stocks)

**Step 2: Calculate Sub-Factors (all in percentiles)**

*Fundamental:*
- P/E: 22 vs sector avg 28 → 79th percentile (cheaper than 79%)
- P/B: 4.2 vs sector avg 5.1 → 74th percentile
- ROE: 18% → 82nd percentile
- Net Margin: 12% → 76th percentile
- Revenue Growth: 15% YoY → 68th percentile

*Technical:*
- 12-1 month return: +18% → 85th percentile
- Price vs 200-MA: Above → 100 points on binary
- MAD: +4.5% → 78th percentile
- Volume: Low relative volume → Early stage bonus

*Sentiment:*
- Market sentiment: VIX elevated, AAII bearish → 62
- Stock sentiment: Short interest moderate, analyst neutral → 45
- Base Sentiment Score: (62 × 0.4) + (45 × 0.6) = 51.8

**Step 3: Calculate Pillar Scores**

```
Fundamental = (79+74+82+76+68) / 5 = 75.8

Technical = (85×0.35) + (89×0.25) + (95×0.20) + (72×0.10) + (100×0.05) + (100×0.05)
          = 88.1

Base Sentiment = 51.8
```

**Step 4: Calculate Base Composite**

```
Base Composite = (75.8 × 0.45) + (88.1 × 0.35) + (51.8 × 0.20)
               = 34.11 + 30.84 + 10.36
               = 75.31

Percentile: 75th
Base Recommendation: BUY
```

**Step 5: MODEL-FIRST REVIEW - Do You Override?**

**Your Analysis:**
"The model says BUY at 75th percentile. Let me review:

Fundamentals (75.8): Solid. I agree - reasonable valuation with good profitability.

Technical (88.1): Very strong momentum and trend. I agree.

Sentiment (51.8): Base model says neutral sentiment. BUT I disagree here.

Why I disagree with sentiment score:
1. Short interest is actually informed sellers (NOT contrarian opportunity) - there's a supply chain issue emerging that shorts know about but isn't in financial data yet
2. The 'neutral analyst' consensus is masking that 3 analysts downgraded in past 2 weeks citing this issue
3. Management's recent commentary on earnings call was evasive about supplier problems

The model's sentiment is TOO OPTIMISTIC. I see risk the model doesn't capture."

**Your Override Decision:**

```
Override Type: Sentiment Adjustment

Weight Adjustment: None (keep 45/35/20)

Sentiment Adjustment: -10 points
Base Sentiment: 51.8 → Adjusted: 41.8
Reasoning: Supply chain concerns not captured by model. Short sellers 
appear informed. Analyst downgrades are material not noise.

Conviction: Medium (not changing to SELL, but lowering enthusiasm)
```

**Step 6: Calculate Final Composite with Override**

```
Final Composite = (75.8 × 0.45) + (88.1 × 0.35) + (41.8 × 0.20)
                = 34.11 + 30.84 + 8.36
                = 73.31

Percentile: 73rd
Final Recommendation: BUY (but lower confidence)
```

**Impact of Your Override:**
- Moved from 75th percentile → 73rd percentile
- Stays in BUY range (70-84th) but at lower end
- Suggests smaller position size or tighter stop-loss
- Override captured risk model missed

**Documentation (Mandatory):**
```
Stock: XYZ
Override: -10 sentiment points
Reason: Emerging supply chain issue visible in insider/analyst behavior 
        but not yet in financial metrics
Falsification: If Q3 earnings show supply chain is NOT an issue
Review in: 6 months
```

---

## Appendix C: Research Citations

**Factor Weighting:**
- Fama & French (1992, 1993, 2015): Common risk factors in stock returns
- AQR Capital Management (2020): Israel, Laursen & Richardson - Value investing research
- Asness, Moskowitz & Pedersen (2013): Value and momentum everywhere
- MSCI (2018): Adaptive Multi-Factor Allocation

**Technical Indicators:**
- Jegadeesh & Titman (1993, 2001, 2023): Returns to buying winners and selling losers
- Brock, Lakonishok & LeBaron (1992): Simple technical trading rules
- Levine & Pedersen (2016): Which trend is your friend?
- Lee & Swaminathan (2000): Price momentum and trading volume

**Sentiment & Behavioral:**
- Baker & Wurgler (2006, 2007): Investor sentiment and the cross-section of stock returns
- Rapach, Ringgenberg & Zhou (2016): Short interest and aggregate stock returns
- Hong & Kubik (2003): Analyzing the analysts: Career concerns and biased forecasts
- Tetlock (2007): Giving content to investor sentiment

**Percentile Ranking:**
- Gu, Kelly & Xiu (2020): Empirical asset pricing via machine learning
- Deutsche Bank (2014): Seven sins of quantitative investing
- Goldman Sachs Asset Management: Multi-factor investing research

---

## Document Version Control

**Version 2.0 Changes:**
- Implemented research-backed 45/35/20 weighting (from 40/30/30)
- Replaced linear scoring with percentile ranking
- Restructured technical indicators based on academic evidence
- Converted sentiment from subjective slider to rules-based + override
- Added Model-First override system with mandatory documentation
- Added quarterly review and learning framework

**Review Schedule:**
- Monthly: Check if any sub-factors need adjustment
- Quarterly: Override performance review
- Annually: Full methodology review incorporating learnings

**Next Version Preview (v3.0):**
- Regime detection for automatic weight adjustment
- Machine learning enhancement for sub-factor combinations
- Expanded universe beyond equities (ETFs, international)
- Integration with portfolio construction and risk management

---

*This framework combines the best of quantitative rigor with human judgment. The model does the heavy lifting; your intuition provides the edge. Document everything, review quarterly, and continuously improve.*

**Remember: The goal is not to be right every time. The goal is to be right more often than wrong, and to learn from both successes and failures.**
