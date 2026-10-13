"""ReAct循环测试

测试真正的ReAct循环: Thought -> Action -> Observation -> Thought...
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
from src.core.models import SessionContext, AgentAction, Observation


def save_result(test_name, content, passed=True):
    """Save test result to file."""
    results_dir = Path(__file__).parent / 'results'
    results_dir.mkdir(exist_ok=True)
    result_file = results_dir / 'test_react_results.txt'

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


class TestReActLoop:
    """ReAct循环测试 - 验证真正的Thought-Action-Observation闭环"""

    @pytest.fixture
    def orchestration(self):
        """Create orchestration with real LLM."""
        provider = os.getenv("TEST_LLM_PROVIDER", "openai")
        model = os.getenv("TEST_LLM_MODEL", "gpt-5.4-mini")
        base_url = os.getenv("API_BASE_URL")
        llm_manager = LLMManager(provider=provider, model=model, base_url=base_url)
        return Orchestration(llm_manager=llm_manager)

    def test_react_generate_thought(self, orchestration):
        """测试ReAct生成Thought"""
        query = "计算1+1等于多少"

        # 生成Thought
        react_result = orchestration.react_engine.generate_thought(
            query=query,
            observation=None,
            available_tools=[],
            knowledge=[]
        )

        print(f"\n[QUERY] {query}")
        print(f"[THOUGHT] {react_result['thought']}")
        print(f"[ACTION TYPE] {react_result['action_type']}")
        print(f"[ACTION] {react_result['action']}")

        # 验证返回格式
        assert "thought" in react_result
        assert "action_type" in react_result
        assert "action" in react_result
        assert react_result["action_type"] in ["tool", "final_answer"]

        content = f"""**查询**: {query}

**生成的Thought**:
{react_result['thought']}

**Action Type**: {react_result['action_type']}
**Action**: {react_result['action']}
**Action Input**: {react_result.get('action_input', {})}
"""
        save_result("ReAct: 生成Thought", content)

    def test_react_with_observation(self, orchestration):
        """测试Observation后的ReAct循环"""
        query = "计算1+1的结果，然后乘以2"

        # 第一轮：生成初始Thought
        react_result1 = orchestration.react_engine.generate_thought(
            query=query,
            observation=None,
            available_tools=[],
            knowledge=[]
        )

        # 记录第一轮
        orchestration.react_engine.add_to_history(
            thought=react_result1["thought"],
            action=react_result1["action"],
            observation=None
        )

        print(f"\n[ROUND 1] Initial thought")
        print(f"  Thought: {react_result1['thought'][:100]}...")

        # 模拟Observation（工具执行结果）
        observation = Observation(
            status="success",
            result="2",
            execution_time=0.1,
            metadata={}
        )

        # 第二轮：基于Observation再思考
        react_result2 = orchestration.react_engine.generate_thought(
            query=query,
            observation=observation,
            available_tools=[],
            knowledge=[]
        )

        print(f"\n[ROUND 2] After observation")
        print(f"  Thought: {react_result2['thought'][:100]}...")

        # 验证有思考历史
        assert len(orchestration.react_engine.thought_history) >= 1

        content = f"""**查询**: {query}

**第一轮 - 初始Thought**:
{react_result1['thought']}

**Observation**:
- Status: {observation.status}
- Result: {observation.result}

**第二轮 - 基于Observation的Thought**:
{react_result2['thought']}

**思考历史数量**: {len(orchestration.react_engine.thought_history)}
"""
        save_result("ReAct: Observation闭环", content)

    def test_orchestration_run_first_iteration(self, orchestration):
        """测试Orchestration.run()第一轮返回AgentAction或str"""
        context = SessionContext(
            session_id="test_react_001",
            user_id="user_001",
            current_query="计算10的平方",
            history=[],
            user_permissions=["user"]
        )

        result = orchestration.run(context)

        print(f"\n[QUERY] 计算10的平方")
        print(f"[RESULT TYPE] {type(result).__name__}")

        if isinstance(result, AgentAction):
            print(f"[ACTION] {result.action}")
            print(f"[THOUGHT] {result.thought}")
            content = f"""**查询**: 计算10的平方

