"""
Telegram Bot handlers using python-telegram-bot v20+
"""

import csv
import io
import logging
import os
from datetime import datetime, timedelta, date

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
    link_user_by_phone,
    set_budget,
    get_user_budgets,
    check_budget_status,
    get_transactions_by_date,
    update_transaction,
    get_transaction_by_id
)
from .utils import format_currency, format_currency_full, format_date, format_datetime
from .ai_service import is_ai_enabled, transcribe_voice, parse_with_ai, get_category_name_from_ai, generate_transaction_comment
from .message_handler import process_text_message
from .charts import generate_pie_chart, generate_bar_chart

# Configure logging with file output for debugging
import sys
log_file = '/home/botuser/logs/telegram_bot.log' if sys.platform != 'win32' else 'logs/telegram_bot.log'
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
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
        "• /edit → Sửa giao dịch (chọn ngày → giao dịch)\n"
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
        income_txs = [tx for tx in summary.transactions if tx.category and tx.category.type.value == "INCOME"]
        expense_txs = [tx for tx in summary.transactions if not tx.category or tx.category.type.value != "INCOME"]
        
        # Build message
        lines = [f"📅 *Hôm nay* ({format_date(datetime.now())})\n"]
        
        # Income section
        lines.append(f"💰 *Thu: {format_currency_full(summary.total_income)}*")
        if income_txs:
            for tx in income_txs[:5]:
                lines.append(f"  + {format_currency(tx.amount)} - {tx.note or 'N/A'}")
            if len(income_txs) > 5:
                lines.append(f"  _... và {len(income_txs) - 5} giao dịch khác_")
        
        # Expense section
        lines.append(f"💸 *Chi: {format_currency_full(summary.total_expense)}*")
        if expense_txs:
            for tx in expense_txs[:5]:
                lines.append(f"  - {format_currency(tx.amount)} - {tx.note or 'N/A'}")
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
        
        # Send Pie Chart if there are expenses
        if summary.total_expense > 0 and summary.category_breakdown:
            chart_data = [(cat.category_name, cat.total) for cat in summary.category_breakdown]
            chart_buf = generate_pie_chart(chart_data, f"Chi tiêu tháng {now.month}/{now.year}")
            if chart_buf:
                 await update.message.reply_photo(photo=chart_buf)
        
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
        
        # Comparison Chart (This Month vs Last Month)
        chart_data = [
            ("Tháng trước", insights.total_last_month),
            ("Tháng này", insights.total_this_month)
        ]
        chart_buf = generate_bar_chart(chart_data, "So sánh chi tiêu", y_label="VNĐ")
        if chart_buf:
            await update.message.reply_photo(photo=chart_buf)
        
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


