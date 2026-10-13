"""L1: User Interaction Layer - Handle external inputs with complete component architecture.

Components:
- ProtocolAdapter: Abstract base for channel-specific adapters
- DataValidator: Input validation with security checks
- EventNormalizer: Converts raw data to StandardEvent
- ErrorHandler: Retry mechanism with exponential backoff
"""
import time
import re
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from src.core.models import StandardEvent
from src.core.interfaces import MemoryInterface
from src.core.exceptions import (
    ValidationError, UnsupportedChannelError, ParseError
)

# Configure logging
logger = logging.getLogger(__name__)


class ProtocolAdapter(ABC):
    """Abstract base class for protocol adapters.

    Defines the interface for adapting different external protocols
    (WebSocket, Telegram, Webhook) to the internal StandardEvent format.
    """

    @abstractmethod
    def can_handle(self, raw_data: Dict) -> bool:
        """Check if this adapter can handle the given raw data.

        Args:
            raw_data: Raw input data from external source

        Returns:
            True if this adapter can process the data
        """
        pass

    @abstractmethod
    def parse(self, raw_data: Dict) -> StandardEvent:
        """Parse raw data into StandardEvent.

        Args:
            raw_data: Raw input data

        Returns:
            StandardEvent instance

        Raises:
            ParseError: If data cannot be parsed
        """
        pass

    @abstractmethod
    def get_channel_name(self) -> str:
        """Get the channel name this adapter handles.

        Returns:
            Channel identifier string
        """
        pass


class TelegramAdapter(ProtocolAdapter):
    """Adapter for Telegram Bot API messages."""

    def can_handle(self, raw_data: Dict) -> bool:
        """Check if data is a Telegram update."""
        return "update_id" in raw_data or "message" in raw_data

    def parse(self, raw_data: Dict) -> StandardEvent:
        """Parse Telegram update into StandardEvent.

        Raises:
            ParseError: If message format is invalid
        """
        try:
            message = raw_data.get("message", {})
            from_user = message.get("from", {})

            if not from_user.get("id"):
                raise ParseError("Telegram message missing user_id")

            if "text" not in message:
                raise ParseError("Telegram message missing content")

            return StandardEvent(
                channel="telegram",
                user_id=str(from_user.get("id", "")),
                content=message.get("text", ""),
                timestamp=float(message.get("date", time.time())),
                metadata={
                    "chat_id": message.get("chat", {}).get("id"),
                    "message_id": message.get("message_id"),
                    "first_name": from_user.get("first_name"),
                    "username": from_user.get("username"),
                    "update_id": raw_data.get("update_id")
                }
            )
        except Exception as e:
            raise ParseError(f"Failed to parse Telegram message: {str(e)}")

    def get_channel_name(self) -> str:
        """Return channel name."""
        return "telegram"


class WebSocketAdapter(ProtocolAdapter):
    """Adapter for WebSocket messages."""

    def can_handle(self, raw_data: Dict) -> bool:
        """Check if data is a WebSocket message."""
        # WebSocket messages typically have 'type' field
        return "type" in raw_data and "user_id" in raw_data

    def parse(self, raw_data: Dict) -> StandardEvent:
        """Parse WebSocket message into StandardEvent.

        Raises:
            ParseError: If message format is invalid
        """
        try:
            user_id = raw_data.get("user_id")
            if not user_id:
                raise ParseError("WebSocket message missing user_id")

            content = raw_data.get("content") or raw_data.get("message")
            if not content:
                raise ParseError("WebSocket message missing content")

            return StandardEvent(
                channel="websocket",
                user_id=str(user_id),
                content=str(content),
                timestamp=float(raw_data.get("timestamp", time.time())),
                metadata={
                    "type": raw_data.get("type", "message"),
                    "connection_id": raw_data.get("connection_id")
                }
            )
        except Exception as e:
            raise ParseError(f"Failed to parse WebSocket message: {str(e)}")

    def get_channel_name(self) -> str:
        """Return channel name."""
        return "websocket"