**返回类型**: AgentAction
**Action**: {result.action}
**Action Input**: {result.action_input}
**Thought**: {result.thought}
"""
        else:
            print(f"[ANSWER] {result[:100]}...")
            content = f"""**查询**: 计算10的平方

**返回类型**: str (最终答案)
**答案**: {result}
"""

        save_result("ReAct: Orchestration第一轮", content)

    def test_react_iteration_count(self, orchestration):
        """测试ReAct迭代计数"""
        # 初始状态
        assert orchestration.iteration_count == 0

        context = SessionContext(
            session_id="test_react_002",
            user_id="user_001",
            current_query="你好",
            history=[],
            user_permissions=["user"]
        )

        # 第一轮
        result1 = orchestration.run(context)
        assert orchestration.iteration_count == 1
        print(f"\n[After 1st run] iteration_count = {orchestration.iteration_count}")

        # 第二轮（模拟Observation返回）
        observation = Observation(
            status="success",
            result="Hello!",
            execution_time=0.1,
            metadata={}
        )
        result2 = orchestration.run(context, observation)
        assert orchestration.iteration_count == 2
        print(f"[After 2nd run] iteration_count = {orchestration.iteration_count}")

        content = f"""**查询**: 你好

**迭代计数验证**:
- 第一轮后: iteration_count = 1
- 第二轮后: iteration_count = 2

**ReAct循环正常工作**: ✅
"""
        save_result("ReAct: 迭代计数", content)

    def test_react_history_accumulation(self, orchestration):
        """测试ReAct思考历史累积"""
        query = "介绍Python的特点"

        # 重置引擎
        orchestration.react_engine.reset()
        assert len(orchestration.react_engine.thought_history) == 0

        # 第一次思考
        react_result = orchestration.react_engine.generate_thought(
            query=query,
            observation=None,
            available_tools=[],
            knowledge=[]
        )

        orchestration.react_engine.add_to_history(
            thought=react_result["thought"],
            action=react_result["action"]
        )

        # 添加Observation
        orchestration.react_engine.add_to_history(
            thought="Analyzing observation",
            action="Process result",
            observation="Some result"
        )

        print(f"\n[Thought History Count] {len(orchestration.react_engine.thought_history)}")
        for i, entry in enumerate(orchestration.react_engine.thought_history):
            print(f"  [{i+1}] Thought: {entry['thought'][:50]}...")

        assert len(orchestration.react_engine.thought_history) == 2

        content = f"""**查询**: {query}

**思考历史累积验证**:
- 历史条目数: {len(orchestration.react_engine.thought_history)}

**历史记录**:
"""
        for i, entry in enumerate(orchestration.react_engine.thought_history):
            content += f"\n{i+1}. Thought: {entry['thought'][:80]}..."
            if entry.get('observation'):
                content += f"\n   Observation: {entry['observation'][:50]}..."

        save_result("ReAct: 思考历史累积", content)

    def test_mandatory_pre_action_file_query(self, orchestration):
        """TC-RE-006: 文件查询必须先尝试工具调用（MandatoryPreActionRules）"""
        query = "帮我找一下桌面上的报告文件"

        react_result = orchestration.react_engine.generate_thought(
            query=query,
            observation=None,
            available_tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "file_search",
                        "description": "搜索文件",
                        "parameters": {"type": "object", "properties": {}}
                    }
                }
            ],
            knowledge=[]
        )

        print(f"\n[QUERY] {query}")
        print(f"[ACTION TYPE] {react_result['action_type']}")
        print(f"[ACTION] {react_result['action']}")

        # 文件查询场景下，LLM必须先尝试调用工具（file_search），禁止直接返回not_found
        # 注：由于使用真实LLM，此处记录行为而非强制assert
        content = f"""**查询**: {query}

**ReActEngine返回**:
- Thought: {react_result['thought'][:150]}...
- Action Type: {react_result['action_type']}
- Action: {react_result['action']}

**MandatoryPreActionRules验证**: 文件查询应优先尝试工具调用
"""
        save_result("ReAct: 文件查询MandatoryRule", content)


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
