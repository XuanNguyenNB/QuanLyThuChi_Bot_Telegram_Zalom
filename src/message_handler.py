"""
Shared message handling logic for both Telegram and Zalo bots.
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional, Tuple, List

# Configure logging with file output for debugging
import sys
log_file = '/home/botuser/logs/message_handler.log' if sys.platform != 'win32' else 'logs/message_handler.log'
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
# Set console encoding for Windows
if sys.platform == 'win32':
    try:
        import codecs
        if hasattr(sys.stdout, 'detach'):
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())
    except (AttributeError, OSError):
        # Windows console doesn't support detach, use default encoding
        pass

from .models import get_session, Category
from .services import (
    parse_message,
    detect_category,
    get_category_by_name,
    get_all_categories,
    add_transaction,
    get_today_summary,
    find_category_from_user_history,
    get_spending_insights,
    smart_query_transactions
)
from .utils import format_currency, format_currency_full
from .ai_service import (
    parse_with_ai,
    is_ai_enabled,
    get_category_name_from_ai,
    is_question,
    answer_question,
    chat_casual,
    generate_transaction_comment,
    parse_query_intent
)

logger = logging.getLogger(__name__)


@dataclass
class TransactionResult:
    """Result of processing a transaction message"""
    success: bool
    response: str
    amount: float = 0
    note: str = ""
    category_name: str = ""
    category_id: Optional[int] = None
    tx_id: Optional[int] = None
    needs_category_selection: bool = False
    categories: Optional[List] = None


@dataclass
class MessageResult:
    """Result of processing any message"""
    response: str
    is_transaction: bool = False
    transaction_result: Optional[TransactionResult] = None


async def process_text_message(
    db_user_id: int,
    text: str,
    user_display_name: str = ""
) -> MessageResult:
    """
    Process a text message and return the result.
    This is the shared logic for both Telegram and Zalo bots.
    
    Args:
        db_user_id: Database user ID (not Telegram/Zalo ID)
        text: The message text
        user_display_name: User's display name for personalization
        
    Returns:
        MessageResult with response and transaction info
    """
    text = text.strip()
    logger.info(f"Processing text message: '{text}' (length: {len(text)})")
    
    if len(text) < 2:
        logger.info(f"Message too short, returning empty response")
        return MessageResult(response="🤔 Tin nhắn quá ngắn. Hãy gõ rõ hơn nhé!")
    
    async with await get_session() as session:
        # Check if this is a question/query
        if is_question(text):
            result = await _handle_question(session, db_user_id, text)
            return MessageResult(response=result, is_transaction=False)
        
        # Try to parse as transaction
        tx_result = await _handle_transaction(session, db_user_id, text)
        
        if tx_result.success:
            return MessageResult(
                response=tx_result.response,
                is_transaction=True,
                transaction_result=tx_result
            )
        
        # Neither question nor transaction - casual chat
        if is_ai_enabled():
            reply = await chat_casual(text)
            return MessageResult(response=f"💬 {reply}", is_transaction=False)
        else:
            return MessageResult(
                response="🤔 Không hiểu. Gõ như: cafe 50 hoặc /help",
                is_transaction=False
            )


async def _handle_question(session, db_user_id: int, text: str) -> str:
    """Handle a question message"""
    # Try smart query first
    query_intent = await parse_query_intent(text)
    
    if query_intent.is_query:
        result = await smart_query_transactions(
            session,
            db_user_id,
            time_range=query_intent.time_range,
            category_name=query_intent.category,
            keyword=query_intent.keyword
        )
        
        time_labels = {
            "today": "hôm nay",
            "week": "tuần này",
            "month": "tháng này",
            "year": "năm nay",
            "all": "từ đầu tới giờ"
        }
        time_label = time_labels.get(result.time_range, result.time_range)
        
        if result.count == 0:
            filter_desc = ""
            if result.keyword:
                filter_desc = f" cho \"{result.keyword}\""
            elif result.category_name:
                filter_desc = f" ({result.category_name})"
            return f"📭 Không tìm thấy giao dịch nào{filter_desc} {time_label}."
        
        lines = [f"📊 Thống kê {time_label}\n"]
        if result.keyword:
            lines.append(f"🔍 Tìm: {result.keyword}")
        if result.category_name:
            lines.append(f"🏷️ Danh mục: {result.category_name}")
        
        lines.append(f"\n💰 Tổng: {format_currency_full(result.total)}")
        lines.append(f"📝 Số giao dịch: {result.count}")
        
        if result.transactions:
            lines.append(f"\n📋 Chi tiết (mới nhất):")
            for tx in result.transactions[:5]:
                lines.append(f"• {format_currency(tx.amount)} - {tx.note or 'N/A'}")
            if result.count > 5:
                lines.append(f"_... và {result.count - 5} giao dịch khác_")
        
        return "\n".join(lines)
    
    # Fall back to general Q&A
    insights = await get_spending_insights(session, db_user_id)
    today_summary = await get_today_summary(session, db_user_id)
    
    spending_context = f"""
