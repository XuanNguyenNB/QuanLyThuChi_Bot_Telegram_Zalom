"""
Business logic services: message parsing, category detection, reporting.
"""

import re
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, Category, Transaction, TransactionType, Budget
from .utils import get_today_start, get_today_end, get_month_start, get_month_end, get_week_start, get_year_start, get_vietnam_now


@dataclass
class ParsedMessage:
    """Result of parsing a user message"""
    amount: float
    note: str
    raw_text: str
    is_valid: bool = True
    error_message: Optional[str] = None


def parse_message(text: str) -> ParsedMessage:
    """
    Parse user message to extract amount and note.
    
    Supported formats:
    - "50k cafe" -> amount=50000, note="cafe"
    - "2tr tiền nhà" -> amount=2000000, note="tiền nhà"
    - "1.5m điện" -> amount=1500000, note="điện"
    - "10000 ăn sáng" -> amount=10000, note="ăn sáng"
    - "+100k lương" -> amount=100000, note="lương" (income, positive)
    - "-50k cafe" -> amount=50000, note="cafe" (expense, already default)
    
    Args:
        text: Raw message from user
        
    Returns:
        ParsedMessage with amount and note
    """
    text = text.strip()
    if not text:
        return ParsedMessage(
            amount=0,
            note="",
            raw_text=text,
            is_valid=False,
            error_message="Tin nhắn trống"
        )
    
    # Pattern: optional sign, number (with optional decimal), optional suffix, then note
    # Examples: 50k cafe, 2tr tiền nhà, 1.5m điện, +100k lương
    # Note: longer suffixes must come first in alternation (triệu before tr)
    pattern = r'^([+-])?(\d+(?:[.,]\d+)?)\s*(triệu|nghìn|tr|m|k)?\s*(.*)$'
    match = re.match(pattern, text, re.IGNORECASE | re.UNICODE)
    
    if not match:
        return ParsedMessage(
            amount=0,
            note=text,
            raw_text=text,
            is_valid=False,
            error_message="Không nhận dạng được số tiền. Hãy gõ theo format: 50k cafe"
        )
    
    sign, number_str, suffix, note = match.groups()
    
    # Parse number (handle both . and , as decimal separator)
    number_str = number_str.replace(",", ".")
    try:
        amount = float(number_str)
    except ValueError:
        return ParsedMessage(
            amount=0,
            note=text,
            raw_text=text,
            is_valid=False,
            error_message="Số tiền không hợp lệ"
        )
    
    # Apply suffix multiplier
    if suffix:
        suffix = suffix.lower()
        if suffix == "k" or suffix == "nghìn":
            amount *= 1_000
        elif suffix in ("tr", "m", "triệu"):
            amount *= 1_000_000
    else:
        # No suffix - auto-detect based on amount
        # In Vietnam, amounts under 1000 are almost always meant to be thousands
        # e.g., "350" means 350k, not 350 đồng
        if amount < 1000:
            amount *= 1_000
    
    # Clean up note
    note = note.strip() if note else ""
    
    return ParsedMessage(
        amount=amount,
        note=note,
        raw_text=text,
        is_valid=True
    )


async def detect_category(
    session: AsyncSession, 
    note: str
) -> Optional[Category]:
    """
    Detect category based on keywords matching in note.
    
    Args:
        session: Database session
        note: Transaction note to match
        
    Returns:
        Matched Category or None if no match found
    """
    note_lower = note.lower()
    
    # Get all categories
    result = await session.execute(select(Category))
    categories = result.scalars().all()
    
    # Find best matching category
    for category in categories:
        keywords = category.get_keywords_list()
        for keyword in keywords:
            if keyword and keyword in note_lower:
                return category
    
    # Return "Khác" category if no match
    for category in categories:
        if category.name == "Khác":
            return category
    
    return None


async def get_category_by_name(
    session: AsyncSession,
    name: str
) -> Optional[Category]:
    """Get category by name"""
    result = await session.execute(
        select(Category).where(Category.name == name)
    )
    category = result.scalar_one_or_none()
    
    if category is None:
        # Fallback to "Khác"
        result = await session.execute(
            select(Category).where(Category.name == "Khác")
        )
        category = result.scalar_one_or_none()
    
    return category


async def get_all_categories(session: AsyncSession) -> List[Category]:
    """Get all categories"""
    result = await session.execute(select(Category).order_by(Category.id))
    return list(result.scalars().all())


