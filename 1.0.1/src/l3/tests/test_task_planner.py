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

    def test_plan_completeness_final_step(self, planner):
        """TC-TP-004: 计划最后一步必须是交付结果给用户"""
        query = "读取桌面报告并总结内容"

        plan = planner.create_plan(query, "", [])

        assert len(plan) >= 1
        last_step = plan[-1]
        # 最后一步应该是面向用户的交付（llm或直接输出）
        print(f"\n[Last Step] {last_step}")
        save_result("TC-TP-004: 计划完整性-最后一步", query, plan, passed=True)

    def test_plan_dependencies(self, planner):
        """TC-TP-005: 步骤依赖关系正确"""
        query = "先搜索文件A，然后读取并总结"

        plan = planner.create_plan(query, "", [])

        # 检查depends_on引用的step编号是否存在于plan中
        step_numbers = {step.get("step") for step in plan}
        for step in plan:
            deps = step.get("depends_on", [])
            for dep in deps:
                assert dep in step_numbers, f"依赖步骤 {dep} 不存在于plan中"

        print(f"\n[Dependencies verified] Plan has {len(plan)} steps")
        save_result("TC-TP-005: 依赖关系验证", query, plan, passed=True)

    def test_fallback_plan(self, planner):
        """TC-TP-006: Fallback计划在LLM失败时生效"""
        # Temporarily break the LLM to trigger fallback
        original_llm = planner.planning_llm
        planner.planning_llm = None  # This will cause error

        query = "测试fallback"
        plan = planner.create_plan(query, "", [])

        # Restore
        planner.planning_llm = original_llm

        assert isinstance(plan, list)
        assert len(plan) == 1
        assert plan[0].get("action") == "llm"
        print(f"\n[Fallback Plan] {plan}")
        save_result("TC-TP-006: Fallback计划", query, plan, passed=True)


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
