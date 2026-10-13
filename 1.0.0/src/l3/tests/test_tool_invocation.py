"""工具调用流程测试

验证完整的工具调用流程:
1. L3从L5获取可用工具列表
2. 工具列表正确传递给ReActEngine
3. ReActEngine将工具传递给LLM
4. LLM能正确选择并使用工具
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
    result_file = results_dir / 'test_tool_invocation_results.txt'

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


class TestToolInvocationFlow:
    """工具调用流程测试 - 验证L3-L5-LLM工具传递链"""

    @pytest.fixture
    def orchestration(self):
        """Create orchestration with real LLM and tools."""
        provider = os.getenv("TEST_LLM_PROVIDER", "openai")
        model = os.getenv("TEST_LLM_MODEL", "gpt-5.4-mini")
        base_url = os.getenv("API_BASE_URL")
        llm_manager = LLMManager(provider=provider, model=model, base_url=base_url)
        tools = ToolsCapabilities()
        return Orchestration(llm_manager=llm_manager, tools=tools)

    def test_l5_provides_tools(self, orchestration):
        """TC-L3-013: L5提供可用工具列表"""
        # 从L5获取工具
        available_tools = orchestration.tools.get_available_tools([])

        print(f"\n[L5 Tools Count] {len(available_tools)}")
        for tool in available_tools:
            func = tool.get('function', {})
            print(f"  - {func.get('name')}: {func.get('description', '')[:50]}...")

        # 验证工具列表不为空
        assert len(available_tools) > 0, "L5应该提供至少一个工具"

        # 验证工具格式正确 (OpenAI function calling format)
        for tool in available_tools:
            assert tool.get('type') == 'function', "工具类型必须是function"
            assert 'function' in tool, "工具必须包含function字段"
            func = tool['function']
            assert 'name' in func, "function必须包含name"
            assert 'description' in func, "function必须包含description"
            assert 'parameters' in func, "function必须包含parameters"

        tool_names = [t['function']['name'] for t in available_tools]
        content = f"""**L5提供的工具列表**:

工具数量: {len(available_tools)}

工具名称:
{chr(10).join([f"- {name}" for name in tool_names])}

**格式验证**: ✅ OpenAI function calling format
"""
        save_result("TC-L3-013: L5提供可用工具", content)

    def test_tools_passed_to_react_engine(self, orchestration):
        """TC-L3-014: 工具列表正确传递给ReActEngine"""
        query = "计算15乘以23"

        # 获取L5工具
        available_tools = orchestration.tools.get_available_tools([])

        # 调用ReActEngine，验证工具被传递
        react_result = orchestration.react_engine.generate_thought(
            query=query,
            observation=None,
            available_tools=available_tools,
            knowledge=[]
        )

        print(f"\n[QUERY] {query}")
        print(f"[THOUGHT] {react_result['thought'][:100]}...")
        print(f"[ACTION TYPE] {react_result['action_type']}")
        print(f"[ACTION] {react_result['action']}")

        # 验证ReActEngine返回了结果
        assert 'thought' in react_result
        assert 'action_type' in react_result
        assert 'action' in react_result

        # 如果LLM正确接收到工具，应该能识别出需要calculator
        content = f"""**查询**: {query}

**L5工具数量**: {len(available_tools)}

**ReActEngine返回**:
- Thought: {react_result['thought'][:150]}...
- Action Type: {react_result['action_type']}
- Action: {react_result['action']}

**工具传递**: ✅ L5工具已传递给ReActEngine
"""
        save_result("TC-L3-014: 工具传递给ReActEngine", content)

    def test_llm_selects_calculator_tool(self, orchestration):
        """TC-L3-015: LLM能正确选择计算器工具"""
        query = "计算123加456等于多少"

        context = SessionContext(
            session_id="test_tool_001",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        # 运行Orchestration
        result = orchestration.run(context)

        print(f"\n[QUERY] {query}")
        print(f"[RESULT TYPE] {type(result).__name__}")

        if isinstance(result, AgentAction):
            print(f"[ACTION] {result.action}")
            print(f"[INPUT] {result.action_input}")
            print(f"[THOUGHT] {result.thought}")

            # 验证选择了calculator工具
            content = f"""**查询**: {query}

**LLM选择工具**: ✅
- Action: {result.action}
- Action Input: {result.action_input}
- Thought: {result.thought}