async def learn_keyword_for_user(
    session: AsyncSession,
    user_id: int,
    category_id: int,
    keyword: str
) -> bool:
    """
    Save user-specific keyword to category mapping.
    This is the 'learning' feature - when user chooses a category,
    we save the mapping for that specific user.
    
    Args:
        session: Database session
        user_id: User ID
        category_id: Category to map to
        keyword: Keyword to learn
        
    Returns:
        True if learned successfully
    """
    from .models import UserKeyword
    
    # Clean keyword
    keyword = keyword.lower().strip()
    if not keyword or len(keyword) < 2:
        return False
    
    # Check if mapping already exists for this user
    result = await session.execute(
        select(UserKeyword).where(
            UserKeyword.user_id == user_id,
            UserKeyword.keyword == keyword
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update existing mapping
        existing.category_id = category_id
        existing.count += 1
    else:
        # Create new mapping
        new_mapping = UserKeyword(
            user_id=user_id,
            keyword=keyword,
            category_id=category_id
        )
        session.add(new_mapping)
    
    await session.commit()
    return True


def calculate_word_similarity(text1: str, text2: str) -> float:
    """
    Calculate word-based similarity between two texts.
    Returns a score from 0 to 1.
    """
    # Extract words (remove common Vietnamese stop words)
    stop_words = {'được', 'đc', 'cái', 'con', 'cho', 'và', 'với', 'của', 'là', 'có', 'được', 'này', 'đó'}
    
    def get_words(text):
        words = set(text.lower().split())
        return words - stop_words
    
    words1 = get_words(text1)
    words2 = get_words(text2)
    
    if not words1 or not words2:
        return 0.0
    
    # Calculate Jaccard similarity
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    if union == 0:
        return 0.0
    
    return intersection / union


async def find_category_from_user_history(
    session: AsyncSession,
    user_id: int,
    note: str,
    similarity_threshold: float = 0.5
) -> Optional[Category]:
    """
    Find category based on user's past keyword mappings using fuzzy matching.
    This is a simple RAG-like approach - look up user's history first.
    
    Args:
        session: Database session
        user_id: User ID
        note: Transaction note to match
        similarity_threshold: Minimum similarity score (0-1) to match
        
    Returns:
        Category if found in user's history, None otherwise
    """
    from .models import UserKeyword
    
    note_lower = note.lower().strip()
    
    # First, try exact match
    result = await session.execute(
        select(UserKeyword).where(
            UserKeyword.user_id == user_id,
            UserKeyword.keyword == note_lower
        )
    )
    exact_match = result.scalar_one_or_none()
    
    if exact_match:
        cat_result = await session.execute(
            select(Category).where(Category.id == exact_match.category_id)
        )
        return cat_result.scalar_one_or_none()
    
    # Get all user's learned keywords
    result = await session.execute(
        select(UserKeyword).where(UserKeyword.user_id == user_id)
    )
    user_keywords = result.scalars().all()
    
    # Find best fuzzy match
    best_match = None
    best_score = 0.0
    
    for uk in user_keywords:
        # Calculate similarity
        score = calculate_word_similarity(note_lower, uk.keyword)
        
        # Also check substring match (boost score if one contains the other)
        if uk.keyword in note_lower or note_lower in uk.keyword:
            score = max(score, 0.7)  # At least 70% if substring match
        
        if score > best_score:
            best_score = score
            best_match = uk
    
    # If best match meets threshold, return it
    if best_match and best_score >= similarity_threshold:
        cat_result = await session.execute(
            select(Category).where(Category.id == best_match.category_id)
        )
        return cat_result.scalar_one_or_none()
    
    return None


async def get_user_learned_keywords(
    session: AsyncSession,
    user_id: int,
    limit: int = 20
) -> List[tuple]:
    """
    Get user's learned keyword mappings for AI context.
    
    Returns:
        List of (keyword, category_name) tuples
    """
    from .models import UserKeyword
    
    result = await session.execute(
        select(UserKeyword, Category)
        .join(Category, UserKeyword.category_id == Category.id)
        .where(UserKeyword.user_id == user_id)
        .order_by(UserKeyword.count.desc())
        .limit(limit)
    )
    
    return [(uk.keyword, cat.name) for uk, cat in result.all()]


async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    username: Optional[str] = None,
    full_name: Optional[str] = None
) -> User:
    """Get existing user by Telegram ID or create new one"""
    result = await session.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        user = User(telegram_id=user_id, username=username, full_name=full_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    
    return user


async def get_or_create_zalo_user(
    session: AsyncSession,
    zalo_id: str,
    full_name: Optional[str] = None
) -> User:
    """Get existing user by Zalo ID or create new one"""
    result = await session.execute(select(User).where(User.zalo_id == zalo_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        user = User(zalo_id=zalo_id, full_name=full_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    
    return user


async def link_user_by_phone(
    session: AsyncSession,
    phone: str,
    telegram_id: Optional[int] = None,
    zalo_id: Optional[str] = None
) -> Optional[User]:
    """Link Telegram and Zalo accounts by phone number"""
    # Find existing user with this phone
    result = await session.execute(select(User).where(User.phone == phone))
    user_with_phone = result.scalar_one_or_none()
    
    # Find existing user with telegram_id (if provided)
    user_with_telegram = None
    if telegram_id:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user_with_telegram = result.scalar_one_or_none()
    
    # Find existing user with zalo_id (if provided)
    user_with_zalo = None
    if zalo_id:
        result = await session.execute(select(User).where(User.zalo_id == zalo_id))
        user_with_zalo = result.scalar_one_or_none()
    
    # Case 1: User with phone exists
    if user_with_phone:
        # Check if trying to link telegram_id that already belongs to another user
        if telegram_id and user_with_telegram and user_with_telegram.id != user_with_phone.id:
            # Telegram ID already linked to different user - cannot link
            return None
            
        # Check if trying to link zalo_id that already belongs to another user  
        if zalo_id and user_with_zalo and user_with_zalo.id != user_with_phone.id:
            # Zalo ID already linked to different user - cannot link
            return None
            
        # Safe to update
        if telegram_id:
            user_with_phone.telegram_id = telegram_id
        if zalo_id:
            user_with_phone.zalo_id = zalo_id
        await session.commit()
        return user_with_phone
    
    # Case 2: No user with phone, but user with telegram_id exists
    if user_with_telegram:
        user_with_telegram.phone = phone
        if zalo_id:
            user_with_telegram.zalo_id = zalo_id
        await session.commit()
        return user_with_telegram
    
    # Case 3: No user with phone or telegram_id, but user with zalo_id exists
    if user_with_zalo:
        user_with_zalo.phone = phone
        if telegram_id:
            user_with_zalo.telegram_id = telegram_id
        await session.commit()
        return user_with_zalo
    
    return None


async def get_last_transaction(
    session: AsyncSession,
    user_id: int
) -> Optional[Transaction]:
    """Get user's most recent transaction"""
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def update_transaction_category(
    session: AsyncSession,
    transaction_id: int,
    category_id: int
) -> bool:
    """Update transaction's category"""
    result = await session.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    tx = result.scalar_one_or_none()
    if tx:
        tx.category_id = category_id
        await session.commit()
        return True
    return False


async def delete_transaction(
    session: AsyncSession,
    transaction_id: int,
    user_id: int
) -> Optional[Transaction]:
    """Delete a transaction by ID (only if belongs to user). Returns deleted tx info."""
    result = await session.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id
        )
    )
    tx = result.scalar_one_or_none()
    if tx:
        # Store info before deleting
        deleted_tx = Transaction(
            id=tx.id,
            amount=tx.amount,
            note=tx.note,
            category_id=tx.category_id
        )
        await session.delete(tx)
        await session.commit()
        return tx
    return None


async def add_transaction(
    session: AsyncSession,
    user_id: int,
    amount: float,
    note: str,
    raw_text: str,
    category_id: Optional[int] = None,
    transaction_date: Optional[datetime] = None
) -> Transaction:
    """Add a new transaction"""
    transaction = Transaction(
        user_id=user_id,
        amount=amount,
        note=note,
        raw_text=raw_text,
        category_id=category_id,
        date=transaction_date or get_vietnam_now()
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction


@dataclass
class DailySummary:
    """Summary of daily transactions"""
    total_expense: float
    total_income: float
    transaction_count: int
    transactions: List[Transaction]


async def get_today_summary(
    session: AsyncSession,
    user_id: int
) -> DailySummary:
    """Get summary of today's transactions"""
    today_start = get_today_start()
    today_end = get_today_end()
    
    # Get all transactions for today
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.date >= today_start)
        .where(Transaction.date <= today_end)
        .order_by(Transaction.date.desc())
    )
    transactions = list(result.scalars().all())
    
    total_expense = 0.0
    total_income = 0.0
    
    for tx in transactions:
        if tx.category and tx.category.type == TransactionType.INCOME:
            total_income += tx.amount
        else:
            total_expense += tx.amount
    
    return DailySummary(
        total_expense=total_expense,
        total_income=total_income,
        transaction_count=len(transactions),
        transactions=transactions
    )


@dataclass
class CategorySummary:
    """Summary per category"""
    category_name: str
    total: float
    count: int


@dataclass
class SpendingInsights:
    """Spending insights and analytics"""
    total_this_month: float
    total_last_month: float
    daily_average: float
    top_categories: List[CategorySummary]
    biggest_expense: Optional[Transaction]
    trend: str  # "up", "down", "stable"
    suggestion: str


async def get_spending_insights(
    session: AsyncSession,
    user_id: int
) -> SpendingInsights:
    """Get spending insights for user"""
    from datetime import timedelta
    
    now = get_vietnam_now()
    
    # This month
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Last month
    last_month_end = month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    
    # Get this month's transactions
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.date >= month_start)
    )
    this_month_txs = list(result.scalars().all())
    
    # Get last month's transactions
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.date >= last_month_start)
        .where(Transaction.date < month_start)
    )
    last_month_txs = list(result.scalars().all())
    
    # Calculate totals (expenses only)
    total_this_month = sum(
        tx.amount for tx in this_month_txs 
        if not tx.category or tx.category.type != TransactionType.INCOME
    )
    total_last_month = sum(
        tx.amount for tx in last_month_txs 
        if not tx.category or tx.category.type != TransactionType.INCOME
    )
    
    # Daily average
    days_in_month = now.day
    daily_average = total_this_month / days_in_month if days_in_month > 0 else 0
    
    # Top categories
    category_totals: dict[str, float] = {}
    for tx in this_month_txs:
        if tx.category and tx.category.type == TransactionType.INCOME:
            continue
        cat_name = tx.category.name if tx.category else "Khác"
        category_totals[cat_name] = category_totals.get(cat_name, 0) + tx.amount
    
    top_categories = [
        CategorySummary(name, total, 0)
        for name, total in sorted(category_totals.items(), key=lambda x: -x[1])[:5]
    ]
    
    # Biggest expense
    expenses = [tx for tx in this_month_txs if not tx.category or tx.category.type != TransactionType.INCOME]
    biggest_expense = max(expenses, key=lambda x: x.amount) if expenses else None
    
    # Trend
    if total_last_month == 0:
        trend = "stable"
    elif total_this_month > total_last_month * 1.1:
        trend = "up"
    elif total_this_month < total_last_month * 0.9:
        trend = "down"
    else:
        trend = "stable"
    
    # Suggestion
    if trend == "up":
        suggestion = "Chi tiêu tháng này đang tăng. Hãy xem lại các khoản chi lớn nhất!"
    elif trend == "down":
        suggestion = "Tuyệt vời! Chi tiêu tháng này ít hơn tháng trước."
    else:
        suggestion = "Chi tiêu ổn định. Tiếp tục duy trì nhé!"
    
    if top_categories:
        top_cat = top_categories[0].category_name
        suggestion += f" Danh mục chi nhiều nhất: {top_cat}."
    
    return SpendingInsights(
        total_this_month=total_this_month,
        total_last_month=total_last_month,
        daily_average=daily_average,
        top_categories=top_categories,
        biggest_expense=biggest_expense,
        trend=trend,
        suggestion=suggestion
    )


