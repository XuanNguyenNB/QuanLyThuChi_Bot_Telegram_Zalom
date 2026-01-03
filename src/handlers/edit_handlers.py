"""
Handlers cho lệnh /edit - sửa giao dịch
"""

import logging
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select

from ..models import get_session
from ..models import Category
from ..services import (
    get_or_create_user,
    get_transactions_by_date,
    get_transaction_by_id,
    get_all_categories,
    update_transaction,
    update_transaction_category,
    learn_keyword_for_user,
    get_today_summary,
)
from ..utils import format_currency, format_currency_full, get_vietnam_today

logger = logging.getLogger(__name__)


def build_7_days_keyboard(callback_prefix: str = "eday") -> list:
    """Build keyboard with last 7 days"""
    keyboard = []
    today = get_vietnam_today()
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
        
        callback_data = f"{callback_prefix}:{target_date.strftime('%Y-%m-%d')}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
    
    # Add custom date and cancel buttons
    keyboard.append([InlineKeyboardButton("📆 Nhập ngày khác...", callback_data=f"{callback_prefix}:custom")])
    keyboard.append([InlineKeyboardButton("❌ Hủy", callback_data=f"{callback_prefix}:cancel")])
    
    return keyboard


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /edit command - show last 7 days to select for editing transactions"""
    try:
        keyboard = build_7_days_keyboard("eday")
        
        await update.message.reply_text(
            "📝 *Sửa giao dịch*\n\n"
            "Chọn ngày muốn xem giao dịch:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
            
    except Exception as e:
        logger.error(f"Error in edit_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def handle_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle edit category callback - update transaction and re-learn (legacy callback)"""
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
        keyboard = build_7_days_keyboard("eday")
        
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
