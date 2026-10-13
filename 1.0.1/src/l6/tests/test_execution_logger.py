"""Test ExecutionLogger integration in L6 RuntimeEnvironment."""
import sys
sys.path.insert(0, 'src')

from unittest.mock import Mock, patch
from src.l6.runtime_environment import RuntimeEnvironment
from src.l6.execution_logger import ExecutionLogger


class TestExecutionLoggerWiring:
    """Verify ExecutionLogger is wired and called after code execution."""

    def test_execution_logger_instantiated(self):
        """RuntimeEnvironment must create an ExecutionLogger instance."""
        runtime = RuntimeEnvironment()
        assert runtime.execution_logger is not None
        assert hasattr(runtime.execution_logger, 'log')
        assert hasattr(runtime.execution_logger, 'get_logs')

    def test_log_called_after_successful_run(self):
        """A successful run_code must call execution_logger.log()."""
        runtime = RuntimeEnvironment()
        runtime.execution_logger = Mock()
        runtime.execution_logger.log = Mock()

        with patch.object(runtime.sandbox, 'create', return_value='env_123'):
            with patch.object(
                runtime.sandbox, 'execute',
                return_value=Mock(
                    exit_code=0, stdout="ok", stderr="",
                    execution_time=0.1,
                    resource_usage={"memory_peak_mb": 64.0, "cpu_time_ms": 12.0}
                )
            ):
                with patch.object(runtime.sandbox, 'destroy'):
                    runtime.run_code("python", "print('hello')", timeout=5)

        runtime.execution_logger.log.assert_called_once()
        call_kwargs = runtime.execution_logger.log.call_args[1]
        assert call_kwargs['status'] == 'success'
        assert call_kwargs['resource_usage'] == {
            "memory_peak_mb": 64.0, "cpu_time_ms": 12.0
        }

    def test_log_called_after_failed_run(self):
        """A failed run_code (non-zero exit) must log status='error'."""
        runtime = RuntimeEnvironment()
        runtime.execution_logger = Mock()
        runtime.execution_logger.log = Mock()

        with patch.object(runtime.sandbox, 'create', return_value='env_456'):
            with patch.object(
                runtime.sandbox, 'execute',
                return_value=Mock(
                    exit_code=1, stdout="", stderr="SyntaxError",
                    execution_time=0.05,
                    resource_usage={"memory_peak_mb": 32.0, "cpu_time_ms": 5.0}
                )
            ):
                with patch.object(runtime.sandbox, 'destroy'):
                    runtime.run_code("python", "bad syntax", timeout=5)

        runtime.execution_logger.log.assert_called_once()
        call_kwargs = runtime.execution_logger.log.call_args[1]
        assert call_kwargs['status'] == 'error'

    def test_resource_usage_populated_in_result(self):
        """ExecutionResult from sandbox must contain resource_usage keys."""
        from src.l6.docker_sandbox import DockerSandbox
        from src.l6.config import SandboxConfig

        config = SandboxConfig()
        sandbox = DockerSandbox(config)

        # Mock controller to avoid real Docker
        sandbox.controller = Mock()
        sandbox.controller.create_container.return_value = "container_123"
        sandbox.controller.exec_in_container.return_value = (
            0, "hello", ""
        )
        sandbox.controller.get_container_stats.return_value = {
            "memory_peak_mb": 64.0, "cpu_time_ms": 12.0
        }
        sandbox.controller.remove_container.return_value = True

        env_id = sandbox.create("env_test")
        result = sandbox.execute(env_id, "python", "print('hello')")

        assert "memory_peak_mb" in result.resource_usage
        assert "cpu_time_ms" in result.resource_usage
        sandbox.destroy(env_id)


class TestExecutionLoggerUnit:
    """Standalone unit tests for ExecutionLogger (EL_001~005)."""

    def test_el001_record_single_log(self):
        """EL_001: Record and retrieve a single log entry."""
        logger = ExecutionLogger()
        logger.log(
            code_hash="abc",
            resource_usage={"memory_peak_mb": 10.0},
            status="success",
        )
        logs = logger.get_logs(limit=1)
        assert len(logs) == 1
        assert logs[0]["code_hash"] == "abc"
        assert logs[0]["status"] == "success"
        assert "timestamp" in logs[0]

    def test_el002_get_multiple_logs(self):
        """EL_002: Retrieve multiple logs in reverse chronological order."""
        logger = ExecutionLogger()
        logger.log(code_hash="a", resource_usage={}, status="success")
        logger.log(code_hash="b", resource_usage={}, status="error")
        logger.log(code_hash="c", resource_usage={}, status="success")
        logs = logger.get_logs(limit=2)
        assert len(logs) == 2
        assert logs[0]["code_hash"] == "c"
        assert logs[1]["code_hash"] == "b"

    def test_el003_clear_logs(self):
        """EL_003: Clear all logs."""
        logger = ExecutionLogger()
        logger.log(code_hash="x", resource_usage={}, status="success")
        logger.clear()
        logs = logger.get_logs()
        assert logs == []

    def test_el004_default_user_id(self):
        """EL_004: Default user_id is 'unknown'."""
        logger = ExecutionLogger()
        logger.log(code_hash="x", resource_usage={}, status="success")
        logs = logger.get_logs(1)
        assert logs[0]["user_id"] == "unknown"

    def test_el005_custom_user_id(self):
        """EL_005: Custom user_id is recorded."""
        logger = ExecutionLogger()
        logger.log(
            code_hash="x",
            resource_usage={},
            status="success",
            user_id="user_42",
        )
        logs = logger.get_logs(1)
        assert logs[0]["user_id"] == "user_42"