@dataclass
class MonthlySummary:
    """Summary of monthly transactions"""
    total_expense: float
    total_income: float
    transaction_count: int
    category_breakdown: List[CategorySummary]


async def get_month_summary(
    session: AsyncSession,
    user_id: int
) -> MonthlySummary:
    """Get summary of current month's transactions"""
    month_start = get_month_start()
    month_end = get_month_end()
    
    # Get all transactions for this month
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.date >= month_start)
        .where(Transaction.date <= month_end)
    )
    transactions = list(result.scalars().all())
    
    total_expense = 0.0
    total_income = 0.0
    category_totals: dict[str, Tuple[float, int]] = {}
    
    for tx in transactions:
        cat_name = tx.category.name if tx.category else "Khác"
        
        if tx.category and tx.category.type == TransactionType.INCOME:
            total_income += tx.amount
        else:
            total_expense += tx.amount
            # Only track expense categories in breakdown
            if cat_name not in category_totals:
                category_totals[cat_name] = (0.0, 0)
            current_total, current_count = category_totals[cat_name]
            category_totals[cat_name] = (current_total + tx.amount, current_count + 1)
    
    # Sort categories by total (descending)
    sorted_categories = sorted(
        category_totals.items(),
        key=lambda x: x[1][0],
        reverse=True
    )
    
    category_breakdown = [
        CategorySummary(name, total, count)
        for name, (total, count) in sorted_categories
    ]
    
    return MonthlySummary(
        total_expense=total_expense,
        total_income=total_income,
        transaction_count=len(transactions),
        category_breakdown=category_breakdown
    )


