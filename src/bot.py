"""
Telegram Bot handlers using python-telegram-bot v20+
Refactored version - main entry point only
"""

import logging
import os
import sys

from dotenv import load_dotenv

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from .database import init_db, get_session
from .services import seed_default_categories

# Import all handlers from handlers package
from .handlers import (
    # Basic commands
    start_command,
    help_command,
    today_command,
    month_command,
    insights_command,
    export_command,
    export_excel_command,
    delete_command,
    link_command,
    # Edit handlers
    edit_command,
    handle_edit_callback,
    handle_edit_day_callback,
    handle_edit_tx_callback,
    handle_edit_option_callback,
    handle_edit_category_callback,
    handle_edit_input_callback,
    # Ghilai handlers
    ghilai_command,
    handle_addpast_callback,
    # Budget handlers
    budget_command,
    # Voice handlers
    handle_voice_message,
    handle_voice_callback,
    handle_voice_category_callback,
    # Callback handlers
    handle_category_callback,
    # Text handler
    handle_text_message,
    # Sheet handlers
    sheet_command,
    sync_command,
)


# Configure logging with file output for debugging
log_file = '/home/botuser/logs/telegram_bot.log' if sys.platform != 'win32' else 'logs/telegram_bot.log'
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


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
            BotCommand("ghilai", "📅 Ghi lại giao dịch"),
            BotCommand("sheet", "📊 Google Sheets"),
            BotCommand("sync", "🔄 Đồng bộ Sheets"),
            BotCommand("link", "🔗 Liên kết với Zalo"),
            BotCommand("budget", "💰 Quản lý ngân sách"),
            BotCommand("export", "📄 Xuất file CSV"),
            BotCommand("excel", "📊 Xuất file Excel"),
            BotCommand("help", "❓ Hướng dẫn"),
        ]
        await app.bot.set_my_commands(commands)
        logger.info("Database initialized and bot menu set")
        
        # Start sync scheduler in background
        from .sync_scheduler import start_sync_scheduler
        import asyncio
        asyncio.create_task(start_sync_scheduler())
    
    application.post_init = post_init
    
    # ========== ADD COMMAND HANDLERS ==========
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
    application.add_handler(CommandHandler("sheet", sheet_command))
    application.add_handler(CommandHandler("sync", sync_command))
    
    # ========== ADD CALLBACK HANDLERS ==========
    # Category selection callbacks
    application.add_handler(CallbackQueryHandler(handle_category_callback, pattern="^cat:"))
    application.add_handler(CallbackQueryHandler(handle_edit_callback, pattern="^edit:"))
    application.add_handler(CallbackQueryHandler(handle_voice_callback, pattern="^voice:"))
    application.add_handler(CallbackQueryHandler(handle_voice_category_callback, pattern="^vcat:"))
    
    # New edit flow callbacks
    application.add_handler(CallbackQueryHandler(handle_edit_day_callback, pattern="^eday:"))
    application.add_handler(CallbackQueryHandler(handle_edit_tx_callback, pattern="^etx:"))
    application.add_handler(CallbackQueryHandler(handle_edit_option_callback, pattern="^eopt:"))
    application.add_handler(CallbackQueryHandler(handle_edit_category_callback, pattern="^ecat:"))
    application.add_handler(CallbackQueryHandler(handle_edit_input_callback, pattern="^einput:"))
    
    # Addpast (ghilai) callbacks
    application.add_handler(CallbackQueryHandler(handle_addpast_callback, pattern="^addpast:"))
    
    # ========== ADD MESSAGE HANDLERS ==========
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
