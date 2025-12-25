"""
Business logic services: message parsing, category detection, reporting.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, Category, Transaction, TransactionType
from .utils import get_today_start, get_today_end, get_month_start, get_month_end, get_week_start, get_year_start


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
    user = result.scalar_one_or_none()
    
    if user:
        # Update with new platform ID
        if telegram_id:
            user.telegram_id = telegram_id
        if zalo_id:
            user.zalo_id = zalo_id
        await session.commit()
        return user
    
    # Find by platform ID and add phone
    if telegram_id:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.phone = phone
            if zalo_id:
                user.zalo_id = zalo_id
            await session.commit()
            return user
    
    if zalo_id:
        result = await session.execute(select(User).where(User.zalo_id == zalo_id))
        user = result.scalar_one_or_none()
        if user:
            user.phone = phone
            if telegram_id:
                user.telegram_id = telegram_id
            await session.commit()
            return user
    
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
        date=transaction_date or datetime.now()
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
    
    now = datetime.now()
    
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
    keyword: Optional[str] = None
) -> SmartQueryResult:
    """
    Smart query transactions with filters.
    
    Args:
        time_range: "today", "week", "month", "year", "all"
        category_name: Filter by category name (partial match)
        keyword: Filter by note keyword (partial match)
    """
    # Build date filter
    now = datetime.now()
    start_date = None
    
    if time_range == "today":
        start_date = get_today_start()
    elif time_range == "week":
        start_date = get_week_start()
    elif time_range == "month":
        start_date = get_month_start()
    elif time_range == "year":
        start_date = get_year_start()
    # "all" means no date filter
    
    # Build query
    query = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
    )
    
    if start_date:
        query = query.where(Transaction.date >= start_date)
    
    # Join with category if needed
    if category_name:
        query = query.join(Category).where(
            func.lower(Category.name).contains(category_name.lower())
        )
    
    query = query.order_by(Transaction.date.desc())
    
    result = await session.execute(query)
    transactions = list(result.scalars().all())
    
    # Filter by keyword in note if specified
    if keyword:
        keyword_lower = keyword.lower()
        transactions = [
            tx for tx in transactions 
            if tx.note and keyword_lower in tx.note.lower()
        ]
    
    # Calculate total
    total = sum(tx.amount for tx in transactions)
    
    return SmartQueryResult(
        total=total,
        count=len(transactions),
        transactions=transactions,
        time_range=time_range,
        keyword=keyword,
        category_name=category_name
    )
