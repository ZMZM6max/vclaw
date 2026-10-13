"""
Telegram Polling -> L1 Real Test (Polling Mode)

Test Steps:
1. Add TELEGRAM_BOT_TOKEN to .env file in project root
2. Run from project root: python src/l1/tests/test_telegram_polling.py
3. Or run from this folder: python test_telegram_polling.py
4. Send message to Bot
5. Check terminal output for StandardEvent

Requirements: pip install python-telegram-bot python-dotenv
"""
import sys
from pathlib import Path

# Add project root to path (works from any directory)
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent  # src/l1/tests/ -> project root
sys.path.insert(0, str(project_root))

import asyncio
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[INFO] Loaded environment from {env_path}")
    else:
        print(f"[WARNING] No .env file found at {env_path}")
        print("[HINT] Create .env file with: TELEGRAM_BOT_TOKEN=your_token")
except ImportError:
    print("[WARNING] python-dotenv not installed. Using environment variables only.")
    print("[HINT] Install with: pip install python-dotenv")

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from src.l1.l1_user_interaction import UserInteraction

# Bot Token (from .env file or environment variable)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    print("[ERROR] TELEGRAM_BOT_TOKEN not found!")
    print("[HINT] Add TELEGRAM_BOT_TOKEN=your_token to .env file")
    sys.exit(1)

# Global L1 instance
l1_handler = UserInteraction()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming message"""

    # Get raw update data (convert to dict, same format as webhook)
    update_dict = update.to_dict()

    print("\n" + "="*60)
    print("Received Telegram raw message:")
    print("="*60)
    import json
    print(json.dumps(update_dict, indent=2, ensure_ascii=False))

    # Call L1 to parse
    print("\n" + "-"*60)
    print("Calling L1.receive_payload() to parse...")
    print("-"*60)

    try:
        event = l1_handler.receive_payload(update_dict, channel="telegram")

        print("\n[L1 Parse Success]")
        print(f"  channel: {event.channel}")
        print(f"  user_id: {event.user_id}")
        print(f"  content: {event.content}")
        print(f"  timestamp: {event.timestamp}")
        print(f"  metadata: {event.metadata}")

    except Exception as e:
        print(f"\n[L1 Parse Failed] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print("="*60)
    print("Waiting for next message... (Press Ctrl+C to stop)\n")


def main():
    print("""
+------------------------------------------------------------+
|     VClaw L1 - Telegram Polling Real Test                  |
|     (Polling Mode - No Public IP Required)                 |
+------------------------------------------------------------+

Test Steps:
1. Run this script
2. Send message to Bot in Telegram
3. Observe terminal output

Press Ctrl+C to stop
""")

    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add message handler (handle all text messages)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("[OK] Bot started, polling for messages...")
    print("[OK] Send a message to your Bot now!\n")

    # Start polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
