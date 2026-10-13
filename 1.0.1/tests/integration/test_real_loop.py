"""真实ReAct循环集成测试：L2组装上下文 -> L3决策 -> L5执行工具 -> Observation返回L3 -> 最终回答。

本测试使用真实的L2/L3/L4/L5/L6实例（非Mock），验证跨层ReAct闭环：
- L2 ControlGateway 组装 L3Input（含 SessionContext、可用工具、相关记忆）
- L3 Orchestration 运行 ReAct 循环，决定调用工具或直接回答
- L5 ToolsCapabilities 执行具体工具（calculator/python_repl等）
- Observation 通过测试代码手动传回 L3，完成第二轮推理
- 最终得到自然语言回答

依赖：
- OPENAI_API_KEY: 用于L3的LLM推理
- Docker（可选）: 若L3选择 python_repl 则需要Docker环境
"""

import os
import sys

sys.path.insert(0, "src")

import pytest

from src.core.models import StandardEvent, AgentAction
from src.l2.l2_control_gateway import ControlGateway
from src.l3.l3_orchestration import Orchestration
from src.l5.l5_tools import ToolsCapabilities
from src.l6.runtime_environment import RuntimeEnvironment
from src.l4.config.l4_config import get_l4_memory_production


pytestmark = pytest.mark.integration_real


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
def stack():
    """模块级fixture：构建L2-L6真实实例栈。

    Yields:
        dict: 包含 gateway, l3, l5, l6, l4 的字典
    """
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set, skipping real LLM integration test")

    l6 = RuntimeEnvironment()
    l5 = ToolsCapabilities(runtime=l6)
    l4 = get_l4_memory_production()
    gateway = ControlGateway(memory=l4, tools=l5)
    l3 = Orchestration(memory=l4, tools=l5)

    yield {
        "gateway": gateway,
        "l3": l3,
        "l5": l5,
        "l6": l6,
        "l4": l4,
    }

    # 清理L4测试数据
    try:
        l4.clear()
    except Exception:
        pass


def _execute_tool(l5, action: AgentAction, user_permissions=None):
    """根据AgentAction执行对应工具，返回Observation。

    支持的工具：
    - calculator: 参数 {"expression": "..."}
    - python_repl: 参数 {"code": "..."}（需要Docker）
    - 其他工具：通过 l5.execute 泛化执行

    Args:
        l5: ToolsCapabilities 实例
        action: L3返回的 AgentAction
        user_permissions: 用户权限列表

    Returns:
        Observation: 工具执行结果
    """
    user_permissions = user_permissions or []
    return l5.execute(
        action.action,
        action.action_input,
        user_permissions=user_permissions,
    )


class TestRealReActLoop:
    """真实ReAct循环集成测试类。"""

    def test_tool_call_loop(self, stack):
        """测试工具调用闭环：数学查询 -> L3返回AgentAction -> 执行工具 -> 传回Observation -> 最终回答。

        查询: "帮我算 15乘以23"
        期望: L3选择工具（calculator或python_repl）-> 执行后得到345 -> 最终回答包含"345"
        """
        gateway = stack["gateway"]
        l3 = stack["l3"]
        l5 = stack["l5"]

        # 重置L3状态，避免历史记录干扰
        l3.reset_plan()

        event = StandardEvent(
            channel="test",
            user_id="test_user_real_loop",
            content="帮我算 15乘以23",
        )

        # L2组装上下文
        l3_input = gateway.process_event(event)

        # 第一轮：L3决策
        round1 = l3.run(l3_input.session_context)

        # 如果L3直接返回字符串（某些模型可能直接计算），也接受
        if isinstance(round1, str):
            assert "345" in round1, f"直接回答应包含计算结果345，实际返回: {round1}"
            return

        # 否则应为AgentAction
        assert isinstance(round1, AgentAction), (
            f"第一轮应返回AgentAction或str，实际返回类型: {type(round1)}"
        )

        # 如果L3选择python_repl且Docker不可用，则跳过
        if round1.action == "python_repl" and not _docker_available():
            pytest.skip("L3 chose python_repl but Docker is unavailable")

        # 执行工具
        observation = _execute_tool(l5, round1, user_permissions=[])

        # 第二轮：将Observation传回L3
        round2 = l3.run(l3_input.session_context, observation)

        # 第二轮应返回最终字符串回答
        assert isinstance(round2, str), (
            f"第二轮应返回str类型的最终回答，实际返回类型: {type(round2)}"
        )
        assert "345" in round2, f"最终回答应包含计算结果345，实际返回: {round2}"

    def test_direct_answer_no_tools(self, stack):
        """测试无需工具的直接回答：问候语 -> L3直接返回字符串。

        查询: "你好"
        期望: L3直接返回非空字符串回答，无需调用任何工具
        """
        gateway = stack["gateway"]
        l3 = stack["l3"]

        # 重置L3状态
        l3.reset_plan()

        event = StandardEvent(
            channel="test",
            user_id="test_user_real_loop",
            content="你好",
        )

        # L2组装上下文
        l3_input = gateway.process_event(event)

        # L3决策
        result = l3.run(l3_input.session_context)

        # 应为直接字符串回答
        assert isinstance(result, str), (
            f"问候查询应返回str类型的直接回答，实际返回类型: {type(result)}"
        )
        assert result.strip(), "直接回答应为非空字符串"
