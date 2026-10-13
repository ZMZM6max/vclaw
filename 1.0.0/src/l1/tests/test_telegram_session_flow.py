"""
Telegram Polling -> L1 -> L2 Session Flow Test

验证重构后的 session 管理架构：
- L1 完全无状态，只解析 StandardEvent
- L2 负责 session 创建、复用、持久化到 L4
- 同一用户多次发消息应复用同一 session_id
- /new 命令应触发新建 session

注意：本测试使用 Mock 回复（不调用真实 LLM）。
如需测试真实 LLM 回复及完整的 L4 历史记忆复用，请使用：
    tests/end_to_end/test_telegram_e2e_session_memory.py

Test Steps:
1. 运行: python src/l1/tests/test_telegram_session_flow.py
2. 在 Telegram 向 Bot 发消息（连续发 2-3 条）
3. 观察终端输出的 session_id 是否一致
4. 发送 /new，再发一条消息，观察 session_id 是否变化
"""
import sys
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import os
import json

os.environ['PYTHONIOENCODING'] = 'utf-8'

try:
    from dotenv import load_dotenv
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[INFO] Loaded environment from {env_path}")
    else:
        print(f"[WARNING] No .env file found at {env_path}")
except ImportError:
    print("[WARNING] python-dotenv not installed.")

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from src.l1.l1_user_interaction import UserInteraction
from src.l2.l2_control_gateway import ControlGateway
from src.l4.core.l4_memory import MemoryKnowledge

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    print("[ERROR] TELEGRAM_BOT_TOKEN not found!")
    sys.exit(1)

# 使用 file 模式持久化 L4 memory（仅 memory_store 用 file，vector/embedding 用 mock 避免依赖）
memory = MemoryKnowledge(
    embedding_service={"provider": "mock"},
    vector_store={"store_type": "memory"},
    memory_store={"store_type": "file", "storage_dir": "./src/l4/data/conversations"}
)
l1_handler = UserInteraction()
l2_gateway = ControlGateway(memory=memory)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_dict = update.to_dict()
    user = update.effective_user
    user_id = str(user.id) if user else "unknown"

    print("\n" + "=" * 60)
    print(f"收到来自 user_id={user_id} 的消息: {update.message.text if update.message else ''}")
    print("=" * 60)

    try:
        # Step 1: L1 解析
        event = l1_handler.receive_payload(update_dict, channel="telegram")
        print(f"\n[L1 输出] StandardEvent")
        print(f"  channel: {event.channel}")
        print(f"  user_id: {event.user_id}")
        print(f"  content: {event.content}")
        print(f"  metadata keys: {list(event.metadata.keys())}")

        # 验证 L1 无状态：metadata 中不应有 session_id
        assert "session_id" not in event.metadata, "L1 不应在 metadata 中注入 session_id"
        assert "is_new_session_request" not in event.metadata, "L1 不应注入 is_new_session_request"
        print("  [验证通过] L1 无状态：metadata 中无 session_id")

        # Step 2: L2 处理（创建/复用 session）
        l3_input = l2_gateway.process_event(event)
        session_ctx = l3_input.session_context

        print(f"\n[L2 输出] SessionContext")
        print(f"  session_id: {session_ctx.session_id}")
        print(f"  user_id: {session_ctx.user_id}")
        print(f"  current_query: {session_ctx.current_query}")
        print(f"  history length: {len(session_ctx.history)}")
        print(f"  available_tools: {len(l3_input.available_tools)}")
        print(f"  relevant_memories: {len(l3_input.relevant_memories)}")

        # Step 3: 模拟 L3 回复并触发 L2 保存对话历史
        mock_answer = f"【模拟回复】已收到你的消息：{event.content}"
        l2_gateway.send_response(event, mock_answer)

        # 读取最新历史确认已写入
        updated_history = memory.retrieve_history(session_ctx.session_id, limit=10)
        print(f"\n[验证] 当前会话历史条数: {len(updated_history)}")
        for msg in updated_history:
            print(f"  - {msg['role']}: {msg['content']}")

        print("\n[结论] 此 session_id 和对话历史由 L2 管理并持久化到 L4")

    except Exception as e:
        print(f"\n[错误] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 60)
    print("等待下一条消息... (按 Ctrl+C 停止)\n")


def main():
    print("""
+------------------------------------------------------------+
|     VClaw L1->L2 Session Flow Test (Telegram Polling)      |
+------------------------------------------------------------+

测试说明:
1. 连续发 2-3 条普通消息 → 应看到同一 session_id（L2 自动复用）
2. 发送 /new → 再发一条消息 → 应看到新的 session_id

按 Ctrl+C 停止
""")

    application = Application.builder().token(BOT_TOKEN).build()
    # 处理所有文本消息（包括 /new 等命令，因为命令也是文本）
    application.add_handler(MessageHandler(filters.TEXT, handle_message))

    print("[OK] Bot 已启动，正在轮询消息...")
    print("[OK] 现在去 Telegram 给 Bot 发消息吧！\n")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
