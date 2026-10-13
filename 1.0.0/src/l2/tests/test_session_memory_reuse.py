"""验证：同一 user_id 连续两次请求，session_id 复用且历史记忆被正确组装."""
import sys
import uuid
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

from src.l2.l2_control_gateway import ControlGateway
from src.core.models import StandardEvent

# 使用文件持久化，确保跨请求记忆真实存在
gateway = ControlGateway(
    memory=None,  # 使用 ControlGateway 默认的 file 模式 L4
    tools=None
)

user_id = f"test_user_{uuid.uuid4().hex[:8]}"
print(f"[测试] user_id = {user_id}")

# 第一次请求
event1 = StandardEvent(
    channel="test",
    user_id=user_id,
    content="你好",
    metadata={}
)
result1 = gateway.process_event(event1)
session_id_1 = result1.session_context.session_id
history_1 = result1.session_context.history

print(f"\n[第1次请求]")
print(f"  session_id: {session_id_1}")
print(f"  history 条数: {len(history_1)}")

# 模拟 L3 回复，触发 L2 保存对话历史到 L4
gateway.send_response(event1, "你好！有什么可以帮你的？")

# 第二次请求（同一 user_id）
event2 = StandardEvent(
    channel="test",
    user_id=user_id,
    content="帮我算 1+1",
    metadata={}
)
result2 = gateway.process_event(event2)
session_id_2 = result2.session_context.session_id
history_2 = result2.session_context.history

print(f"\n[第2次请求]")
print(f"  session_id: {session_id_2}")
print(f"  history 条数: {len(history_2)}")
print(f"  history 内容:")
for msg in history_2:
    print(f"    - {msg['role']}: {msg['content']}")

# 验证
assert session_id_1 == session_id_2, f"session_id 没有复用！{session_id_1} != {session_id_2}"
assert len(history_2) == 2, f"历史记录没有复用，期望 2 条，实际 {len(history_2)} 条"
assert history_2[0]["role"] == "user" and history_2[0]["content"] == "你好"
assert history_2[1]["role"] == "assistant" and history_2[1]["content"] == "你好！有什么可以帮你的？"

print("\n[PASS 验证通过] 同一 user_id 连续请求：")
print(f"  - session_id 复用: {session_id_1}")
print(f"  - 历史记忆正确组装: 第2次请求时 history 包含了第1轮的对话")
