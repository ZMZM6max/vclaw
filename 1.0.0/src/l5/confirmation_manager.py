"""Confirmation manager for high-risk operations requiring user confirmation."""
import uuid
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional
from src.core.exceptions import ConfirmationExpiredError, InvalidConfirmationError


@dataclass
class PendingOperation:
    """Represents a pending operation awaiting user confirmation."""
    confirmation_id: str
    tool_name: str
    params: Dict[str, Any]
    created_at: float
    expires_at: float


class ConfirmationManager:
    """Manages pending operations that require user confirmation.

    Features:
    - In-memory storage of pending operations
    - TTL-based automatic expiration (default: 300 seconds)
    - Automatic cleanup of expired records
    - UUID-based confirmation IDs for security
    """

    DEFAULT_TTL = 300  # 5 minutes

    def __init__(self, ttl_seconds: int = DEFAULT_TTL):
        """Initialize the confirmation manager.

        Args:
            ttl_seconds: Time-to-live for pending operations in seconds
        """
        self._ttl = ttl_seconds
        self._pending: Dict[str, PendingOperation] = {}

    def create_pending(self, tool_name: str, params: Dict[str, Any]) -> str:
        """Create a new pending operation.

        Args:
            tool_name: Name of the tool to be executed
            params: Parameters for the tool execution

        Returns:
            Confirmation ID (UUID) for retrieving/consuming the operation
        """
        confirmation_id = str(uuid.uuid4())
        now = time.time()

        operation = PendingOperation(
            confirmation_id=confirmation_id,
            tool_name=tool_name,
            params=params.copy(),
            created_at=now,
            expires_at=now + self._ttl
        )

        self._pending[confirmation_id] = operation
        return confirmation_id

    def get_pending(self, confirmation_id: str) -> Optional[PendingOperation]:
        """Get a pending operation if it exists and is not expired.

        Args:
            confirmation_id: The confirmation ID to look up

        Returns:
            PendingOperation if found and not expired, None otherwise
        """
        self._cleanup_expired()

        operation = self._pending.get(confirmation_id)
        if operation is None:
            return None

        if time.time() > operation.expires_at:
            # Expired - remove it
            del self._pending[confirmation_id]
            return None

        return operation

    def confirm_and_consume(self, confirmation_id: str) -> PendingOperation:
        """Confirm and consume a pending operation.

        Args:
            confirmation_id: The confirmation ID to confirm

        Returns:
            The PendingOperation that was confirmed

        Raises:
            InvalidConfirmationError: If confirmation_id is invalid or expired
        """
        self._cleanup_expired()

        operation = self._pending.get(confirmation_id)
        if operation is None:
            raise InvalidConfirmationError(
                f"Confirmation ID '{confirmation_id}' is invalid or has expired"
            )

        # Consume the operation
        del self._pending[confirmation_id]
        return operation

    def _cleanup_expired(self):
        """Remove all expired pending operations."""
        now = time.time()
        expired_ids = [
            cid for cid, op in self._pending.items()
            if now > op.expires_at
        ]
        for cid in expired_ids:
            del self._pending[cid]