async def ghilai_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ghilai command - record transaction for a past date"""
    user = update.effective_user
    
    try:
        # Build keyboard with last 7 days
        keyboard = []
        today = datetime.now().date()
        
        # Weekday names in Vietnamese
        weekday_names = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
        
        for i in range(7):
            target_date = today - timedelta(days=i)
            weekday = weekday_names[target_date.weekday()]
            
            if i == 0:
                label = f"📅 Hôm nay ({target_date.strftime('%d/%m')})"
            elif i == 1:
                label = f"📅 Hôm qua ({target_date.strftime('%d/%m')})"
            else:
                label = f"📅 {weekday} ({target_date.strftime('%d/%m')})"
            
            callback_data = f"addpast:{target_date.strftime('%Y-%m-%d')}"
            keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
        
        # Add "Enter specific date" and cancel buttons
        keyboard.append([InlineKeyboardButton("📆 Nhập ngày khác...", callback_data="addpast:custom")])
        keyboard.append([InlineKeyboardButton("❌ Hủy", callback_data="addpast:cancel")])
        
        await update.message.reply_text(
            "📝 *Ghi lại giao dịch*\n\n"
            "Chọn ngày muốn ghi giao dịch:\n"
            "_Sau khi chọn, gõ giao dịch như bình thường_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
            
    except Exception as e:
        logger.error(f"Error in ghilai_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def handle_addpast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle day selection callback for adding transaction to past date"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith("addpast:"):
        return
    
    date_str = data[8:]  # Remove "addpast:" prefix
    
    if date_str == "cancel":
        context.user_data.pop('addpast_date', None)
        await query.edit_message_text("❌ Đã hủy.")
        return
    
    if date_str == "custom":
        # Ask user to enter a specific date
        context.user_data['addpast_input_mode'] = True
        keyboard = [[InlineKeyboardButton("❌ Hủy", callback_data="addpast:cancel")]]
        await query.edit_message_text(
            "📆 *Nhập ngày cần ghi giao dịch:*\n\n"
            "Gõ theo format: `dd/mm/yyyy`\n"
            "Ví dụ: `27/12/2025`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    try:
        # Parse date and save to user_data
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        context.user_data['addpast_date'] = target_date
        
        keyboard = [[InlineKeyboardButton("❌ Thoát chế độ ghi lại", callback_data="addpast:cancel")]]
        
        await query.edit_message_text(
            f"✅ *Đang ghi cho ngày {target_date.strftime('%d/%m/%Y')}*\n\n"
            f"Bây giờ hãy gõ giao dịch như bình thường:\n"
            f"• `cafe 50k` → 50,000₫\n"
            f"• `grab 35k` → 35,000₫\n\n"
            f"_Tất cả giao dịch sẽ được ghi vào ngày {target_date.strftime('%d/%m/%Y')}_\n"
            f"_Gõ /ghilai để chọn ngày khác hoặc bấm nút bên dưới để thoát_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error in addpast callback: {e}")
        await query.edit_message_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /edit command - show last 7 days to select for editing transactions"""
    user = update.effective_user
    
    try:
        # Build keyboard with last 7 days
        keyboard = []
        today = datetime.now().date()
        
        # Weekday names in Vietnamese
        weekday_names = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
        
        for i in range(7):
            target_date = today - timedelta(days=i)
            weekday = weekday_names[target_date.weekday()]
            
            # Format: "T2 30/12" or "Hôm nay 03/01"
            if i == 0:
                label = f"📅 Hôm nay ({target_date.strftime('%d/%m')})"
            elif i == 1:
                label = f"📅 Hôm qua ({target_date.strftime('%d/%m')})"
            else:
                label = f"📅 {weekday} ({target_date.strftime('%d/%m')})"
            
            callback_data = f"eday:{target_date.strftime('%Y-%m-%d')}"
            keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
        
        # Add "Enter specific date" and cancel buttons
        keyboard.append([InlineKeyboardButton("📆 Nhập ngày khác...", callback_data="eday:custom")])
        keyboard.append([InlineKeyboardButton("❌ Hủy", callback_data="eday:cancel")])
        
        await update.message.reply_text(
            "📝 *Sửa giao dịch*\n\n"
            "Chọn ngày muốn xem giao dịch:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
            
    except Exception as e:
        logger.error(f"Error in edit_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /budget command - set or view budgets"""
    user = update.effective_user
    args = context.args
    
    try:
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            
            # Case 1: View budgets (no args)
            if not args:
                budgets = await get_user_budgets(session, db_user.id)
                status = await check_budget_status(session, db_user.id)
                
                if not budgets:
                    await update.message.reply_text(
                        "📭 Bạn chưa thiết lập ngân sách.\n\n"
                        "Gõ: `/budget set 10tr` để đặt ngân sách tổng.\n"
                        "Gõ: `/budget set 2tr ăn uống` để đặt ngân sách danh mục.",
                        parse_mode="Markdown"
                    )
                    return
                
                lines = ["📊 *Tình hình ngân sách tháng này*"]
                
                # Total budget status
                if status:
                     icon = "🟢" if not status.is_exceeded else "🔴"
                     lines.append(f"\n{icon} *Tổng chi:* {format_currency_full(status.spent)} / {format_currency_full(status.budget.amount)}")
                     lines.append(f"   (Đã dùng: {status.percentage:.0f}%)")
                
                lines.append("\n*Chi tiết:*")
                for b in budgets:
                    if b.category_id is None: continue # Skip total (shown above)
                    
                    cat_status = await check_budget_status(session, db_user.id, category_id=b.category_id)
                    icon = "✅" if not cat_status.is_exceeded else "⚠️"
                    lines.append(f"{icon} {cat_status.category_name}: {format_currency_full(cat_status.spent)} / {format_currency_full(b.amount)} ({cat_status.percentage:.0f}%)")
                    
                await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
                return
            
            # Case 2: Set budget
            if args[0].lower() == "set":
                # /budget set 500k [category]
                if len(args) < 2:
                    await update.message.reply_text("❌ Thiếu số tiền. VD: `/budget set 5tr`")
                    return
                    
                # Parse amount using parse_message service logic (simplified)
                amount_str = args[1]
                # Reuse parse_message logic or simple parsing
                # Since parse_message expects "50k cafe", we can use it
                parse_res = parse_message(f"{amount_str} budget")
                if not parse_res.is_valid:
                     await update.message.reply_text("❌ Số tiền không hợp lệ.")
                     return
                
                amount = parse_res.amount
                
                # Category?
                category_id = None
                cat_name = "Tổng"
                
                if len(args) > 2:
                    note = " ".join(args[2:])
                    # Find category
                    category = await detect_category(session, note) # Reuse detect logic
                    if not category:
                         # Try finding by name explicitly
                         category = await get_category_by_name(session, note)
                    
                    if category:
                        category_id = category.id
                        cat_name = category.name
                    else:
                        await update.message.reply_text(f"❌ Không tìm thấy danh mục '{note}'")
                        return
                
                await set_budget(session, db_user.id, amount, category_id)
                await update.message.reply_text(
                    f"✅ Đã đặt ngân sách *{cat_name}*: {format_currency_full(amount)}/tháng",
                    parse_mode="Markdown"
                )
                        
    except Exception as e:
        logger.error(f"Error in budget_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra.")


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


async def handle_edit_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle day selection callback for edit - show transactions for selected day"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith("eday:"):
        return
    
    date_str = data[5:]  # Remove "eday:" prefix
    
    if date_str == "cancel":
        await query.edit_message_text("❌ Đã hủy thao tác sửa.")
        return
    
    if date_str == "custom":
        # Ask user to enter a specific date
        context.user_data['edit_date_mode'] = True
        keyboard = [[InlineKeyboardButton("❌ Hủy", callback_data="eday:cancel")]]
        await query.edit_message_text(
            "📆 *Nhập ngày cần xem giao dịch:*\n\n"
            "Gõ theo format: `dd/mm/yyyy`\n"
            "Ví dụ: `27/12/2025`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    try:
        # Parse date
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        user = query.from_user
        
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            transactions = await get_transactions_by_date(session, db_user.id, target_date)
        
        if not transactions:
            await query.edit_message_text(
                f"📭 Ngày {target_date.strftime('%d/%m/%Y')} không có giao dịch nào.",
                parse_mode="Markdown"
            )
            return
        
        # Build transaction list with numbered buttons
        lines = [f"📅 *Giao dịch ngày {target_date.strftime('%d/%m/%Y')}*\n"]
        keyboard = []
        
        for i, tx in enumerate(transactions, 1):
            tx_type = "💰" if (tx.category and tx.category.type.value == "INCOME") else "💸"
            cat_name = tx.category.name if tx.category else "Khác"
            note = tx.note or "Không có ghi chú"
            time_str = tx.date.strftime("%H:%M")
            
            lines.append(f"{i}. {tx_type} {format_currency(tx.amount)} - {note[:20]}{'...' if len(note) > 20 else ''}")
            lines.append(f"   ⏰ {time_str} | 🏷️ {cat_name}")
            
            # Add button for this transaction
            btn_label = f"{i}. {tx_type} {format_currency(tx.amount)}"
            callback_data = f"etx:{tx.id}"
            keyboard.append([InlineKeyboardButton(btn_label, callback_data=callback_data)])
        
        # Add back and cancel buttons
        keyboard.append([
            InlineKeyboardButton("« Chọn ngày khác", callback_data="etx:back"),
            InlineKeyboardButton("❌ Hủy", callback_data="etx:cancel")
        ])
        
        lines.append("\n_Chọn giao dịch cần sửa:_")
        
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error in edit_day_callback: {e}")
        await query.edit_message_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def handle_edit_tx_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle transaction selection callback for edit - show edit options"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith("etx:"):
        return
    
    action = data[4:]  # Remove "etx:" prefix
    
    if action == "cancel":
        await query.edit_message_text("❌ Đã hủy thao tác sửa.")
        return
    
    if action == "back":
        # Go back to day selection - recreate the day selection keyboard
        keyboard = []
        today = datetime.now().date()
        weekday_names = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
        
        for i in range(7):
            target_date = today - timedelta(days=i)
            weekday = weekday_names[target_date.weekday()]
            
            if i == 0:
                label = f"📅 Hôm nay ({target_date.strftime('%d/%m')})"
            elif i == 1:
                label = f"📅 Hôm qua ({target_date.strftime('%d/%m')})"
            else:
                label = f"📅 {weekday} ({target_date.strftime('%d/%m')})"
            
            callback_data = f"eday:{target_date.strftime('%Y-%m-%d')}"
            keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
        
        keyboard.append([InlineKeyboardButton("❌ Hủy", callback_data="eday:cancel")])
        
        await query.edit_message_text(
            "📝 *Sửa giao dịch*\n\nChọn ngày muốn xem giao dịch:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    try:
        tx_id = int(action)
        user = query.from_user
        
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            tx = await get_transaction_by_id(session, tx_id, db_user.id)
            
            if tx is None:
                await query.edit_message_text("❌ Không tìm thấy giao dịch này.")
                return
            
            # Store tx_id in user_data for later use
            context.user_data['edit_tx_id'] = tx_id
            
            tx_type = "Thu" if (tx.category and tx.category.type.value == "INCOME") else "Chi"
            cat_name = tx.category.name if tx.category else "Khác"
            
            # Build edit options keyboard
            keyboard = [
                [InlineKeyboardButton("💰 Sửa số tiền", callback_data=f"eopt:{tx_id}:amount")],
                [InlineKeyboardButton("📝 Sửa ghi chú", callback_data=f"eopt:{tx_id}:note")],
                [InlineKeyboardButton("🏷️ Sửa danh mục", callback_data=f"eopt:{tx_id}:category")],
                [InlineKeyboardButton(f"🔄 Đổi thành {'Chi' if tx_type == 'Thu' else 'Thu'}", callback_data=f"eopt:{tx_id}:type")],
                [
                    InlineKeyboardButton("« Quay lại", callback_data=f"eday:{tx.date.strftime('%Y-%m-%d')}"),
                    InlineKeyboardButton("❌ Hủy", callback_data="eopt:0:cancel")
                ]
            ]
            
            response = (
                f"📝 *Sửa giao dịch:*\n\n"
                f"💰 Số tiền: *{format_currency_full(tx.amount)}*\n"
                f"📝 Ghi chú: {tx.note or 'Không có'}\n"
                f"🏷️ Danh mục: {cat_name}\n"
                f"📊 Loại: {tx_type}\n"
                f"⏰ Thời gian: {tx.date.strftime('%H:%M %d/%m/%Y')}\n\n"
                f"_Chọn thuộc tính cần sửa:_"
            )
            
            await query.edit_message_text(
                response,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        logger.error(f"Error in edit_tx_callback: {e}")
        await query.edit_message_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def handle_edit_option_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle edit option selection callback"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith("eopt:"):
        return
    
    parts = data[5:].split(":")
    if len(parts) < 2:
        return
    
    tx_id_str, option = parts[0], parts[1]
    
    if option == "cancel":
        await query.edit_message_text("❌ Đã hủy thao tác sửa.")
        return
    
    try:
        tx_id = int(tx_id_str)
        user = query.from_user
        
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            tx = await get_transaction_by_id(session, tx_id, db_user.id)
            
            if tx is None:
                await query.edit_message_text("❌ Không tìm thấy giao dịch này.")
                return
            
            if option == "type":
                # Toggle transaction type immediately
                is_income = tx.category and tx.category.type.value == "INCOME"
                updated_tx = await update_transaction(
                    session, tx_id, db_user.id, is_income=not is_income
                )
                
                if updated_tx:
                    new_type = "Thu" if not is_income else "Chi"
                    await query.edit_message_text(
                        f"✅ Đã đổi giao dịch thành: *{new_type}*\n"
                        f"💰 {format_currency_full(updated_tx.amount)} - {updated_tx.note or 'Không có ghi chú'}",
                        parse_mode="Markdown"
                    )
                return
            
            if option == "category":
                # Show category selection keyboard
                all_categories = await get_all_categories(session)
                keyboard = []
                row = []
                excluded_categories = {"Nhà cửa"}
                
                for cat in all_categories:
                    if cat.name in excluded_categories:
                        continue
                    callback_data = f"ecat:{tx_id}:{cat.id}"
                    row.append(InlineKeyboardButton(cat.name, callback_data=callback_data))
                    
                    if len(row) == 3:
                        keyboard.append(row)
                        row = []
                
                if row:
                    keyboard.append(row)
                
                keyboard.append([
                    InlineKeyboardButton("« Quay lại", callback_data=f"etx:{tx_id}"),
                    InlineKeyboardButton("❌ Hủy", callback_data="ecat:0:cancel")
                ])
                
                await query.edit_message_text(
                    f"🏷️ *Chọn danh mục mới:*\n\n"
                    f"💰 {format_currency_full(tx.amount)} - {tx.note or 'Không có ghi chú'}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return
            
            if option in ("amount", "note"):
                # Store edit context for text input
                context.user_data['edit_mode'] = {
                    'tx_id': tx_id,
                    'field': option,
                    'original_value': tx.amount if option == "amount" else tx.note
                }
                
                field_name = "số tiền" if option == "amount" else "ghi chú"
                current_value = format_currency_full(tx.amount) if option == "amount" else (tx.note or "Không có")
                example = "50k hoặc 2tr" if option == "amount" else "cafe sáng"
                
                keyboard = [[InlineKeyboardButton("❌ Hủy", callback_data="einput:cancel")]]
                
                await query.edit_message_text(
                    f"📝 *Sửa {field_name}*\n\n"
                    f"Giá trị hiện tại: *{current_value}*\n\n"
                    f"Nhập giá trị mới (ví dụ: _{example}_):",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return
                
    except Exception as e:
        logger.error(f"Error in edit_option_callback: {e}")
        await query.edit_message_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def handle_edit_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle category selection for edit"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith("ecat:"):
        return
    
    parts = data[5:].split(":")
    if len(parts) < 2:
        return
    
    tx_id_str, cat_id_str = parts[0], parts[1]
    
    if cat_id_str == "cancel":
        await query.edit_message_text("❌ Đã hủy thao tác sửa.")
        return
    
    try:
        tx_id = int(tx_id_str)
        cat_id = int(cat_id_str)
        user = query.from_user
        
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            
            # Update category
            updated_tx = await update_transaction(session, tx_id, db_user.id, category_id=cat_id)
            
            if updated_tx:
                # Re-learn keyword if note exists
                if updated_tx.note:
                    await learn_keyword_for_user(session, db_user.id, cat_id, updated_tx.note)
                
                # Get category name
                from sqlalchemy import select
                result = await session.execute(select(Category).where(Category.id == cat_id))
                category = result.scalar_one_or_none()
                cat_name = category.name if category else "Khác"
                
                await query.edit_message_text(
                    f"✅ Đã sửa danh mục thành: *{cat_name}*\n"
                    f"💰 {format_currency_full(updated_tx.amount)} - {updated_tx.note or 'Không có ghi chú'}\n"
                    f"🧠 Bot đã học từ khóa mới!",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text("❌ Không tìm thấy giao dịch này.")
                
    except Exception as e:
        logger.error(f"Error in edit_category_callback: {e}")
        await query.edit_message_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def handle_edit_input_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle cancel for edit input mode"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "einput:cancel":
        # Clear edit mode
        context.user_data.pop('edit_mode', None)
        await query.edit_message_text("❌ Đã hủy thao tác sửa.")


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
        # Check if user is in edit date mode (entering a specific date)
        edit_date_mode = context.user_data.get('edit_date_mode')
        if edit_date_mode:
            context.user_data.pop('edit_date_mode', None)
            
            # Try to parse the date
            try:
                # Support formats: dd/mm/yyyy, dd/mm, dd-mm-yyyy, dd-mm
                text_clean = text.replace("-", "/")
                parts = text_clean.split("/")
                
                if len(parts) >= 2:
                    day = int(parts[0])
                    month = int(parts[1])
                    year = int(parts[2]) if len(parts) >= 3 else datetime.now().year
                    
                    target_date = date(year, month, day)
                    
                    async with await get_session() as session:
                        db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
                        transactions = await get_transactions_by_date(session, db_user.id, target_date)
                    
                    if not transactions:
                        await update.message.reply_text(
                            f"📭 Ngày {target_date.strftime('%d/%m/%Y')} không có giao dịch nào."
                        )
                        return
                    
                    # Build transaction list with numbered buttons
                    lines = [f"📅 *Giao dịch ngày {target_date.strftime('%d/%m/%Y')}*\n"]
                    keyboard = []
                    
                    for i, tx in enumerate(transactions, 1):
                        tx_type = "💰" if (tx.category and tx.category.type.value == "INCOME") else "💸"
                        cat_name = tx.category.name if tx.category else "Khác"
                        note = tx.note or "Không có ghi chú"
                        time_str = tx.date.strftime("%H:%M")
                        
                        lines.append(f"{i}. {tx_type} {format_currency(tx.amount)} - {note[:20]}{'...' if len(note) > 20 else ''}")
                        lines.append(f"   ⏰ {time_str} | 🏷️ {cat_name}")
                        
                        btn_label = f"{i}. {tx_type} {format_currency(tx.amount)}"
                        callback_data = f"etx:{tx.id}"
                        keyboard.append([InlineKeyboardButton(btn_label, callback_data=callback_data)])
                    
                    keyboard.append([
                        InlineKeyboardButton("« Chọn ngày khác", callback_data="etx:back"),
                        InlineKeyboardButton("❌ Hủy", callback_data="etx:cancel")
                    ])
                    
                    lines.append("\n_Chọn giao dịch cần sửa:_")
                    
                    await update.message.reply_text(
                        "\n".join(lines),
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return
                else:
                    await update.message.reply_text(
                        "❌ Định dạng ngày không đúng. Vui lòng nhập theo format: `dd/mm/yyyy`\n"
                        "Ví dụ: `27/12/2025`",
                        parse_mode="Markdown"
                    )
                    return
                    
            except ValueError as e:
                await update.message.reply_text(
                    f"❌ Ngày không hợp lệ. Vui lòng nhập theo format: `dd/mm/yyyy`\n"
                    f"Ví dụ: `27/12/2025`",
                    parse_mode="Markdown"
                )
                return
        
        # Check if user is in addpast input mode (entering a specific date for ghilai)
        addpast_input_mode = context.user_data.get('addpast_input_mode')
        if addpast_input_mode:
            context.user_data.pop('addpast_input_mode', None)
            
            try:
                text_clean = text.replace("-", "/")
                parts = text_clean.split("/")
                
                if len(parts) >= 2:
                    day = int(parts[0])
                    month = int(parts[1])
                    year = int(parts[2]) if len(parts) >= 3 else datetime.now().year
                    
                    target_date = date(year, month, day)
                    context.user_data['addpast_date'] = target_date
                    
                    keyboard = [[InlineKeyboardButton("❌ Thoát chế độ ghi lại", callback_data="addpast:cancel")]]
                    
                    await update.message.reply_text(
                        f"✅ *Đang ghi cho ngày {target_date.strftime('%d/%m/%Y')}*\n\n"
                        f"Bây giờ hãy gõ giao dịch như bình thường:\n"
                        f"• `cafe 50k` → 50,000₫\n"
                        f"• `grab 35k` → 35,000₫\n\n"
                        f"_Tất cả giao dịch sẽ được ghi vào ngày {target_date.strftime('%d/%m/%Y')}_",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return
                else:
                    await update.message.reply_text(
                        "❌ Định dạng ngày không đúng. Vui lòng nhập theo format: `dd/mm/yyyy`",
                        parse_mode="Markdown"
                    )
                    return
                    
            except ValueError:
                await update.message.reply_text(
                    "❌ Ngày không hợp lệ. Vui lòng nhập theo format: `dd/mm/yyyy`",
                    parse_mode="Markdown"
                )
                return
        
        # Check if user is in addpast mode (recording transactions for a past date)
        addpast_date = context.user_data.get('addpast_date')
        if addpast_date:
            # Parse the transaction and add with the custom date
            parsed = parse_message(text)
            if parsed.is_valid and parsed.amount > 0:
                async with await get_session() as session:
                    db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
                    
                    # Detect category
                    category = await find_category_from_user_history(session, db_user.id, parsed.note)
                    if category is None:
                        category = await detect_category(session, parsed.note)
                    
                    cat_id = category.id if category else None
                    cat_name = category.name if category else "Khác"
                    
                    # Create datetime with the past date but current time
                    now = datetime.now()
                    tx_datetime = datetime(addpast_date.year, addpast_date.month, addpast_date.day, 
                                          now.hour, now.minute, now.second)
                    
                    # Add transaction with past date
                    tx = await add_transaction(
                        session,
                        user_id=db_user.id,
                        amount=parsed.amount,
                        note=parsed.note,
                        raw_text=parsed.raw_text,
                        category_id=cat_id,
                        transaction_date=tx_datetime
                    )
                    
                    # Learn keyword
                    if cat_id and parsed.note:
                        await learn_keyword_for_user(session, db_user.id, cat_id, parsed.note)
                
                keyboard = [[InlineKeyboardButton("❌ Thoát chế độ ghi lại", callback_data="addpast:cancel")]]
                
                await update.message.reply_text(
                    f"✅ Đã ghi vào ngày *{addpast_date.strftime('%d/%m/%Y')}*:\n"
                    f"💰 *{format_currency_full(parsed.amount)}*\n"
                    f"📝 {parsed.note or 'Không có ghi chú'}\n"
                    f"🏷️ {cat_name}\n\n"
                    f"_Tiếp tục gõ giao dịch khác hoặc bấm nút để thoát_",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return
            # If not a valid transaction, fall through to normal handling
        
        # Check if user is in edit mode (editing amount or note)
        edit_mode = context.user_data.get('edit_mode')
        if edit_mode:
            tx_id = edit_mode['tx_id']
            field = edit_mode['field']
            
            async with await get_session() as session:
                db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
                
                if field == "amount":
                    # Parse amount
                    parsed = parse_message(f"{text} edit")
                    if not parsed.is_valid:
                        await update.message.reply_text(
                            f"❌ Số tiền không hợp lệ. Thử lại với format: _50k_ hoặc _2tr_",
                            parse_mode="Markdown"
                        )
                        return
                    
                    updated_tx = await update_transaction(
                        session, tx_id, db_user.id, amount=parsed.amount
                    )
                    
                    if updated_tx:
                        await update.message.reply_text(
                            f"✅ Đã sửa số tiền thành: *{format_currency_full(parsed.amount)}*\n"
                            f"📝 {updated_tx.note or 'Không có ghi chú'}",
                            parse_mode="Markdown"
                        )
                    else:
                        await update.message.reply_text("❌ Không tìm thấy giao dịch này.")
                    
                elif field == "note":
                    updated_tx = await update_transaction(
                        session, tx_id, db_user.id, note=text
                    )
                    
                    if updated_tx:
                        await update.message.reply_text(
                            f"✅ Đã sửa ghi chú thành: *{text}*\n"
                            f"💰 {format_currency_full(updated_tx.amount)}",
                            parse_mode="Markdown"
                        )
                    else:
                        await update.message.reply_text("❌ Không tìm thấy giao dịch này.")
            
            # Clear edit mode
            context.user_data.pop('edit_mode', None)
            return
        
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
            
            # Check total budget
            budget_status = await check_budget_status(session, db_user.id)
            if budget_status and budget_status.is_exceeded:
                response += f"\n\n⚠️ *CẢNH BÁO:* Bạn đã vượt ngân sách tháng ({format_currency_full(budget_status.budget.amount)})!"
                
            await update.message.reply_text(
                response,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            return
        
        # Send regular response with Markdown formatting
        response_text = result.response
        
        # Check budget alert if this was a transaction
        if result.transaction_result and result.transaction_result.success:
            # Check category budget
            cat_id = result.transaction_result.category_id
            if cat_id:
                cat_status = await check_budget_status(session, db_user.id, category_id=cat_id)
                if cat_status and cat_status.is_exceeded:
                    response_text += f"\n\n⚠️ *CẢNH BÁO:* Vượt ngân sách {cat_status.category_name} ({cat_status.percentage:.0f}%)"
            
            # Check total budget
            status = await check_budget_status(session, db_user.id)
            if status and status.is_exceeded:
                response_text += f"\n\n⚠️ *CẢNH BÁO:* Vượt tổng ngân sách tháng ({status.percentage:.0f}%)"
                
        await update.message.reply_text(response_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error handling text message: {e}")
        await update.message.reply_text(
            "❌ Có lỗi xảy ra. Vui lòng thử lại."
        )


async def export_excel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /export_excel command - export transactions to Excel"""
    user = update.effective_user
    
    try:
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            transactions = await get_all_transactions(session, db_user.id)
        
        if not transactions:
            await update.message.reply_text("📭 Chưa có giao dịch nào để xuất.")
            return
            
        # Create Excel file
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Chi tiêu"
        
        # Headers
        headers = ["Ngày", "Giờ", "Số tiền", "Danh mục", "Ghi chú", "Loại", "Nội dung gốc"]
        ws.append(headers)
        
        # Style headers
        from openpyxl.styles import Font
        for cell in ws[1]:
            cell.font = Font(bold=True)
            
        # Data
        for tx in transactions:
            cat_name = tx.category.name if tx.category else "Khác"
            tx_type = "Thu" if (tx.category and tx.category.type.value == "INCOME") else "Chi"
            
            ws.append([
                tx.date.strftime("%Y-%m-%d"),
                tx.date.strftime("%H:%M"),
                tx.amount,
                cat_name,
                tx.note or "",
                tx_type,
                tx.raw_text or ""
            ])
            
        # Save to buffer
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        output.name = f"chi_tieu_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        await update.message.reply_document(
            document=output,
            caption=f"📄 File Excel chi tiêu ({len(transactions)} giao dịch)"
        )
        
    except Exception as e:
        logger.error(f"Error in export_excel_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra khi xuất Excel.")


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
            BotCommand("edit", "✏️ Sửa giao dịch"),
            BotCommand("delete", "🗑️ Xóa giao dịch gần nhất"),
            BotCommand("link", "🔗 Liên kết với Zalo"),
            BotCommand("budget", "💰 Quản lý ngân sách"),
            BotCommand("export", "📄 Xuất file CSV"),
            BotCommand("excel", "📊 Xuất file Excel"),
            BotCommand("ghilai", "📅 Ghi lại giao dịch"),
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
    application.add_handler(CommandHandler("excel", export_excel_command))
    application.add_handler(CommandHandler("budget", budget_command))
    application.add_handler(CommandHandler("edit", edit_command))
    application.add_handler(CommandHandler("delete", delete_command))
    application.add_handler(CommandHandler("insights", insights_command))
    application.add_handler(CommandHandler("link", link_command))
    application.add_handler(CommandHandler("ghilai", ghilai_command))
    
    # Handle category selection callbacks
    application.add_handler(CallbackQueryHandler(handle_category_callback, pattern="^cat:"))
    application.add_handler(CallbackQueryHandler(handle_edit_callback, pattern="^edit:"))
    application.add_handler(CallbackQueryHandler(handle_voice_callback, pattern="^voice:"))
    application.add_handler(CallbackQueryHandler(handle_voice_category_callback, pattern="^vcat:"))
    
    # Handle new edit flow callbacks
    application.add_handler(CallbackQueryHandler(handle_edit_day_callback, pattern="^eday:"))
    application.add_handler(CallbackQueryHandler(handle_edit_tx_callback, pattern="^etx:"))
    application.add_handler(CallbackQueryHandler(handle_edit_option_callback, pattern="^eopt:"))
    application.add_handler(CallbackQueryHandler(handle_edit_category_callback, pattern="^ecat:"))
    application.add_handler(CallbackQueryHandler(handle_edit_input_callback, pattern="^einput:"))
    
    # Handle addpast (ghilai) callbacks
    application.add_handler(CallbackQueryHandler(handle_addpast_callback, pattern="^addpast:"))
    
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
