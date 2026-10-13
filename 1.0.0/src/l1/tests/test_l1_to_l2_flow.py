"""
L1 -> L2 Integration Test
验证L1接收的Telegram消息能被L2正确转换为SessionContext

运行: python src/l1/tests/test_l1_to_l2_flow.py

依赖: pip install python-telegram-bot python-dotenv
"""
import sys
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

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
from src.l2.l2_control_gateway import ControlGateway
from src.core.models import StandardEvent, SessionContext

# Bot Token（从 .env 文件或环境变量读取）
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    print("[ERROR] TELEGRAM_BOT_TOKEN not found!")
    print("[HINT] Add TELEGRAM_BOT_TOKEN=your_token to .env file")
    sys.exit(1)

# Initialize L1 and L2
l1_handler = UserInteraction()
l2_gateway = ControlGateway()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle message through L1 -> L2 flow"""

    update_dict = update.to_dict()

    print("\n" + "="*70)
    print("STEP 1: L1 Receives Telegram Message")
    print("="*70)

    # L1: Parse to StandardEvent
    event = l1_handler.receive_payload(update_dict, channel="telegram")

    print(f"[L1 Output] StandardEvent:")
    print(f"  - channel: {event.channel}")
    print(f"  - user_id: {event.user_id}")
    print(f"  - content: {event.content}")
    print(f"  - timestamp: {event.timestamp}")
    print(f"  - metadata: {event.metadata}")

    print("\n" + "-"*70)
    print("STEP 2: L2 Processes StandardEvent -> SessionContext")
    print("-"*70)

    # L2: Convert to SessionContext
    try:
        session_context = l2_gateway.process_event(event)

        print(f"[L2 Output] SessionContext:")
        print(f"  - session_id: {session_context.session_id}")
        print(f"  - user_id: {session_context.user_id}")
        print(f"  - current_query: {session_context.current_query}")
        print(f"  - history: {len(session_context.history)} messages")
        print(f"  - user_permissions: {session_context.user_permissions}")
        print(f"  - metadata: {session_context.metadata}")

        print("\n" + "="*70)
        print("FLOW COMPLETE: L1 -> L2 Conversion Successful")
        print("="*70)

        # Verify data consistency
        assert event.user_id == session_context.user_id, "User ID mismatch!"
        assert event.content == session_context.current_query, "Content mismatch!"
        assert event.channel == session_context.metadata.get("channel"), "Channel mismatch!"

        print("[Validation] All checks passed!")

    except Exception as e:
        print(f"\n[L2 Error] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print("\nWaiting for next message... (Press Ctrl+C to stop)\n")


def main():
    print("""
+-----------------------------------------------------------------------+
|     VClaw L1 -> L2 Integration Test                                   |
|     Verify StandardEvent -> SessionContext conversion                 |
+-----------------------------------------------------------------------+

Test Flow:
1. Telegram Message -> L1 -> StandardEvent
2. StandardEvent -> L2 -> SessionContext
3. Validate data consistency

Press Ctrl+C to stop
""")

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("[OK] Bot started, waiting for messages...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
