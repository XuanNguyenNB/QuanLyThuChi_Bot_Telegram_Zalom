"""
Handler xử lý tin nhắn text - bao gồm Q&A và ghi giao dịch
"""

import logging
from datetime import datetime, date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ..database import get_session
from ..services import (
    get_or_create_user,
    get_transactions_by_date,
    parse_message,
    find_category_from_user_history,
    detect_category,
    add_transaction,
    learn_keyword_for_user,
    update_transaction,
    check_budget_status,
)
from ..utils import format_currency, format_currency_full, get_vietnam_now, get_vietnam_today
from ..message_handler import process_text_message
from ..keyboards import build_category_keyboard

logger = logging.getLogger(__name__)


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
                    year = int(parts[2]) if len(parts) >= 3 else get_vietnam_today().year
                    
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
                    year = int(parts[2]) if len(parts) >= 3 else get_vietnam_today().year
                    
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
                    now = get_vietnam_now()
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
            async with await get_session() as session:
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
            async with await get_session() as session:
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
