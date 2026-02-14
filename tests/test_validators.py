"""
Tests for data validation utilities.

Framework Reference: CLAUDE.md - Data Quality
- Always validate API responses
- Check for null/missing values
- Verify data types match expectations
- Log when data is unavailable
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from utils.validators import (
    validate_numeric,
    validate_percentage,
    validate_ratio,
    validate_api_response,
    validate_date,
    is_valid_ticker,
    DataValidationError
)


def test_validate_numeric_valid():
    """Test numeric validation with valid values."""
    assert validate_numeric(100.5) == 100.5
    assert validate_numeric(0) == 0
    assert validate_numeric(-50.2) == -50.2


def test_validate_numeric_invalid():
    """Test numeric validation with invalid values."""
    assert validate_numeric(None) is None
    assert validate_numeric(np.nan) is None
    assert validate_numeric("not a number", default=0) == 0


def test_validate_numeric_with_bounds():
    """Test numeric validation with min/max bounds."""
    assert validate_numeric(50, min_value=0, max_value=100) == 50
    assert validate_numeric(-10, min_value=0) is None
    assert validate_numeric(150, max_value=100) is None


def test_validate_percentage():
    """Test percentage validation (0-100 or 0-1)."""
    assert validate_percentage(50) == 50
    assert validate_percentage(0.5, as_decimal=True) == 0.5
    assert validate_percentage(150) is None  # Out of range
    assert validate_percentage(-10) is None  # Negative


def test_validate_ratio():
    """Test ratio validation (positive numbers)."""
    assert validate_ratio(2.5) == 2.5
    assert validate_ratio(0) == 0
    assert validate_ratio(-1.5) is None  # Negative ratio invalid
    assert validate_ratio(None) is None


def test_validate_api_response_success():
    """Test API response validation with valid response."""
    response = {
        'symbol': 'AAPL',
        'pe_ratio': 25.5,
        'market_cap': 3000000000000
    }
    result = validate_api_response(response, required_fields=['symbol', 'pe_ratio'])
    assert result is True


def test_validate_api_response_missing_fields():
    """Test API response validation with missing required fields."""
    response = {'symbol': 'AAPL'}  # Missing pe_ratio
    with pytest.raises(DataValidationError):
        validate_api_response(response, required_fields=['symbol', 'pe_ratio'])


def test_validate_api_response_empty():
    """Test API response validation with empty response."""
    with pytest.raises(DataValidationError):
        validate_api_response({}, required_fields=['symbol'])

    with pytest.raises(DataValidationError):
        validate_api_response(None, required_fields=['symbol'])


def test_validate_date_valid():
    """Test date validation with valid dates."""
    now = datetime.now()
    assert validate_date(now) == now

    date_str = "2024-01-15"
    result = validate_date(date_str)
    assert isinstance(result, datetime)
    assert result.year == 2024


def test_validate_date_freshness():
    """Test date validation with freshness check."""
    old_date = datetime.now() - timedelta(days=10)
    recent_date = datetime.now() - timedelta(days=2)

    # Old date should fail freshness check
    assert validate_date(old_date, max_age_days=5) is None

    # Recent date should pass
    assert validate_date(recent_date, max_age_days=5) == recent_date


def test_validate_date_invalid():
    """Test date validation with invalid dates."""
    assert validate_date(None) is None
    assert validate_date("invalid date") is None
    assert validate_date([1, 2, 3]) is None  # Invalid type


def test_is_valid_ticker():
    """Test ticker symbol validation."""
    assert is_valid_ticker("AAPL") is True
    assert is_valid_ticker("MSFT") is True
    assert is_valid_ticker("BRK.B") is True  # Berkshire class B

    # Invalid tickers
    assert is_valid_ticker("") is False
    assert is_valid_ticker(None) is False
    assert is_valid_ticker("TOOLONGSYMBOL") is False
    assert is_valid_ticker("123") is False  # Starts with number


def test_validate_numeric_allow_zero():
    """Test numeric validation with allow_zero parameter."""
    assert validate_numeric(0, allow_zero=True) == 0
    assert validate_numeric(0, allow_zero=False) is None


def test_validate_ratio_with_bounds():
    """Test ratio validation with reasonable bounds."""
    # P/E ratios typically 0-100
    assert validate_ratio(25, max_value=100) == 25
    assert validate_ratio(500, max_value=100) is None

    # Debt-to-equity can be higher
    assert validate_ratio(2.5, max_value=10) == 2.5