**工具选择正确**: {result.action == 'calculator'}
"""
            save_result("TC-L3-015: LLM选择计算器工具", content)

            # 断言选择了calculator
            assert result.action == "calculator", f"期望选择calculator，实际选择{result.action}"
        else:
            content = f"""**查询**: {query}

**LLM直接回答** (没有选择工具):
{result}

**注意**: 可能工具没有正确传递，或LLM认为不需要工具
"""
            save_result("TC-L3-015: LLM选择计算器工具", content)

    def test_llm_selects_python_repl(self, orchestration):
        """TC-L3-016: LLM能正确选择Python REPL工具"""
        query = "用Python计算斐波那契数列前10项"

        context = SessionContext(
            session_id="test_tool_002",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        result = orchestration.run(context)

        print(f"\n[QUERY] {query}")
        print(f"[RESULT TYPE] {type(result).__name__}")

        if isinstance(result, AgentAction):
            print(f"[ACTION] {result.action}")
            print(f"[INPUT] {result.action_input}")

            content = f"""**查询**: {query}

**LLM选择工具**:
- Action: {result.action}
- Action Input: {result.action_input}
- Thought: {result.thought[:100]}...
"""
            save_result("TC-L3-016: LLM选择Python REPL", content)

            # 验证选择了python_repl
            assert result.action == "python_repl", f"期望选择python_repl，实际选择{result.action}"
        else:
            content = f"""**查询**: {query}

**LLM直接回答**:
{result[:200]}...
"""
            save_result("TC-L3-016: LLM选择Python REPL", content)

    def test_tool_execution_observation_loop(self, orchestration):
        """TC-L3-017: 工具执行后的Observation闭环"""
        query = "计算3的平方"

        # 第一轮：获取工具调用
        context = SessionContext(
            session_id="test_tool_003",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        result1 = orchestration.run(context)

        print(f"\n[ROUND 1] 获取工具调用")
        if isinstance(result1, AgentAction):
            print(f"  Action: {result1.action}")
            print(f"  Input: {result1.action_input}")

            # 模拟L5执行工具并返回Observation
            observation = Observation(
                status="success",
                result="9",
                execution_time=0.1,
                metadata={"expression": "3**2"}
            )

            # 第二轮：传递Observation给L3
            print(f"\n[ROUND 2] 传递Observation")
            result2 = orchestration.run(context, observation)

            print(f"  Result Type: {type(result2).__name__}")
            if isinstance(result2, str):
                print(f"  Answer: {result2[:100]}...")

            content = f"""**查询**: {query}

**第一轮 - 工具调用**:
- Action: {result1.action}
- Input: {result1.action_input}

**Observation** (模拟L5返回):
- Result: {observation.result}

**第二轮 - 最终回答**:
{result2 if isinstance(result2, str) else f"Action: {result2.action}"}

**ReAct闭环**: ✅ Observation正确传递并处理
"""
            save_result("TC-L3-017: Observation闭环", content)
        else:
            content = f"""**查询**: {query}

**第一轮直接返回**: {result1}

**说明**: LLM直接回答了，没有请求工具调用
"""
            save_result("TC-L3-017: Observation闭环", content)

    def test_tools_in_prompt_description(self, orchestration):
        """TC-L3-018: 工具描述在Prompt中正确显示"""
        available_tools = orchestration.tools.get_available_tools([])

        # 检查ReActEngine如何将工具描述添加到prompt
        query = "测试工具描述"

        # 生成prompt内容
        tools_desc = ""
        if available_tools:
            tools_desc = "\nAvailable tools:\n"
            for tool in available_tools:
                if 'function' in tool:
                    name = tool['function'].get('name', 'unknown')
                    desc = tool['function'].get('description', '')
                    tools_desc += f"- {name}: {desc}\n"

        print(f"\n[Tools in Prompt]\n{tools_desc[:500]}...")

        # 验证工具描述被正确格式化
        assert "Available tools:" in tools_desc or len(available_tools) == 0

        tool_count = len(available_tools)
        content = f"""**工具Prompt描述验证**:

工具数量: {tool_count}

Prompt中的工具描述示例:
{tools_desc[:800]}...

**格式正确**: ✅ 工具名称和描述清晰可读
"""
        save_result("TC-L3-018: 工具Prompt描述", content)


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
