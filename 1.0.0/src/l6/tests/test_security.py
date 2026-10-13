"""Tests for SecurityEnforcer."""
import pytest
import sys
sys.path.insert(0, 'src')

from src.l6.security_enforcer import SecurityEnforcer
from src.core.exceptions import UnsupportedLanguageError, SecurityViolationError


class TestSecurityEnforcerLanguage:
    """Tests for language validation."""

    def test_valid_python(self):
        """Test Python is supported."""
        enforcer = SecurityEnforcer()
        enforcer.validate_language("python")  # Should not raise

    def test_valid_javascript(self):
        """Test JavaScript is supported."""
        enforcer = SecurityEnforcer()
        enforcer.validate_language("javascript")  # Should not raise

    def test_valid_bash(self):
        """Test Bash is supported."""
        enforcer = SecurityEnforcer()
        enforcer.validate_language("bash")  # Should not raise

    def test_invalid_language(self):
        """Test unsupported language raises error."""
        enforcer = SecurityEnforcer()
        with pytest.raises(UnsupportedLanguageError):
            enforcer.validate_language("ruby")

    def test_language_case_insensitive(self):
        """Test language validation is case insensitive."""
        enforcer = SecurityEnforcer()
        enforcer.validate_language("PYTHON")
        enforcer.validate_language("JavaScript")


class TestSecurityEnforcerCode:
    """Tests for code security checks."""

    def test_safe_code_passes(self):
        """Test safe code passes security check."""
        enforcer = SecurityEnforcer()
        safe_code = "print('Hello World')"
        enforcer.check_code(safe_code)  # Should not raise

    def test_os_system_blocked(self):
        """Test os.system is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError) as exc_info:
            enforcer.check_code("import os; os.system('rm -rf /')")
        assert "os.system" in str(exc_info.value)

    def test_subprocess_blocked(self):
        """Test subprocess is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_code("import subprocess; subprocess.call(['ls'])")

    def test_eval_blocked(self):
        """Test eval() is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_code("eval('1 + 1')")

    def test_exec_blocked(self):
        """Test exec() is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_code("exec('print(1)')")

    def test_code_size_limit(self):
        """Test code size limit is enforced."""
        enforcer = SecurityEnforcer()
        large_code = "x = 1\n" * 20000  # > 100KB
        with pytest.raises(SecurityViolationError) as exc_info:
            enforcer.check_code(large_code)
        assert "size" in str(exc_info.value).lower()


class TestSecurityEnforcerResources:
    """Tests for resource limit checks."""

    def test_valid_resource_limits(self):
        """Test valid resource limits pass."""
        enforcer = SecurityEnforcer()
        enforcer.check_resource_limits(timeout=30, memory_limit=512, cpu_limit=1.0)

    def test_timeout_too_high(self):
        """Test timeout exceeding max is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_resource_limits(timeout=600, memory_limit=512, cpu_limit=1.0)

    def test_memory_too_high(self):
        """Test memory exceeding max is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_resource_limits(timeout=30, memory_limit=8192, cpu_limit=1.0)

    def test_cpu_too_high(self):
        """Test CPU exceeding max is blocked."""
        enforcer = SecurityEnforcer()
        with pytest.raises(SecurityViolationError):
            enforcer.check_resource_limits(timeout=30, memory_limit=512, cpu_limit=8.0)
