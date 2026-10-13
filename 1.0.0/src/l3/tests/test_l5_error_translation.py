"""TC-L3-007: L5错误转译测试

测试LLM能否将L5工具错误转换为用户友好的中文提示。
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

from src.l3.l3_orchestration import Orchestration, LLMManager
from src.core.models import SessionContext, Observation


def save_result(test_name, query, error_type, response, passed=True):
    """Save test result to file."""
    results_dir = Path(__file__).parent / 'results'
    results_dir.mkdir(exist_ok=True)

    result_file = results_dir / 'test_l5_error_translation_results.txt'

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "✅ 通过" if passed else "❌ 失败"

    content = f"""
## {test_name}
**时间**: {timestamp}
**查询**: "{query}"
**错误类型**: {error_type}

**LLM 转译结果**:
{response}

**状态**: {status}

---
"""

    with open(result_file, 'a', encoding='utf-8') as f:
        f.write(content)

    print(f"\n[RESULT SAVED] {result_file}")


class TestL5ErrorTranslation:
    """TC-L3-007: L5错误转译为用户友好提示"""

    @pytest.fixture
    def orchestration(self):
        """Create orchestration with real LLM."""
        provider = os.getenv("TEST_LLM_PROVIDER", "openai")
        model = os.getenv("TEST_LLM_MODEL", "gpt-5.4-mini")
        base_url = os.getenv("API_BASE_URL")
        llm_manager = LLMManager(provider=provider, model=model, base_url=base_url)
        return Orchestration(llm_manager=llm_manager)

    def test_file_not_found_error(self, orchestration):
        """测试文件不存在错误的转译"""
        query = "读取一个不存在的文件"
        context = SessionContext(
            session_id="test_error_001",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        # Create error observation
        error_observation = Observation(
            status="error",
            result="File not found: /path/to/file.txt",
            execution_time=0.1,
            metadata={"error_type": "FileNotFoundError"}
        )

        # Act - Call real LLM for error translation
        result = orchestration.run(context, error_observation)

        # Assert
        assert isinstance(result, str)
        assert len(result) > 0
        print(f"\n[ERROR TYPE] FileNotFoundError")
        print(f"[TRANSLATED] {result}")
        save_result("TC-L3-007: 文件不存在错误转译", query, "FileNotFoundError", result, passed=True)

    def test_permission_error(self, orchestration):
        """测试权限错误转译"""
        query = "写入系统文件"
        context = SessionContext(
            session_id="test_error_002",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        error_observation = Observation(
            status="error",
            result="Permission denied: /etc/system.conf",
            execution_time=0.1,
            metadata={"error_type": "PermissionError"}
        )

        result = orchestration.run(context, error_observation)

        assert isinstance(result, str)
        assert len(result) > 0
        print(f"\n[ERROR TYPE] PermissionError")
        print(f"[TRANSLATED] {result}")
        save_result("TC-L3-007: 权限错误转译", query, "PermissionError", result, passed=True)

    def test_timeout_error(self, orchestration):
        """测试超时错误转译"""
        query = "执行耗时操作"
        context = SessionContext(
            session_id="test_error_003",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        error_observation = Observation(
            status="error",
            result="Execution timeout after 30 seconds",
            execution_time=30.0,
            metadata={"error_type": "TimeoutError"}
        )

        result = orchestration.run(context, error_observation)

        assert isinstance(result, str)
        assert len(result) > 0
        print(f"\n[ERROR TYPE] TimeoutError")
        print(f"[TRANSLATED] {result}")
        save_result("TC-L3-007: 超时错误转译", query, "TimeoutError", result, passed=True)


# Skip tests if no API key is configured
pytestmark = [
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
        reason="No LLM API key configured."
    ),
    pytest.mark.slow,
    pytest.mark.integration,
    pytest.mark.error_handling,
]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