async def get_all_transactions(
    session: AsyncSession,
    user_id: int
) -> List[Transaction]:
    """Get all transactions for a user"""
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.date.desc())
    )
    return list(result.scalars().all())


@dataclass
class SmartQueryResult:
    """Result of a smart query"""
    total: float
    count: int
    transactions: List[Transaction]
    time_range: str
    keyword: Optional[str] = None
    category_name: Optional[str] = None


async def smart_query_transactions(
    session: AsyncSession,
    user_id: int,
    time_range: str = "all",
    category_name: Optional[str] = None,
    keyword: Optional[str] = None,
    specific_date: Optional[str] = None,
    weekday: Optional[str] = None
) -> SmartQueryResult:
    """
    Smart query transactions with filters.
    
    Args:
        time_range: "today", "yesterday", "week", "month", "year", "all", "specific_date", "weekday_last_week"
        category_name: Filter by category name (partial match)
        keyword: Filter by note keyword (partial match)
        specific_date: "dd/mm" or "dd/mm/yyyy" for specific date queries
        weekday: "thứ hai", "thứ ba", etc. for weekday of last week queries
    """
    from .utils import (
        get_today_start, get_week_start, get_month_start, get_year_start,
        get_yesterday_start, get_yesterday_end, get_specific_date_range,
        get_weekday_of_last_week, parse_weekday_vietnamese
    )
    
    # Build date filter
    start_date = None
    end_date = None
    
    if time_range == "today":
        start_date = get_today_start()
    elif time_range == "yesterday":
        start_date = get_yesterday_start()
        end_date = get_yesterday_end()
    elif time_range == "week":
        start_date = get_week_start()
    elif time_range == "month":
        start_date = get_month_start()
    elif time_range == "year":
        start_date = get_year_start()
    elif time_range == "specific_date" and specific_date:
        # Parse specific_date: "dd/mm" or "dd/mm/yyyy"
        parts = specific_date.split("/")
        if len(parts) >= 2:
            day = int(parts[0])
            month = int(parts[1])
            year = int(parts[2]) if len(parts) > 2 else None
            start_date, end_date = get_specific_date_range(day, month, year)
    elif time_range == "weekday_last_week" and weekday:
        # Parse weekday
        weekday_num = parse_weekday_vietnamese(weekday)
        if weekday_num is not None:
            start_date, end_date = get_weekday_of_last_week(weekday_num)
    
    # Base query
    query = select(Transaction).where(Transaction.user_id == user_id)
    
    if start_date:
        query = query.where(Transaction.date >= start_date)
    if end_date:
        query = query.where(Transaction.date <= end_date)
    
    if category_name:
        # Join with Category
        query = query.join(Transaction.category).where(Category.name.ilike(f"%{category_name}%"))
        
    if keyword:
        query = query.where(Transaction.note.ilike(f"%{keyword}%"))
    
    result = await session.execute(query.order_by(Transaction.date.desc()))
    transactions = list(result.scalars().all())
    
    total = sum(tx.amount for tx in transactions)
    
    return SmartQueryResult(
        total=total,
        count=len(transactions),
        transactions=transactions,
        time_range=time_range,
        keyword=keyword,
        category_name=category_name
    )


