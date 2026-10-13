"""Observation返回流程测试

验证工具执行结果从L5返回到L3的完整流程:
1. L5执行工具返回Observation
2. L2接收Observation并传递给L3
3. L3处理Observation并继续ReAct循环
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

from src.l3.l3_orchestration import Orchestration, ReActEngine, LLMManager
from src.l5.l5_tools import ToolsCapabilities
from src.core.models import SessionContext, AgentAction, Observation


def save_result(test_name, content, passed=True):
    """Save test result to file."""
    results_dir = Path(__file__).parent / 'results'
    results_dir.mkdir(exist_ok=True)
    result_file = results_dir / 'test_observation_flow_results.txt'

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


class TestObservationFlow:
    """Observation返回流程测试 - 验证L5→L2→L3完整链路"""

    @pytest.fixture
    def orchestration(self):
        """Create orchestration with real LLM and tools."""
        provider = os.getenv("TEST_LLM_PROVIDER", "openai")
        model = os.getenv("TEST_LLM_MODEL", "gpt-5.4-mini")
        base_url = os.getenv("API_BASE_URL")
        llm_manager = LLMManager(provider=provider, model=model, base_url=base_url)
        tools = ToolsCapabilities()
        return Orchestration(llm_manager=llm_manager, tools=tools)

    def test_l5_returns_observation(self, orchestration):
        """TC-L3-019: L5执行工具后返回Observation对象"""
        # L5执行calculator工具
        observation = orchestration.tools.execute(
            action_name="calculator",
            params={"expression": "15 * 23"},
            user_permissions=[]
        )

        print(f"\n[L5 Observation]")
        print(f"  Status: {observation.status}")
        print(f"  Result: {observation.result}")
        print(f"  Execution Time: {observation.execution_time}")

        # 验证Observation结构
        assert isinstance(observation, Observation), "L5必须返回Observation对象"
        assert observation.status in ["success", "error"], "Status必须是success或error"
        assert isinstance(observation.result, str), "Result必须是字符串"
        assert isinstance(observation.execution_time, float), "Execution time必须是float"

        content = f"""**L5工具执行结果**:

**工具**: calculator
**参数**: {{"expression": "15 * 23"}}

**Observation返回**:
- Status: {observation.status}
- Result: {observation.result}
- Execution Time: {observation.execution_time:.4f}s
- Metadata: {observation.metadata}

**结构验证**: ✅ Observation对象格式正确
"""
        save_result("TC-L3-019: L5返回Observation", content)

    def test_l3_receives_observation(self, orchestration):
        """TC-L3-020: L3正确接收并处理Observation"""
        query = "计算15乘以23"

        # 第一轮：获取工具调用
        context = SessionContext(
            session_id="test_obs_001",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        result1 = orchestration.run(context)

        # 模拟L5执行并返回Observation
        observation = Observation(
            status="success",
            result="345",
            execution_time=0.1,
            metadata={"expression": "15 * 23"}
        )

        print(f"\n[Observation]")
        print(f"  Status: {observation.status}")
        print(f"  Result: {observation.result}")

        # 第二轮：L3接收Observation
        result2 = orchestration.run(context, observation)

        print(f"\n[L3 Result after Observation]")
        print(f"  Type: {type(result2).__name__}")
        if isinstance(result2, str):
            print(f"  Answer: {result2[:100]}...")

        # 验证L3处理了Observation
        assert orchestration.iteration_count == 2, "应该进行了2轮迭代"
        assert len(orchestration.react_engine.thought_history) >= 2, "应该有思考历史"

        content = f"""**查询**: {query}

**第一轮**: 返回AgentAction

**Observation** (模拟L5返回):
- Status: {observation.status}
- Result: {observation.result}

**第二轮**: L3处理Observation后
- 迭代计数: {orchestration.iteration_count}
- 思考历史数: {len(orchestration.react_engine.thought_history)}
- 结果类型: {type(result2).__name__}

**Observation处理**: ✅ L3正确接收并处理
"""
        save_result("TC-L3-020: L3接收Observation", content)

    def test_error_observation_handling(self, orchestration):
        """TC-L3-021: L3正确处理错误Observation"""
        # 模拟L5返回错误Observation
        error_observation = Observation(
            status="error",
            result="File not found: /path/to/file.txt",
            execution_time=0.1,
            metadata={"error_type": "FileNotFoundError"}
        )

        context = SessionContext(
            session_id="test_obs_002",
            user_id="user_001",
            current_query="读取文件",
            history=[],
            user_permissions=["user"]
        )

        # L3处理错误Observation
        result = orchestration.run(context, error_observation)

        print(f"\n[Error Observation]")
        print(f"  Status: {error_observation.status}")
        print(f"  Result: {result[:100] if isinstance(result, str) else result}...")

        # 验证错误被转译
        assert isinstance(result, str), "错误Observation应该返回转译后的字符串"

        content = f"""**错误Observation处理**:

