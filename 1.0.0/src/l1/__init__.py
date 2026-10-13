"""L1: User Interaction Layer

Components:
- ProtocolAdapter: Abstract base for channel-specific adapters
- TelegramAdapter: Adapter for Telegram Bot API messages
- WebSocketAdapter: Adapter for WebSocket messages
- HttpWebhookAdapter: Adapter for HTTP Webhook callbacks
- DataValidator: Input validation with security checks
- EventNormalizer: Converts raw data to StandardEvent
- ErrorHandler: Retry mechanism with exponential backoff
- UserInteraction: Main L1 implementation integrating all components
"""

from .l1_user_interaction import (
    ProtocolAdapter,
    TelegramAdapter,
    WebSocketAdapter,
    HttpWebhookAdapter,
    DataValidator,
    EventNormalizer,
    ErrorHandler,
    UserInteraction,
)

__all__ = [
    "ProtocolAdapter",
    "TelegramAdapter",
    "WebSocketAdapter",
    "HttpWebhookAdapter",
    "DataValidator",
    "EventNormalizer",
    "ErrorHandler",
    "UserInteraction",
]
