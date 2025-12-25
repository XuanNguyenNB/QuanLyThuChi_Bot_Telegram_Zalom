"""
Utility functions for formatting currency, datetime, etc.
"""

from datetime import datetime, date, timedelta
from typing import Optional


def format_currency(amount: float) -> str:
    """
    Format amount to Vietnamese currency style.
    Example: 50000 -> "50,000₫" or "50k"
    """
    if amount >= 1_000_000:
        if amount % 1_000_000 == 0:
            return f"{int(amount // 1_000_000)}tr"
        else:
            return f"{amount / 1_000_000:.1f}tr"
    elif amount >= 1_000:
        if amount % 1_000 == 0:
            return f"{int(amount // 1_000)}k"
        else:
            return f"{amount / 1_000:.1f}k"
    else:
        return f"{int(amount)}₫"


def format_currency_full(amount: float) -> str:
    """
    Format amount with full number and thousand separators.
    Example: 50000 -> "50,000₫"
    """
    return f"{amount:,.0f}₫"


def format_date(dt: datetime) -> str:
    """Format datetime to Vietnamese date string"""
    return dt.strftime("%d/%m/%Y")


def format_datetime(dt: datetime) -> str:
    """Format datetime to Vietnamese datetime string"""
    return dt.strftime("%H:%M %d/%m/%Y")


def get_today_start() -> datetime:
    """Get the start of today (00:00:00)"""
    today = date.today()
    return datetime(today.year, today.month, today.day, 0, 0, 0)


def get_today_end() -> datetime:
    """Get the end of today (23:59:59)"""
    today = date.today()
    return datetime(today.year, today.month, today.day, 23, 59, 59)


def get_month_start() -> datetime:
    """Get the start of current month"""
    today = date.today()
    return datetime(today.year, today.month, 1, 0, 0, 0)


def get_month_end() -> datetime:
    """Get the end of current month"""
    today = date.today()
    if today.month == 12:
        next_month = datetime(today.year + 1, 1, 1)
    else:
        next_month = datetime(today.year, today.month + 1, 1)
    from datetime import timedelta
    last_day = next_month - timedelta(days=1)
    return datetime(last_day.year, last_day.month, last_day.day, 23, 59, 59)


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text if it exceeds max length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def get_week_start() -> datetime:
    """Get the start of current week (Monday)"""
    today = date.today()
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    return datetime(monday.year, monday.month, monday.day, 0, 0, 0)


def get_year_start() -> datetime:
    """Get the start of current year"""
    today = date.today()
    return datetime(today.year, 1, 1, 0, 0, 0)
