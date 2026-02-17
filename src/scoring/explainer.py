"""
Score Explainability Module — generates human-readable text for each sub-component score.

Reads raw metrics from the database and combines them with calculated scores
to produce explanations like:
  "Trading at a P/E of 14.2 and P/B of 2.1 — cheaper than 56% of the universe."

Framework Reference: Sections 3-5 (Fundamental, Technical, Sentiment scoring)
"""

from typing import Dict, Optional

from sqlalchemy.orm import Session

from database.models import (
    FundamentalData, TechnicalIndicator, SentimentData,
    MarketSentiment, PriceData, Stock,
)


def _fmt(val, decimals=1, pct=False, prefix='') -> str:
    """Format a numeric value for display."""
    if val is None:
        return 'N/A'
    v = float(val)
    if pct:
        return f"{v * 100:.{decimals}f}%"
    return f"{prefix}{v:,.{decimals}f}"


def _score_label(score: Optional[float]) -> str:
    """Convert a 0-100 score to a qualitative label."""
    if score is None:
        return 'no data'
    s = float(score)
    if s >= 75:
        return 'strong'
    if s >= 60:
        return 'above average'
    if s >= 40:
        return 'moderate'
    if s >= 25:
        return 'below average'
    return 'weak'


class ScoreExplainer:
    """Generates human-readable explanations for stock score sub-components."""

    def explain(
        self,
        ticker: str,
        sub_components: Dict,
        session: Session,
    ) -> Dict[str, Dict[str, str]]:
        """Generate explanation text for all sub-components.

        Args:
            ticker: Stock ticker symbol.
            sub_components: Dict from latest_scores.json with keys
                'fundamental', 'technical', 'sentiment', each containing
                sub-score values.
            session: Database session for reading raw metrics.

        Returns:
            Nested dict: {pillar: {sub_component: explanation_string}}.
        """
        fund_data = self._load_fundamental(ticker, session)
        tech_data = self._load_technical(ticker, session)
        sent_data = self._load_sentiment(ticker, session)
        market_data = self._load_market_sentiment(session)
        price = self._load_latest_price(ticker, session)
        stock = session.query(Stock).filter_by(ticker=ticker).first()
        market_cap = float(stock.market_cap) if stock and stock.market_cap else None

        fund_sub = sub_components.get('fundamental', {}) or {}
        tech_sub = sub_components.get('technical', {}) or {}
        sent_sub = sub_components.get('sentiment', {}) or {}

        return {
            'fundamental': {
                'value': self._explain_value(fund_data, fund_sub.get('value_score')),
                'quality': self._explain_quality(fund_data, fund_sub.get('quality_score')),
                'growth': self._explain_growth(fund_data, fund_sub.get('growth_score')),
            },
            'technical': {
                'momentum': self._explain_momentum(tech_data, tech_sub.get('momentum_score')),
                'trend': self._explain_trend(tech_data, tech_sub.get('trend_score')),
                'volume_qualified': self._explain_volume_qualified(tech_data, tech_sub.get('volume_qualified_score')),
                'relative_strength': self._explain_relative_strength(tech_data, tech_sub.get('relative_strength_score')),
                'rsi': self._explain_rsi(tech_data, tech_sub.get('rsi_score')),
                'multi_speed': self._explain_multi_speed(tech_data, tech_sub.get('multi_speed_score')),
            },
            'sentiment': {
                'market': self._explain_market_sentiment(market_data, sent_sub.get('market_sentiment')),
                'stock': self._explain_stock_sentiment(sent_sub),
                'short_interest': self._explain_short_interest(sent_data, sent_sub.get('short_interest_score')),
                'revision': self._explain_revision(sent_data, sent_sub.get('revision_score')),
                'consensus': self._explain_consensus(sent_data, price, market_cap, sent_sub.get('consensus_score')),
                'insider': self._explain_insider(sent_data, sent_sub.get('insider_score')),
            },
        }

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_fundamental(ticker: str, session: Session) -> Optional[Dict]:
        row = session.query(FundamentalData).filter_by(ticker=ticker).first()
        if not row:
            return None
        return {
            'pe_ratio': float(row.pe_ratio) if row.pe_ratio else None,
            'pb_ratio': float(row.pb_ratio) if row.pb_ratio else None,
            'ps_ratio': float(row.ps_ratio) if row.ps_ratio else None,
            'ev_to_ebitda': float(row.ev_to_ebitda) if row.ev_to_ebitda else None,
            'dividend_yield': float(row.dividend_yield) if row.dividend_yield else None,
            'roe': float(row.roe) if row.roe else None,
            'roa': float(row.roa) if row.roa else None,
            'net_margin': float(row.net_margin) if row.net_margin else None,
            'operating_margin': float(row.operating_margin) if row.operating_margin else None,
            'gross_margin': float(row.gross_margin) if row.gross_margin else None,
            'revenue_growth_yoy': float(row.revenue_growth_yoy) if row.revenue_growth_yoy else None,
            'eps_growth_yoy': float(row.eps_growth_yoy) if row.eps_growth_yoy else None,
        }

    @staticmethod
    def _load_technical(ticker: str, session: Session) -> Optional[Dict]:
        row = (
            session.query(TechnicalIndicator)
            .filter_by(ticker=ticker)
            .order_by(TechnicalIndicator.calculation_date.desc())
            .first()
        )
        if not row:
            return None
        return {
            'momentum_12_1': float(row.momentum_12_1) if row.momentum_12_1 is not None else None,
            'momentum_6m': float(row.momentum_6m) if row.momentum_6m is not None else None,
            'momentum_3m': float(row.momentum_3m) if row.momentum_3m is not None else None,
            'momentum_1m': float(row.momentum_1m) if row.momentum_1m is not None else None,
            'sma_20': float(row.sma_20) if row.sma_20 is not None else None,
            'sma_50': float(row.sma_50) if row.sma_50 is not None else None,
            'sma_200': float(row.sma_200) if row.sma_200 is not None else None,
            'mad': float(row.mad) if row.mad is not None else None,
            'price_vs_200ma': row.price_vs_200ma,
            'relative_volume': float(row.relative_volume) if row.relative_volume is not None else None,
            'rsi_14': float(row.rsi_14) if row.rsi_14 is not None else None,
            'adx': float(row.adx) if row.adx is not None else None,
            'sector_relative_6m': float(row.sector_relative_6m) if row.sector_relative_6m is not None else None,
        }

    @staticmethod
    def _load_sentiment(ticker: str, session: Session) -> Optional[Dict]:
        row = session.query(SentimentData).filter_by(ticker=ticker).first()
        if not row:
            return None
        return {
            'days_to_cover': float(row.days_to_cover) if row.days_to_cover else None,
            'consensus_price_target': float(row.consensus_price_target) if row.consensus_price_target else None,
            'num_buy_ratings': int(row.num_buy_ratings) if row.num_buy_ratings else None,
            'num_hold_ratings': int(row.num_hold_ratings) if row.num_hold_ratings else None,
            'num_sell_ratings': int(row.num_sell_ratings) if row.num_sell_ratings else None,
            'num_analyst_opinions': int(row.num_analyst_opinions) if row.num_analyst_opinions else None,
            'upgrades_30d': int(row.upgrades_30d) if row.upgrades_30d else None,
            'downgrades_30d': int(row.downgrades_30d) if row.downgrades_30d else None,
            'estimate_revisions_up_90d': int(row.estimate_revisions_up_90d) if row.estimate_revisions_up_90d else None,
            'estimate_revisions_down_90d': int(row.estimate_revisions_down_90d) if row.estimate_revisions_down_90d else None,
            'insider_buys_6m': int(row.insider_buys_6m) if row.insider_buys_6m else None,
            'insider_sells_6m': int(row.insider_sells_6m) if row.insider_sells_6m else None,
            'insider_net_shares_6m': int(row.insider_net_shares_6m) if row.insider_net_shares_6m else None,
            'short_interest_pct': float(row.short_interest_pct) if row.short_interest_pct else None,
        }

    @staticmethod
    def _load_market_sentiment(session: Session) -> Optional[Dict]:
        row = (
            session.query(MarketSentiment)
            .order_by(MarketSentiment.date.desc())
            .first()
        )
        if not row:
            return None
        return {
            'market_sentiment_score': float(row.market_sentiment_score),
            'num_indicators_available': int(row.num_indicators_available),
            'vix_score': float(row.vix_score) if row.vix_score else None,
            'putcall_score': float(row.putcall_score) if row.putcall_score else None,
            'fund_flows_score': float(row.fund_flows_score) if row.fund_flows_score else None,
            'aaii_score': float(row.aaii_score) if row.aaii_score else None,
            'vix_value': float(row.vix_value) if row.vix_value else None,
            'putcall_ratio': float(row.putcall_ratio) if row.putcall_ratio else None,
        }

    @staticmethod
    def _load_latest_price(ticker: str, session: Session) -> Optional[float]:
        row = (
            session.query(PriceData)
            .filter_by(ticker=ticker)
            .order_by(PriceData.date.desc())
            .first()
        )
        if row and row.close:
            return float(row.close)
        return None

    # ------------------------------------------------------------------
    # Fundamental explanations
    # ------------------------------------------------------------------

    def _explain_value(self, data: Optional[Dict], score: Optional[float]) -> str:
        if not data:
            return "No fundamental data available."
        parts = []
        pe = data.get('pe_ratio')
        pb = data.get('pb_ratio')
        ps = data.get('ps_ratio')
        ev = data.get('ev_to_ebitda')
        dy = data.get('dividend_yield')
        if pe is not None:
            parts.append(f"P/E {_fmt(pe)}")
        if pb is not None:
            parts.append(f"P/B {_fmt(pb)}")
        if ps is not None:
            parts.append(f"P/S {_fmt(ps)}")
        if ev is not None:
            parts.append(f"EV/EBITDA {_fmt(ev)}")
        if dy is not None:
            parts.append(f"Div Yield {_fmt(dy, 2, pct=True)}")
        if not parts:
            return "No valuation metrics available."
        metrics_str = ', '.join(parts)
        label = _score_label(score)
        return f"{metrics_str}. Valuation is {label} vs. universe ({_fmt(score)}th pctl)."

    def _explain_quality(self, data: Optional[Dict], score: Optional[float]) -> str:
        if not data:
            return "No fundamental data available."
        parts = []
        roe = data.get('roe')
        roa = data.get('roa')
        nm = data.get('net_margin')
        om = data.get('operating_margin')
        gm = data.get('gross_margin')
        if roe is not None:
            parts.append(f"ROE {_fmt(roe, 1, pct=True)}")
        if roa is not None:
            parts.append(f"ROA {_fmt(roa, 1, pct=True)}")
        if nm is not None:
            parts.append(f"Net Margin {_fmt(nm, 1, pct=True)}")
        if om is not None:
            parts.append(f"Op Margin {_fmt(om, 1, pct=True)}")
        if gm is not None:
            parts.append(f"Gross Margin {_fmt(gm, 1, pct=True)}")
        if not parts:
            return "No quality metrics available."
        metrics_str = ', '.join(parts)
        label = _score_label(score)
        return f"{metrics_str}. Profitability is {label} ({_fmt(score)}th pctl)."

    def _explain_growth(self, data: Optional[Dict], score: Optional[float]) -> str:
        if not data:
            return "No fundamental data available."
        parts = []
        rg = data.get('revenue_growth_yoy')
        eg = data.get('eps_growth_yoy')
        if rg is not None:
            parts.append(f"Revenue {'+' if rg >= 0 else ''}{_fmt(rg, 1, pct=True)} YoY")
        if eg is not None:
            parts.append(f"EPS {'+' if eg >= 0 else ''}{_fmt(eg, 1, pct=True)} YoY")
        if not parts:
            return "No growth metrics available."
        metrics_str = ', '.join(parts)
        label = _score_label(score)
        return f"{metrics_str}. Growth is {label} ({_fmt(score)}th pctl)."

    # ------------------------------------------------------------------
    # Technical explanations
    # ------------------------------------------------------------------

    def _explain_momentum(self, data: Optional[Dict], score: Optional[float]) -> str:
        if not data:
            return "No technical data available."
        m12 = data.get('momentum_12_1')
        if m12 is None:
            return "12-1 month momentum not available."
        direction = 'gained' if m12 >= 0 else 'lost'
        return (
            f"12-1 month return: {'+' if m12 >= 0 else ''}{m12 * 100:.1f}% "
            f"({direction} over the past year ex. last month). "
            f"Momentum is {_score_label(score)} ({_fmt(score)}th pctl)."
        )

    def _explain_trend(self, data: Optional[Dict], score: Optional[float]) -> str:
        if not data:
            return "No technical data available."
        above_200 = data.get('price_vs_200ma')
        sma50 = data.get('sma_50')
        sma200 = data.get('sma_200')
        mad = data.get('mad')
        parts = []
        if above_200 is True:
            parts.append("Price above 200-day MA")
        elif above_200 is False:
            parts.append("Price below 200-day MA")
        if sma50 is not None and sma200 is not None:
            if sma50 > sma200:
                parts.append(f"50-day MA (${_fmt(sma50, 0)}) above 200-day (${_fmt(sma200, 0)})")
            else:
                parts.append(f"50-day MA (${_fmt(sma50, 0)}) below 200-day (${_fmt(sma200, 0)})")
        if mad is not None:
            parts.append(f"MAD {mad * 100:.1f}%")
        if not parts:
            return "No trend data available."
        return f"{'. '.join(parts)}. Trend is {_score_label(score)} ({_fmt(score)}th pctl)."

    def _explain_volume_qualified(self, data: Optional[Dict], score: Optional[float]) -> str:
        if not data:
            return "No technical data available."
        rv = data.get('relative_volume')
        if rv is None:
            return f"Relative volume not available. Score: {_fmt(score)}."
        if rv < 1.2:
            vol_desc = f"Relative volume {_fmt(rv, 2)} (low) — early-stage signal, +10 bonus"
        elif rv <= 1.8:
            vol_desc = f"Relative volume {_fmt(rv, 2)} (normal) — no adjustment"
        else:
            vol_desc = f"Relative volume {_fmt(rv, 2)} (high) — late-stage risk, -10 penalty"
        return f"{vol_desc}. Volume-qualified momentum is {_score_label(score)} ({_fmt(score)}th pctl)."

    def _explain_relative_strength(self, data: Optional[Dict], score: Optional[float]) -> str:
        if not data:
            return "No technical data available."
        sr = data.get('sector_relative_6m')
        if sr is None:
            return "Sector-relative return not available."
        direction = 'outperformed' if sr >= 0 else 'underperformed'
        return (
            f"{direction.capitalize()} sector by {'+' if sr >= 0 else ''}{sr * 100:.1f}pp over 6 months. "
            f"Relative strength is {_score_label(score)} ({_fmt(score)}th pctl)."
        )

    def _explain_rsi(self, data: Optional[Dict], score: Optional[float]) -> str:
        if not data:
            return "No technical data available."
        rsi = data.get('rsi_14')
        if rsi is None:
            return "RSI data not available."
        if rsi > 50:
            trend = "above 50 — confirms uptrend"
        else:
            trend = "at or below 50 — no uptrend confirmation"
        return f"RSI(14) at {_fmt(rsi)}. {trend.capitalize()}."

    def _explain_multi_speed(self, data: Optional[Dict], score: Optional[float]) -> str:
        if not data:
            return "No technical data available."
        sma20 = data.get('sma_20')
        sma50 = data.get('sma_50')
        sma200 = data.get('sma_200')
        if sma20 is None or sma50 is None or sma200 is None:
            return "Insufficient moving average data for multi-speed analysis."
        # We can't perfectly reconstruct current price here, but we can
        # describe the MA alignment which is the key input
        short_up = sma20 > sma50 if sma20 and sma50 else None
        long_up = sma50 > sma200 if sma50 and sma200 else None
        if score is not None and float(score) == 100:
            return "Both short-term (20>50 MA) and long-term (50>200 MA) trends aligned upward."
        elif score is not None and float(score) == 50:
            if short_up:
                return "Short-term trend up (20>50 MA), but long-term trend not confirmed."
            else:
                return "Long-term trend up (50>200 MA), but short-term trend not confirmed."
        else:
            return "Neither short-term nor long-term trend aligned upward."

    # ------------------------------------------------------------------
    # Sentiment explanations
    # ------------------------------------------------------------------

    def _explain_market_sentiment(self, data: Optional[Dict], score: Optional[float]) -> str:
        if not data:
            return "No market sentiment data available."
        n = data.get('num_indicators_available', 0)
        parts = []
        vix = data.get('vix_value')
        if vix is not None:
            parts.append(f"VIX at {_fmt(vix)}")
        pc = data.get('putcall_ratio')
        if pc is not None:
            parts.append(f"Put/Call ratio {_fmt(pc, 2)}")
        detail = f" ({', '.join(parts)})" if parts else ''
        return (
            f"Market-wide sentiment: {_fmt(score)} "
            f"({n}/4 indicators available){detail}. "
            f"Higher = more fear (contrarian bullish)."
        )

    def _explain_stock_sentiment(self, sent_sub: Dict) -> str:
        score = sent_sub.get('stock_sentiment')
        if score is None:
            return "No stock-specific sentiment data."
        label = _score_label(score)
        return f"Stock sentiment is {label} ({_fmt(score)}) — average of short interest, revision, consensus, and insider signals."

    def _explain_short_interest(self, data: Optional[Dict], score: Optional[float]) -> str:
        if not data:
            return "No sentiment data available."
        dtc = data.get('days_to_cover')
        si = data.get('short_interest_pct')
        if dtc is None and si is None:
            return f"No short interest data — score neutral at {_fmt(score)}."
        parts = []
        if dtc is not None:
            if dtc < 3:
                parts.append(f"Days to cover: {_fmt(dtc)} (normal)")
            elif dtc <= 5:
                parts.append(f"Days to cover: {_fmt(dtc)} (mild concern)")
            elif dtc <= 8:
                parts.append(f"Days to cover: {_fmt(dtc)} (significant)")
            else:
                parts.append(f"Days to cover: {_fmt(dtc)} (contrarian opportunity)")
        if si is not None:
            parts.append(f"Short interest: {_fmt(si, 1, pct=True)} of float")
        return f"{'. '.join(parts)}. Score: {_fmt(score)}."

    def _explain_revision(self, data: Optional[Dict], score: Optional[float]) -> str:
        if not data:
            return "No sentiment data available."
        up = data.get('estimate_revisions_up_90d')
        down = data.get('estimate_revisions_down_90d')
        if up is not None and down is not None:
            total = up + down
            if total > 0:
                up_pct = up / total * 100
                return (
                    f"{up} upward vs {down} downward revisions in 90 days "
                    f"({up_pct:.0f}% positive). "
                    f"Revision momentum is {_score_label(score)} ({_fmt(score)})."
                )
        # Fallback: check analyst ratings
        buy = data.get('num_buy_ratings')
        hold = data.get('num_hold_ratings')
        sell = data.get('num_sell_ratings')
        if buy is not None:
            return (
                f"No revision data — using analyst consensus proxy: "
                f"{buy} Buy, {hold or 0} Hold, {sell or 0} Sell. "
                f"Score: {_fmt(score)}."
            )
        return f"No revision or analyst data available — score neutral at {_fmt(score)}."

    def _explain_consensus(
        self, data: Optional[Dict], price: Optional[float],
        market_cap: Optional[float], score: Optional[float],
    ) -> str:
        if not data:
            return "No sentiment data available."
        target = data.get('consensus_price_target')
        if target is None or price is None:
            return f"No analyst price target available — score neutral at {_fmt(score)}."
        # Determine discount tier (mirrors sentiment calculator logic)
        if market_cap is not None:
            if market_cap > 10e9:
                discount, tier = 0.05, 'large-cap'
            elif market_cap > 2e9:
                discount, tier = 0.08, 'mid-cap'
            else:
                discount, tier = 0.12, 'small-cap'
        else:
            discount, tier = 0.08, 'unknown-cap'
        discounted = target * (1 - discount)
        implied_return = (discounted - price) / price
        return (
            f"Analyst target ${_fmt(target, 0)}, discounted to ${_fmt(discounted, 0)} "
            f"({tier}, {discount:.0%} haircut). Current price ${_fmt(price, 2)}. "
            f"Implied return {'+' if implied_return >= 0 else ''}{implied_return * 100:.1f}%. "
            f"Score: {_fmt(score)}."
        )

    def _explain_insider(self, data: Optional[Dict], score: Optional[float]) -> str:
        if not data:
            return "No sentiment data available."
        buys = data.get('insider_buys_6m')
        sells = data.get('insider_sells_6m')
        net = data.get('insider_net_shares_6m')
        if net is None and buys is None:
            return f"No insider activity data — score neutral at {_fmt(score)}."
        parts = []
        if buys is not None or sells is not None:
            parts.append(f"{buys or 0} buys, {sells or 0} sells (6 months)")
        if net is not None:
            if net > 0:
                parts.append(f"Net +{net:,} shares (buying)")
            elif net < 0:
                parts.append(f"Net {net:,} shares (selling)")
            else:
                parts.append("Net 0 shares (neutral)")
        return f"{'. '.join(parts)}. Insider score: {_fmt(score)}."
