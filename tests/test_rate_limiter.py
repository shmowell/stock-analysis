"""
Tests for rate limiter utility.

Framework Reference: Section 9 (API Integration)
- Alpha Vantage: 5 calls/min free tier
- Need exponential backoff for failures
"""

import pytest
import time
from utils.rate_limiter import RateLimiter


def test_rate_limiter_initialization():
    """Test rate limiter can be initialized with calls and period."""
    limiter = RateLimiter(calls=5, period=60)
    assert limiter.max_calls == 5
    assert limiter.period == 60


def test_rate_limiter_allows_calls_under_limit():
    """Test that calls under the limit are allowed immediately."""
    limiter = RateLimiter(calls=5, period=1)

    # First 5 calls should be immediate
    start = time.time()
    for _ in range(5):
        limiter.wait_if_needed()
    elapsed = time.time() - start

    # Should complete almost instantly (< 0.1 seconds)
    assert elapsed < 0.1


def test_rate_limiter_enforces_limit():
    """Test that calls exceeding limit are delayed."""
    limiter = RateLimiter(calls=3, period=1)

    # Make 3 calls (under limit)
    for _ in range(3):
        limiter.wait_if_needed()

    # 4th call should be delayed
    start = time.time()
    limiter.wait_if_needed()
    elapsed = time.time() - start

    # Should wait approximately 1 second
    assert elapsed >= 0.9  # Allow some tolerance


def test_rate_limiter_context_manager():
    """Test rate limiter works as context manager."""
    limiter = RateLimiter(calls=5, period=1)

    start = time.time()
    for _ in range(5):
        with limiter:
            pass
    elapsed = time.time() - start

    # Should complete quickly
    assert elapsed < 0.1


def test_rate_limiter_decorator():
    """Test rate limiter can be used as decorator."""
    limiter = RateLimiter(calls=3, period=1)

    @limiter.limit
    def api_call():
        return "success"

    # First 3 calls should be fast
    start = time.time()
    for _ in range(3):
        result = api_call()
        assert result == "success"
    elapsed = time.time() - start

    assert elapsed < 0.1


def test_rate_limiter_reset():
    """Test that rate limiter resets after period expires."""
    limiter = RateLimiter(calls=2, period=0.5)

    # Use up the limit
    for _ in range(2):
        limiter.wait_if_needed()

    # Wait for reset
    time.sleep(0.6)

    # Should be able to make calls again without delay
    start = time.time()
    limiter.wait_if_needed()
    elapsed = time.time() - start

    assert elapsed < 0.1