async def set_budget(
    session: AsyncSession,
    user_id: int,
    amount: float,
    category_id: Optional[int] = None
) -> Budget:
    """Set budget for a category or total (category_id=None)"""
    # Check if exists
    query = select(Budget).where(Budget.user_id == user_id)
    if category_id:
        query = query.where(Budget.category_id == category_id)
    else:
        query = query.where(Budget.category_id.is_(None))
        
    result = await session.execute(query)
    budget = result.scalar_one_or_none()
    
    if budget:
        budget.amount = amount
    else:
        budget = Budget(user_id=user_id, amount=amount, category_id=category_id)
        session.add(budget)
        
    await session.commit()
    await session.refresh(budget)
    return budget


async def get_user_budgets(
    session: AsyncSession,
    user_id: int
) -> List[Budget]:
    """Get all budgets for user"""
    result = await session.execute(
        select(Budget).where(Budget.user_id == user_id).order_by(Budget.category_id)
    )
    return list(result.scalars().all())


@dataclass
class BudgetStatus:
    budget: Budget
    spent: float
    remaining: float
    percentage: float
    is_exceeded: bool
    category_name: str


async def check_budget_status(
    session: AsyncSession,
    user_id: int,
    category_id: Optional[int] = None,
    added_amount: float = 0
) -> Optional[BudgetStatus]:
    """
    Check status of a budget (total or specific category).
    Returns BudgetStatus if budget exists, else None.
    """
    # Get budget
    query = select(Budget).where(Budget.user_id == user_id)
    if category_id:
        query = query.where(Budget.category_id == category_id)
    else:
        query = query.where(Budget.category_id.is_(None))
        
    result = await session.execute(query)
    budget = result.scalar_one_or_none()
    
    if not budget:
        return None
        
    # Calculate spending this month
    month_start = get_month_start()
    
    spend_query = select(func.sum(Transaction.amount)).where(
        Transaction.user_id == user_id,
        Transaction.date >= month_start
    )
    
    if category_id:
        spend_query = spend_query.where(Transaction.category_id == category_id)
    else:
        # For total budget, convert None result to 0
        pass
        
    result = await session.execute(spend_query)
    spent = result.scalar() or 0.0
    
    # Add the amount currently being added (to see if this tx breaks the budget)
    spent += added_amount
    
    remaining = budget.amount - spent
    percentage = (spent / budget.amount * 100) if budget.amount > 0 else 0
    is_exceeded = spent > budget.amount
    
    cat_name = "Tổng"
    if budget.category:
        cat_name = budget.category.name
    elif category_id:
        # If budget object doesn't have loaded category relation yet
        cat_res = await session.execute(select(Category).where(Category.id == category_id))
        c = cat_res.scalar_one_or_none()
        if c: cat_name = c.name
            
    return BudgetStatus(
        budget=budget,
        spent=spent,
        remaining=remaining,
        percentage=percentage,
        is_exceeded=is_exceeded,
        category_name=cat_name
    )