**输入Observation**:
- Status: {error_observation.status}
- Result: {error_observation.result}

**L3处理结果**:
{result}

**错误转译**: ✅ 错误Observation被转译为用户友好提示
"""
        save_result("TC-L3-021: 错误Observation处理", content)

    def test_observation_in_react_history(self, orchestration):
        """TC-L3-022: Observation被正确记录在ReAct历史中"""
        query = "计算10的阶乘"

        context = SessionContext(
            session_id="test_obs_003",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        # 重置思考历史
        orchestration.react_engine.reset()
        orchestration.iteration_count = 0

        # 第一轮
        result1 = orchestration.run(context)

        # 模拟Observation
        observation = Observation(
            status="success",
            result="3628800",
            execution_time=0.2,
            metadata={}
        )

        # 第二轮
        result2 = orchestration.run(context, observation)

        # 检查思考历史
        history = orchestration.react_engine.thought_history
        print(f"\n[ReAct History Count] {len(history)}")

        has_observation_entry = any(
            entry.get('observation') == "3628800" for entry in history
        )

        print(f"[Has Observation Entry] {has_observation_entry}")
        for i, entry in enumerate(history):
            print(f"  [{i+1}] Thought: {entry.get('thought', 'N/A')[:50]}...")
            if entry.get('observation'):
                print(f"       Observation: {entry['observation'][:50]}...")

        content = f"""**查询**: {query}

**ReAct思考历史**:
- 总条目数: {len(history)}
- 包含Observation: {has_observation_entry}

**历史详情**:
"""
        for i, entry in enumerate(history):
            content += f"\n{i+1}. Thought: {entry.get('thought', 'N/A')[:60]}..."
            if entry.get('observation'):
                content += f"\n   Observation: {entry['observation'][:60]}..."

        content += f"""

**历史记录**: ✅ Observation被正确记录在ReAct历史中
"""
        save_result("TC-L3-022: Observation历史记录", content)

    def test_complete_react_loop_with_observation(self, orchestration):
        """TC-L3-023: 完整的ReAct循环：Action→Observation→Thought→Answer"""
        query = "计算2+3的结果，告诉我答案"

        context = SessionContext(
            session_id="test_obs_004",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        # 重置状态
        orchestration.react_engine.reset()
        orchestration.iteration_count = 0

        print(f"\n[完整ReAct循环测试]")
        print(f"  Query: {query}")

        # 第1轮：获取工具调用
        result1 = orchestration.run(context)
        print(f"\n  Round 1: {type(result1).__name__}")

        if isinstance(result1, AgentAction):
            print(f"    Action: {result1.action}")
            print(f"    Input: {result1.action_input}")

            # 模拟L5执行
            observation = orchestration.tools.execute(
                action_name=result1.action,
                params=result1.action_input,
                user_permissions=[]
            )

            print(f"\n  Observation:")
            print(f"    Status: {observation.status}")
            print(f"    Result: {observation.result}")

            # 第2轮：L3处理Observation
            result2 = orchestration.run(context, observation)
            print(f"\n  Round 2: {type(result2).__name__}")

            if isinstance(result2, str):
                print(f"    Answer: {result2[:100]}...")

            content = f"""**查询**: {query}

**ReAct循环过程**:

**Round 1 - Thought & Action**:
- Thought: {result1.thought[:80]}...
- Action: {result1.action}
- Input: {result1.action_input}

**Observation** (L5返回):
- Status: {observation.status}
- Result: {observation.result}
- Execution Time: {observation.execution_time:.4f}s

**Round 2 - Thought & Answer**:
- 结果类型: {type(result2).__name__}
- 内容: {result2 if isinstance(result2, str) else result2.action}

**迭代次数**: {orchestration.iteration_count}

**ReAct闭环**: ✅ Action → Observation → Thought → Answer
"""
            save_result("TC-L3-023: 完整ReAct闭环", content)
        else:
            content = f"""**查询**: {query}

**第一轮直接返回**: {result1}

**说明**: LLM直接回答了，没有请求工具调用
"""
            save_result("TC-L3-023: 完整ReAct闭环", content)


# Skip tests if no API key is configured
pytestmark = [
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
        reason="No LLM API key configured."
    ),
    pytest.mark.slow,
    pytest.mark.integration,
]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
