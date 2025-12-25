"""
Zalo Bot handlers using HTTP polling (similar to Telegram Bot API)
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

import httpx
from dotenv import load_dotenv

from .models import init_db, get_session, seed_default_categories, Category
from .services import (
    parse_message,
    detect_category,
    get_category_by_name,
    get_all_categories,
    get_or_create_zalo_user,
    add_transaction,
    get_today_summary,
    get_month_summary,
    get_last_transaction,
    delete_transaction,
    link_user_by_phone,
    smart_query_transactions,
    get_spending_insights
)
from .utils import format_currency, format_currency_full, format_date
from .ai_service import is_ai_enabled, transcribe_voice, parse_with_ai, generate_transaction_comment
from .message_handler import process_text_message

# Configure logging with file output for debugging
import sys
log_file = '/home/botuser/logs/zalo_bot.log' if sys.platform != 'win32' else 'logs/zalo_bot.log'
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()


class ZaloBot:
    """Zalo Bot client using HTTP API"""
    
    def __init__(self, token: str):
        self.token = token
        # Use correct base URL from documentation
        self.base_url = f"https://bot-api.zaloplatforms.com/bot{token}"
        self.client = httpx.AsyncClient(timeout=60.0)
        self.offset = 0
    
    async def _post(self, method: str, data: dict = None):
        """Make POST request to Zalo Bot API"""
        url = f"{self.base_url}/{method}"
        try:
            response = await self.client.post(url, json=data or {})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Zalo API POST {method} error: {e}")
            return None
    
    async def get_me(self):
        """Get bot info - uses POST per API docs"""
        return await self._post("getMe")
    
    async def get_updates(self, timeout: int = 30):
        """Get updates using long polling - uses POST per API docs"""
        payload = {
            "timeout": timeout
        }
        return await self._post("getUpdates", payload)
    
    async def send_message(self, chat_id: str, text: str):
        """Send text message"""
        payload = {
            "chat_id": chat_id,
            "text": text
        }
        return await self._post("sendMessage", payload)
    
    async def send_chat_action(self, chat_id: str, action: str = "typing"):
        """Send chat action (typing indicator)"""
        payload = {
            "chat_id": chat_id,
            "action": action
        }
        return await self._post("sendChatAction", payload)
    
    async def delete_webhook(self):
        """Delete webhook to enable getUpdates"""
        return await self._post("deleteWebhook")
    
    async def get_file(self, file_id: str):
        """Get file info by file_id"""
        payload = {"file_id": file_id}
        return await self._post("getFile", payload)
    
    async def download_file(self, file_url: str) -> bytes:
        """Download file from URL"""
        try:
            response = await self.client.get(file_url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Download file error: {e}")
            return None
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


async def handle_message(bot: ZaloBot, message: dict):
    """Process incoming Zalo message"""
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()
    from_user = message.get("from", {})
    user_id = from_user.get("id")
    user_name = from_user.get("first_name", "")
    
    # Check if message has no text (voice/media message)
    if not text and chat_id:
        
        # Zalo API limitation: voice messages only have metadata, no audio data
        # Notify user to use text instead
        await bot.send_message(
            chat_id,
            "🎤 Zalo Bot API chưa hỗ trợ xử lý tin nhắn thoại, nhãn dán, hình ảnh và video.\n\n"
            "Hãy chọn gửi dạng văn bản để mình xử lí nhé!"
        )
        return
    
    if not chat_id or not text:
        return
    
    logger.info(f"Zalo message from {user_id}: {text}")
    
    # Handle commands
    if text.startswith("/"):
        await handle_command(bot, chat_id, user_id, user_name, text)
        return
    
    # Handle regular message (transaction or question)
    await handle_text(bot, chat_id, user_id, user_name, text)


async def handle_command(bot: ZaloBot, chat_id: str, user_id: str, user_name: str, text: str):
    """Handle Zalo bot commands"""
    command = text.split()[0].lower()
    
    if command == "/start":
        response = (
            f"Chào {user_name}! 👋\n\n"
            "Tôi là bot ghi chép chi tiêu.\n"
            "Gõ nhanh để ghi:\n"
            "• cafe 50 → 50,000₫\n"
            "• grab 35k → 35,000₫\n"
            "• tiền nhà 2tr → 2,000,000₫\n\n"
            "📋 Các lệnh:\n"
            "/start - Bắt đầu sử dụng\n"
            "/today - Chi tiêu hôm nay\n"
            "/month - Chi tiêu tháng\n"
            "/phantich - Phân tích thông minh\n"
            "/delete - Xóa giao dịch gần nhất\n"
            "/link 0901234567 - Liên kết Telegram\n"
            "/help - Hướng dẫn chi tiết\n\n"
            "💡 Không cần gõ 'k', bot tự hiểu!"
        )
        await bot.send_message(chat_id, response)
        return
    
    if command == "/help":
        response = (
            "📖 HƯỚNG DẪN SỬ DỤNG\n"
            "━━━━━━━━━━━━━━━\n\n"
            "💰 Ghi chi tiêu:\n"
            "cafe 50 → 50,000₫\n"
            "grab 35k → 35,000₫\n"
            "tiền nhà 2tr → 2,000,000₫\n\n"
            "📈 Ghi thu nhập:\n"
            "lương 15tr → Thu 15,000,000₫\n"
            "bán hàng 500 → Thu 500,000₫\n\n"
            "💬 Hỏi đáp thông minh:\n"
            "Tháng này chi bao nhiêu?\n"
            "Tuần này cafe hết bao nhiêu?\n\n"
            "📋 Các lệnh:\n"
            "/start - Bắt đầu sử dụng\n"
            "/today - Chi tiêu hôm nay\n"
            "/month - Chi tiêu tháng\n"
            "/phantich - Phân tích thông minh\n"
            "/delete - Xóa giao dịch gần nhất\n"
            "/link 0901234567 - Liên kết Telegram\n"
            "/help - Hướng dẫn chi tiết\n\n"
            "💡 Không cần gõ 'k', bot tự hiểu!"
        )
        await bot.send_message(chat_id, response)
        return
    
    if command == "/today":
        async with await get_session() as session:
            user = await get_or_create_zalo_user(session, user_id, user_name)
            summary = await get_today_summary(session, user.id)
        
        if summary.transaction_count == 0:
            await bot.send_message(chat_id, "📭 Hôm nay chưa có giao dịch nào.")
            return
        
        # Separate income and expense
        income_txs = [tx for tx in summary.transactions if tx.category and tx.category.type.value == "income"]
        expense_txs = [tx for tx in summary.transactions if not tx.category or tx.category.type.value != "income"]
        
        lines = [f"📅 Hôm nay ({format_date(datetime.now())})\n"]
        
        lines.append(f"💰 Thu: {format_currency_full(summary.total_income)}")
        if income_txs:
            for tx in income_txs[:3]:
                cat_name = tx.category.name if tx.category else "Khác"
                lines.append(f"  • {format_currency(tx.amount)} - {tx.note or 'N/A'}")
        
        lines.append("")
        lines.append(f"💸 Chi: {format_currency_full(summary.total_expense)}")
        if expense_txs:
            for tx in expense_txs[:5]:
                cat_name = tx.category.name if tx.category else "Khác"
                lines.append(f"  • {format_currency(tx.amount)} - {tx.note or 'N/A'}")
        
        balance = summary.total_income - summary.total_expense
        lines.append("")
        if balance >= 0:
            lines.append(f"📈 Thặng dư: +{format_currency_full(balance)}")
        else:
            lines.append(f"📉 Thâm hụt: {format_currency_full(balance)}")
        
        await bot.send_message(chat_id, "\n".join(lines))
        return
    
    if command == "/month":
        async with await get_session() as session:
            user = await get_or_create_zalo_user(session, user_id, user_name)
            summary = await get_month_summary(session, user.id)
        
        if summary.transaction_count == 0:
            await bot.send_message(chat_id, "📭 Tháng này chưa có giao dịch nào.")
            return
        
        now = datetime.now()
        lines = [f"📊 Tháng {now.month}/{now.year}\n"]
        lines.append(f"💰 Thu: {format_currency_full(summary.total_income)}")
        lines.append("")
        lines.append(f"💸 Chi: {format_currency_full(summary.total_expense)}")
        
        if summary.category_breakdown:
            lines.append("🏷️ Top danh mục:")
            for i, cat in enumerate(summary.category_breakdown[:5], 1):
                percent = (cat.total / summary.total_expense * 100) if summary.total_expense > 0 else 0
                lines.append(f"  {i}. {cat.category_name}: {format_currency_full(cat.total)} ({percent:.0f}%)")
        
        balance = summary.total_income - summary.total_expense
        lines.append("")
        if balance >= 0:
            lines.append(f"📈 Thặng dư: +{format_currency_full(balance)}")
        else:
            lines.append(f"📉 Thâm hụt: {format_currency_full(balance)}")
        
        await bot.send_message(chat_id, "\n".join(lines))
        return
    
    if command == "/delete":
        async with await get_session() as session:
            user = await get_or_create_zalo_user(session, user_id, user_name)
            last_tx = await get_last_transaction(session, user.id)
            
            if last_tx is None:
                await bot.send_message(chat_id, "❌ Không có giao dịch nào để xóa.")
                return
            
            amount = last_tx.amount
            note = last_tx.note or "Không có ghi chú"
            cat_name = last_tx.category.name if last_tx.category else "Khác"
            
            await delete_transaction(session, last_tx.id, user.id)
            summary = await get_today_summary(session, user.id)
        
        response = (
            f"🗑️ Đã xóa giao dịch:\n"
            f"💰 {format_currency_full(amount)}\n"
            f"📝 {note}\n"
            f"🏷️ {cat_name}\n"
            f"───────────────\n"
            f"💸 Tổng chi hôm nay: {format_currency_full(summary.total_expense)}"
        )
        await bot.send_message(chat_id, response)
        return
    
    if command == "/link":
        parts = text.split()
        if len(parts) < 2:
            await bot.send_message(chat_id, "❌ Vui lòng nhập số điện thoại.\nVí dụ: /link 0901234567")
            return
        
        phone = parts[1].strip()
        if not phone.isdigit() or len(phone) < 9:
            await bot.send_message(chat_id, "❌ Số điện thoại không hợp lệ.")
            return
        
        async with await get_session() as session:
            user = await link_user_by_phone(session, phone, zalo_id=user_id)
            
            if user and user.telegram_id:
                await bot.send_message(
                    chat_id,
                    f"✅ Đã liên kết với Telegram!\n"
                    f"📱 SĐT: {phone}\n"
                    f"Dữ liệu chi tiêu sẽ được đồng bộ."
                )
            else:
                # Create/update user with phone
                user = await get_or_create_zalo_user(session, user_id, user_name)
                user.phone = phone
                await session.commit()
                
                await bot.send_message(
                    chat_id,
                    f"📱 Đã lưu SĐT: {phone}\n"
                    f"Để đồng bộ với Telegram, gõ /link {phone} trên Telegram."
                )
        return
    
    if command == "/phantich" or command == "/insights":
        async with await get_session() as session:
            user = await get_or_create_zalo_user(session, user_id, user_name)
            insights = await get_spending_insights(session, user.id)
        
        # Trend emoji
        trend_emoji = "📈" if insights.trend == "up" else "📉" if insights.trend == "down" else "➡️"
        
        lines = [
            "💡 PHÂN TÍCH CHI TIÊU",
            "",
            f"📊 Tháng này: {format_currency_full(insights.total_this_month)}",
            f"📊 Tháng trước: {format_currency_full(insights.total_last_month)}",
            f"{trend_emoji} Xu hướng: {'Tăng' if insights.trend == 'up' else 'Giảm' if insights.trend == 'down' else 'Ổn định'}",
            f"📅 Trung bình/ngày: {format_currency_full(insights.daily_average)}",
            "",
        ]
        
        if insights.top_categories:
            lines.append("🏷️ Top 5 danh mục chi:")
            for i, cat in enumerate(insights.top_categories[:5], 1):
                percent = (cat.total / insights.total_this_month * 100) if insights.total_this_month > 0 else 0
                lines.append(f"  {i}. {cat.category_name}: {format_currency_full(cat.total)} ({percent:.0f}%)")
            lines.append("")
        
        if insights.biggest_expense:
            lines.append(f"💸 Chi lớn nhất: {format_currency_full(insights.biggest_expense.amount)}")
            lines.append(f"   📝 {insights.biggest_expense.note or 'Không có ghi chú'}")
            lines.append("")
        
        lines.append(f"💬 Gợi ý: {insights.suggestion}")
        
        await bot.send_message(chat_id, "\n".join(lines))
        return
    
    # Unknown command
    await bot.send_message(chat_id, "❓ Lệnh không hợp lệ. Gõ /help để xem hướng dẫn.")


async def handle_text(bot: ZaloBot, chat_id: str, user_id: str, user_name: str, text: str):
    """Handle regular text message (transaction or question)"""
    
    # Send typing indicator
    await bot.send_chat_action(chat_id, "typing")
    
    try:
        async with await get_session() as session:
            user = await get_or_create_zalo_user(session, user_id, user_name)
        
        # Use shared message handler
        result = await process_text_message(
            db_user_id=user.id,
            text=text,
            user_display_name=user_name
        )
        
        if result.response:
            await bot.send_message(chat_id, result.response)
    
    except Exception as e:
        logger.error(f"Error handling text: {e}")
        await bot.send_message(chat_id, "❌ Có lỗi xảy ra. Vui lòng thử lại.")


async def handle_voice(bot: ZaloBot, chat_id: str, user_id: str, user_name: str, message: dict):
    """Handle voice message - transcribe and process as transaction"""
    
    # Send typing indicator
    await bot.send_chat_action(chat_id, "typing")
    
    try:
        # Get voice/audio info from message
        voice = message.get("voice") or message.get("audio")
        if not voice:
            await bot.send_message(chat_id, "🎤 Không thể xử lý tin nhắn thoại.")
            return
        
        # Try to get file_id and download
        file_id = voice.get("file_id") if isinstance(voice, dict) else voice
        
        # Try to download the voice file
        voice_bytes = None
        
        # Method 1: If there's a file_url directly
        if isinstance(voice, dict) and voice.get("file_url"):
            voice_bytes = await bot.download_file(voice.get("file_url"))
        
        # Method 2: Try getFile API
        if not voice_bytes and file_id:
            file_info = await bot.get_file(file_id)
            if file_info and file_info.get("ok") and file_info.get("result"):
                file_url = file_info["result"].get("file_path") or file_info["result"].get("file_url")
                if file_url:
                    voice_bytes = await bot.download_file(file_url)
        
        if not voice_bytes:
            # Cannot download voice file - notify user
            await bot.send_message(
                chat_id,
                "🎤 Zalo chưa hỗ trợ xử lý tin nhắn thoại.\n"
                "Hãy gõ text như: `ăn bánh mì 25k`"
            )
            return
        
        # Transcribe voice
        text = await transcribe_voice(voice_bytes)
        
        if not text:
            await bot.send_message(
                chat_id,
                "🎤 Không nghe rõ. Hãy thử nói rõ hơn hoặc gõ text nhé!"
            )
            return
        
        logger.info(f"Voice transcribed: {text}")
        
        # Parse with AI
        ai_result = await parse_with_ai(text)
        
        if not ai_result.understood or not ai_result.transactions:
            await bot.send_message(
                chat_id,
                f"🎤 Nhận diện: {text}\n\n"
                f"🤔 Không hiểu nội dung. Hãy thử nói rõ như: ăn bánh mì hai mươi lăm nghìn"
            )
            return
        
        # Process transaction
        ai_tx = ai_result.transactions[0]
        
        async with await get_session() as session:
            user = await get_or_create_zalo_user(session, user_id, user_name)
            
            # Get category
            category = None
            if ai_tx.category:
                from .services import get_category_by_name, detect_category
                category = await get_category_by_name(session, ai_tx.category)
            if category is None and ai_tx.note:
                from .services import detect_category
                category = await detect_category(session, ai_tx.note)
            
            # Save transaction
            tx = await add_transaction(
                session,
                user_id=user.id,
                amount=ai_tx.amount,
                note=ai_tx.note,
                raw_text=text,
                category_id=category.id if category else None
            )
            
            cat_name = category.name if category else "Khác"
            summary = await get_today_summary(session, user.id)
            
            # Generate AI comment
            tx_type = ai_tx.type if hasattr(ai_tx, 'type') else "expense"
            ai_comment = await generate_transaction_comment(
                ai_tx.amount, ai_tx.note or "", cat_name, tx_type
            )
            
            response = (
                f"🎤 Nhận diện: {text}\n\n"
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
            
            await bot.send_message(chat_id, response)
    
    except Exception as e:
        logger.error(f"Error handling voice: {e}")
        await bot.send_message(
            chat_id,
            "🎤 Zalo chưa hỗ trợ xử lý tin nhắn thoại.\n"
            "Hãy gõ text như: `ăn bánh mì 25k`"
        )


async def run_polling(bot: ZaloBot):
    """Run bot using long polling"""
    logger.info("Zalo bot started polling...")
    
    while True:
        try:
            result = await bot.get_updates(timeout=30)
            
            # Debug: log what we received
            logger.info(f"API response type: {type(result).__name__}, content: {str(result)[:200]}")
            
            # Handle different response formats
            if result is None:
                await asyncio.sleep(1)
                continue
            
            # If result is a string, log and continue
            if isinstance(result, str):
                logger.info(f"Received string response: {result[:200]}")
                await asyncio.sleep(1)
                continue
            
            # Handle dict response
            if isinstance(result, dict):
                if result.get("ok") and result.get("result"):
                    data = result["result"]
                    
                    # Zalo API returns result.message directly (not a list)
                    if isinstance(data, dict) and "message" in data:
                        message = data["message"]
                        message_id = message.get("message_id", "")
                        
                        # Use message_id as offset to avoid duplicate processing
                        if message_id and message_id != bot.offset:
                            bot.offset = message_id
                            await handle_message(bot, message)
                    
                    # Also handle if it's a list (for compatibility)
                    elif isinstance(data, list):
                        for update in data:
                            if isinstance(update, dict):
                                update_id = update.get("update_id", 0)
                                bot.offset = update_id + 1
                                
                                if "message" in update:
                                    await handle_message(bot, update["message"])
            
            await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Polling error: {e}")
            await asyncio.sleep(5)


async def main():
    """Main entry point for Zalo bot"""
    token = os.getenv("ZALO_BOT_TOKEN")
    if not token:
        raise ValueError("ZALO_BOT_TOKEN not found in environment variables!")
    
    db_url = os.getenv("DB_URL", "sqlite+aiosqlite:///./finance_bot.db")
    
    # Initialize database
    await init_db(db_url)
    async with await get_session() as session:
        await seed_default_categories(session)
    
    # Create bot and verify
    bot = ZaloBot(token)
    
    # Delete webhook to enable getUpdates (per API docs)
    webhook_result = await bot.delete_webhook()
    if webhook_result and webhook_result.get("ok"):
        logger.info("Webhook deleted, using getUpdates mode")
    
    me = await bot.get_me()
    if me and me.get("ok"):
        bot_info = me.get('result', {})
        bot_name = bot_info.get('account_name', 'Unknown')
        logger.info(f"Zalo Bot connected: {bot_name}")
    else:
        logger.warning(f"Could not verify Zalo bot token: {me}")
    
    try:
        await run_polling(bot)
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
