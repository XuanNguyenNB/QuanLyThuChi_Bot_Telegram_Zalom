"""
Entry point to run both Telegram and Zalo bots.
Usage:
    python run.py          # Run both bots
    python run.py telegram # Run only Telegram bot
    python run.py zalo     # Run only Zalo bot
"""

import asyncio
import sys
import signal
import threading
import time

from src.bot import main as telegram_main
from src.zalo_bot import main as zalo_main


def run_telegram():
    """Run Telegram bot in its own thread"""
    try:
        print("📱 Starting Telegram bot...")
        telegram_main()
    except Exception as e:
        print(f"❌ Telegram bot error: {e}")


async def run_both():
    """Run both bots concurrently"""
    print("🚀 Khởi động cả 2 bot...")
    print("   📱 Telegram Bot")
    print("   💬 Zalo Bot")
    print("─" * 30)
    
    # Start Telegram in separate thread
    telegram_thread = threading.Thread(target=run_telegram, daemon=True)
    telegram_thread.start()
    
    # Give Telegram bot time to start
    await asyncio.sleep(2)
    
    # Run Zalo bot in main async loop
    try:
        print("💬 Starting Zalo bot...")
        await zalo_main()
    except Exception as e:
        print(f"❌ Zalo bot error: {e}")
    finally:
        # Keep main thread alive
        try:
            while telegram_thread.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down bots...")
            return


def main():
    """Main entry point"""
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "both"
    
    if mode == "telegram":
        print("🚀 Khởi động Telegram Bot...")
        telegram_main()
    elif mode == "zalo":
        print("🚀 Khởi động Zalo Bot...")
        asyncio.run(zalo_main())
    else:
        # Run both
        asyncio.run(run_both())


if __name__ == "__main__":
    main()
