"""Tests for RateLimiter component.

TC-L2-002: Rate limiting
TC-RateLimiter-003: IP-level rate limiting
TC-RateLimiter-004: Global rate limiting
TC-RateLimiter-005: IP limit for different users
TC-RateLimiter-006: Rate limiting without IP
"""
import pytest
import sys
sys.path.insert(0, 'src')

from src.l2.l2_control_gateway import RateLimiter


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def rate_limiter():
    """Provide RateLimiter with default limits."""
    return RateLimiter()


@pytest.fixture
def custom_rate_limiter():
    """Provide RateLimiter with custom limits for testing."""
    return RateLimiter(limits={
        "user": (10, 60),
        "ip": (5, 60),
        "global": (10000, 1)
    })


# =============================================================================
# Basic Rate Limiting Tests
# =============================================================================

class TestRateLimiter:
    """Tests for basic rate limiting (user level)."""

    def test_rate_limit_allows_under_limit(self):
        """Test that requests under limit are allowed."""
        limiter = RateLimiter(limits={
            "user": (10, 60),
            "ip": (100, 60),
            "global": (1000, 1)
        })

        # 10 requests should be allowed
        for i in range(10):
            allowed, _ = limiter.is_allowed(f"user_{i}")
            assert allowed is True

    def test_rate_limit_blocks_over_limit(self):
        """Test that requests over limit are blocked."""
        limiter = RateLimiter(limits={
            "user": (2, 60),
            "ip": (100, 60),
            "global": (1000, 1)
        })
        user_id = "test_user"

        # First 2 requests allowed
        assert limiter.is_allowed(user_id)[0] is True
        assert limiter.is_allowed(user_id)[0] is True

        # 3rd request blocked
        allowed, reason = limiter.is_allowed(user_id)
        assert allowed is False
        assert reason == "user_rate_limit"


# =============================================================================
# Enhanced Rate Limiting Tests (IP and Global)
# =============================================================================

class TestEnhancedRateLimiter:
    """Tests for enhanced RateLimiter with IP and global limits."""

    def test_rate_limit_with_ip(self, custom_rate_limiter):
        """TC-RateLimiter-003: IP-level rate limiting."""
        user_id = "user_123"
        ip = "192.168.1.1"

        # First 5 requests should succeed
        for _ in range(5):
            allowed, _ = custom_rate_limiter.is_allowed(user_id, ip)
            assert allowed is True

        # 6th request from same IP should fail
        allowed, reason = custom_rate_limiter.is_allowed(user_id, ip)
        assert allowed is False
        assert reason == "ip_rate_limit"

    def test_rate_limit_global_blocks_all(self, rate_limiter):
        """TC-RateLimiter-004: Global rate limiting blocks all users."""
        # Make 1000 requests from different users
        for i in range(1000):
            rate_limiter.is_allowed(f"user_{i}", f"192.168.1.{i % 256}")

        # Next request should be blocked by global limit
        allowed, reason = rate_limiter.is_allowed("new_user", "10.0.0.1")
        assert allowed is False
        assert reason == "global_rate_limit"

    def test_rate_limit_ip_blocks_same_ip(self, rate_limiter):
        """TC-RateLimiter-005: IP limit applies to same IP, different users."""
        ip = "192.168.1.1"

        # Make 100 requests from same IP but different users
        for i in range(100):
            rate_limiter.is_allowed(f"user_{i}", ip)

        # New user from same IP should be blocked
        allowed, _ = rate_limiter.is_allowed("new_user", ip)
        assert allowed is False

    def test_rate_limit_without_ip(self, rate_limiter):
        """TC-RateLimiter-006: Rate limiting without IP still works."""
        # First 60 user requests should succeed
        for _ in range(60):
            allowed, _ = rate_limiter.is_allowed("user_123")
            assert allowed is True

        # 61st request should be blocked by user limit
        allowed, reason = rate_limiter.is_allowed("user_123")
        assert allowed is False
        assert reason == "user_rate_limit"
