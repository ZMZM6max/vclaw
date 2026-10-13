"""Unit tests for core interface contracts."""
import inspect
import sys
sys.path.insert(0, 'src')

from src.core.interfaces import RuntimeInterface, MemoryInterface, ToolsInterface


class TestRuntimeInterface:
    """Verify RuntimeInterface has all required methods."""

    def test_has_run_code(self):
        assert hasattr(RuntimeInterface, 'run_code')
        sig = inspect.signature(RuntimeInterface.run_code)
        params = list(sig.parameters.keys())
        assert 'language' in params
        assert 'code' in params
        assert 'timeout' in params

    def test_has_run_command(self):
        assert hasattr(RuntimeInterface, 'run_command')
        sig = inspect.signature(RuntimeInterface.run_command)
        params = list(sig.parameters.keys())
        assert 'command' in params
        assert 'timeout' in params

    def test_run_command_is_abstract(self):
        assert getattr(RuntimeInterface.run_command, '__isabstractmethod__', False)
