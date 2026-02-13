"""
Financial Modeling Prep (FMP) data collection module.

Framework Reference: Section 5.2, 9.3
Collects:
- Analyst estimates (EPS, revenue consensus) for revision tracking
- Stock grades (upgrades/downgrades) for analyst sentiment

Free tier: 250 calls/day, all endpoints below verified working.
Insider trading endpoints require premium (402).
"""

import requests
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, date
import logging

from src.utils.rate_limiter import RateLimiter
from src.utils.validators import (
    validate_numeric,
    is_valid_ticker,
    DataValidationError
)

logger = logging.getLogger(__name__)


class FMPCollector:
    """
    Collects analyst data from Financial Modeling Prep API.

    Framework Section 9.3: FMP provides analyst estimates and grade data
    for sentiment scoring.

    Free Tier: 250 calls/day
    """

    BASE_URL = "https://financialmodelingprep.com/stable"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize FMP collector.

        Args:
            api_key: FMP API key (defaults to FMP_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('FMP_API_KEY')
        if not self.api_key:
            raise ValueError(
                "FMP API key not provided. Set FMP_API_KEY in .env "
                "or pass api_key parameter."
            )

        # Rate limiter: 10 calls per 60 seconds (conservative for free tier)
        self.rate_limiter = RateLimiter(calls=10, period=60)
        self.logger = logger

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """
        Make rate-limited API request to FMP.

        Args:
            endpoint: API endpoint path (e.g., 'analyst-estimates')
            params: Query parameters

        Returns:
            Parsed JSON response (list or dict)

        Raises:
            DataValidationError: If request fails or returns error
        """
        if params is None:
            params = {}
        params['apikey'] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}"

        with self.rate_limiter:
            try:
                response = requests.get(url, params=params, timeout=30)

                if response.status_code == 402:
                    raise DataValidationError(
                        f"FMP endpoint requires premium subscription: {endpoint}"
                    )

                if response.status_code == 429:
                    raise DataValidationError("FMP daily rate limit exceeded")

                response.raise_for_status()
                data = response.json()

                # FMP returns error messages as strings or dicts
                if isinstance(data, dict) and 'Error Message' in data:
                    raise DataValidationError(
                        f"FMP API error: {data['Error Message']}"
                    )

                return data

            except requests.exceptions.RequestException as e:
                self.logger.error(f"FMP API request failed: {e}")
                raise DataValidationError(f"FMP API request failed: {e}")

    def get_analyst_estimates(
        self,
        ticker: str,
        period: str = 'annual'
    ) -> List[Dict]:
        """
        Fetch analyst estimates for a ticker.

        Framework Section 5.2: Used for analyst revision momentum tracking.
        Note: FMP free tier only supports period='annual'. Quarterly requires premium.

        Args:
            ticker: Stock ticker symbol
            period: 'annual' (free tier) or 'quarter' (premium only)

        Returns:
            List of estimate dicts with keys: date, estimatedEpsAvg,
            estimatedRevenueAvg, numberAnalystEstimatedEps, etc.
        """
        if not is_valid_ticker(ticker):
            raise DataValidationError(f"Invalid ticker: {ticker}")

        self.logger.info(f"Fetching analyst estimates for {ticker}")

        data = self._make_request('analyst-estimates', {
            'symbol': ticker,
            'period': period,
        })

        if not isinstance(data, list):
            self.logger.warning(f"Unexpected response type for {ticker}: {type(data)}")
            return []

        # Validate and clean numeric fields in each estimate
        # FMP field names: epsAvg, revenueAvg, numAnalystsEps, etc.
        cleaned = []
        for item in data:
            cleaned.append({
                'symbol': item.get('symbol', ticker),
                'date': item.get('date'),
                'estimatedEpsAvg': validate_numeric(item.get('epsAvg')),
                'estimatedEpsHigh': validate_numeric(item.get('epsHigh')),
                'estimatedEpsLow': validate_numeric(item.get('epsLow')),
                'estimatedRevenueAvg': validate_numeric(item.get('revenueAvg'), min_value=0),
                'estimatedRevenueHigh': validate_numeric(item.get('revenueHigh'), min_value=0),
                'estimatedRevenueLow': validate_numeric(item.get('revenueLow'), min_value=0),
                'numberAnalystEstimatedEps': validate_numeric(item.get('numAnalystsEps'), min_value=0),
                'numberAnalystEstimatedRevenue': validate_numeric(item.get('numAnalystsRevenue'), min_value=0),
            })

        self.logger.info(f"Got {len(cleaned)} estimate periods for {ticker}")
        return cleaned

    def get_stock_grades(self, ticker: str) -> List[Dict]:
        """
        Fetch analyst grade changes (upgrades/downgrades) for a ticker.

        Framework Section 5.2: Used for analyst revision momentum.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of grade dicts with keys: date, gradingCompany,
            previousGrade, newGrade, action
        """
        if not is_valid_ticker(ticker):
            raise DataValidationError(f"Invalid ticker: {ticker}")

        self.logger.info(f"Fetching stock grades for {ticker}")

        data = self._make_request('grades', {
            'symbol': ticker,
        })

        if not isinstance(data, list):
            self.logger.warning(f"Unexpected response type for {ticker}: {type(data)}")
            return []

        self.logger.info(f"Got {len(data)} grade records for {ticker}")
        return data

    def calculate_upgrades_downgrades(
        self,
        ticker: str,
        lookback_days: int = 30
    ) -> Dict[str, int]:
        """
        Count analyst upgrades and downgrades within a lookback window.

        Args:
            ticker: Stock ticker symbol
            lookback_days: Number of days to look back (default 30)

        Returns:
            Dict with 'upgrades', 'downgrades', 'maintains', 'total'
        """
        grades = self.get_stock_grades(ticker)

        cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        upgrades = 0
        downgrades = 0
        maintains = 0

        for grade in grades:
            grade_date = grade.get('date', '')
            if grade_date < cutoff:
                continue

            action = (grade.get('action') or '').lower()
            if action == 'upgrade':
                upgrades += 1
            elif action == 'downgrade':
                downgrades += 1
            elif action == 'maintain':
                maintains += 1

        result = {
            'upgrades': upgrades,
            'downgrades': downgrades,
            'maintains': maintains,
            'total': upgrades + downgrades + maintains,
        }

        self.logger.info(
            f"{ticker}: {upgrades} upgrades, {downgrades} downgrades, "
            f"{maintains} maintains in past {lookback_days} days"
        )
        return result

    def calculate_estimate_revisions(
        self,
        ticker: str,
        previous_snapshots: Optional[Dict[str, Dict]] = None
    ) -> Dict[str, Any]:
        """
        Calculate estimate revisions by comparing current estimates to previous snapshots.

        Framework Section 5.2: Analyst Revision Momentum
        Compares current EPS/revenue estimates for each fiscal period against
        previously stored values to detect upward/downward revisions.

        Args:
            ticker: Stock ticker symbol
            previous_snapshots: Dict keyed by fiscal_date string, each value
                containing 'eps_avg' and 'revenue_avg' from a prior collection.
                If None, this is the first run (baseline only).

        Returns:
            Dict with:
                'revisions_up': int or None (None if no baseline)
                'revisions_down': int or None
                'total': int or None
                'current_estimates': list of current estimate dicts for storage
        """
        current_estimates = self.get_analyst_estimates(ticker)

        result = {
            'revisions_up': None,
            'revisions_down': None,
            'total': None,
            'current_estimates': current_estimates,
        }

        if not current_estimates:
            return result

        # No previous data — first run, store baseline
        if not previous_snapshots:
            self.logger.info(f"{ticker}: First run, storing baseline estimates")
            return result

        # Compare current vs previous for matching fiscal periods
        revisions_up = 0
        revisions_down = 0

        for estimate in current_estimates:
            fiscal_date = estimate.get('date')
            if not fiscal_date or fiscal_date not in previous_snapshots:
                continue

            prev = previous_snapshots[fiscal_date]

            # EPS revision check (tolerance: $0.01)
            curr_eps = estimate.get('estimatedEpsAvg')
            prev_eps = prev.get('eps_avg')
            if curr_eps is not None and prev_eps is not None:
                if curr_eps > prev_eps + 0.01:
                    revisions_up += 1
                elif curr_eps < prev_eps - 0.01:
                    revisions_down += 1

            # Revenue revision check (tolerance: 0.5%)
            curr_rev = estimate.get('estimatedRevenueAvg')
            prev_rev = prev.get('revenue_avg')
            if curr_rev is not None and prev_rev is not None and prev_rev > 0:
                if curr_rev > prev_rev * 1.005:
                    revisions_up += 1
                elif curr_rev < prev_rev * 0.995:
                    revisions_down += 1

        result['revisions_up'] = revisions_up
        result['revisions_down'] = revisions_down
        result['total'] = revisions_up + revisions_down

        self.logger.info(
            f"{ticker}: {revisions_up} revisions up, {revisions_down} down "
            f"(compared against {len(previous_snapshots)} previous periods)"
        )
        return result