class HttpWebhookAdapter(ProtocolAdapter):
    """Adapter for HTTP Webhook callbacks.

    Supports two formats:
    1. Simple format: {user_id, content, timestamp, headers, webhook_type}
    2. Event format: {event, payload: {user_id, message, timestamp}}
    """

    def can_handle(self, raw_data: Dict) -> bool:
        """Check if data is an HTTP Webhook request."""
        # Webhooks typically have headers, webhook-specific fields, or event/payload structure
        return (
            "headers" in raw_data or
            "webhook_type" in raw_data or
            ("event" in raw_data and "payload" in raw_data)
        )

    def parse(self, raw_data: Dict) -> StandardEvent:
        """Parse Webhook request into StandardEvent.

        Raises:
            ParseError: If request format is invalid
        """
        try:
            # Try event/payload format first (from mock tests)
            if "event" in raw_data and "payload" in raw_data:
                payload = raw_data.get("payload", {})
                user_id = payload.get("user_id")
                content = payload.get("message")
                timestamp = payload.get("timestamp", time.time())
                event_type = raw_data.get("event")

                if not user_id:
                    raise ParseError("Webhook payload missing user_id")
                if not content:
                    raise ParseError("Webhook payload missing message")

                return StandardEvent(
                    channel="webhook",
                    user_id=str(user_id),
                    content=str(content),
                    timestamp=float(timestamp),
                    metadata={
                        "event": event_type,
                        "raw_payload": payload
                    }
                )

            # Fall back to simple format
            user_id = raw_data.get("user_id")
            if not user_id:
                raise ParseError("Webhook missing user_id")

            content = raw_data.get("content") or raw_data.get("body")
            if not content:
                raise ParseError("Webhook missing content")

            return StandardEvent(
                channel="webhook",
                user_id=str(user_id),
                content=str(content),
                timestamp=float(raw_data.get("timestamp", time.time())),
                metadata={
                    "headers": raw_data.get("headers", {}),
                    "webhook_type": raw_data.get("webhook_type"),
                    "signature": raw_data.get("headers", {}).get("X-Signature")
                }
            )
        except Exception as e:
            raise ParseError(f"Failed to parse Webhook request: {str(e)}")

    def get_channel_name(self) -> str:
        """Return channel name."""
        return "webhook"


