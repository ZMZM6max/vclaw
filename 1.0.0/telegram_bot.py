"""
VClaw Telegram Bot - 完整的 L1-L6 流水线接入

运行方式:
    python telegram_bot.py

环境要求:
    - TELEGRAM_BOT_TOKEN 已在 .env 文件中配置
    - 可选: OPENAI_API_KEY (用于真实LLM响应)
"""
import sys
import os
import asyncio
import json
from pathlib import Path
from typing import Optional

# 设置编码
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Telegram 库
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# VClaw 各层
from src.l1.l1_user_interaction import UserInteraction
from src.l2.l2_control_gateway import ControlGateway
from src.l3.l3_orchestration import Orchestration
from src.l4 import MemoryKnowledge
from src.l5.l5_tools import ToolsCapabilities
from src.l6.l6_runtime import RuntimeEnvironment

# 获取 Bot Token
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    print("[ERROR] TELEGRAM_BOT_TOKEN not found in .env file!")
    print("[HINT] 请在 .env 文件中添加: TELEGRAM_BOT_TOKEN=your_bot_token")
    sys.exit(1)


class VClawTelegramBot:
    """VClaw Telegram Bot - 完整的 L1-L6 流水线"""

    def __init__(self):
        """初始化所有层"""
        print("[*] 初始化 VClaw 系统...")

        # L6: 运行时环境
        self.l6 = RuntimeEnvironment()
        print("  [OK] L6 RuntimeEnvironment")

        # L5: 工具能力层
        self.l5 = ToolsCapabilities(runtime=self.l6)
        print("  [OK] L5 ToolsCapabilities")

        # L4: 记忆知识层
        self.l4 = MemoryKnowledge()
        print("  [OK] L4 MemoryKnowledge")

        # L3: 逻辑编排层
        self.l3 = Orchestration(memory=self.l4, tools=self.l5)
        print("  [OK] L3 Orchestration")

        # L2: 控制网关层
        self.l2 = ControlGateway(memory=self.l4, tools=self.l5)
        print("  [OK] L2 ControlGateway")

        # L1: 用户交互层
        self.l1 = UserInteraction()
        print("  [OK] L1 UserInteraction")

        # 用户会话映射 (user_id -> session_id)
        self.user_sessions = {}

        print("[*] 系统初始化完成!")
        print()

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 Telegram 消息"""
        if not update.message or not update.message.text:
            return

        user_id = str(update.message.from_user.id)
        chat_id = update.message.chat_id
        message_text = update.message.text

        print(f"\n{'='*60}")
        print(f"[收到消息] 用户: {user_id}, 内容: {message_text[:50]}")
        print('='*60)

        try:
            # Step 1: L1 处理 - 标准化输入
            print("\n[Step 1] L1: 标准化输入...")
            update_dict = update.to_dict()
            event = self.l1.receive_payload(update_dict, channel="telegram")
            print(f"  => Channel: {event.channel}")
            print(f"  => User ID: {event.user_id}")
            print(f"  => Content: {event.content}")

            # Step 2: L2 处理 - 限流、会话管理、组装上下文
            print("\n[Step 2] L2: 处理事件...")
            l3_input = self.l2.process_event(event)
            print(f"  => Session ID: {l3_input.session_context.session_id[:8]}...")
            print(f"  => Tools: {len(l3_input.available_tools)} 个可用工具")
            print(f"  => History: {len(l3_input.session_context.history)} 条历史")

            # 更新会话映射
            self.l1.update_session_mapping(user_id, l3_input.session_context.session_id)

            # Step 3: L3 处理 - ReAct 循环生成响应
            print("\n[Step 3] L3: 生成响应...")

            api_key = os.getenv("OPENAI_API_KEY")
            print(f"  => API Key loaded: {api_key[:15]}..." if api_key else "  => API Key: not found")

            if not api_key:
                # 无 API Key: 使用简单回复
                reply_text = f"你说了: {message_text}\n\n(提示: 配置 OPENAI_API_KEY 可获得 AI 回复)"
                print("  => [Mock] 无 API Key, 使用默认回复")
            else:
                # 有 API Key: 调用 L3
                try:
                    result = self.l3.run(l3_input.session_context)

                    if hasattr(result, 'action'):
                        # 需要调用工具
                        print(f"  => Action: {result.action}")
                        print(f"  => Input: {result.action_input}")

                        # Step 4: L5 执行工具
                        print("\n[Step 4] L5: 执行工具...")
                        observation = self.l5.execute(
                            result.action,
                            result.action_input,
                            user_permissions=[]
                        )
                        print(f"  => Status: {observation.status}")

                        # 再次调用 L3，传入工具结果
                        reply_text = f"[工具执行结果]\n{observation.result}"
                    else:
                        # 直接返回文本回复
                        reply_text = str(result) if result and str(result) not in ["{}", "", "None"] else f"我收到了: {message_text}"
                        print(f"  => Reply: {reply_text[:100]}...")

                except Exception as e:
                    print(f"  => [Error] L3 处理失败: {e}")
                    reply_text = f"抱歉, 处理请求时出错: {str(e)}"

            # 发送回复
            print(f"\n[发送回复] {reply_text[:100]}...")
            await update.message.reply_text(reply_text)

        except Exception as e:
            print(f"\n[Error] 处理失败: {e}")
            import traceback
            traceback.print_exc()
            await update.message.reply_text(f"处理消息时出错: {str(e)}")

        print('='*60)

    def run(self):
        """启动 Bot"""
        print("""
+------------------------------------------------------------+
|           VClaw Telegram Bot                               |
|           (L1-L6 完整流水线)                                |
+------------------------------------------------------------+

命令:
  /new    - 创建新会话
  /reset  - 重置当前会话
  /start  - 开始 (同 /new)

按 Ctrl+C 停止
""")

        # 创建应用
        application = Application.builder().token(BOT_TOKEN).build()

        # 添加消息处理器
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        print("[OK] Bot 已启动, 正在监听消息...")
        print("[OK] 现在去 Telegram 发送消息给 Bot 吧!\n")

        # 启动轮询
        application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    bot = VClawTelegramBot()
    bot.run()


if __name__ == "__main__":
    main()