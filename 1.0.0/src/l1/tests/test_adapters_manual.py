"""
L1 Adapters Manual Test
测试 WebSocketAdapter 和 HttpWebhookAdapter

运行: python src/l1/tests/test_adapters_manual.py
"""
import sys
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.l1.l1_user_interaction import (
    TelegramAdapter,
    WebSocketAdapter,
    HttpWebhookAdapter,
    DataValidator
)
from src.core.exceptions import ParseError


def test_telegram_adapter():
    """测试 TelegramAdapter"""
    print("\n" + "="*70)
    print("TEST 1: TelegramAdapter")
    print("="*70)

    adapter = TelegramAdapter()

    # 测试数据 - 模拟真实Telegram消息
    valid_telegram_msg = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {
                "id": 123456789,
                "first_name": "Test",
                "username": "test_user"
            },
            "chat": {
                "id": 123456789,
                "type": "private"
            },
            "date": 1704067200,
            "text": "Hello, World!"
        }
    }

    # Test can_handle
    print("\n[1.1] can_handle() check:")
    result = adapter.can_handle(valid_telegram_msg)
    print(f"  Input has 'update_id': True")
    print(f"  can_handle() returns: {result}")
    assert result == True, "Should handle valid Telegram message"
    print("  PASS")

    # Test parse
    print("\n[1.2] parse() valid message:")
    event = adapter.parse(valid_telegram_msg)
    print(f"  channel: {event.channel}")
    print(f"  user_id: {event.user_id}")
    print(f"  content: {event.content}")
    print(f"  metadata: {event.metadata}")
    assert event.channel == "telegram"
    assert event.user_id == "123456789"
    assert event.content == "Hello, World!"
    print("  PASS")

    # Test invalid message (missing text)
    print("\n[1.3] parse() invalid message (no text):")
    invalid_msg = {
        "update_id": 123,
        "message": {
            "from": {"id": 123},
            "photo": [{"file_id": "xxx"}]  # Photo instead of text
        }
    }
    try:
        adapter.parse(invalid_msg)
        print("  FAIL - Should have raised ParseError")
    except ParseError as e:
        print(f"  Got expected ParseError: {e}")
        print("  PASS")

    print("\n[1.4] get_channel_name():")
    print(f"  Channel: {adapter.get_channel_name()}")
    assert adapter.get_channel_name() == "telegram"
    print("  PASS")


def test_websocket_adapter():
    """测试 WebSocketAdapter"""
    print("\n" + "="*70)
    print("TEST 2: WebSocketAdapter")
    print("="*70)

    adapter = WebSocketAdapter()

    # 测试数据 - WebSocket格式
    valid_ws_msg = {
        "type": "message",
        "user_id": "user_123",
        "content": "WebSocket message content",
        "timestamp": 1704067200.0,
        "connection_id": "conn_abc123"
    }

    # Test can_handle
    print("\n[2.1] can_handle() check:")
    result = adapter.can_handle(valid_ws_msg)
    print(f"  Input has 'type' and 'user_id': True")
    print(f"  can_handle() returns: {result}")
    assert result == True
    print("  PASS")

    # Test parse
    print("\n[2.2] parse() valid message:")
    event = adapter.parse(valid_ws_msg)
    print(f"  channel: {event.channel}")
    print(f"  user_id: {event.user_id}")
    print(f"  content: {event.content}")
    print(f"  metadata: {event.metadata}")
    assert event.channel == "websocket"
    assert event.user_id == "user_123"
    assert event.content == "WebSocket message content"
    print("  PASS")

    # Test with 'message' field instead of 'content'
    print("\n[2.3] parse() with 'message' field:")
    msg_alt = {
        "type": "message",
        "user_id": "user_456",
        "message": "Alternative content field"
    }
    event = adapter.parse(msg_alt)
    print(f"  content: {event.content}")
    assert event.content == "Alternative content field"
    print("  PASS")

    # Test invalid (missing user_id)
    print("\n[2.4] parse() invalid (missing user_id):")
    invalid_msg = {
        "type": "message",
        "content": "No user id"
    }
    try:
        adapter.parse(invalid_msg)
        print("  FAIL - Should have raised ParseError")
    except ParseError as e:
        print(f"  Got expected ParseError: {e}")
        print("  PASS")

    print("\n[2.5] get_channel_name():")
    print(f"  Channel: {adapter.get_channel_name()}")
    assert adapter.get_channel_name() == "websocket"
    print("  PASS")


