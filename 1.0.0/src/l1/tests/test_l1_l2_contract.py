"""
L1-L2 Interface Contract Test
验证L1输出的StandardEvent满足L2的输入要求

这是一个契约测试，确保层间接口兼容性
运行: python src/l1/tests/test_l1_l2_contract.py
"""
import sys
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.l1.l1_user_interaction import (
    TelegramAdapter,
    WebSocketAdapter,
    HttpWebhookAdapter
)
from src.l2.l2_control_gateway import ControlGateway
from src.core.models import StandardEvent
from src.core.exceptions import RateLimitExceeded


def test_telegram_to_l2():
    """测试 Telegram 消息经过L1后能正确被L2处理"""
    print("\n" + "="*70)
    print("TEST 1: Telegram Message -> L1 -> L2 Contract")
    print("="*70)

    # L1: 模拟Telegram消息
    telegram_msg = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {"id": 123456789, "first_name": "Test"},
            "chat": {"id": 123456789, "type": "private"},
            "date": 1704067200,
            "text": "Hello from Telegram"
        }
    }

    # L1 处理
    adapter = TelegramAdapter()
    event = adapter.parse(telegram_msg)

    print(f"[L1 Output] StandardEvent:")
    print(f"  user_id: {event.user_id} (type: {type(event.user_id).__name__})")
    print(f"  content: {event.content}")
    print(f"  channel: {event.channel}")

    # 验证L1输出满足L2要求
    assert event.user_id, "L2 requires user_id for rate limiting"
    assert event.content, "L2 requires content for current_query"
    assert event.channel, "L2 requires channel for metadata"
    print("  [Contract Check] L1 output satisfies L2 input requirements")

    # L2 处理
    l2 = ControlGateway()
    l3_input = l2.process_event(event)
    context = l3_input.session_context

    print(f"\n[L2 Output] SessionContext:")
    print(f"  session_id: {context.session_id}")
    print(f"  user_id: {context.user_id}")
    print(f"  current_query: {context.current_query}")
    print(f"  metadata: {context.metadata}")

    # 验证数据一致性
    assert context.user_id == event.user_id, "User ID mismatch"
    assert context.current_query == event.content, "Content mismatch"
    assert context.metadata.get("channel") == event.channel, "Channel mismatch"
    print("  [Contract Check] Data consistency verified")

    print("\n  PASS - Telegram -> L1 -> L2 flow works correctly")


def test_websocket_to_l2():
    """测试 WebSocket 消息经过L1后能正确被L2处理"""
    print("\n" + "="*70)
    print("TEST 2: WebSocket Message -> L1 -> L2 Contract")
    print("="*70)

    # L1: 模拟WebSocket消息
    ws_msg = {
        "type": "message",
        "user_id": "ws_user_123",
        "content": "Hello from WebSocket",
        "timestamp": 1704067200.0,
        "connection_id": "conn_abc"
    }

    # L1 处理
    adapter = WebSocketAdapter()
    event = adapter.parse(ws_msg)

    print(f"[L1 Output] StandardEvent:")
    print(f"  user_id: {event.user_id}")
    print(f"  content: {event.content}")
    print(f"  channel: {event.channel}")

    # L2 处理
    l2 = ControlGateway()
    l3_input = l2.process_event(event)
    context = l3_input.session_context

    print(f"\n[L2 Output] SessionContext:")
    print(f"  user_id: {context.user_id}")
    print(f"  current_query: {context.current_query}")

    assert context.user_id == "ws_user_123"
    assert context.current_query == "Hello from WebSocket"
    print("\n  PASS - WebSocket -> L1 -> L2 flow works correctly")


