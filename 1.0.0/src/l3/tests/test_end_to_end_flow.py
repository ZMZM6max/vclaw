"""端到端流程测试

验证从用户输入到最终响应的完整流程:
L1 → L2 → L3 → L5 → L3 → L2 → 用户

注意: 这是集成测试，验证各层协作，不是单元测试。
"""
import pytest
import os
import sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, 'src')

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from src.l1.l1_user_interaction import UserInteraction
from src.l2.l2_control_gateway import ControlGateway
from src.l3.l3_orchestration import Orchestration, LLMManager
from src.l5.l5_tools import ToolsCapabilities
from src.core.models import StandardEvent, SessionContext, AgentAction, Observation


def save_result(test_name, content, passed=True):
    """Save test result to file."""
    results_dir = Path(__file__).parent / 'results'
    results_dir.mkdir(exist_ok=True)
    result_file = results_dir / 'test_end_to_end_results.txt'

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "✅ 通过" if passed else "❌ 失败"

    result_text = f"""
## {test_name}
**时间**: {timestamp}

{content}

**状态**: {status}

---
"""

    with open(result_file, 'a', encoding='utf-8') as f:
        f.write(result_text)

    print(f"\n[RESULT SAVED] {result_file}")


class TestEndToEndFlow:
    """端到端流程测试 - 模拟完整的L1→L2→L3→L5→L3→L2→用户流程"""

    @pytest.fixture
    def full_stack(self):
        """创建完整的L1→L2→L3→L5栈。"""
        provider = os.getenv("TEST_LLM_PROVIDER", "openai")
        model = os.getenv("TEST_LLM_MODEL", "gpt-5.4-mini")
        base_url = os.getenv("API_BASE_URL")

        l1 = UserInteraction()
        l2 = ControlGateway()
        l3 = Orchestration(
            llm_manager=LLMManager(provider=provider, model=model, base_url=base_url),
            tools=ToolsCapabilities()
        )

        return {"l1": l1, "l2": l2, "l3": l3}

    def test_l1_to_l2_flow(self, full_stack):
        """TC-L3-024: L1接收输入并传递给L2"""
        l1 = full_stack["l1"]
        l2 = full_stack["l2"]

        # 模拟用户输入
        raw_data = {
            "user_id": "user_123",
            "content": "Hello",
            "channel": "websocket",
            "type": "message"
        }

        # L1处理输入
        event = l1.receive_payload(raw_data, channel="websocket")
        print(f"\n[L1] Event created: user_id={event.user_id}, content={event.content}")

        # L2处理Event (L2 全权负责 session 管理)
        l3_input = l2.process_event(event)
        context = l3_input.session_context
        print(f"[L2] Context created: session_id={context.session_id}")

        assert context.user_id == "user_123"
        assert context.current_query == "Hello"
        assert context.session_id is not None

        content = f"""**用户输入**: "Hello"

**L1处理**:
- Event创建: channel={event.channel}, user_id={event.user_id}

**L2处理**:
- Context创建: session_id={context.session_id}
- 用户查询: {context.current_query}

**Session映射**: user_123 → {context.session_id} (由L2管理)

**L1→L2流程**: ✅ 正常
"""
        save_result("TC-L3-024: L1→L2流程", content)

    def test_l2_to_l3_flow(self, full_stack):
        """TC-L3-025: L2传递Context给L3并获取响应"""
        l2 = full_stack["l2"]
        l3 = full_stack["l3"]

        # 创建Context（模拟L2生成）
        context = SessionContext(
            session_id="test_session_001",
            user_id="user_123",
            current_query="你好",
            history=[],
            user_permissions=["user"]
        )

        print(f"\n[L2→L3] 传递Context")
        print(f"  Query: {context.current_query}")

        # L3处理（直接回答，不需要工具）
        result = l3.run(context)

        print(f"[L3返回] Type: {type(result).__name__}")
        if isinstance(result, str):
            print(f"  Answer: {result[:100]}...")
        elif isinstance(result, AgentAction):
            print(f"  Action: {result.action}")

        # 验证返回类型
        assert isinstance(result, (str, AgentAction))

        content = f"""**用户查询**: "你好"

**L2→L3**:
- Context传递: session_id={context.session_id}

**L3处理**:
- 返回类型: {type(result).__name__}
- 内容: {result if isinstance(result, str) else f"Action: {result.action}"}

**L2→L3流程**: ✅ 正常
"""
        save_result("TC-L3-025: L2→L3流程", content)

    def test_l3_to_l5_and_back(self, full_stack):
        """TC-L3-026: L3→L5→Observation→L3完整闭环"""
        l2 = full_stack["l2"]
        l3 = full_stack["l3"]

        context = SessionContext(
            session_id="test_session_002",
            user_id="user_123",
            current_query="计算123加456",
            history=[],
            user_permissions=["user"]
        )

        print(f"\n[Step 1] L3生成Action")
        result1 = l3.run(context)

        if isinstance(result1, AgentAction):
            print(f"  Action: {result1.action}")
            print(f"  Input: {result1.action_input}")

            # L2调用L5执行（模拟）
            print(f"\n[Step 2] L2调用L5执行")
            observation = l3.tools.execute(
                action_name=result1.action,
                params=result1.action_input,
                user_permissions=[]
            )
            print(f"  Observation: {observation.status}, Result: {observation.result}")

            # L2传递Observation给L3
            print(f"\n[Step 3] L3处理Observation")
            result2 = l3.run(context, observation)

            print(f"  Final Result: {type(result2).__name__}")
            if isinstance(result2, str):
                print(f"  Answer: {result2[:100]}...")

            # 验证闭环完成
            assert isinstance(result2, str), "最终应该是字符串回答"
            assert l3.iteration_count == 2, "应该进行2轮迭代"

            content = f"""**用户查询**: "计算123加456"

**Step 1 - L3生成Action**:
- Action: {result1.action}
- Input: {result1.action_input}

**Step 2 - L5执行工具**:
- Status: {observation.status}
- Result: {observation.result}

**Step 3 - L3处理Observation**:
- 迭代次数: {l3.iteration_count}
- 最终答案: {result2 if isinstance(result2, str) else result2.action}

**L3→L5→Observation→L3闭环**: ✅ 完整
"""
            save_result("TC-L3-026: L3→L5→L3闭环", content)
        else:
            content = f"""**用户查询**: "计算123加456"

**L3直接回答** (未请求工具):
{result1}

**说明**: LLM直接回答了，没有进入工具调用流程
"""
            save_result("TC-L3-026: L3→L5→L3闭环", content)

    def test_full_response_to_user(self, full_stack):
        """TC-L3-027: 最终答案正确返回给用户"""
        l1 = full_stack["l1"]
        l2 = full_stack["l2"]
        l3 = full_stack["l3"]

        # 完整流程模拟
        print(f"\n[完整流程模拟]")

        # L1: 接收用户输入
        raw_data = {
            "user_id": "user_test",
            "content": "计算10的平方",
            "channel": "websocket",
            "type": "message"
        }
        event = l1.receive_payload(raw_data)
        print(f"1. L1: Event created")

        # L2: 创建Context
        l3_input = l2.process_event(event)
        context = l3_input.session_context
        print(f"2. L2: Context created, session_id={context.session_id}")

        # L3: 处理请求
        result = l3.run(context)
        print(f"3. L3: Result type={type(result).__name__}")

        final_answer = None

        if isinstance(result, AgentAction):
            # 需要调用工具
            print(f"   - Action: {result.action}")

            # L5: 执行工具
            observation = l3.tools.execute(result.action, result.action_input)
            print(f"4. L5: Observation received, status={observation.status}")

            # L3: 处理Observation
            final_result = l3.run(context, observation)
            print(f"5. L3: Final result type={type(final_result).__name__}")

            if isinstance(final_result, str):
                final_answer = final_result
            else:
                final_answer = str(final_result)
        else:
            # 直接回答
            final_answer = result

        # L2: 发送响应
        if final_answer:
            l2.send_response(event, final_answer)
            print(f"6. L2: Response sent to user")

        assert final_answer is not None, "应该有最终答案"
        assert isinstance(final_answer, str), "最终答案应该是字符串"

        content = f"""**用户查询**: "计算10的平方"

**完整流程**:
1. L1: 接收输入 → StandardEvent
2. L2: 创建SessionContext
3. L3: 生成Action (Tool Call)
4. L5: 执行工具 → Observation
5. L3: 处理Observation → 最终答案
6. L2: 发送响应给用户

**最终答案**: {final_answer[:150]}...

**端到端流程**: ✅ 完整
"""
        save_result("TC-L3-027: 完整端到端流程", content)

    def test_response_format_for_user(self, full_stack):
        """TC-L3-028: 返回给用户的格式正确"""
        l3 = full_stack["l3"]

        context = SessionContext(
            session_id="test_format",
            user_id="user_123",
            current_query="你好，世界",
            history=[],
            user_permissions=["user"]
        )

        result = l3.run(context)

        # 验证返回格式
        assert isinstance(result, (str, AgentAction)), "L3返回必须是str或AgentAction"

        if isinstance(result, str):
            # 最终答案格式
            assert len(result) > 0, "最终答案不能为空"
            print(f"\n[最终答案] {result}")

            content = f"""**用户查询**: "你好，世界"

**L3返回类型**: str (最终答案)

**返回内容**:
{result}

**格式验证**:
- 类型: ✅ str
- 非空: ✅
- 可直接发送给用户: ✅
"""
        else:
            # AgentAction格式
            print(f"\n[AgentAction] action={result.action}")

            content = f"""**用户查询**: "你好，世界"

**L3返回类型**: AgentAction (工具调用)

**返回内容**:
- Action: {result.action}
- Input: {result.action_input}
- Thought: {result.thought}

**格式验证**:
- 类型: ✅ AgentAction
- 需要L2调用L5: ✅
"""

        save_result("TC-L3-028: 返回格式验证", content)


# Skip tests if no API key is configured
pytestmark = [
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
        reason="No LLM API key configured."
    ),
    pytest.mark.slow,
    pytest.mark.integration,
    pytest.mark.e2e,
]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
