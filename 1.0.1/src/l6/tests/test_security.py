"""Tests for SecurityEnforcer."""
import pytest
import sys
sys.path.insert(0, 'src')

from src.l6.security_enforcer import SecurityEnforcer
from src.core.exceptions import UnsupportedLanguageError, SecurityViolationError


class TestSecurityEnforcerLanguage:
    """Tests for language validation."""

    def test_valid_python(self):
        """SE_001: Python is supported."""
        enforcer = SecurityEnforcer()
        enforcer.validate_language("python")  # Should not raise

    def test_valid_javascript(self):
        """SE_001: JavaScript is supported."""
        enforcer = SecurityEnforcer()
        enforcer.validate_language("javascript")  # Should not raise

    def test_valid_bash(self):
        """SE_001: Bash is supported."""
        enforcer = SecurityEnforcer()
        enforcer.validate_language("bash")  # Should not raise

    def test_invalid_language(self):
        """SE_002: Unsupported language raises UnsupportedLanguageError."""
        enforcer = SecurityEnforcer()
        with pytest.raises(UnsupportedLanguageError):
            enforcer.validate_language("ruby")

    def test_language_case_insensitive(self):
        """SE_003: Language validation is case insensitive."""
        enforcer = SecurityEnforcer()
        enforcer.validate_language("PYTHON")
        enforcer.validate_language("JavaScript")

    def test_language_with_whitespace(self):
        """SE_003: Language validation strips whitespace."""
        enforcer = SecurityEnforcer()
        enforcer.validate_language("  python  ")
        enforcer.validate_language("  bash  ")


class TestSecurityEnforcerCode:
    """Tests for code security checks."""

    def test_safe_code_passes(self):
        """SE_004: Safe code passes security check."""
        enforcer = SecurityEnforcer()
        enforcer.check_code("print('hello')")
        enforcer.check_code("x = 1 + 2")

    def test_os_system_blocked(self):
        """SE_005: os.system is blocked with correct message."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError) as exc_info:
            enforcer.check_code("import os; os.system('ls')")
        assert "os.system" in str(exc_info.value)

    def test_os_popen_blocked(self):
        """os.popen is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_code("import os; os.popen('whoami').read()")

    def test_subprocess_blocked(self):
        """subprocess is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_code("import subprocess; subprocess.call(['ls'])")

    def test_eval_blocked(self):
        """SE_006: eval() is blocked with correct message."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError) as exc_info:
            enforcer.check_code("eval('1+1')")
        assert "eval" in str(exc_info.value)

    def test_exec_blocked(self):
        """exec() is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_code("exec('print(1)')")

    def test_compile_blocked(self):
        """compile() is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_code("compile('malicious_code', '<string>', 'exec')")

    def test_import_blocked(self):
        """__import__ is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_code("__import__('os').system('id')")

    def test_os_unlink_blocked(self):
        """os.unlink is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_code("os.unlink('/sandbox/important.txt')")

    def test_os_rmdir_blocked(self):
        """os.rmdir is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_code("os.rmdir('/sandbox/data')")

    def test_shutil_rmtree_blocked(self):
        """shutil.rmtree is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_code("shutil.rmtree('/sandbox')")

    def test_code_size_limit(self):
        """SE_007: Code size exceeds 102400 bytes is blocked."""
        enforcer = SecurityEnforcer()
        large_code = "x" * 102401
        with pytest.raises(SecurityViolationError) as exc_info:
            enforcer.check_code(large_code)
        assert "size" in str(exc_info.value).lower()


class TestSecurityEnforcerResources:
    """Tests for resource limit checks."""

    def test_valid_resource_limits(self):
        """SE_008: Valid resource limits pass."""
        enforcer = SecurityEnforcer()
        enforcer.check_resource_limits(timeout=30, memory_limit=512, cpu_limit=1.0)

    def test_timeout_too_high(self):
        """SE_009: Timeout exceeding 300s is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_resource_limits(timeout=301, memory_limit=512, cpu_limit=1.0)

    def test_memory_too_high(self):
        """SE_010: Memory exceeding 4096MB is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_resource_limits(timeout=30, memory_limit=4097, cpu_limit=1.0)

    def test_cpu_too_high(self):
        """SE_011: CPU exceeding 4 cores is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_resource_limits(timeout=30, memory_limit=512, cpu_limit=4.1)
