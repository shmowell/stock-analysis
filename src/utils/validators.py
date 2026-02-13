"""
Data validation utilities for API responses and metrics.

Framework Reference: CLAUDE.md - Data Quality
- Validate all API responses
- Check for null/missing values
- Verify data types match expectations
- Handle missing data gracefully
- Never use arbitrary defaults

Usage:
    # Validate numeric metric
    pe_ratio = validate_numeric(data.get('pe_ratio'), min_value=0)

    # Validate API response
    validate_api_response(response, required_fields=['symbol', 'price'])

    # Validate ticker symbol
    if is_valid_ticker(ticker):
        fetch_data(ticker)
"""

import logging
from typing import Any, Optional, List, Union
from datetime import datetime, timedelta
import numpy as np
import re

logger = logging.getLogger(__name__)


class DataValidationError(Exception):
    """Raised when data validation fails."""
    pass


def validate_numeric(
    value: Any,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    allow_zero: bool = True,
    default: Optional[float] = None
) -> Optional[float]:
    """
    Validate and clean numeric value.

    Args:
        value: Value to validate
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)
        allow_zero: Whether zero is a valid value
        default: Default value if validation fails

    Returns:
        Validated float or None/default if invalid

    Examples:
        >>> validate_numeric(25.5)
        25.5
        >>> validate_numeric(None)
        None
        >>> validate_numeric(-10, min_value=0)
        None
        >>> validate_numeric(150, max_value=100)
        None
    """
    # Handle None and NaN
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return default

    # Try to convert to float
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        logger.warning(f"Could not convert {value} to numeric")
        return default

    # Check for NaN after conversion
    if np.isnan(numeric_value):
        return default

    # Check zero
    if not allow_zero and numeric_value == 0:
        return default

    # Check bounds
    if min_value is not None and numeric_value < min_value:
        logger.debug(f"Value {numeric_value} below minimum {min_value}")
        return default

    if max_value is not None and numeric_value > max_value:
        logger.debug(f"Value {numeric_value} above maximum {max_value}")
        return default

    return numeric_value


def validate_percentage(
    value: Any,
    as_decimal: bool = False,
    default: Optional[float] = None
) -> Optional[float]:
    """
    Validate percentage value (0-100 or 0-1).

    Args:
        value: Percentage value to validate
        as_decimal: If True, expects 0-1 range; if False, expects 0-100
        default: Default value if validation fails

    Returns:
        Validated percentage or None/default

    Examples:
        >>> validate_percentage(50)
        50.0
        >>> validate_percentage(0.5, as_decimal=True)
        0.5
        >>> validate_percentage(150)
        None
    """
    max_val = 1.0 if as_decimal else 100.0
    return validate_numeric(value, min_value=0, max_value=max_val, default=default)


def validate_ratio(
    value: Any,
    min_value: float = 0,
    max_value: Optional[float] = None,
    allow_zero: bool = True,
    default: Optional[float] = None
) -> Optional[float]:
    """
    Validate financial ratio (typically positive).

    Args:
        value: Ratio value to validate
        min_value: Minimum allowed value (default 0)
        max_value: Maximum allowed value
        allow_zero: Whether zero is valid
        default: Default value if validation fails

    Returns:
        Validated ratio or None/default

    Examples:
        >>> validate_ratio(2.5)
        2.5
        >>> validate_ratio(-1.5)
        None
        >>> validate_ratio(500, max_value=100)
        None
    """
    return validate_numeric(
        value,
        min_value=min_value,
        max_value=max_value,
        allow_zero=allow_zero,
        default=default
    )


def validate_api_response(
    response: Any,
    required_fields: Optional[List[str]] = None
) -> bool:
    """
    Validate API response structure.

    Args:
        response: API response to validate
        required_fields: List of required field names

    Returns:
        True if valid

    Raises:
        DataValidationError: If response is invalid

    Examples:
        >>> response = {'symbol': 'AAPL', 'price': 150}
        >>> validate_api_response(response, ['symbol', 'price'])
        True
    """
    # Check response is not None/empty
    if response is None:
        raise DataValidationError("API response is None")

    if not isinstance(response, dict):
        raise DataValidationError(f"API response is not a dict: {type(response)}")

    if not response:
        raise DataValidationError("API response is empty dict")

    # Check required fields
    if required_fields:
        missing_fields = [field for field in required_fields if field not in response]
        if missing_fields:
            raise DataValidationError(
                f"Missing required fields: {missing_fields}. Response keys: {list(response.keys())}"
            )

    return True


def validate_date(
    value: Any,
    max_age_days: Optional[int] = None
) -> Optional[datetime]:
    """
    Validate and parse date value.

    Args:
        value: Date to validate (datetime, string, or timestamp)
        max_age_days: Maximum age in days (for freshness check)

    Returns:
        Validated datetime or None if invalid

    Examples:
        >>> from datetime import datetime
        >>> validate_date(datetime.now())
        datetime.datetime(...)
        >>> validate_date("2024-01-15")
        datetime.datetime(2024, 1, 15, 0, 0)
        >>> validate_date(None)
        None
    """
    if value is None:
        return None

    # Already a datetime
    if isinstance(value, datetime):
        dt = value
    # String - try to parse
    elif isinstance(value, str):
        try:
            # Try common formats
            for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"]:
                try:
                    dt = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue
            else:
                # No format matched
                logger.warning(f"Could not parse date string: {value}")
                return None
        except Exception as e:
            logger.warning(f"Error parsing date {value}: {e}")
            return None
    # Timestamp (int or float)
    elif isinstance(value, (int, float)):
        try:
            dt = datetime.fromtimestamp(value)
        except (ValueError, OSError) as e:
            logger.warning(f"Could not convert timestamp {value}: {e}")
            return None
    else:
        logger.warning(f"Unsupported date type: {type(value)}")
        return None

    # Check freshness if requested
    if max_age_days is not None:
        age = datetime.now() - dt
        if age > timedelta(days=max_age_days):
            logger.debug(f"Date {dt} is older than {max_age_days} days")
            return None

    return dt


def is_valid_ticker(ticker: Any) -> bool:
    """
    Validate stock ticker symbol.

    Args:
        ticker: Ticker symbol to validate

    Returns:
        True if valid ticker format

    Examples:
        >>> is_valid_ticker("AAPL")
        True
        >>> is_valid_ticker("BRK.B")
        True
        >>> is_valid_ticker("")
        False
        >>> is_valid_ticker("TOOLONG")
        False
    """
    if not ticker or not isinstance(ticker, str):
        return False

    # Ticker should be 1-5 characters, letters and dots only
    # Examples: AAPL, BRK.B, T
    pattern = r'^[A-Z]{1,5}(\.[A-Z])?$'

    return bool(re.match(pattern, ticker.upper()))
