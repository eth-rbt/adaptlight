"""
Time utility functions for AdaptLight.

Provides helper functions for time-based operations:
- Time formatting
- Schedule checking
- Time-based conditions
"""

from datetime import datetime, timezone


def get_current_time_info():
    """
    Get current time information.

    Returns:
        Dict with hour, minute, second, day_of_week, timestamp
    """
    now = datetime.now()
    return {
        'hour': now.hour,
        'minute': now.minute,
        'second': now.second,
        'day_of_week': now.weekday(),  # 0=Monday
        'timestamp': now.timestamp()
    }


def is_time_in_range(start_hour, start_minute, end_hour, end_minute):
    """
    Check if current time is within a range.

    Args:
        start_hour: Start hour (0-23)
        start_minute: Start minute (0-59)
        end_hour: End hour (0-23)
        end_minute: End minute (0-59)

    Returns:
        True if current time is in range
    """
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    start_minutes = start_hour * 60 + start_minute
    end_minutes = end_hour * 60 + end_minute

    if start_minutes <= end_minutes:
        return start_minutes <= current_minutes <= end_minutes
    else:
        # Range crosses midnight
        return current_minutes >= start_minutes or current_minutes <= end_minutes


def format_timestamp(timestamp=None, fmt='%Y-%m-%d %H:%M:%S'):
    """
    Format a timestamp.

    Args:
        timestamp: Unix timestamp (None for current time)
        fmt: Format string

    Returns:
        Formatted time string
    """
    if timestamp is None:
        dt = datetime.now()
    else:
        dt = datetime.fromtimestamp(timestamp)

    return dt.strftime(fmt)


def get_iso_timestamp():
    """Get current time as ISO format string."""
    return datetime.now(timezone.utc).isoformat()
