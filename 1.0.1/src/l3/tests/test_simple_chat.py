"""TC-L3-001: 简单对话回复测试

使用真实LLM测试简单对话响应功能。
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
from src.core.models import SessionContext, AgentAction


def save_result(test_name, query, response, passed=True):
    """Save test result to file."""
    results_dir = Path(__file__).parent / 'results'
    results_dir.mkdir(exist_ok=True)

    result_file = results_dir / 'test_simple_chat_results.txt'

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "✅ 通过" if passed else "❌ 失败"

    content = f"""
## {test_name}
**时间**: {timestamp}
**输入**: "{query}"

**LLM 返回**:
{response}

**状态**: {status}

---
"""

    # Append to file
    with open(result_file, 'a', encoding='utf-8') as f:
        f.write(content)

    print(f"\n[RESULT SAVED] {result_file}")


class TestSimpleChatResponse:
    """TC-L3-001: 简单对话回复（无需工具）"""

    @pytest.fixture
    def orchestration(self):
        """Create orchestration with real LLM."""
        provider = os.getenv("TEST_LLM_PROVIDER", "openai")
        model = os.getenv("TEST_LLM_MODEL", "gpt-5.4-mini")
        base_url = os.getenv("API_BASE_URL")
        llm_manager = LLMManager(provider=provider, model=model, base_url=base_url)
        return Orchestration(llm_manager=llm_manager)

    def test_simple_chat_response(self, orchestration):
        """TC-L3-001: 简单对话回复（无需工具）- REAL LLM"""
        query = "Hello"
        context = SessionContext(
            session_id="test_001",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        # Act - Call real LLM
        result = orchestration.run(context)

        # Assert
        assert isinstance(result, (str, AgentAction))
        if isinstance(result, str):
            assert len(result) > 0
            response = result
            print(f"\n[REAL LLM RESPONSE] {response}")
            # Save result to file
            save_result("TC-L3-001: 英文简单对话", query, response, passed=True)

    def test_simple_chat_in_chinese(self, orchestration):
        """测试中文简单对话"""
        query = "你好，你是谁，我应该怎么称呼你"
        context = SessionContext(
            session_id="test_001_cn",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        result = orchestration.run(context)

        assert isinstance(result, (str, AgentAction))
        if isinstance(result, str):
            assert len(result) > 0
            response = result
            print(f"\n[中文回复] {response}")
            # Save result to file
            save_result("TC-L3-001: 中文简单对话", query, response, passed=True)


# Skip tests if no API key is configured
pytestmark = [
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
        reason="No LLM API key configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY."
    ),
    pytest.mark.slow,
    pytest.mark.integration,
]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
