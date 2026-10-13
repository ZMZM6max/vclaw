"""任务规划测试

使用真实LLM测试任务规划功能。
"""
import pytest
import os
import sys
import json
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

from src.l3.l3_orchestration import TaskPlanner, LLMManager


def save_result(test_name, query, plan, passed=True):
    """Save test result to file."""
    results_dir = Path(__file__).parent / 'results'
    results_dir.mkdir(exist_ok=True)

    result_file = results_dir / 'test_task_planner_results.txt'

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "✅ 通过" if passed else "❌ 失败"

    plan_str = json.dumps(plan, ensure_ascii=False, indent=2) if isinstance(plan, list) else str(plan)

    content = f"""
## {test_name}
**时间**: {timestamp}
**查询**: "{query}"

**生成计划**:
```json
{plan_str}
```

**状态**: {status}

---
"""

    with open(result_file, 'a', encoding='utf-8') as f:
        f.write(content)

    print(f"\n[RESULT SAVED] {result_file}")


class TestTaskPlanner:
    """任务规划器测试"""

    @pytest.fixture
    def planner(self):
        """Create task planner with real LLM."""
        provider = os.getenv("TEST_LLM_PROVIDER", "openai")
        model = os.getenv("TEST_LLM_MODEL", "gpt-5.4-mini")
        base_url = os.getenv("API_BASE_URL")
        llm_manager = LLMManager(provider=provider, model=model, base_url=base_url)
        return TaskPlanner(llm_manager=llm_manager)

    def test_create_simple_plan(self, planner):
        """测试创建简单任务计划"""
        query = "计算斐波那契数列前10项"

        plan = planner.create_plan(query, "", [])

        assert isinstance(plan, list)
        assert len(plan) >= 1
        print(f"\n[QUERY] {query}")
        print(f"[PLAN] {plan}")
        save_result("TC-L3-005: 简单任务计划", query, plan, passed=True)

    def test_create_math_plan(self, planner):
        """测试数学计算任务规划"""
        query = "1+1等于几"

        plan = planner.create_plan(query, "", [])

        assert isinstance(plan, list)
        assert len(plan) >= 1
        print(f"\n[QUERY] {query}")
        print(f"[PLAN] {plan}")
        save_result("TC-L3-005: 数学计算任务规划", query, plan, passed=True)

    def test_create_file_operation_plan(self, planner):
        """测试文件操作任务规划"""
        query = "在桌面创建一个hello.txt文件"

        plan = planner.create_plan(query, "", [])

        assert isinstance(plan, list)
        assert len(plan) >= 1
        print(f"\n[QUERY] {query}")
        print(f"[PLAN] {plan}")
        save_result("TC-L3-005: 文件操作任务规划", query, plan, passed=True)


# Skip tests if no API key is configured
pytestmark = [
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
        reason="No LLM API key configured."
    ),
    pytest.mark.slow,
    pytest.mark.integration,
    pytest.mark.planning,
]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
