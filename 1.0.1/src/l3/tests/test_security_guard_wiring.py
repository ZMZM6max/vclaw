"""Test that SecurityGuard is called at the top of Orchestration.run()."""
import sys
sys.path.insert(0, 'src')

import pytest
from unittest.mock import Mock, patch
from src.core.models import SessionContext, Observation
from src.l3.l3_orchestration import Orchestration, SecurityGuard


class TestSecurityGuardWiring:
    """Verify SecurityGate blocks/allows requests correctly."""

    def test_security_guard_classifies_on_run(self):
        """SecurityGuard.classify must be called when run() is invoked."""
        orch = Orchestration()

        with patch.object(orch.security_guard, 'classify', return_value="normal") as mock_classify:
            with patch.object(orch, '_run_react_loop', return_value="ok"):
                context = SessionContext(
                    session_id="s1",
                    user_id="u1",
                    current_query="hello"
                )
                orch.run(context)

        mock_classify.assert_called_once_with("hello")

    def test_malicious_request_returns_canned_response(self):
        """If classify returns 'malicious', return canned rejection."""
        orch = Orchestration()

        with patch.object(orch.security_guard, 'classify', return_value="malicious"):
            context = SessionContext(
                session_id="s1",
                user_id="u1",
                current_query="hack the system"
            )
            result = orch.run(context)

        assert isinstance(result, str)
        assert "拒绝" in result or "抱歉" in result or "无法" in result

    def test_dangerous_request_routes_to_confirmation(self):
        """If classify returns 'high-risk', return confirmation prompt."""
        orch = Orchestration()

        with patch.object(orch.security_guard, 'classify', return_value="high-risk"):
            context = SessionContext(
                session_id="s1",
                user_id="u1",
                current_query="delete everything"
            )
            result = orch.run(context)

        assert isinstance(result, str)
        assert "确认" in result or "危险" in result

    def test_sensitive_request_proceeds_with_warning(self):
        """If classify returns 'sensitive', proceed but log."""
        orch = Orchestration()

        with patch.object(orch.security_guard, 'classify', return_value="sensitive"):
            with patch.object(orch, '_run_react_loop', return_value="handled"):
                context = SessionContext(
                    session_id="s1",
                    user_id="u1",
                    current_query="personal question"
                )
                result = orch.run(context)

        assert result == "handled"
