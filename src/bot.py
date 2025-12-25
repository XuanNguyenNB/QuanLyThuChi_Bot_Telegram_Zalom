"""
Telegram Bot handlers using python-telegram-bot v20+
"""

import csv
import io
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from .models import init_db, get_session, seed_default_categories, Category, TransactionType
from .services import (
    parse_message,
    detect_category,
    get_category_by_name,
    get_all_categories,
    get_or_create_user,
    add_transaction,
    get_today_summary,
    get_month_summary,
    get_all_transactions,
    learn_keyword_for_user,
    find_category_from_user_history,
    get_user_learned_keywords,
    get_last_transaction,
    update_transaction_category,
    delete_transaction,
    get_spending_insights,
    smart_query_transactions,
    link_user_by_phone
)
from .utils import format_currency, format_currency_full, format_date, format_datetime
from .ai_service import is_ai_enabled, transcribe_voice, parse_with_ai, get_category_name_from_ai, generate_transaction_comment
from .message_handler import process_text_message

# Configure logging with file output for debugging
import sys
log_file = '/home/botuser/logs/telegram_bot.log' if sys.platform != 'win32' else 'logs/telegram_bot.log'
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(encoding='utf-8') if sys.platform == 'win32' else logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    user = update.effective_user
    
    async with await get_session() as session:
        await get_or_create_user(
            session,
            user_id=user.id,
            username=user.username,
            full_name=user.full_name
        )
    
    welcome_message = (
        f"Chào {user.first_name}! 👋\n\n"
        "Tôi là bot ghi chép chi tiêu. Gõ nhanh để ghi:\n"
        "• `cafe 50` → 50,000₫ (không cần gõ k)\n"
        "• `grab 35k` → 35,000₫\n"
        "• `tiền nhà 2tr` → 2,000,000₫\n\n"
        "� *Lệnh hữu ích:*\n"
        "/today • /month • /insights • /help\n\n"
        "💬 *Hỏi đáp:* Gõ tự nhiên như:\n"
        "_\"Tháng này chi bao nhiêu?\"_"
    )
    
    await update.message.reply_text(welcome_message, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    help_text = (
        "📖 *HƯỚNG DẪN SỬ DỤNG*\n"
        "━━━━━━━━━━━━━━━\n\n"
        "💰 *Ghi chi tiêu - Gõ tự nhiên:*\n"
        "```\n"
        "cafe 50      → 50,000₫\n"
        "grab 35k     → 35,000₫\n"
        "tiền nhà 2tr → 2,000,000₫\n"
        "```\n\n"
        "📈 *Ghi thu nhập:*\n"
        "```\n"
        "bán hàng 350      → Thu 350,000₫\n"
        "lương 15tr        → Thu 15,000,000₫\n"
        "bán x 500 trừ vốn 200 → Thu 300,000₫\n"
        "```\n\n"
        "💬 *Hỏi đáp thông minh:*\n"
        "```\n"
        "Tháng này chi bao nhiêu?\n"
        "Tôi chi nhiều nhất vào gì?\n"
        "```\n\n"
        "📋 *Các lệnh:*\n"
        "• /today → Chi tiêu hôm nay\n"
        "• /month → Chi tiêu tháng\n"
        "• /insights → Phân tích thông minh\n"
        "• /edit → Sửa giao dịch gần nhất\n"
        "• /delete → Xóa giao dịch gần nhất\n"
        "• /export → Xuất file CSV\n\n"
        "💡 *Mẹo:* Không cần gõ 'k', bot tự hiểu!\n"
        "`50 cafe` = `50k cafe` = 50,000₫"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /today command - show today's summary"""
    user = update.effective_user
    
    try:
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            summary = await get_today_summary(session, db_user.id)
        
        if summary.transaction_count == 0:
            await update.message.reply_text("📭 Hôm nay chưa có giao dịch nào.")
            return
        
        # Separate income and expense transactions
        income_txs = [tx for tx in summary.transactions if tx.category and tx.category.type.value == "income"]
        expense_txs = [tx for tx in summary.transactions if not tx.category or tx.category.type.value != "income"]
        
        # Build message
        lines = [f"📅 *Hôm nay* ({format_date(datetime.now())})\n"]
        
        # Income section
        lines.append(f"💰 *Thu: {format_currency_full(summary.total_income)}*")
        if income_txs:
            lines.append(f"� Chi tiết ({len(income_txs)} giao dịch):")
            for tx in income_txs[:5]:
                cat_name = tx.category.name if tx.category else "Khác"
                lines.append(f"  • {format_currency(tx.amount)} - {tx.note or 'N/A'} ({cat_name})")
            if len(income_txs) > 5:
                lines.append(f"  _... và {len(income_txs) - 5} giao dịch khác_")
        
        lines.append("")  # Empty line
        
        # Expense section
        lines.append(f"💸 *Chi: {format_currency_full(summary.total_expense)}*")
        if expense_txs:
            lines.append(f"📝 Chi tiết ({len(expense_txs)} giao dịch):")
            for tx in expense_txs[:5]:
                cat_name = tx.category.name if tx.category else "Khác"
                lines.append(f"  • {format_currency(tx.amount)} - {tx.note or 'N/A'} ({cat_name})")
            if len(expense_txs) > 5:
                lines.append(f"  _... và {len(expense_txs) - 5} giao dịch khác_")
        
        lines.append("")  # Empty line
        
        # Balance
        balance = summary.total_income - summary.total_expense
        if balance >= 0:
            lines.append(f"📈 *Thặng dư: +{format_currency_full(balance)}*")
        else:
            lines.append(f"📉 *Thâm hụt: {format_currency_full(balance)}*")
        
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in today_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra. Vui lòng thử lại sau.")


async def month_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /month command - show monthly summary"""
    user = update.effective_user
    
    try:
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            summary = await get_month_summary(session, db_user.id)
        
        if summary.transaction_count == 0:
            await update.message.reply_text("📭 Tháng này chưa có giao dịch nào.")
            return
        
        # Build message
        now = datetime.now()
        lines = [f"📊 *Tháng {now.month}/{now.year}*\n"]
        
        # Income section
        lines.append(f"💰 *Thu: {format_currency_full(summary.total_income)}*")
        
        lines.append("")  # Empty line
        
        # Expense section
        lines.append(f"💸 *Chi: {format_currency_full(summary.total_expense)}*")
        if summary.category_breakdown:
            lines.append(f"🏷️ Top danh mục:")
            for i, cat in enumerate(summary.category_breakdown[:5], 1):
                percent = (cat.total / summary.total_expense * 100) if summary.total_expense > 0 else 0
                lines.append(f"  {i}. {cat.category_name}: {format_currency_full(cat.total)} ({percent:.0f}%)")
        
        lines.append("")  # Empty line
        
        # Balance
        balance = summary.total_income - summary.total_expense
        if balance >= 0:
            lines.append(f"📈 *Thặng dư: +{format_currency_full(balance)}*")
        else:
            lines.append(f"📉 *Thâm hụt: {format_currency_full(balance)}*")
        
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in month_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra. Vui lòng thử lại sau.")


async def insights_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /insights command - show spending insights"""
    user = update.effective_user
    
    try:
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            insights = await get_spending_insights(session, db_user.id)
        
        # Trend emoji
        trend_emoji = "📈" if insights.trend == "up" else "📉" if insights.trend == "down" else "➡️"
        
        lines = [
            "💡 *PHÂN TÍCH CHI TIÊU*",
            "",
            f"📊 *Tháng này:* {format_currency_full(insights.total_this_month)}",
            f"📊 *Tháng trước:* {format_currency_full(insights.total_last_month)}",
            f"{trend_emoji} *Xu hướng:* {'Tăng' if insights.trend == 'up' else 'Giảm' if insights.trend == 'down' else 'Ổn định'}",
            f"📅 *Trung bình/ngày:* {format_currency_full(insights.daily_average)}",
            "",
        ]
        
        if insights.top_categories:
            lines.append("🏷️ *Top 5 danh mục chi:*")
            for i, cat in enumerate(insights.top_categories[:5], 1):
                percent = (cat.total / insights.total_this_month * 100) if insights.total_this_month > 0 else 0
                lines.append(f"  {i}. {cat.category_name}: {format_currency_full(cat.total)} ({percent:.0f}%)")
            lines.append("")
        
        if insights.biggest_expense:
            lines.append(f"💸 *Chi lớn nhất:* {format_currency_full(insights.biggest_expense.amount)}")
            lines.append(f"   📝 {insights.biggest_expense.note or 'Không có ghi chú'}")
            lines.append("")
        
        lines.append(f"💬 *Gợi ý:* {insights.suggestion}")
        
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in insights_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra. Vui lòng thử lại sau.")


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /export command - export transactions to CSV"""
    user = update.effective_user
    
    try:
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            transactions = await get_all_transactions(session, db_user.id)
        
        if not transactions:
            await update.message.reply_text("📭 Chưa có giao dịch nào để xuất.")
            return
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(["Ngày", "Số tiền", "Danh mục", "Ghi chú", "Loại"])
        
        # Data rows
        for tx in transactions:
            cat_name = tx.category.name if tx.category else "Khác"
            tx_type = "Thu" if (tx.category and tx.category.type == TransactionType.INCOME) else "Chi"
            writer.writerow([
                format_datetime(tx.date),
                tx.amount,
                cat_name,
                tx.note or "",
                tx_type
            ])
        
        # Send file
        output.seek(0)
        file_bytes = io.BytesIO(output.getvalue().encode('utf-8-sig'))  # UTF-8 BOM for Excel
        file_bytes.name = f"chi_tieu_{datetime.now().strftime('%Y%m%d')}.csv"
        
        await update.message.reply_document(
            document=file_bytes,
            caption=f"📄 Xuất {len(transactions)} giao dịch thành công!"
        )
        
    except Exception as e:
        logger.error(f"Error in export_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra khi xuất file. Vui lòng thử lại sau.")


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /delete command - delete last transaction"""
    user = update.effective_user
    
    try:
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            
            # Get last transaction
            last_tx = await get_last_transaction(session, db_user.id)
            
            if last_tx is None:
                await update.message.reply_text("❌ Không có giao dịch nào để xóa.")
                return
            
            # Store info before deleting
            amount = last_tx.amount
            note = last_tx.note or "Không có ghi chú"
            cat_name = last_tx.category.name if last_tx.category else "Khác"
            
            # Delete the transaction
            await delete_transaction(session, last_tx.id, db_user.id)
            
            # Get updated today's summary
            summary = await get_today_summary(session, db_user.id)
        
        await update.message.reply_text(
            f"🗑️ *Đã xóa giao dịch:*\n"
            f"💰 {format_currency_full(amount)}\n"
            f"📝 {note}\n"
            f"🏷️ {cat_name}\n"
            f"───────────────\n"
            f"💸 Tổng chi hôm nay: *{format_currency_full(summary.total_expense)}*",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in delete_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /link command - link with Zalo account by phone"""
    user = update.effective_user
    
    # Get phone from command args
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "📱 *Liên kết với Zalo*\n\n"
            "Để đồng bộ dữ liệu giữa Telegram và Zalo:\n"
            "1. Gõ: `/link 0901234567` (SĐT của bạn)\n"
            "2. Trên Zalo bot, gõ: `/link 0901234567`\n\n"
            "Sau khi liên kết, dữ liệu chi tiêu sẽ được đồng bộ!",
            parse_mode="Markdown"
        )
        return
    
    phone = context.args[0].strip()
    
    # Validate phone
    if not phone.isdigit() or len(phone) < 9:
        await update.message.reply_text("❌ Số điện thoại không hợp lệ.")
        return
    
    try:
        async with await get_session() as session:
            linked_user = await link_user_by_phone(session, phone, telegram_id=user.id)
            
            if linked_user is None:
                # Cannot link - telegram_id or phone already linked to another user
                await update.message.reply_text(
                    f"❌ *Không thể liên kết*\n\n"
                    f"SĐT {phone} hoặc tài khoản Telegram của bạn đã được liên kết với tài khoản khác.\n\n"
                    f"Mỗi SĐT chỉ có thể liên kết với một tài khoản Telegram và một tài khoản Zalo.",
                    parse_mode="Markdown"
                )
                return
            
            if linked_user.zalo_id:
                await update.message.reply_text(
                    f"✅ *Đã liên kết với Zalo!*\n"
                    f"📱 SĐT: {phone}\n\n"
                    f"Dữ liệu chi tiêu sẽ được đồng bộ giữa Telegram và Zalo.",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    f"📱 *Đã lưu SĐT:* {phone}\n\n"
                    f"Để đồng bộ với Zalo, hãy gõ `/link {phone}` trên Zalo bot.",
                    parse_mode="Markdown"
                )
                
    except Exception as e:
        logger.error(f"Error in link_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /edit command - edit last transaction's category"""
    user = update.effective_user
    
    try:
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            
            # Get last transaction
            last_tx = await get_last_transaction(session, db_user.id)
            
            if last_tx is None:
                await update.message.reply_text("❌ Không có giao dịch nào để sửa.")
                return
            
            # Get current category name
            current_cat = "Khác"
            if last_tx.category:
                current_cat = last_tx.category.name
            
            # Get all categories for buttons
            all_categories = await get_all_categories(session)
            keyboard = build_category_keyboard_for_edit(last_tx.id, last_tx.note or "", all_categories)
            
            response = (
                f"📝 *Sửa giao dịch gần nhất:*\n"
                f"💰 {format_currency_full(last_tx.amount)}\n"
                f"📝 {last_tx.note or 'Không có ghi chú'}\n"
                f"🏷️ Danh mục hiện tại: {current_cat}\n\n"
                f"Chọn danh mục mới:"
            )
            
            await update.message.reply_text(
                response,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Error in edit_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


def build_category_keyboard_for_edit(tx_id: int, note: str, categories: list) -> InlineKeyboardMarkup:
    """Build inline keyboard for edit command - uses 'edit:' prefix"""
    keyboard = []
    row = []
    excluded_categories = {"Nhà cửa"}
    
    for cat in categories:
        if cat.name in excluded_categories:
            continue
        short_note = note[:20] if note else ""
        callback_data = f"edit:{tx_id}:{cat.id}:{short_note}"
        
        if len(callback_data.encode('utf-8')) > 64:
            callback_data = f"edit:{tx_id}:{cat.id}:"
        
        row.append(InlineKeyboardButton(cat.name, callback_data=callback_data))
        
        if len(row) == 3:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    return InlineKeyboardMarkup(keyboard)


async def handle_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle edit category callback - update transaction and re-learn"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith("edit:"):
        return
    
    parts = data.split(":", 3)
    if len(parts) < 4:
        return
    
    _, tx_id_str, cat_id_str, note = parts
    
    try:
        tx_id = int(tx_id_str)
        cat_id = int(cat_id_str)
        user_id = query.from_user.id
        
        async with await get_session() as session:
            # Update transaction category
            await update_transaction_category(session, tx_id, cat_id)
            
            # Re-learn: update user's keyword mapping
            if note:
                await learn_keyword_for_user(session, user_id, cat_id, note)
                logger.info(f"User {user_id} re-learned: '{note}' -> category {cat_id}")
            
            # Get category name
            from sqlalchemy import select
            result = await session.execute(
                select(Category).where(Category.id == cat_id)
            )
            category = result.scalar_one_or_none()
            cat_name = category.name if category else "Khác"
            
            # Get today's summary
            summary = await get_today_summary(session, user_id)
        
        await query.edit_message_text(
            f"✅ Đã sửa danh mục thành: *{cat_name}*\n"
            f"🧠 Bot đã học lại từ khóa này!\n"
            f"───────────────\n"
            f"💸 Tổng chi hôm nay: *{format_currency_full(summary.total_expense)}*",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in edit callback: {e}")
        await query.edit_message_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages - Q&A or transaction parsing"""
    text = update.message.text.strip()
    user = update.effective_user
    
    # Skip if message starts with / or is too short
    if text.startswith("/"):
        return
    
    if len(text) < 2:
        return  # Ignore very short messages
    
    try:
        # Get database user first
        async with await get_session() as session:
            db_user = await get_or_create_user(
                session,
                user_id=user.id,
                username=user.username,
                full_name=user.full_name
            )
        
        # Send typing indicator
        await update.message.chat.send_action("typing")
        
        # Use shared message handler
        result = await process_text_message(
            db_user_id=db_user.id,
            text=text,
            user_display_name=user.first_name or ""
        )
        
        if not result.response:
            return
        
        # Handle Telegram-specific features (inline keyboard for category selection)
        if result.transaction_result and result.transaction_result.needs_category_selection:
            tx_result = result.transaction_result
            keyboard = build_category_keyboard(
                tx_result.tx_id,
                tx_result.note,
                tx_result.categories
            )
            response = (
                f"✅ Đã ghi: *{format_currency_full(tx_result.amount)}*\n"
                f"📝 {tx_result.note}\n"
                f"🤔 Chưa xác định danh mục. Chọn một danh mục:\n"
                f"_(Bot sẽ học để lần sau tự nhận diện)_"
            )
            await update.message.reply_text(
                response,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            return
        
        # Send regular response with Markdown formatting
        await update.message.reply_text(result.response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error handling text message: {e}")
        await update.message.reply_text(
            "❌ Có lỗi xảy ra. Vui lòng thử lại."
        )


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
            from sqlalchemy import update as sql_update
            from .models import Transaction
            
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
            category = await get_category_by_name(session, "")
            from sqlalchemy import select
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


def build_category_keyboard(tx_id: int, note: str, categories: list) -> InlineKeyboardMarkup:
    """Build inline keyboard with category buttons"""
    keyboard = []
    row = []
    excluded_categories = {"Nhà cửa"}
    
    for cat in categories:
        if cat.name in excluded_categories:
            continue
        # Limit callback data to avoid Telegram limit
        short_note = note[:20] if note else ""
        callback_data = f"cat:{tx_id}:{cat.id}:{short_note}"
        
        # Truncate if too long (Telegram limit is 64 bytes)
        if len(callback_data.encode('utf-8')) > 64:
            callback_data = f"cat:{tx_id}:{cat.id}:"
        
        row.append(InlineKeyboardButton(cat.name, callback_data=callback_data))
        
        if len(row) == 3:  # 3 buttons per row
            keyboard.append(row)
            row = []
    
    if row:  # Add remaining buttons
        keyboard.append(row)
    
    return InlineKeyboardMarkup(keyboard)


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages - transcribe, parse, show result, then confirm"""
    voice = update.message.voice
    user = update.effective_user
    
    if not voice:
        return
    
    try:
        # Send typing indicator
        await update.message.chat.send_action("typing")
        
        # Download voice file
        voice_file = await context.bot.get_file(voice.file_id)
        voice_bytes = await voice_file.download_as_bytearray()
        
        # Transcribe using Gemini
        text = await transcribe_voice(bytes(voice_bytes))
        
        if not text:
            await update.message.reply_text(
                "🎤 Không nghe rõ. Hãy thử nói rõ hơn hoặc gõ text nhé!"
            )
            return
        
        # Parse with AI to show preview
        if not is_ai_enabled():
            await update.message.reply_text("❌ AI chưa được cấu hình.")
            return
        
        ai_result = await parse_with_ai(text)
        
        if not ai_result.understood or not ai_result.transactions:
            await update.message.reply_text(
                f"🎤 Nhận diện: _{text}_\n\n"
                f"🤔 Không hiểu nội dung. Hãy thử nói rõ như: _cafe năm mươi nghìn_",
                parse_mode="Markdown"
            )
            return
        
        # Get first transaction for preview
        ai_tx = ai_result.transactions[0]
        
        async with await get_session() as session:
            # Get category
            category = None
            if ai_tx.category:
                category = await get_category_by_name(session, ai_tx.category)
            
            if category is None:
                db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
                category = await find_category_from_user_history(session, db_user.id, ai_tx.note)
            
            if category is None and ai_tx.note:
                category = await detect_category(session, ai_tx.note)
            
            cat_name = category.name if category else None
            
            # Store parsed data for confirmation
            context.user_data['voice_data'] = {
                'text': text,
                'amount': ai_tx.amount,
                'note': ai_tx.note,
                'category_id': category.id if category else None,
                'category_name': cat_name
            }
            
            # If category is unknown, show category selection
            if cat_name is None or cat_name == "Khác":
                all_categories = await get_all_categories(session)
                
                # Build category keyboard with voice prefix
                keyboard = []
                row = []
                excluded_categories = {"Nhà cửa"}
                
                for cat in all_categories:
                    if cat.name in excluded_categories:
                        continue
                    callback_data = f"vcat:{cat.id}"
                    row.append(InlineKeyboardButton(cat.name, callback_data=callback_data))
                    
                    if len(row) == 3:
                        keyboard.append(row)
                        row = []
                
                if row:
                    keyboard.append(row)
                
                # Add cancel button
                keyboard.append([InlineKeyboardButton("❌ Hủy", callback_data="voice:cancel")])
                
                await update.message.reply_text(
                    f"🎤 Nhận diện từ voice:\n"
                    f"💰 *{format_currency_full(ai_tx.amount)}*\n"
                    f"📝 {ai_tx.note or 'Không có ghi chú'}\n\n"
                    f"🏷️ Chọn danh mục:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                # Category known - show confirm buttons
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Ghi vào sổ", callback_data="voice:confirm"),
                        InlineKeyboardButton("❌ Hủy", callback_data="voice:cancel")
                    ]
                ])
                
                await update.message.reply_text(
                    f"🎤 Nhận diện từ voice:\n"
                    f"💰 *{format_currency_full(ai_tx.amount)}*\n"
                    f"📝 {ai_tx.note or 'Không có ghi chú'}\n"
                    f"🏷️ Danh mục: {cat_name}\n\n"
                    f"Bạn muốn ghi vào sổ không?",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
        
    except Exception as e:
        logger.error(f"Error handling voice message: {e}")
        await update.message.reply_text(
            "❌ Không thể xử lý tin nhắn thoại. Vui lòng thử lại."
        )


async def handle_voice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice confirmation callback"""
    query = update.callback_query
    await query.answer()
    
    action = query.data.split(":")[1]
    
    if action == "cancel":
        await query.edit_message_text("❌ Đã hủy.")
        return
    
    # Get stored voice data
    voice_data = context.user_data.get('voice_data')
    if not voice_data:
        await query.edit_message_text("❌ Không tìm thấy nội dung. Hãy gửi lại voice.")
        return
    
    user = query.from_user
    
    try:
        async with await get_session() as session:
            # Ensure user exists and get database user
            db_user = await get_or_create_user(
                session,
                user_id=user.id,
                username=user.username,
                full_name=user.full_name
            )
            
            # Add transaction with stored data
            tx = await add_transaction(
                session,
                user_id=db_user.id,
                amount=voice_data['amount'],
                note=voice_data['note'],
                raw_text=voice_data['text'],
                category_id=voice_data.get('category_id')
            )
            
            # Learn keyword if category was selected
            if voice_data.get('category_id') and voice_data.get('note'):
                await learn_keyword_for_user(
                    session, db_user.id, voice_data['category_id'], voice_data['note']
                )
            
            # Get today's summary
            summary = await get_today_summary(session, db_user.id)
            
            cat_name = voice_data.get('category_name') or "Khác"
            
            response = (
                f"🎤✅ Đã ghi từ voice:\n"
                f"💰 *{format_currency_full(voice_data['amount'])}*\n"
                f"📝 {voice_data['note'] or 'Không có ghi chú'}\n"
                f"🏷️ Danh mục: {cat_name}\n"
                f"───────────────\n"
                f"💸 Tổng chi hôm nay: *{format_currency_full(summary.total_expense)}*"
            )
            
            await query.edit_message_text(response, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error in voice callback: {e}")
        await query.edit_message_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def handle_voice_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice category selection callback"""
    query = update.callback_query
    await query.answer()
    
    # Parse category ID from callback data: "vcat:{cat_id}"
    cat_id = int(query.data.split(":")[1])
    
    # Get stored voice data
    voice_data = context.user_data.get('voice_data')
    if not voice_data:
        await query.edit_message_text("❌ Không tìm thấy nội dung. Hãy gửi lại voice.")
        return
    
    user = query.from_user
    
    try:
        async with await get_session() as session:
            # Get category name
            from sqlalchemy import select
            result = await session.execute(
                select(Category).where(Category.id == cat_id)
            )
            category = result.scalar_one_or_none()
            cat_name = category.name if category else "Khác"
            
            # Update voice_data with selected category
            voice_data['category_id'] = cat_id
            voice_data['category_name'] = cat_name
            context.user_data['voice_data'] = voice_data
            
            # Show confirm buttons
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Ghi vào sổ", callback_data="voice:confirm"),
                    InlineKeyboardButton("❌ Hủy", callback_data="voice:cancel")
                ]
            ])
            
            await query.edit_message_text(
                f"🎤 Nhận diện từ voice:\n"
                f"💰 *{format_currency_full(voice_data['amount'])}*\n"
                f"📝 {voice_data['note'] or 'Không có ghi chú'}\n"
                f"🏷️ Danh mục: {cat_name}\n\n"
                f"Bạn muốn ghi vào sổ không?",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Error in voice category callback: {e}")
        await query.edit_message_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors"""
    logger.error(f"Exception while handling an update: {context.error}")


def main() -> None:
    """Start the bot"""
    # Get token from environment
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN not found in environment variables!")
    
    db_url = os.getenv("DB_URL", "sqlite+aiosqlite:///./finance_bot.db")
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add startup hook to initialize database and set menu commands
    async def post_init(app: Application) -> None:
        await init_db(db_url)
        async with await get_session() as session:
            await seed_default_categories(session)
        
        # Set bot menu commands
        commands = [
            BotCommand("start", "🚀 Bắt đầu sử dụng"),
            BotCommand("today", "📊 Chi tiêu hôm nay"),
            BotCommand("month", "📅 Chi tiêu tháng này"),
            BotCommand("insights", "💡 Phân tích thông minh"),
            BotCommand("edit", "✏️ Sửa giao dịch gần nhất"),
            BotCommand("delete", "🗑️ Xóa giao dịch gần nhất"),
            BotCommand("link", "🔗 Liên kết với Zalo"),
            BotCommand("export", "📄 Xuất file CSV"),
            BotCommand("help", "❓ Hướng dẫn"),
        ]
        await app.bot.set_my_commands(commands)
        logger.info("Database initialized and bot menu set")
    
    application.post_init = post_init
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("month", month_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("edit", edit_command))
    application.add_handler(CommandHandler("delete", delete_command))
    application.add_handler(CommandHandler("insights", insights_command))
    application.add_handler(CommandHandler("link", link_command))
    
    # Handle category selection callbacks
    application.add_handler(CallbackQueryHandler(handle_category_callback, pattern="^cat:"))
    application.add_handler(CallbackQueryHandler(handle_edit_callback, pattern="^edit:"))
    application.add_handler(CallbackQueryHandler(handle_voice_callback, pattern="^voice:"))
    application.add_handler(CallbackQueryHandler(handle_voice_category_callback, pattern="^vcat:"))
    
    # Handle voice messages
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
    
    # Handle text messages (must be last)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Run the bot
    logger.info("Starting bot...")
    
    # Check if we're in main thread or not
    import threading
    if threading.current_thread() is threading.main_thread():
        # Main thread - use run_polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    else:
        # In thread - use async approach
        import asyncio
        loop = asyncio.get_event_loop()
        
        async def start_bot():
            await application.initialize()
            await application.start()
            await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            
            try:
                # Keep running until stopped
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                pass
            finally:
                await application.updater.stop()
                await application.stop()
                await application.shutdown()
        
        loop.run_until_complete(start_bot())


if __name__ == "__main__":
    main()
