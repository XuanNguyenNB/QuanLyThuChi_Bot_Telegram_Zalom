"""
Handlers cho lệnh /ghilai - ghi giao dịch cho ngày trong quá khứ
"""

import logging
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ..utils import get_vietnam_today

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


async def ghilai_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ghilai command - record transaction for a past date"""
    try:
        keyboard = build_7_days_keyboard("addpast")
        
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
