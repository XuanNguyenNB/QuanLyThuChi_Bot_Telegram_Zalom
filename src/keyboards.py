"""
Keyboard builders - các hàm tạo inline keyboards
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


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


def build_days_keyboard(days_data: list, callback_prefix: str = "eday") -> InlineKeyboardMarkup:
    """
    Build keyboard with day buttons
    
    Args:
        days_data: List of (label, date_str) tuples
        callback_prefix: Prefix for callback data (eday, addpast, etc.)
    """
    keyboard = []
    for label, date_str in days_data:
        callback_data = f"{callback_prefix}:{date_str}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
    
    # Add custom date and cancel buttons
    keyboard.append([InlineKeyboardButton("📆 Nhập ngày khác...", callback_data=f"{callback_prefix}:custom")])
    keyboard.append([InlineKeyboardButton("❌ Hủy", callback_data=f"{callback_prefix}:cancel")])
    
    return InlineKeyboardMarkup(keyboard)