class DataValidator:
    """Data validator with security checks and JSON Schema-like validation.

    Validates:
    - Required fields presence
    - Channel against predefined valid values
    - User ID length limit (256 chars)
    - Content is not empty
    - Timestamp is valid Unix timestamp
    - No injection attacks in content
    """

    REQUIRED_FIELDS = ["channel", "user_id", "content"]
    VALID_CHANNELS = {"telegram", "websocket", "webhook"}
    MAX_USER_ID_LENGTH = 256
    MAX_CONTENT_LENGTH = 10000  # 10KB limit for safety

    # Injection patterns to check
    INJECTION_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # XSS
        r'javascript:',  # JavaScript protocol
        r'on\w+\s*=',  # Event handlers
        r'\$\{.*\}',  # Template injection
        r'<%.*%>',  # JSP/ASP injection
    ]

    def __init__(self):
        """Initialize validator with compiled patterns."""
        self._injection_patterns = [
            re.compile(pattern, re.IGNORECASE | re.DOTALL)
            for pattern in self.INJECTION_PATTERNS
        ]

    def validate(self, data: Dict) -> bool:
        """Validate raw data with all checks.

        Args:
            data: Raw input data dictionary

        Returns:
            True if validation passes

        Raises:
            ValidationError: If validation fails with details
        """
        # Check required fields
        self._validate_required_fields(data)

        # Validate channel
        self._validate_channel(data.get("channel"))

        # Validate user_id
        self._validate_user_id(data.get("user_id"))

        # Validate content
        self._validate_content(data.get("content"))

        # Validate timestamp if present
        if "timestamp" in data and data["timestamp"]:
            self._validate_timestamp(data["timestamp"])

        return True

    def _validate_required_fields(self, data: Dict) -> None:
        """Check all required fields are present and not empty."""
        for field in self.REQUIRED_FIELDS:
            if field not in data or data[field] is None or data[field] == "":
                raise ValidationError(f"Missing required field: {field}")

    def _validate_channel(self, channel: Any) -> None:
        """Validate channel is in predefined valid values."""
        if channel not in self.VALID_CHANNELS:
            raise ValidationError(
                f"Invalid channel '{channel}'. "
                f"Must be one of: {self.VALID_CHANNELS}"
            )

    def _validate_user_id(self, user_id: Any) -> None:
        """Validate user_id is not empty and within length limit."""
        if not user_id:
            raise ValidationError("user_id cannot be empty")

        user_id_str = str(user_id)
        if len(user_id_str) > self.MAX_USER_ID_LENGTH:
            raise ValidationError(
                f"user_id exceeds maximum length of {self.MAX_USER_ID_LENGTH} characters"
            )

    def _validate_content(self, content: Any) -> None:
        """Validate content is not empty, within limits, and has no injection."""
        if not content:
            raise ValidationError("content cannot be empty")

        content_str = str(content)

        # Check length
        if len(content_str) > self.MAX_CONTENT_LENGTH:
            raise ValidationError(
                f"content exceeds maximum length of {self.MAX_CONTENT_LENGTH} characters"
            )

        # Check for injection attacks
        for pattern in self._injection_patterns:
            if pattern.search(content_str):
                raise ValidationError(
                    "content contains potentially malicious content (injection detected)"
                )

    def _validate_timestamp(self, timestamp: Any) -> None:
        """Validate timestamp is a valid Unix timestamp."""
        try:
            ts = float(timestamp)
            # Check if timestamp is within reasonable range
            # (1970 to 2100)
            if ts < 0 or ts > 4102444800:
                raise ValidationError(
                    "timestamp must be a valid Unix timestamp between 1970 and 2100"
                )
        except (ValueError, TypeError):
            raise ValidationError("timestamp must be a valid numeric Unix timestamp")