async def get_transactions_by_date(
    session: AsyncSession,
    user_id: int,
    target_date: date
) -> List[Transaction]:
    """
    Get all transactions for a specific date.
    
    Args:
        session: Database session
        user_id: User ID (database ID, not telegram_id)
        target_date: The date to query transactions for
        
    Returns:
        List of transactions for that date, ordered by time
    """
    start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
    end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)
    
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.date >= start)
        .where(Transaction.date <= end)
        .order_by(Transaction.date.asc())
    )
    return list(result.scalars().all())


async def update_transaction(
    session: AsyncSession,
    transaction_id: int,
    user_id: int,
    amount: Optional[float] = None,
    note: Optional[str] = None,
    category_id: Optional[int] = None,
    is_income: Optional[bool] = None
) -> Optional[Transaction]:
    """
    Update a transaction's details.
    
    Args:
        session: Database session
        transaction_id: Transaction ID to update
        user_id: User ID for ownership verification
        amount: New amount (optional)
        note: New note (optional)
        category_id: New category ID (optional)
        is_income: If True, change to income category; if False, change to expense category (optional)
        
    Returns:
        Updated transaction or None if not found
    """
    result = await session.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id
        )
    )
    tx = result.scalar_one_or_none()
    
    if tx is None:
        return None
    
    if amount is not None:
        tx.amount = amount
    
    if note is not None:
        tx.note = note
        
    if category_id is not None:
        tx.category_id = category_id
        
    # If changing transaction type (income/expense), we need to find appropriate category
    if is_income is not None:
        target_type = TransactionType.INCOME if is_income else TransactionType.EXPENSE
        
        # If current category type doesn't match, find a default category
        if tx.category is None or tx.category.type != target_type:
            cat_result = await session.execute(
                select(Category).where(Category.type == target_type).limit(1)
            )
            new_cat = cat_result.scalar_one_or_none()
            if new_cat:
                tx.category_id = new_cat.id
    
    await session.commit()
    await session.refresh(tx)
    return tx


async def get_transaction_by_id(
    session: AsyncSession,
    transaction_id: int,
    user_id: int
) -> Optional[Transaction]:
    """Get a specific transaction by ID, verifying ownership."""
    result = await session.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id
        )
    )
    return result.scalar_one_or_none()
