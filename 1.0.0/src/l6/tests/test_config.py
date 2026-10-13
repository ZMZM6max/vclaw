"""Tests for SandboxConfig."""
import pytest
import sys
sys.path.insert(0, 'src')

from src.l6.config import SandboxConfig


class TestSandboxConfig:
    """Tests for SandboxConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = SandboxConfig()
        assert config.memory_limit == 512
        assert config.cpu_limit == 1.0
        assert config.timeout == 30
        assert config.enable_network is False
        assert config.disk_limit == 100
        assert config.allowed_imports is None

    def test_custom_values(self):
        """Test custom configuration values."""
        config = SandboxConfig(
            memory_limit=1024,
            cpu_limit=2.0,
            timeout=60,
            enable_network=True
        )
        assert config.memory_limit == 1024
        assert config.cpu_limit == 2.0
        assert config.timeout == 60
        assert config.enable_network is True

    def test_memory_limit_validation(self):
        """Test memory limit validation."""
        with pytest.raises(ValueError):
            SandboxConfig(memory_limit=32)  # Too low
        with pytest.raises(ValueError):
            SandboxConfig(memory_limit=8192)  # Too high

    def test_cpu_limit_validation(self):
        """Test CPU limit validation."""
        with pytest.raises(ValueError):
            SandboxConfig(cpu_limit=0)  # Too low
        with pytest.raises(ValueError):
            SandboxConfig(cpu_limit=8)  # Too high

    def test_timeout_validation(self):
        """Test timeout validation."""
        with pytest.raises(ValueError):
            SandboxConfig(timeout=0)  # Too low
        with pytest.raises(ValueError):
            SandboxConfig(timeout=600)  # Too high
