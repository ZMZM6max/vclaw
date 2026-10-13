"""
Telegram Webhook → L1 真实测试

测试流程：
1. 在 .env 文件添加 TELEGRAM_BOT_TOKEN
2. 启动 ngrok: ngrok http 8000
3. 从项目根目录运行: python src/l1/tests/test_telegram_webhook.py
4. 给 Bot 发送消息
5. 查看终端输出的 StandardEvent

依赖: pip install fastapi uvicorn python-telegram-bot python-dotenv
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path (works from any directory)
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent  # src/l1/tests/ -> project root
sys.path.insert(0, str(project_root))

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

from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import uvicorn

from src.l1.l1_user_interaction import UserInteraction
from src.l4 import MemoryKnowledge
from telegram import Update

# Bot Token（从 .env 文件或环境变量读取）
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ngrok 公网 URL（需要用户启动 ngrok 后填写）
# 例如: https://xxxx.ngrok-free.app
WEBHOOK_URL = None  # 运行后会提示输入

# 全局 L1 实例 (注入 L4 memory 实现 session 持久化)
l1_handler = UserInteraction(memory=MemoryKnowledge())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时设置 Webhook
    from telegram.ext import Application

    global WEBHOOK_URL
    if not WEBHOOK_URL:
        print("\n" + "="*60)
        print("请先启动 ngrok:")
        print("  1. 打开另一个终端")
        print("  2. 运行: ngrok http 8000")
        print("  3. 复制 https://xxxx.ngrok-free.app 的 URL")
        print("="*60)
        WEBHOOK_URL = input("\n请输入 ngrok URL (如 https://xxxx.ngrok-free.app): ").strip()

    app = Application.builder().token(BOT_TOKEN).build()
    await app.initialize()

    webhook_url = f"{WEBHOOK_URL}/webhook"
    await app.bot.set_webhook(url=webhook_url)
    print(f"\n✅ Webhook 已设置: {webhook_url}")
    print("📱 现在给 Bot 发送消息，查看解析结果...\n")

    yield

    # 关闭时清理
    await app.bot.delete_webhook()
    print("\n✅ Webhook 已清理")


app = FastAPI(lifespan=lifespan)


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """接收 Telegram Webhook 消息"""
    # 获取原始 JSON 数据
    data = await request.json()

    print("\n" + "="*60)
    print("📨 收到 Telegram 原始消息:")
    print("="*60)
    import json
    print(json.dumps(data, indent=2, ensure_ascii=False))

    # 调用 L1 解析
    print("\n" + "-"*60)
    print("🔍 调用 L1.receive_payload() 解析...")
    print("-"*60)

    try:
        event = l1_handler.receive_payload(data, channel="telegram")

        print("\n✅ L1 解析成功!")
        print(f"   channel: {event.channel}")
        print(f"   user_id: {event.user_id}")
        print(f"   content: {event.content}")
        print(f"   timestamp: {event.timestamp}")
        print(f"   metadata: {event.metadata}")

    except Exception as e:
        print(f"\n❌ L1 解析失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print("="*60)

    return {"ok": True}


@app.get("/")
async def root():
    """健康检查"""
    return {"status": "running", "service": "VClaw L1 Telegram Test"}


if __name__ == "__main__":
    if not BOT_TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN not found!")
        print("[HINT] Add TELEGRAM_BOT_TOKEN=your_token to .env file")
        sys.exit(1)

    print("""
╔════════════════════════════════════════════════════════════╗
║     VClaw L1 - Telegram Webhook 真实测试                    ║
╚════════════════════════════════════════════════════════════╝

测试步骤:
1. 确保已安装 ngrok: https://ngrok.com/download
2. 在另一个终端运行: ngrok http 8000
3. 复制 ngrok 提供的 https URL
4. 运行此脚本并输入 ngrok URL
5. 给 Bot 发送消息，观察解析结果

按 Ctrl+C 停止
    """)

    uvicorn.run(app, host="0.0.0.0", port=8000)