Tháng này: {insights.total_this_month:,.0f}đ
Tháng trước: {insights.total_last_month:,.0f}đ
Trung bình/ngày: {insights.daily_average:,.0f}đ
Hôm nay: {today_summary.total_expense:,.0f}đ ({today_summary.transaction_count} giao dịch)
Top danh mục: {', '.join([f'{c.category_name}: {c.total:,.0f}đ' for c in insights.top_categories[:3]])}
"""
    
    answer = await answer_question(text, spending_context)
    return f"💬 {answer}"


async def _handle_transaction(session, db_user_id: int, text: str) -> TransactionResult:
    """Handle a transaction message - try AI first, then regex fallback"""
    
    # Try AI parsing first
    if is_ai_enabled():
        try:
            ai_result = await parse_with_ai(text)
            
            if ai_result.understood and ai_result.transactions:
                ai_tx = ai_result.transactions[0]
                
                # Get category from user history first
                category = await find_category_from_user_history(
                    session, db_user_id, ai_tx.note
                )
                
                # If not found, use AI's suggestion
                if category is None and ai_tx.category:
                    cat_name = get_category_name_from_ai(ai_tx.category)
                    category = await get_category_by_name(session, cat_name)
                
                # If still not found, try keyword detection
                if category is None and ai_tx.note:
                    category = await detect_category(session, ai_tx.note)
                
                # Save transaction
                tx = await add_transaction(
                    session,
                    user_id=db_user_id,
                    amount=ai_tx.amount,
                    note=ai_tx.note,
                    raw_text=text,
                    category_id=category.id if category else None
                )
                
                cat_name = category.name if category else "Khác"
                summary = await get_today_summary(session, db_user_id)
                
                # Check if needs category selection
                if cat_name == "Khác" and ai_tx.note:
                    all_categories = await get_all_categories(session)
                    return TransactionResult(
                        success=True,
                        response=(
                            f"✅ Đã ghi: {format_currency_full(ai_tx.amount)}\n"
                            f"📝 {ai_tx.note}\n"
                            f"🤔 Chưa xác định danh mục. Chọn một danh mục:"
                        ),
                        amount=ai_tx.amount,
                        note=ai_tx.note,
                        category_name=cat_name,
                        category_id=category.id if category else None,
                        tx_id=tx.id,
                        needs_category_selection=True,
                        categories=all_categories
                    )
                
                # Generate AI comment
                tx_type = ai_tx.type if hasattr(ai_tx, 'type') else "expense"
                ai_comment = await generate_transaction_comment(
                    ai_tx.amount, ai_tx.note or "", cat_name, tx_type
                )
                
                response = (
                    f"✅ Đã ghi: {format_currency_full(ai_tx.amount)}\n"
                    f"📝 {ai_tx.note or 'Không có ghi chú'}\n"
                    f"🏷️ Danh mục: {cat_name}\n"
                )
                if ai_comment:
                    response += f"\n💬 {ai_comment}\n"
                response += (
                    f"───────────────\n"
                    f"💸 Tổng chi hôm nay: {format_currency_full(summary.total_expense)}"
                )
                
                return TransactionResult(
                    success=True,
                    response=response,
                    amount=ai_tx.amount,
                    note=ai_tx.note,
                    category_name=cat_name,
                    category_id=category.id if category else None,
                    tx_id=tx.id
                )
        except Exception as e:
            logger.error(f"AI parsing error: {e}")
    
    # Fallback to regex parsing
    parsed = parse_message(text)
    
    if parsed.is_valid and parsed.amount > 0:
        # Get category
        category = await find_category_from_user_history(
            session, db_user_id, parsed.note
        )
        if category is None:
            category = await detect_category(session, parsed.note)
        
        # Save transaction
        tx = await add_transaction(
            session,
            user_id=db_user_id,
            amount=parsed.amount,
            note=parsed.note,
            raw_text=parsed.raw_text,
            category_id=category.id if category else None
        )
        
        cat_name = category.name if category else "Khác"
        summary = await get_today_summary(session, db_user_id)
        
        # Check if needs category selection
        if cat_name == "Khác" and parsed.note:
            all_categories = await get_all_categories(session)
            return TransactionResult(
                success=True,
                response=(
                    f"✅ Đã ghi: {format_currency_full(parsed.amount)}\n"
                    f"📝 {parsed.note}\n"
                    f"🤔 Chưa xác định danh mục. Chọn một danh mục:"
                ),
                amount=parsed.amount,
                note=parsed.note,
                category_name=cat_name,
                category_id=category.id if category else None,
                tx_id=tx.id,
                needs_category_selection=True,
                categories=all_categories
            )
        
        response = (
            f"✅ Đã ghi: {format_currency_full(parsed.amount)}\n"
            f"📝 {parsed.note or 'Không có ghi chú'}\n"
            f"🏷️ Danh mục: {cat_name}\n"
            f"───────────────\n"
            f"💸 Tổng chi hôm nay: {format_currency_full(summary.total_expense)}"
        )
        
        return TransactionResult(
            success=True,
            response=response,
            amount=parsed.amount,
            note=parsed.note,
            category_name=cat_name,
            category_id=category.id if category else None,
            tx_id=tx.id
        )
    
    # Neither AI nor regex could parse
    return TransactionResult(
        success=False,
        response=""
    )