class ErrorHandler:
    """Error handler with retry mechanism, exponential backoff, and business
    error formatting for L3 error flow-back via L2.

    Responsibilities:
    1. L1 internal errors (connection/parse/validation): retry + exponential backoff
    2. L3 business errors (flowed back through L2): protocol-level formatting

    Configuration:
    - MaxRetries: 3
    - BackoffStrategy: exponential
    - InitialDelay: 1000ms
    """

    DEFAULT_MAX_RETRIES = 3
    DEFAULT_INITIAL_DELAY = 1.0  # 1 second = 1000ms
    DEFAULT_MAX_DELAY = 60.0  # Cap at 60 seconds

    def __init__(self,
                 max_retries: int = DEFAULT_MAX_RETRIES,
                 initial_delay: float = DEFAULT_INITIAL_DELAY,
                 max_delay: float = DEFAULT_MAX_DELAY):
        """Initialize error handler.

        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds (1000ms = 1.0)
            max_delay: Maximum delay cap in seconds
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay

    # ------------------------------------------------------------------ #
    #  L1 internal error handling — retry + exponential backoff
    # ------------------------------------------------------------------ #

    def execute_with_retry(self,
                          operation: Callable,
                          *args,
                          retryable_exceptions: tuple = (Exception,),
                          **kwargs) -> Any:
        """Execute an operation with retry logic.

        Args:
            operation: Callable to execute
            *args: Positional arguments for operation
            retryable_exceptions: Tuple of exception types that should trigger retry
            **kwargs: Keyword arguments for operation

        Returns:
            Result of operation

        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        delay = self.initial_delay

        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                logger.debug(f"Attempt {attempt + 1}/{self.max_retries + 1}")
                result = operation(*args, **kwargs)

                # Log success after retry
                if attempt > 0:
                    logger.info(f"Operation succeeded after {attempt} retries")

                return result

            except retryable_exceptions as e:
                last_exception = e

                if attempt < self.max_retries:
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {str(e)}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                    # Exponential backoff: delay *= 2
                    delay = min(delay * 2, self.max_delay)
                else:
                    logger.error(
                        f"All {self.max_retries + 1} attempts failed. "
                        f"Last error: {str(e)}"
                    )

        # All retries exhausted
        raise last_exception

    def is_retryable(self, exception: Exception,
                     retryable_types: tuple = (Exception,)) -> bool:
        """Check if an exception is retryable.

        Args:
            exception: The exception to check
            retryable_types: Tuple of retryable exception types

        Returns:
            True if exception is retryable
        """
        return isinstance(exception, retryable_types)

    # ------------------------------------------------------------------ #
    #  L3 business error handling — protocol-level formatting (framework)
    #  TODO: Fill concrete formatting logic after L3.ErrorTranslator output
    #        structure is finalized.
    # ------------------------------------------------------------------ #

    def handle_error(self,
                     error: Any,
                     channel: str,
                     metadata: Optional[Dict] = None) -> Any:
        """Route errors to channel-specific formatters.

        Supports two error sources:
        1. L1 internal errors (Exception): connection/parse/validation failures
        2. L3 business errors (dict): errors translated by L3.ErrorTranslator
           and flowed back through L2

        Args:
            error: Error to handle. Exception for L1 errors, dict for L3 errors.
            channel: Target channel (telegram/websocket/webhook)
            metadata: Optional channel-specific metadata (e.g., chat_id)

        Returns:
            Formatted error response. Type depends on channel:
            - telegram: dict (Bot API message structure)
            - websocket: dict (JSON object)
            - webhook: tuple[int, dict] (status_code, body)
        """
        metadata = metadata or {}

        # Determine error type and extract message
        if isinstance(error, Exception):
            error_message = str(error)
            logger.error(f"L1 internal error ({channel}): {error_message}")
        elif isinstance(error, dict):
            # L3 business error flowed back through L2
            error_message = error.get("error_message", "Unknown error")
            logger.info(f"L3 business error ({channel}): {error_message}")
        else:
            error_message = str(error)
            logger.warning(f"Unhandled error type ({channel}): {error_message}")

        # Route to channel-specific formatter
        if channel == "telegram":
            return self.format_for_telegram(error_message, metadata)
        elif channel == "websocket":
            return self.format_for_websocket(error_message, metadata)
        elif channel == "webhook":
            return self.format_for_webhook(error_message, metadata)
        else:
            logger.error(f"Unknown channel '{channel}' for error formatting")
            return {"error": error_message}

    def format_for_telegram(self,
                            error_message: str,
                            metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Format error for Telegram Bot API.

        TODO: Business error formatting logic to be filled after
        L3.ErrorTranslator output structure is finalized.

        Args:
            error_message: Human-readable error text (from L3.ErrorTranslator)
            metadata: Channel-specific metadata (e.g., chat_id)

        Returns:
            Dict compatible with Telegram Bot API sendMessage parameters
        """
        metadata = metadata or {}
        return {
            "chat_id": metadata.get("chat_id"),
            "text": error_message,
            "parse_mode": None
        }

    def format_for_websocket(self,
                             error_message: str,
                             metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Format error for WebSocket channel.

        TODO: Business error formatting logic to be filled after
        L3.ErrorTranslator output structure is finalized.

        Args:
            error_message: Human-readable error text (from L3.ErrorTranslator)
            metadata: Channel-specific metadata (e.g., connection_id)

        Returns:
            JSON-compatible dict with error fields
        """
        return {
            "type": "error",
            "message": error_message,
            "timestamp": time.time()
        }

    def format_for_webhook(self,
                           error_message: str,
                           metadata: Optional[Dict] = None) -> tuple[int, Dict[str, Any]]:
        """Format error for HTTP Webhook channel.

        TODO: Business error formatting logic to be filled after
        L3.ErrorTranslator output structure is finalized.

        Args:
            error_message: Human-readable error text (from L3.ErrorTranslator)
            metadata: Channel-specific metadata (e.g., webhook_type)

        Returns:
            Tuple of (HTTP status_code, response_body dict)
        """
        return (
            500,  # Internal Server Error
            {"error": error_message}
        )


class EventNormalizer:
    """Event normalizer that uses ProtocolAdapters to convert raw data."""

    def __init__(self, adapters: Optional[list] = None):
        """Initialize with protocol adapters.

        Args:
            adapters: List of ProtocolAdapter instances. If None, uses defaults.
        """
        if adapters is None:
            self.adapters = [
                TelegramAdapter(),
                WebSocketAdapter(),
                HttpWebhookAdapter()
            ]
        else:
            self.adapters = adapters

    def normalize(self, raw_data: Dict, channel: str = None) -> StandardEvent:
        """Normalize raw data to StandardEvent using appropriate adapter.

        Args:
            raw_data: Raw input data
            channel: Optional channel hint. If None, auto-detect.

        Returns:
            StandardEvent instance

        Raises:
            UnsupportedChannelError: If no adapter can handle the data
            ParseError: If parsing fails
        """
        # If channel is specified, find matching adapter
        if channel:
            for adapter in self.adapters:
                if adapter.get_channel_name() == channel:
                    return adapter.parse(raw_data)
            raise UnsupportedChannelError(f"No adapter found for channel: {channel}")

        # Auto-detect using can_handle
        for adapter in self.adapters:
            if adapter.can_handle(raw_data):
                logger.debug(f"Using {adapter.__class__.__name__} for data")
                return adapter.parse(raw_data)

        raise UnsupportedChannelError(
            "No adapter can handle the provided data format"
        )


class UserInteraction:
    """L1 implementation - User interaction layer with complete component architecture.

    Integrates:
    - ProtocolAdapters for channel-specific parsing
    - DataValidator for input validation
    - EventNormalizer for data conversion
    - ErrorHandler for retry logic
    - Session management (user_id -> session_id mapping)
    """

    # Commands to create a new session
    NEW_SESSION_COMMANDS = {"/new", "/reset", "/start", "新会话"}

    PREFERENCE_KEY_ACTIVE_SESSION = "active_session_id"

    def __init__(self,
                 error_handler: Optional[ErrorHandler] = None,
                 validator: Optional[DataValidator] = None,
                 normalizer: Optional[EventNormalizer] = None,
                 memory: Optional[MemoryInterface] = None):
        """Initialize L1 with all components.

        Args:
            error_handler: ErrorHandler instance for retry logic
            validator: DataValidator instance for validation
            normalizer: EventNormalizer instance for data conversion
            memory: Optional L4 MemoryInterface for persistent session mapping.
                    If None, session mapping is in-memory only (backward compatible).
        """
        self.error_handler = error_handler or ErrorHandler()
        self.validator = validator or DataValidator()
        self.normalizer = normalizer or EventNormalizer()
        self.memory = memory

        # Session management: user_id -> session_id (in-memory cache)
        # When memory is provided, L4 serves as the persistent source of truth
        # and this dict acts as a hot cache to avoid repeated L4 lookups.
        self._user_session_map: Dict[str, str] = {}

        # Response context: user_id -> channel metadata for send_response
        # Used to route L2's response back to the correct channel format.
        # NOTE: Concurrent requests from the same user_id may overwrite each
        # other. For high-concurrency or multi-channel per user scenarios,
        # the caller should pass channel/metadata explicitly to send_response().
        self._response_context_map: Dict[str, Dict[str, Any]] = {}

        logger.info("UserInteraction layer initialized with all components")

    @staticmethod
    def _make_session_key(user_id: str, channel: str = None) -> str:
        """Generate a session lookup key for a user.

        Args:
            user_id: User identifier
            channel: Optional channel source

        Returns:
            Session lookup key string
        """
        if channel:
            return f"{user_id}:{channel}"
        return user_id

    def _get_session_id(self, user_id: str, content: str, channel: str = None) -> tuple[Optional[str], bool]:
        """Get session ID for user, handling new session commands.

        Uses in-memory cache first; falls back to L4 persistence if available.

        Args:
            user_id: User identifier
            content: Message content to check for commands
            channel: Channel source (e.g., 'telegram', 'websocket')

        Returns:
            Tuple of (session_id, is_new_session_request)
            - session_id: Existing session ID or None (to create new)
            - is_new_session_request: True if user explicitly requested new session
        """
        key = self._make_session_key(user_id, channel)

        # Check if user wants a new session
        if content and content.strip() in self.NEW_SESSION_COMMANDS:
            logger.info(f"User {user_id} requested new session via command: {content.strip()}")
            # Remove from in-memory cache (both channel-specific and plain user_id for backward compat)
            for k in {key, user_id}:
                if k in self._user_session_map:
                    old_session = self._user_session_map[k]
                    logger.debug(f"Removing old session mapping: {old_session}")
                    del self._user_session_map[k]
            # Remove from L4 persistence if available (save None as placeholder)
            if self.memory:
                self.memory.save_user_preference(
                    user_id, self.PREFERENCE_KEY_ACTIVE_SESSION, None
                )
                logger.debug(f"Cleared persistent session mapping for user {user_id}")
            return None, True

        # 1. Check in-memory cache first (channel-specific, then plain user_id for backward compat)
        for k in {key, user_id}:
            session_id = self._user_session_map.get(k)
            if session_id:
                return session_id, False

        # 2. Fall back to L4 persistence if available
        if self.memory:
            session_id = self.memory.load_user_preference(
                user_id, self.PREFERENCE_KEY_ACTIVE_SESSION
            )
            if session_id:
                # Backfill into memory cache for subsequent requests
                self._user_session_map[key] = session_id
                logger.debug(f"Restored session mapping from L4: {key} -> {session_id}")
                return session_id, False

        # No mapping found: let L2 create a new session
        return None, False

    def update_session_mapping(self, user_id: str, session_id: str, channel: str = None) -> None:
        """Update the user_id -> session_id mapping.

        Writes to both in-memory cache and L4 persistence (if available).
        This should be called after L2 returns a session context.

        Args:
            user_id: User identifier
            session_id: Session ID from L2
            channel: Channel source
        """
        key = self._make_session_key(user_id, channel)
        self._user_session_map[key] = session_id
        if self.memory:
            self.memory.save_user_preference(
                user_id, self.PREFERENCE_KEY_ACTIVE_SESSION, session_id
            )
            logger.debug(
                f"Persisted session mapping to L4: {user_id} -> {session_id}"
            )
        else:
            logger.debug(f"Updated in-memory session mapping: {key} -> {session_id}")

    def get_user_session(self, user_id: str, channel: str = None) -> Optional[str]:
        """Get current session ID for a user.

        Checks in-memory cache first, then falls back to L4 persistence.

        Args:
            user_id: User identifier
            channel: Channel source

        Returns:
            Session ID if exists, None otherwise
        """
        key = self._make_session_key(user_id, channel)
        session_id = self._user_session_map.get(key)
        if session_id:
            return session_id
        if self.memory:
            session_id = self.memory.load_user_preference(
                user_id, self.PREFERENCE_KEY_ACTIVE_SESSION
            )
            if session_id:
                self._user_session_map[key] = session_id
        return session_id

    def receive_payload(self, raw_data: Dict, channel: str = None) -> StandardEvent:
        """Receive and process payload from any channel with full validation and retry.

        Args:
            raw_data: Raw input data from external source
            channel: Optional channel type hint

        Returns:
            Validated StandardEvent with session_id in metadata

        Raises:
            ValidationError: If data validation fails
            UnsupportedChannelError: If channel is not supported
            ParseError: If data parsing fails
        """
        logger.info(f"Receiving payload from channel: {channel or 'auto-detect'}")

        # Use retry logic for the entire processing pipeline
        return self.error_handler.execute_with_retry(
            self._process_payload,
            raw_data,
            channel,
            retryable_exceptions=(ParseError, ConnectionError)
        )

    def _process_payload(self, raw_data: Dict, channel: str = None) -> StandardEvent:
        """Internal processing method (called with retry)."""
        # Step 1: Normalize to StandardEvent
        event = self.normalizer.normalize(raw_data, channel)
        logger.debug(f"Normalized event: channel={event.channel}, user_id={event.user_id}")

        # Step 2: Validate the event data
        self.validator.validate(event.model_dump())
        logger.debug("Validation passed")

        # Step 3: Get or create session mapping (channel-aware)
        session_id, is_new = self._get_session_id(
            event.user_id, event.content, event.channel
        )
        event.metadata["session_id"] = session_id
        event.metadata["is_new_session_request"] = is_new
        logger.debug(
            f"Session ID for user {event.user_id} on {event.channel}: "
            f"{session_id}, new_session={is_new}"
        )

        # Step 4: Save response context for send_response() routing
        self._response_context_map[event.user_id] = {
            "channel": event.channel,
            "chat_id": event.metadata.get("chat_id"),
            "connection_id": event.metadata.get("connection_id"),
        }
        logger.debug(f"Saved response context for user {event.user_id}: channel={event.channel}")

        # Step 5: Log successful processing (monitoring)
        logger.info(
            f"Successfully processed payload: "
            f"channel={event.channel}, "
            f"user_id={event.user_id[:20]}..., "
            f"session_id={session_id}, new_session={is_new}"
        )
        return event

    def get_supported_channels(self) -> list:
        """Get list of supported channel names.

        Returns:
            List of supported channel identifiers
        """
        return [adapter.get_channel_name() for adapter in self.normalizer.adapters]

    def send_response(self,
                      user_id: str,
                      content: str,
                      channel: str = None,
                      metadata: Optional[Dict] = None) -> Any:
        """Format L2's response text for the user's original channel.

        Looks up the user's most recent request context to determine the
        channel format. Callers may pass channel/metadata explicitly to
        avoid race conditions when the same user_id sends concurrent
        requests from multiple channels.

        Args:
            user_id: User identifier
            content: Response text from L2/L3
            channel: Optional channel override. If None, auto-detected from
                     the user's last request context.
            metadata: Optional metadata override (e.g., chat_id, connection_id).
                      If None, auto-detected from the last request context.

        Returns:
            Formatted response structure. Type depends on channel:
            - telegram: dict (Bot API message structure)
            - websocket: dict (JSON object)
            - webhook: tuple[int, dict] (HTTP status_code, body)

        Raises:
            UnsupportedChannelError: If channel is not supported and cannot
                                     be auto-detected.
        """
        # Auto-detect channel and metadata from last request context
        if channel is None or metadata is None:
            context = self._response_context_map.get(user_id, {})
            channel = channel or context.get("channel", "unknown")
            metadata = metadata or {
                "chat_id": context.get("chat_id"),
                "connection_id": context.get("connection_id"),
            }

        logger.info(f"Sending response to user {user_id[:20]}... via channel: {channel}")

        if channel == "telegram":
            return {
                "chat_id": metadata.get("chat_id"),
                "text": content,
                "parse_mode": None
            }
        elif channel == "websocket":
            return {
                "type": "response",
                "message": content,
                "connection_id": metadata.get("connection_id"),
                "timestamp": time.time()
            }
        elif channel == "webhook":
            return (
                200,
                {
                    "response": content,
                    "user_id": user_id,
                    "timestamp": time.time()
                }
            )
        else:
            logger.error(f"Cannot send response: unsupported channel '{channel}'")
            raise UnsupportedChannelError(
                f"No response formatter for channel: {channel}"
            )

