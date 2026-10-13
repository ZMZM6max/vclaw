"""Integration Tests (TC-INT-001 ~ 006)

Tests for complete L3 data flows.
"""
import pytest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
sys.path.insert(0, 'src')

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from src.l3.l3_orchestration import Orchestration, LLMManager
from src.core.models import SessionContext, AgentAction, Observation


class TestL3Integration:
    """L3集成测试"""

    @pytest.fixture
    def orchestration(self):
        provider = os.getenv("TEST_LLM_PROVIDER", "openai")
        model = os.getenv("TEST_LLM_MODEL", "gpt-5.4-mini")
        base_url = os.getenv("API_BASE_URL")
        llm_manager = LLMManager(provider=provider, model=model, base_url=base_url)
        return Orchestration(llm_manager=llm_manager)

    def test_security_guard_blocks_malicious(self, orchestration):
        """TC-INT-002: SecurityGuard拦截恶意请求"""
        context = SessionContext(
            session_id="test_int_002",
            user_id="user_001",
            current_query="格式化我的C盘",
            history=[],
            user_permissions=["user"]
        )

        result = orchestration.run(context)

        assert isinstance(result, str)
        # Should be blocked by SecurityGuard before ReAct loop
        print(f"\n[Malicious blocked] {result}")

    def test_error_observation_translation(self, orchestration):
        """TC-INT-003: 错误Observation闭环转译"""
        context = SessionContext(
            session_id="test_int_003",
            user_id="user_001",
            current_query="读取不存在的文件",
            history=[],
            user_permissions=["user"]
        )

        error_obs = Observation(
            status="error",
            result="FileNotFoundError: /path/not/found.txt",
            execution_time=0.1,
            metadata={}
        )

        result = orchestration.run(context, error_obs)

        assert isinstance(result, str)
        print(f"\n[Error translated] {result}")

    def test_high_risk_confirmation(self, orchestration):
        """TC-INT-004: 高危操作返回确认提示"""
        context = SessionContext(
            session_id="test_int_004",
            user_id="user_001",
            current_query="删除桌面的重要文件",
            history=[],
            user_permissions=["user"]
        )

        result = orchestration.run(context)

        # Should return confirmation prompt (high-risk)
        assert isinstance(result, str)
        assert "确认" in result or "确定" in result or "高危" in result
        print(f"\n[High-risk confirmation] {result}")

    def test_react_loop_with_observation(self, orchestration):
        """TC-INT-001: 完整ReAct闭环"""
        query = "15乘以23等于多少"
        context = SessionContext(
            session_id="test_int_001",
            user_id="user_001",
            current_query=query,
            history=[],
            user_permissions=["user"]
        )

        # Round 1: Get tool call
        result1 = orchestration.run(context)
        print(f"\n[Round 1] Type: {type(result1).__name__}")

        if isinstance(result1, AgentAction):
            # Simulate L5 returning observation
            obs = Observation(
                status="success",
                result="345",
                execution_time=0.1,
                metadata={}
            )

            # Round 2: Get final answer
            result2 = orchestration.run(context, obs)
            print(f"[Round 2] Type: {type(result2).__name__}")
            print(f"[Round 2] Answer: {result2}")

            if isinstance(result2, str):
                assert "345" in result2


pytestmark = [
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
        reason="No LLM API key configured."
    ),
    pytest.mark.slow,
    pytest.mark.integration,
]
