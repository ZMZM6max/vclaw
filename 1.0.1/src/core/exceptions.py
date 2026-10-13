"""Centralized exception definitions for VClaw.

This module contains all exceptions used across the VClaw architecture
to avoid duplication and provide consistent error handling.
"""


class VClawException(Exception):
    """Base exception for all VClaw errors."""
    pass


# ==================== L1: User Interaction Exceptions ====================

class ValidationError(VClawException):
    """Raised when data validation fails."""
    pass


class UnsupportedChannelError(VClawException):
    """Raised when an unsupported channel is used."""
    pass


class ParseError(VClawException):
    """Raised when data parsing fails."""
    pass


# ==================== L2: Control Gateway Exceptions ====================

class RateLimitExceeded(VClawException):
    """Raised when rate limit is exceeded."""
    pass


class AuthenticationError(VClawException):
    """Raised when authentication fails. (Deprecated - auth removed from L2)"""
    pass


class ForbiddenError(VClawException):
    """Raised when user lacks permission. (Deprecated - permissions removed from L2)"""
    pass


class SessionError(VClawException):
    """Raised when session operation fails."""
    pass


# ==================== L3: Orchestration Exceptions ====================

class LLMError(VClawException):
    """Raised when LLM call fails."""
    pass


class MaxIterationsExceeded(VClawException):
    """Raised when max ReAct iterations reached."""
    pass


class ToolExecutionError(VClawException):
    """Raised when tool execution fails."""
    pass


# ==================== L5: Tools & Capabilities Exceptions ====================

class ToolNotFoundError(VClawException):
    """Raised when tool is not found."""
    pass


class PermissionDeniedError(VClawException):
    """Raised when user lacks permission to execute a tool."""
    pass


class InvalidRuleError(VClawException):
    """Raised when a permission rule format is invalid."""
    pass


class RuleLimitExceeded(VClawException):
    """Raised when the number of rules per user exceeds the limit."""
    pass


class ExecutionTimeoutError(VClawException):
    """Raised when execution times out."""
    pass


# ==================== L6: Runtime Exceptions ====================

class UnsupportedLanguageError(VClawException):
    """Raised when language is not supported."""
    pass


class ResourceExceededError(VClawException):
    """Raised when resource limits are exceeded."""
    pass


class SecurityViolationError(VClawException):
    """Raised when code violates security policy."""
    pass


class SandboxCreationError(VClawException):
    """Raised when sandbox creation fails."""
    pass


# ==================== L5: Tools & Capabilities Exceptions (Additional) ====================

class ConfirmationRequiredError(VClawException):
    """Raised when user confirmation is required for high-risk operations.

    This is not a true error but a state indicator that requires user interaction.
    """
    def __init__(self, message: str, confirmation_id: str, affected_count: int = 1):
        super().__init__(message)
        self.confirmation_id = confirmation_id
        self.affected_count = affected_count


class ConfirmationExpiredError(VClawException):
    """Raised when confirmation has expired."""
    pass


class InvalidConfirmationError(VClawException):
    """Raised when confirmation_id is invalid or has been consumed."""
    pass
