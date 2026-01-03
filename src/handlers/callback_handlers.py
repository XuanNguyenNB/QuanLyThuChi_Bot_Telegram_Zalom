"""
Handlers cho category callbacks - xử lý khi user chọn danh mục
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select, update as sql_update

from ..database import get_session
from ..models import Transaction, Category
from ..services import (
    get_or_create_user,
    get_category_by_name,
    learn_keyword_for_user,
    get_today_summary,
)
from ..utils import format_currency_full

logger = logging.getLogger(__name__)


async def handle_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle category selection callback from inline buttons"""
    query = update.callback_query
    await query.answer()
    
    # Parse callback data: "cat:{tx_id}:{cat_id}:{note}"
    data = query.data
    if not data.startswith("cat:"):
        return
    
    parts = data.split(":", 3)
    if len(parts) < 4:
        return
    
    _, tx_id_str, cat_id_str, note = parts
    
    try:
        tx_id = int(tx_id_str)
        cat_id = int(cat_id_str)
        
        async with await get_session() as session:
            # Update transaction with selected category
            await session.execute(
                sql_update(Transaction)
                .where(Transaction.id == tx_id)
                .values(category_id=cat_id)
            )
            await session.commit()
            
            # Get database user for learning and summary
            tg_user = query.from_user
            db_user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.full_name)
            
            # Learn from user's choice - save user-specific mapping
            if note:
                learned = await learn_keyword_for_user(session, db_user.id, cat_id, note)
                if learned:
                    logger.info(f"User {db_user.id} learned: '{note}' -> category {cat_id}")
            
            # Get category name for response
            result = await session.execute(
                select(Category).where(Category.id == cat_id)
            )
            category = result.scalar_one_or_none()
            cat_name = category.name if category else "Khác"
            
            # Get today's total
            summary = await get_today_summary(session, db_user.id)
        
        # Update the message
        await query.edit_message_text(
            f"✅ Đã cập nhật danh mục: *{cat_name}*\n"
            f"📝 {note}\n"
            f"🧠 Bot đã học từ khóa mới!\n"
            f"───────────────\n"
            f"💸 Tổng chi hôm nay: *{format_currency_full(summary.total_expense)}*",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in category callback: {e}")
        await query.edit_message_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")
