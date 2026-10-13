"""L1→L6 全真实端到端测试.

从 L1 接收原始负载到 L2 发送应答，全部使用真实实现。
3 个场景：闲聊 / 工具调用 / 代码沙盒。
"""
import sys
sys.path.insert(0, 'src')

import os
import pytest
from src.l4.config.l4_config import get_l4_memory_production
from src.l3.l3_orchestration import Orchestration
from src.l5.l5_tools import ToolsCapabilities
from src.l6.runtime_environment import RuntimeEnvironment
from src.l2.l2_control_gateway import ControlGateway
from src.l1.l1_user_interaction import UserInteraction
from src.core.models import StandardEvent, AgentAction


def _docker_available() -> bool:
    """检查Docker是否可用（用于python_repl等L6委托工具）。"""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def full_stack():
    """模块级 fixture：L1-L6 全真实实例."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set, skipping real LLM end-to-end test")

    l6 = RuntimeEnvironment()
    l5 = ToolsCapabilities(runtime=l6)
    l4 = get_l4_memory_production()
    l3 = Orchestration(memory=l4, tools=l5)
    l2 = ControlGateway(memory=l4, tools=l5)
    l1 = UserInteraction(memory=l4)
    yield l1, l2, l3, l4, l5, l6
    # cleanup
    try:
        l4.clear()
    except Exception:
        pass


@pytest.mark.e2e_real
class TestE2EReal:
    """L1→L6 端到端真实测试."""

    def _run_pipeline(self, l1, l2, l3, l5, raw_data):
        """辅助方法：跑完整 L1→L6 管道，返回最终字符串."""
        # L1: 标准化输入
        event = l1.receive_payload(raw_data, channel="telegram")
        assert event.channel == "telegram"
        assert event.content == raw_data.get("message", {}).get("text", "")

        # L2: 组装上下文
        l3_input = l2.process_event(event)
        assert l3_input.session_context is not None

        # L3: 第一轮决策
        result = l3.run(l3_input.session_context)

        if isinstance(result, AgentAction):
            # 工具调用路径
            observation = l5.execute(result.action, result.action_input, user_permissions=[])
            # L3: 第二轮基于 Observation
            final = l3.run(l3_input.session_context, observation)
            return str(final)
        else:
            # 直接回答
            return str(result)

    def test_e2e_chat_no_tools(self, full_stack):
        """场景1: 闲聊，不走 L5/L6."""
        l1, l2, l3, l4, l5, l6 = full_stack

        # 重置L3状态，避免历史记录干扰
        l3.reset_plan()

        raw = {
            "message": {
                "text": "你好",
                "from": {"id": 123456},
                "chat": {"id": 123456}
            }
        }
        answer = self._run_pipeline(l1, l2, l3, l5, raw)

        assert isinstance(answer, str)
        assert len(answer) > 0
        assert "error" not in answer.lower()

    def test_e2e_tool_call(self, full_stack):
        """场景2: 工具调用，走 L5（不走 L6）."""
        l1, l2, l3, l4, l5, l6 = full_stack

        # 重置L3状态
        l3.reset_plan()

        raw = {
            "message": {
                "text": "帮我算 (15+27)*3",
                "from": {"id": 123457},
                "chat": {"id": 123457}
            }
        }
        answer = self._run_pipeline(l1, l2, l3, l5, raw)

        assert isinstance(answer, str)
        assert "126" in answer, f"期望包含 126，实际: {answer}"

    def test_e2e_code_sandbox(self, full_stack):
        """场景3: 代码沙盒，走 L5→L6."""
        l1, l2, l3, l4, l5, l6 = full_stack

        # 如果Docker不可用，直接跳过
        if not _docker_available():
            pytest.skip("Docker is unavailable, skipping python_repl test")

        # 重置L3状态
        l3.reset_plan()

        raw = {
            "message": {
                "text": "用 python 跑一段代码：print(2**10)",
                "from": {"id": 123458},
                "chat": {"id": 123458}
            }
        }
        answer = self._run_pipeline(l1, l2, l3, l5, raw)

        assert isinstance(answer, str)
        assert "1024" in answer, f"期望包含 1024，实际: {answer}"