def test_webhook_to_l2():
    """测试 Webhook 消息经过L1后能正确被L2处理"""
    print("\n" + "="*70)
    print("TEST 3: Webhook Message -> L1 -> L2 Contract")
    print("="*70)

    # L1: 模拟Webhook消息 (Event/Payload格式)
    webhook_msg = {
        "event": "incoming_message",
        "payload": {
            "user_id": "webhook_user_456",
            "message": "Hello from Webhook",
            "timestamp": 1704067200.0
        }
    }

    # L1 处理
    adapter = HttpWebhookAdapter()
    event = adapter.parse(webhook_msg)

    print(f"[L1 Output] StandardEvent:")
    print(f"  user_id: {event.user_id}")
    print(f"  content: {event.content}")
    print(f"  channel: {event.channel}")

    # L2 处理
    l2 = ControlGateway()
    l3_input = l2.process_event(event)
    context = l3_input.session_context

    print(f"\n[L2 Output] SessionContext:")
    print(f"  user_id: {context.user_id}")
    print(f"  current_query: {context.current_query}")

    assert context.user_id == "webhook_user_456"
    assert context.current_query == "Hello from Webhook"
    print("\n  PASS - Webhook -> L1 -> L2 flow works correctly")


def test_session_persistence():
    """测试 L2 自动管理并复用 session（L1 无状态，不再传递 session_id）"""
    print("\n" + "="*70)
    print("TEST 4: Session Persistence Managed by L2")
    print("="*70)

    l2 = ControlGateway()

    # 第一次请求 - L1 产出的 StandardEvent 中无 session_id
    event1 = StandardEvent(
        channel="telegram",
        user_id="user_123",
        content="First message",
        metadata={}
    )

    l3_input1 = l2.process_event(event1)
    context1 = l3_input1.session_context

    print(f"[First Request] L2 created session:")
    print(f"  session_id: {context1.session_id}")
    session_id = context1.session_id

    # 第二次请求 - L1 仍然不传递 session_id，L2 通过 L4 自动复用
    event2 = StandardEvent(
        channel="telegram",
        user_id="user_123",
        content="Second message",
        metadata={}
    )

    l3_input2 = l2.process_event(event2)
    context2 = l3_input2.session_context

    print(f"\n[Second Request] L2 automatically reused session:")
    print(f"  session_id: {context2.session_id}")

    # 验证session保持一致
    assert context1.session_id == context2.session_id, "Session should be persistent"
    print("  [Contract Check] Session persistence verified")
    print("\n  PASS - Session correctly maintained across requests")


def test_rate_limiting():
    """测试 L2 的 Rate Limiting 能正确处理 L1 输出"""
    print("\n" + "="*70)
    print("TEST 5: Rate Limiting with L1 Output")
    print("="*70)

    # 使用非常严格的rate limit进行测试
    l2 = ControlGateway()
    l2.rate_limiter.max_requests = 3
    l2.rate_limiter.window_seconds = 60

    user_id = "rate_limited_user"

    # 发送3个请求（应该成功）
    for i in range(3):
        event = StandardEvent(
            channel="websocket",
            user_id=user_id,
            content=f"Message {i+1}"
        )
        l3_input = l2.process_event(event)
        context = l3_input.session_context
        print(f"  Request {i+1}: session_id={context.session_id[:8]}...")

    # 第4个请求应该被限流
    event_over_limit = StandardEvent(
        channel="websocket",
        user_id=user_id,
        content="Message 4 - should be blocked"
    )

    try:
        l2.process_event(event_over_limit)
        print("  FAIL - Should have raised RateLimitExceeded")
    except RateLimitExceeded as e:
        print(f"  Request 4: RateLimitExceeded raised as expected")
        print(f"    Error: {e}")
        print("\n  PASS - Rate limiting works correctly")


def main():
    print("""
+-----------------------------------------------------------------------+
|     L1-L2 Interface Contract Test Suite                               |
|     Verify L1 StandardEvent output satisfies L2 input requirements    |
+-----------------------------------------------------------------------+
""")

    tests = [
        test_telegram_to_l2,
        test_websocket_to_l2,
        test_webhook_to_l2,
        test_session_persistence,
        test_rate_limiting
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n  [FAILED] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70)

    if failed == 0:
        print("\nAll contract tests passed! L1-L2 interface is compatible.")
    else:
        print(f"\n{failed} test(s) failed. Interface contract violation detected.")


if __name__ == "__main__":
    main()
