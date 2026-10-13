"""Tests for ResourceLimiter."""
import sys

sys.path.insert(0, 'src')

from src.l6.resource_limiter import ResourceLimiter


class TestResourceLimiterInit:
    """Tests for ResourceLimiter initialization (RL_001)."""

    def test_rl001_default_limits(self):
        """RL_001: Default limits initialization."""
        limiter = ResourceLimiter()
        limits = limiter.get_limits()
        assert limits == {
            "cpu": 1.0,
            "memory": 512,
            "time": 30,
            "disk": 100,
            "network": False,
        }


class TestResourceLimiterSet:
    """Tests for set method (RL_002)."""

    def test_rl002_dynamic_update(self):
        """RL_002: Dynamic update of limits."""
        limiter = ResourceLimiter()
        limiter.set(memory=1024, cpu=2.0)
        limits = limiter.get_limits()
        assert limits["memory"] == 1024
        assert limits["cpu"] == 2.0
        assert limits["time"] == 30  # unchanged
        assert limits["disk"] == 100  # unchanged


class TestResourceLimiterCheck:
    """Tests for check method (RL_003, RL_004)."""

    def test_rl003_usage_within_limits(self):
        """RL_003: Usage within limits returns True."""
        limiter = ResourceLimiter()
        assert limiter.check({"memory": 400, "cpu": 0.8}) is True

    def test_rl004_usage_exceeds_limits(self):
        """RL_004: Usage exceeding limits returns False."""
        limiter = ResourceLimiter()
        assert limiter.check({"memory": 600, "cpu": 0.5}) is False


class TestResourceLimiterGetLimits:
    """Tests for get_limits method (RL_005)."""

    def test_rl005_returns_copy(self):
        """RL_005: get_limits returns a copy."""
        limiter = ResourceLimiter()
        limits = limiter.get_limits()
        limits["memory"] = 9999
        assert limiter.get_limits()["memory"] == 512
