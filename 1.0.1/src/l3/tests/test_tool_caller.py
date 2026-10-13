"""ToolCaller Tests (TC-TC-001 ~ 004)

Mock-based tests for ToolCaller component.
"""
import pytest
import sys
sys.path.insert(0, 'src')

from unittest.mock import MagicMock
from src.l3.l3_orchestration import ToolCaller
from src.core.models import AgentAction, Observation
from src.core.exceptions import ToolNotFoundError


class TestToolCaller:
    """ToolCaller单元测试"""

    @pytest.fixture
    def mock_tools(self):
        """Create mock ToolsInterface."""
        tools = MagicMock()
        tools.execute.return_value = Observation(
            status="success",
            result="42",
            execution_time=0.1,
            metadata={}
        )
        tools.get_available_tools.return_value = [
            {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "数学计算",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]
        return tools

    def test_call_tool_success(self, mock_tools):
        """TC-TC-001: 成功调用工具返回Observation"""
        caller = ToolCaller(tools=mock_tools)
        action = AgentAction(
            action="calculator",
            action_input={"expression": "1+1"}
        )

        result = caller.call_tool(action)

        assert isinstance(result, Observation)
        assert result.status == "success"
        assert result.result == "42"
        mock_tools.execute.assert_called_once_with("calculator", {"expression": "1+1"})

    def test_call_tool_not_found(self, mock_tools):
        """TC-TC-002: 工具不存在返回错误Observation"""
        mock_tools.execute.side_effect = ToolNotFoundError("nonexistent")

        caller = ToolCaller(tools=mock_tools)
        action = AgentAction(action="nonexistent", action_input={})

        result = caller.call_tool(action)

        assert isinstance(result, Observation)
        assert result.status == "error"
        assert result.metadata.get("error_type") == "ToolNotFoundError"
        assert result.metadata.get("source") == "ToolCaller"

    def test_call_tool_permission_error(self, mock_tools):
        """TC-TC-003: 权限不足返回错误Observation"""
        mock_tools.execute.side_effect = Exception("PermissionError: access denied")

        caller = ToolCaller(tools=mock_tools)
        action = AgentAction(action="admin_tool", action_input={})

        result = caller.call_tool(action)

        assert result.status == "error"
        assert "PermissionError" in result.result

    def test_format_tools_for_llm(self, mock_tools):
        """TC-TC-004: 格式化工具列表为OpenAI格式"""
        caller = ToolCaller(tools=mock_tools)
        tools = caller.format_tools_for_llm()

        assert isinstance(tools, list)
        assert len(tools) > 0
        assert tools[0]["type"] == "function"
        assert "function" in tools[0]
        assert "name" in tools[0]["function"]
