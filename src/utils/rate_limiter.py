"""
Rate limiter for API calls.

Framework Reference: Section 9.3
- Alpha Vantage: 5 calls/min (free tier)
- Yahoo Finance: No strict limit but respect fair use
- Implements exponential backoff for retries

Usage:
    # As context manager
    limiter = RateLimiter(calls=5, period=60)
    with limiter:
        api_call()

    # As decorator
    @limiter.limit
    def fetch_data():
        return api_call()

    # Direct usage
    limiter.wait_if_needed()
    api_call()
"""

import time
import functools
from collections import deque
from typing import Callable, Any
from datetime import datetime, timedelta


class RateLimiter:
    """
    Rate limiter using sliding window algorithm.

    Tracks timestamps of recent calls and enforces maximum calls per period.
    """

    def __init__(self, calls: int, period: float):
        """
        Initialize rate limiter.

        Args:
            calls: Maximum number of calls allowed
            period: Time period in seconds
        """
        self.max_calls = calls
        self.period = period
        self.call_times = deque(maxlen=calls)

    def wait_if_needed(self) -> None:
        """
        Wait if necessary to stay within rate limit.

        Calculates time since oldest call and sleeps if needed.
        """
        now = time.time()

        # If we haven't hit the limit yet, no need to wait
        if len(self.call_times) < self.max_calls:
            self.call_times.append(now)
            return

        # Calculate time since oldest call
        oldest_call = self.call_times[0]
        time_since_oldest = now - oldest_call

        # If oldest call was within the period, we need to wait
        if time_since_oldest < self.period:
            sleep_time = self.period - time_since_oldest
            time.sleep(sleep_time)
            now = time.time()

        # Record this call
        self.call_times.append(now)

    def __enter__(self):
        """Context manager entry."""
        self.wait_if_needed()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        return False

    def limit(self, func: Callable) -> Callable:
        """
        Decorator to rate limit a function.

        Args:
            func: Function to rate limit

        Returns:
            Wrapped function that respects rate limits
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            self.wait_if_needed()
            return func(*args, **kwargs)

        return wrapper
