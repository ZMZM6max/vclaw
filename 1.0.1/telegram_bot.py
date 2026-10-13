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
import time
from pathlib import Path
from typing import Optional, Tuple

# 设置编码
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(override=True)

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Telegram 库
from telegram import Update
from telegram.ext import (
    Application, MessageHandler, filters, ContextTypes, CommandHandler
)

# VClaw 各层
from src.l1.l1_user_interaction import UserInteraction
from src.l2.l2_control_gateway import ControlGateway
from src.l3.l3_orchestration import Orchestration
from src.l4 import MemoryKnowledge
from src.l5.l5_tools import ToolsCapabilities
from src.l6.runtime_environment import RuntimeEnvironment
from src.core.models import AgentAction

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

        # L5: 工具能力层（注入 L6 runtime 以支持 python_repl 等 L6_DELEGATE 工具）
        self.l5 = ToolsCapabilities(runtime=self.l6)
        print("  [OK] L5 ToolsCapabilities")

        # L4: 记忆知识层（使用 .env 配置的持久化存储）
        l4_memory_store_type = os.getenv("L4_MEMORY_STORE_TYPE", "file")
        l4_storage_dir = os.getenv(
            "L4_MEMORY_STORAGE_DIR", "./src/l4/data/conversations"
        )
        self.l4 = MemoryKnowledge(
            memory_store={
                "store_type": l4_memory_store_type,
                "storage_dir": l4_storage_dir,
            }
        )
        print(
            f"  [OK] L4 MemoryKnowledge "
            f"(store={l4_memory_store_type}, dir={l4_storage_dir})"
        )

        # L3: 逻辑编排层
        self.l3 = Orchestration(memory=self.l4, tools=self.l5)
        print("  [OK] L3 Orchestration")

        # L2: 控制网关层
        self.l2 = ControlGateway(memory=self.l4, tools=self.l5)
        print("  [OK] L2 ControlGateway")

        # L1: 用户交互层 (注入 L4 memory 实现 session 持久化)
        self.l1 = UserInteraction(memory=self.l4)
        print("  [OK] L1 UserInteraction")

        # 用户会话映射 (user_id -> session_id)
        self.user_sessions = {}

        # 待确认操作映射 (user_id -> pending state)
        self._pending_confirmations: dict = {}

        print("[*] 系统初始化完成!")
        print()

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    async def _run_react_loop(
        self,
        user_id: str,
        message_text: str,
        l3_input,
        initial_observation=None,
    ) -> Tuple[str, str]:
        """运行多轮 ReAct 循环。

        Args:
            user_id: 用户 ID
            message_text: 原始消息文本
            l3_input: L2 组装好的 L3 输入
            initial_observation: 可选的初始 observation（用于确认后恢复）

        Returns:
            (reply_text, status)
            status: "done" 或 "pending_confirmation"
        """
        max_iterations = 5
        observation = initial_observation

        for iteration in range(1, max_iterations + 1):
            print(f"\n[Step 3.{iteration}] L3: 第 {iteration} 轮推理...")
            result = self.l3.run(l3_input.session_context, observation)

            if isinstance(result, AgentAction):
                print(f"  => Action: {result.action}")
                print(f"  => Input: {result.action_input}")

                # 执行工具
                print(f"\n[Step 4.{iteration}] L5: 执行工具...")
                observation = self.l5.execute(
                    result.action,
                    result.action_input,
                    user_permissions=[],
                )
                print(f"  => Status: {observation.status}")

                # 处理需要确认的操作
                if observation.status == "pending_confirmation":
                    self._pending_confirmations[user_id] = {
                        "action": result.action,
                        "action_input": result.action_input,
                        "l3_input": l3_input,
                    }
                    reply_text = (
                        f"⚠️ 执行 **{result.action}** 需要您的确认。\n\n"
                        f"是否继续？（回复\"是\"继续，\"否\"取消）"
                    )
                    return reply_text, "pending_confirmation"

                # 继续下一轮 ReAct（success / error 都由 L3 处理）
                continue

            else:
                # 最终答案（str）或错误提示
                reply_text = (
                    str(result)
                    if result and str(result) not in ["{}", "", "None"]
                    else f"我收到了: {message_text}"
                )
                print(f"  => Reply: {reply_text[:100]}...")
                return reply_text, "done"

        return "请求处理时间过长，请稍后重试。", "done"

    async def _handle_confirmation_reply(
        self, user_id: str, message_text: str, update: Update
    ) -> bool:
        """处理用户对确认提示的回复。

        Returns:
            True 表示已处理（无论确认/取消/无效回复），False 表示无待确认操作。
        """
        pending = self._pending_confirmations.get(user_id)
        if not pending:
            return False

        confirm_keywords = ["是", "yes", "y", "确定", "好", "继续", "ok"]
        cancel_keywords = ["否", "no", "n", "取消", "算了", "不", "no"]
        msg_lower = message_text.lower().strip()

        if any(kw in msg_lower for kw in confirm_keywords):
            del self._pending_confirmations[user_id]

            # 重新执行工具（跳过确认检查）
            print(f"\n[确认] 用户 {user_id} 确认执行 {pending['action']}")
            observation = self.l5.execute(
                pending["action"],
                {**pending["action_input"], "confirmed": True},
                user_permissions=[],
            )
            print(f"  => Status: {observation.status}")

            # 继续 ReAct 循环
            reply_text, _ = await self._run_react_loop(
                user_id,
                message_text,
                pending["l3_input"],
                initial_observation=observation,
            )
            await update.message.reply_text(reply_text)

            # 持久化历史 + 重置 L3
            session_id = pending["l3_input"].session_context.session_id
            self._persist_history(session_id, message_text, reply_text)
            return True

        elif any(kw in msg_lower for kw in cancel_keywords):
            del self._pending_confirmations[user_id]
            await update.message.reply_text("已取消操作")
            return True

        else:
            await update.message.reply_text('请回复"是"继续，或"否"取消')
            return True

    def _persist_history(self, session_id: str, user_msg: str, assistant_msg: str):
        """持久化对话历史到 L4 并重置 L3 状态。"""
        if not session_id:
            return

        try:
            history = self.l4.retrieve_history(session_id)
            history.append({"role": "user", "content": user_msg})
            history.append({"role": "assistant", "content": assistant_msg})
            self.l4.store_conversation(session_id, history)
            print(f"  [OK] 历史已保存: {len(history)} 条消息")
        except Exception as e:
            print(f"  [WARN] 保存历史失败: {e}")

        self.l3.reset_plan()
        print("  [OK] L3 状态已重置")

    # ------------------------------------------------------------------
    # 消息 / 命令处理器
    # ------------------------------------------------------------------

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 Telegram 消息"""
        if not update.message or not update.message.text:
            return

        user_id = str(update.message.from_user.id)
        chat_id = update.message.chat_id
        message_text = update.message.text

        print(f"\n{'='*60}")
        print(f"[收到消息] 用户: {user_id}, 内容: {message_text[:50]}")
        print("=" * 60)

        # 优先检查待确认操作
        if await self._handle_confirmation_reply(user_id, message_text, update):
            print("=" * 60)
            return

        session_id = None
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
            session_id = l3_input.session_context.session_id
            self.l1.update_session_mapping(user_id, session_id)

            # Step 3: L3 处理 - ReAct 循环生成响应
            print("\n[Step 3] L3: 生成响应...")

            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                print(f"  => API Key loaded: {api_key[:15]}...")
            else:
                print("  => API Key: not found")

            if not api_key:
                # 无 API Key: 使用简单回复
                reply_text = (
                    f"你说了: {message_text}\n\n"
                    f"(提示: 配置 OPENAI_API_KEY 可获得 AI 回复)"
                )
                print("  => [Mock] 无 API Key, 使用默认回复")
            else:
                # 有 API Key: 运行多轮 ReAct 循环
                reply_text, status = await self._run_react_loop(
                    user_id, message_text, l3_input
                )

            # 发送回复
            print(f"\n[发送回复] {reply_text[:100]}...")
            await update.message.reply_text(reply_text)

            # 持久化历史 + 重置 L3
            self._persist_history(session_id, message_text, reply_text)

        except Exception as e:
            print(f"\n[Error] 处理失败: {e}")
            import traceback

            traceback.print_exc()
            await update.message.reply_text(f"处理消息时出错: {str(e)}")

        print("=" * 60)

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 Telegram 命令 (/start, /new, /reset)"""
        if not update.message or not update.message.text:
            return

        command = update.message.text.strip().lower()
        user_id = str(update.message.from_user.id)

        if command in ("/start", "/new", "/reset"):
            print(f"\n[命令] 用户 {user_id} 发送 {command}")

            # 清除待确认状态
            if user_id in self._pending_confirmations:
                del self._pending_confirmations[user_id]
                print("  => 已清除待确认操作")

            # 通过 L1 处理新会话命令
            raw_data = {
                "update_id": 123456789,
                "message": {
                    "message_id": update.message.message_id,
                    "from": {
                        "id": update.message.from_user.id,
                        "first_name": update.message.from_user.first_name
                        or "User",
                    },
                    "chat": {
                        "id": update.message.chat_id,
                        "type": "private",
                    },
                    "date": int(time.time()),
                    "text": command,
                },
            }
            event = self.l1.receive_payload(raw_data, channel="telegram")
            # L2 会识别 is_new_session_request 并创建新会话
            l3_input = self.l2.process_event(event)
            session_id = l3_input.session_context.session_id
            self.l1.update_session_mapping(
                user_id, session_id, channel="telegram"
            )

            reply_text = "已创建新会话！之前的对话历史已清除。"
            await update.message.reply_text(reply_text)
            print(f"  => 新会话 ID: {session_id[:8]}...")

    def run(self):
        """启动 Bot"""
        print(
            """
+------------------------------------------------------------+
|           VClaw Telegram Bot                               |
|           (L1-L6 完整流水线)                                |
+------------------------------------------------------------+

命令:
  /new    - 创建新会话
  /reset  - 重置当前会话
  /start  - 开始 (同 /new)

按 Ctrl+C 停止
"""
        )

        # 创建应用
        application = Application.builder().token(BOT_TOKEN).build()

        # 添加命令处理器
        application.add_handler(
            CommandHandler(["start", "new", "reset"], self.handle_command)
        )

        # 添加消息处理器 (非命令文本)
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
