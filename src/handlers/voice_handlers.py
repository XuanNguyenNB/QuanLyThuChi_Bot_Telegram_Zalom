"""
Handlers cho voice messages - transcribe và xử lý tin nhắn thoại
"""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select

from ..models import get_session
from ..models import Category
from ..services import (
    get_or_create_user,
    get_all_categories,
    get_category_by_name,
    find_category_from_user_history,
    detect_category,
    add_transaction,
    learn_keyword_for_user,
    get_today_summary,
)
from ..utils import format_currency_full
from ..ai_service import is_ai_enabled, transcribe_voice, parse_with_ai

logger = logging.getLogger(__name__)


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
    
    try:
        async with await get_session() as session:
            # Get category name
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