def test_webhook_adapter():
    """测试 HttpWebhookAdapter - 两种格式"""
    print("\n" + "="*70)
    print("TEST 3: HttpWebhookAdapter")
    print("="*70)

    adapter = HttpWebhookAdapter()

    # ===== 格式1: Event/Payload 格式 =====
    print("\n[3.1] Event/Payload format:")
    event_payload_msg = {
        "event": "user_message",
        "payload": {
            "user_id": "webhook_user_1",
            "message": "Hello from webhook",
            "timestamp": 1704067200.0
        }
    }

    print("  Input: {event, payload: {user_id, message, timestamp}}")
    result = adapter.can_handle(event_payload_msg)
    print(f"  can_handle(): {result}")
    assert result == True

    event = adapter.parse(event_payload_msg)
    print(f"  Parsed:")
    print(f"    channel: {event.channel}")
    print(f"    user_id: {event.user_id}")
    print(f"    content: {event.content}")
    print(f"    metadata: {event.metadata}")
    assert event.channel == "webhook"
    assert event.user_id == "webhook_user_1"
    assert event.content == "Hello from webhook"
    print("  PASS")

    # ===== 格式2: Simple 格式 =====
    print("\n[3.2] Simple format:")
    simple_msg = {
        "user_id": "webhook_user_2",
        "content": "Simple webhook message",
        "timestamp": 1704067200.0,
        "headers": {
            "Content-Type": "application/json",
            "X-Signature": "sha256=abc123"
        },
        "webhook_type": "incoming_message"
    }

    print("  Input: {user_id, content, headers, webhook_type}")
    result = adapter.can_handle(simple_msg)
    print(f"  can_handle(): {result}")
    assert result == True

    event = adapter.parse(simple_msg)
    print(f"  Parsed:")
    print(f"    channel: {event.channel}")
    print(f"    user_id: {event.user_id}")
    print(f"    content: {event.content}")
    print(f"    metadata: {event.metadata}")
    assert event.channel == "webhook"
    assert event.user_id == "webhook_user_2"
    assert event.content == "Simple webhook message"
    assert event.metadata.get("signature") == "sha256=abc123"
    print("  PASS")

    # Test with 'body' field instead of 'content'
    print("\n[3.3] Simple format with 'body' field:")
    body_msg = {
        "user_id": "webhook_user_3",
        "body": "Message in body field",
        "headers": {}
    }
    event = adapter.parse(body_msg)
    print(f"  content: {event.content}")
    assert event.content == "Message in body field"
    print("  PASS")

    print("\n[3.4] get_channel_name():")
    print(f"  Channel: {adapter.get_channel_name()}")
    assert adapter.get_channel_name() == "webhook"
    print("  PASS")


def test_validator():
    """测试 DataValidator"""
    print("\n" + "="*70)
    print("TEST 4: DataValidator")
    print("="*70)

    validator = DataValidator()

    # Valid event
    print("\n[4.1] Validate valid event:")
    valid_event = {
        "channel": "telegram",
        "user_id": "user123",
        "content": "Hello",
        "timestamp": 1704067200.0,
        "metadata": {}
    }
    result = validator.validate(valid_event)
    print(f"  Result: {result}")
    assert result == True
    print("  PASS")

    # Invalid channel
    print("\n[4.2] Validate invalid channel:")
    invalid_channel = {
        "channel": "unknown",
        "user_id": "user123",
        "content": "Hello"
    }
    try:
        validator.validate(invalid_channel)
        print("  FAIL - Should have raised ValidationError")
    except Exception as e:
        print(f"  Got expected error: {type(e).__name__}: {e}")
        print("  PASS")

    # Missing required field
    print("\n[4.3] Validate missing required field:")
    missing_field = {
        "channel": "telegram",
        "user_id": "user123"
        # missing content
    }
    try:
        validator.validate(missing_field)
        print("  FAIL - Should have raised ValidationError")
    except Exception as e:
        print(f"  Got expected error: {type(e).__name__}: {e}")
        print("  PASS")

    # XSS injection check
    print("\n[4.4] Validate XSS injection:")
    xss_content = {
        "channel": "webhook",
        "user_id": "user123",
        "content": "<script>alert('xss')</script>"
    }
    try:
        validator.validate(xss_content)
        print("  FAIL - Should have detected XSS")
    except Exception as e:
        print(f"  Got expected error: {type(e).__name__}: {e}")
        print("  PASS")


def main():
    print("""
+-----------------------------------------------------------------------+
|     L1 Adapters Manual Test Suite                                     |
|     Testing Telegram, WebSocket, and Webhook Adapters                  |
+-----------------------------------------------------------------------+
""")

    try:
        test_telegram_adapter()
        test_websocket_adapter()
        test_webhook_adapter()
        test_validator()

        print("\n" + "="*70)
        print("ALL TESTS PASSED!")
        print("="*70)

    except AssertionError as e:
        print(f"\n[FAILED] Assertion error: {e}")
    except Exception as e:
        print(f"\n[FAILED] Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
