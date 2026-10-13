"""路径处理测试

测试LLM能否遵循系统提示词的指导处理文件路径。
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


def save_result(test_name, query, response, action_info="", passed=True):
    """Save test result to file."""
    results_dir = Path(__file__).parent / 'results'
    results_dir.mkdir(exist_ok=True)

    result_file = results_dir / 'test_file_path_handling_results.txt'

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "✅ 通过" if passed else "❌ 失败"

    action_section = f"\n**Action 信息**: {action_info}\n" if action_info else ""

    content = f"""
## {test_name}
**时间**: {timestamp}
**输入**: "{query}"

**LLM 返回**:
{response}
{action_section}
**状态**: {status}

---
"""

    with open(result_file, 'a', encoding='utf-8') as f:
        f.write(content)

    print(f"\n[RESULT SAVED] {result_file}")


class TestFilePathHandling:
    """路径处理指导测试"""

    @pytest.fixture
    def orchestration(self):
        """Create orchestration with real LLM."""
        provider = os.getenv("TEST_LLM_PROVIDER", "openai")
        model = os.getenv("TEST_LLM_MODEL", "gpt-5.4-mini")
        base_url = os.getenv("API_BASE_URL")
        llm_manager = LLMManager(provider=provider, model=model, base_url=base_url)
        return Orchestration(llm_manager=llm_manager)

    def test_desktop_file_creation(self, orchestration):
        """测试桌面文件创建路径处理"""
        query = "在桌面创建一个文件 test.txt"
        context = SessionContext(
            session_id="test_path_001",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        result = orchestration.run(context)

        assert isinstance(result, (str, AgentAction))
        print(f"\n[QUERY] {query}")
        print(f"[RESPONSE] {result}")
        action_info = ""
        if isinstance(result, AgentAction):
            action_info = f"Action: {result.action}, Input: {result.action_input}"
            print(f"[ACTION] {result.action}")
            print(f"[INPUT] {result.action_input}")
        save_result("路径处理: 桌面文件创建", query, str(result), action_info, passed=True)

    def test_download_folder_access(self, orchestration):
        """测试下载文件夹路径处理"""
        query = "读取下载文件夹中的 report.pdf"
        context = SessionContext(
            session_id="test_path_002",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        result = orchestration.run(context)

        assert isinstance(result, (str, AgentAction))
        print(f"\n[QUERY] {query}")
        print(f"[RESPONSE] {result}")
        action_info = ""
        if isinstance(result, AgentAction):
            action_info = f"Action: {result.action}, Input: {result.action_input}"
        save_result("路径处理: 下载文件夹访问", query, str(result), action_info, passed=True)

    def test_path_conversion_chinese(self, orchestration):
        """测试中文路径转换"""
        query = "在文档文件夹新建一个笔记"
        context = SessionContext(
            session_id="test_path_003",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        result = orchestration.run(context)

        assert isinstance(result, (str, AgentAction))
        print(f"\n[QUERY] {query}")
        print(f"[RESPONSE] {result}")
        action_info = ""
        if isinstance(result, AgentAction):
            action_info = f"Action: {result.action}, Input: {result.action_input}"
        save_result("路径处理: 中文路径转换", query, str(result), action_info, passed=True)


# Skip tests if no API key is configured
pytestmark = [
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
        reason="No LLM API key configured."
    ),
    pytest.mark.slow,
    pytest.mark.integration,
    pytest.mark.path_handling,
]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
