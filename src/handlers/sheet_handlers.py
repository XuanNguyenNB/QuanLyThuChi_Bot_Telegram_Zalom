"""
Handlers cho Google Sheets integration
"""

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from ..models import get_session
from ..services import get_or_create_user, get_all_transactions
from ..models import User, TransactionType
from ..sheets_service import (
    is_sheets_enabled,
    create_user_sheet,
    get_sheet_url,
    sync_all_transactions_to_sheet,
    pull_transactions_from_sheet,
)
from ..utils import get_vietnam_now

logger = logging.getLogger(__name__)


async def sheet_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sheet command - create or view Google Sheet link"""
    user = update.effective_user
    
    if not is_sheets_enabled():
        await update.message.reply_text(
            "❌ Google Sheets chưa được cấu hình trên server."
        )
        return
    
    try:
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            
            # Check if user already has a sheet
            if db_user.sheet_id:
                url = await get_sheet_url(db_user.sheet_id)
                await update.message.reply_text(
                    f"📊 *Google Sheet của bạn:*\n\n"
                    f"🔗 [Mở Sheet]({url})\n\n"
                    f"💡 Gõ `/sync` để đồng bộ dữ liệu",
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
                return
            
            # Create new sheet
            await update.message.reply_text("⏳ Đang tạo Google Sheet...")
            
            sheet_id = await create_user_sheet(user.full_name or user.username or f"User_{user.id}")
            
            if not sheet_id:
                await update.message.reply_text("❌ Không thể tạo Google Sheet. Vui lòng thử lại.")
                return
            
            # Save sheet_id to user
            db_user.sheet_id = sheet_id
            db_user.last_sync = get_vietnam_now()
            await session.commit()
            
            # Sync existing transactions
            transactions = await get_all_transactions(session, db_user.id)
            if transactions:
                tx_data = []
                for tx in transactions:
                    tx_data.append({
                        'id': tx.id,
                        'date': tx.date,
                        'amount': tx.amount,
                        'note': tx.note,
                        'category': tx.category.name if tx.category else "Khác",
                        'type': "Thu" if (tx.category and tx.category.type == TransactionType.INCOME) else "Chi"
                    })
                await sync_all_transactions_to_sheet(sheet_id, tx_data)
            
            url = await get_sheet_url(sheet_id)
            await update.message.reply_text(
                f"✅ *Đã tạo Google Sheet!*\n\n"
                f"🔗 [Mở Sheet]({url})\n\n"
                f"📝 Đã đồng bộ {len(transactions)} giao dịch\n"
                f"💡 Gõ `/sync` bất kỳ lúc nào để đồng bộ",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            
    except Exception as e:
        logger.error(f"Error in sheet_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sync command - sync data with Google Sheet"""
    user = update.effective_user
    
    if not is_sheets_enabled():
        await update.message.reply_text("❌ Google Sheets chưa được cấu hình.")
        return
    
    try:
        async with await get_session() as session:
            db_user = await get_or_create_user(session, user.id, user.username, user.full_name)
            
            if not db_user.sheet_id:
                await update.message.reply_text(
                    "❌ Bạn chưa có Google Sheet.\n"
                    "Gõ `/sheet` để tạo mới.",
                    parse_mode="Markdown"
                )
                return
            
            await update.message.reply_text("🔄 Đang đồng bộ...")
            
            # Get all transactions from DB
            transactions = await get_all_transactions(session, db_user.id)
            
            # Push to sheet
            tx_data = []
            for tx in transactions:
                tx_data.append({
                    'id': tx.id,
                    'date': tx.date,
                    'amount': tx.amount,
                    'note': tx.note,
                    'category': tx.category.name if tx.category else "Khác",
                    'type': "Thu" if (tx.category and tx.category.type == TransactionType.INCOME) else "Chi"
                })
            
            success = await sync_all_transactions_to_sheet(db_user.sheet_id, tx_data)
            
            if success:
                # Update last_sync
                db_user.last_sync = get_vietnam_now()
                await session.commit()
                
                url = await get_sheet_url(db_user.sheet_id)
                await update.message.reply_text(
                    f"✅ *Đồng bộ thành công!*\n\n"
                    f"📊 {len(transactions)} giao dịch đã được cập nhật\n"
                    f"🔗 [Mở Sheet]({url})",
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
            else:
                await update.message.reply_text("❌ Đồng bộ thất bại. Vui lòng thử lại.")
                
    except Exception as e:
        logger.error(f"Error in sync_command: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra. Vui lòng thử lại.")
