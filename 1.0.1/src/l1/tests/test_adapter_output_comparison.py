"""
L1 三种适配器输出对比测试
验证 Telegram、WebSocket、Webhook 经过 L1 转换后输出结构一致

运行: python src/l1/tests/test_adapter_output_comparison.py
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


def compare_outputs():
    """对比三种适配器的输出"""

    # 1. Telegram 输入
    telegram_input = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {"id": 123456789, "first_name": "Test", "username": "test_user"},
            "chat": {"id": 123456789, "type": "private"},
            "date": 1704067200,
            "text": "Hello from Telegram"
        }
    }

    # 2. WebSocket 输入
    websocket_input = {
        "type": "message",
        "user_id": "ws_user_123",
        "content": "Hello from WebSocket",
        "timestamp": 1704067200.0,
        "connection_id": "conn_abc123"
    }

    # 3. Webhook 输入 (Event/Payload 格式)
    webhook_input = {
        "event": "user_message",
        "payload": {
            "user_id": "webhook_user_1",
            "message": "Hello from Webhook",
            "timestamp": 1704067200.0
        }
    }

    # 创建适配器
    telegram_adapter = TelegramAdapter()
    websocket_adapter = WebSocketAdapter()
    webhook_adapter = HttpWebhookAdapter()

    # 解析
    telegram_event = telegram_adapter.parse(telegram_input)
    websocket_event = websocket_adapter.parse(websocket_input)
    webhook_event = webhook_adapter.parse(webhook_input)

    print("\n" + "="*80)
    print("L1 ADAPTER OUTPUT COMPARISON")
    print("="*80)

    # 打印对比表格
    print("\n{:<20} {:<20} {:<20} {:<20}".format("Field", "Telegram", "WebSocket", "Webhook"))
    print("-"*80)

    print("{:<20} {:<20} {:<20} {:<20}".format(
        "channel",
        telegram_event.channel,
        websocket_event.channel,
        webhook_event.channel
    ))

    print("{:<20} {:<20} {:<20} {:<20}".format(
        "user_id",
        telegram_event.user_id,
        websocket_event.user_id,
        webhook_event.user_id
    ))

    print("{:<20} {:<20} {:<20} {:<20}".format(
        "content",
        telegram_event.content[:15] + "...",
        websocket_event.content[:15] + "...",
        webhook_event.content[:15] + "..."
    ))

    print("{:<20} {:<20} {:<20} {:<20}".format(
        "timestamp",
        str(telegram_event.timestamp),
        str(websocket_event.timestamp),
        str(webhook_event.timestamp)
    ))

    print("{:<20} {:<20} {:<20} {:<20}".format(
        "metadata_type",
        type(telegram_event.metadata).__name__,
        type(websocket_event.metadata).__name__,
        type(webhook_event.metadata).__name__
    ))

    print("\n" + "="*80)
    print("STRUCTURE VERIFICATION")
    print("="*80)

    # 验证所有输出都是 StandardEvent
    from src.core.models import StandardEvent

    events = [
        ("Telegram", telegram_event),
        ("WebSocket", websocket_event),
        ("Webhook", webhook_event)
    ]

    all_pass = True

    for name, event in events:
        checks = [
            ("Type is StandardEvent", isinstance(event, StandardEvent)),
            ("Has channel", hasattr(event, 'channel') and event.channel is not None),
            ("Has user_id", hasattr(event, 'user_id') and event.user_id is not None),
            ("Has content", hasattr(event, 'content') and event.content is not None),
            ("Has timestamp", hasattr(event, 'timestamp') and event.timestamp is not None),
            ("Has metadata", hasattr(event, 'metadata') and isinstance(event.metadata, dict)),
        ]

        print(f"\n{name}:")
        for check_name, result in checks:
            status = "[OK]" if result else "[FAIL]"
            print(f"  {status} {check_name}")
            if not result:
                all_pass = False

    print("\n" + "="*80)
    if all_pass:
        print("RESULT: [OK] All adapters produce consistent StandardEvent output")
    else:
        print("RESULT: [FAIL] Some adapters have inconsistent output")
    print("="*80)

    # 打印详细的输出示例
    print("\n" + "="*80)
    print("DETAILED OUTPUT SAMPLES")
    print("="*80)

    for name, event in events:
        print(f"\n{name}Adapter Output:")
        print(f"  StandardEvent(")
        print(f"    channel='{event.channel}',")
        print(f"    user_id='{event.user_id}',")
        print(f"    content='{event.content}',")
        print(f"    timestamp={event.timestamp},")
        print(f"    metadata={event.metadata}")
        print(f"  )")

    return all_pass


def main():
    print("""
+-----------------------------------------------------------------------+
|     L1 Adapter Output Comparison                                      |
|     Verify all adapters produce consistent StandardEvent              |
+-----------------------------------------------------------------------+
""")

    try:
        result = compare_outputs()

        print("\n" + "="*80)
        if result:
            print("CONCLUSION:")
            print("  All three adapters (Telegram, WebSocket, Webhook) produce")
            print("  the same StandardEvent structure after L1 processing.")
            print("  This ensures L2 receives consistent input regardless of source.")
        else:
            print("CONCLUSION:")
            print("  Inconsistencies detected in adapter outputs!")
        print("="*80)

    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
