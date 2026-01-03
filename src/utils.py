"""
Utility functions for formatting currency, datetime, etc.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional

# Vietnam timezone (GMT+7)
VIETNAM_TZ = timezone(timedelta(hours=7))


def get_vietnam_now() -> datetime:
    """Get current datetime in Vietnam timezone (GMT+7)"""
    return datetime.now(VIETNAM_TZ)


def get_vietnam_today() -> date:
    """Get current date in Vietnam timezone (GMT+7)"""
    return get_vietnam_now().date()


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
    """Get the start of today (00:00:00) in Vietnam timezone"""
    today = get_vietnam_today()
    return datetime(today.year, today.month, today.day, 0, 0, 0)


def get_today_end() -> datetime:
    """Get the end of today (23:59:59) in Vietnam timezone"""
    today = get_vietnam_today()
    return datetime(today.year, today.month, today.day, 23, 59, 59)


def get_month_start() -> datetime:
    """Get the start of current month in Vietnam timezone"""
    today = get_vietnam_today()
    return datetime(today.year, today.month, 1, 0, 0, 0)


def get_month_end() -> datetime:
    """Get the end of current month in Vietnam timezone"""
    today = get_vietnam_today()
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
    """Get the start of current week (Monday) in Vietnam timezone"""
    today = get_vietnam_today()
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    return datetime(monday.year, monday.month, monday.day, 0, 0, 0)


def get_year_start() -> datetime:
    """Get the start of current year in Vietnam timezone"""
    today = get_vietnam_today()
    return datetime(today.year, 1, 1, 0, 0, 0)


def get_yesterday_start() -> datetime:
    """Get the start of yesterday (00:00:00) in Vietnam timezone"""
    yesterday = get_vietnam_today() - timedelta(days=1)
    return datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0)


def get_yesterday_end() -> datetime:
    """Get the end of yesterday (23:59:59) in Vietnam timezone"""
    yesterday = get_vietnam_today() - timedelta(days=1)
    return datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59)


def get_specific_date_range(day: int, month: int, year: Optional[int] = None) -> tuple[datetime, datetime]:
    """
    Get start and end datetime for a specific date (dd/mm or dd/mm/yyyy).
    If year is None, uses current year.
    """
    if year is None:
        year = get_vietnam_today().year
    try:
        target_date = date(year, month, day)
        start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
        end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)
        return start, end
    except ValueError:
        # Invalid date
        return None, None


def get_weekday_of_last_week(weekday: int) -> tuple[datetime, datetime]:
    """
    Get start and end datetime for a specific weekday of LAST week.
    weekday: 0=Monday, 1=Tuesday, ..., 6=Sunday
    
    Example: If today is Thursday Dec 26, and weekday=0 (Monday),
    returns Monday Dec 16 (last week's Monday)
    """
    today = get_vietnam_today()
    # Find last week's same weekday
    days_diff = today.weekday() - weekday + 7  # Go back to last week
    target_date = today - timedelta(days=days_diff)
    
    start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
    end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)
    return start, end


def parse_weekday_vietnamese(text: str) -> Optional[int]:
    """
    Parse Vietnamese weekday name to weekday number.
    Returns: 0=Monday, ..., 6=Sunday, or None if not found
    """
    text_lower = text.lower().strip()
    weekday_map = {
        'thứ hai': 0, 'thứ 2': 0, 't2': 0,
        'thứ ba': 1, 'thứ 3': 1, 't3': 1,
        'thứ tư': 2, 'thứ 4': 2, 't4': 2,
        'thứ năm': 3, 'thứ 5': 3, 't5': 3,
        'thứ sáu': 4, 'thứ 6': 4, 't6': 4,
        'thứ bảy': 5, 'thứ 7': 5, 't7': 5,
        'chủ nhật': 6, 'cn': 6,
    }
    for key, value in weekday_map.items():
        if key in text_lower:
            return value
    return None

