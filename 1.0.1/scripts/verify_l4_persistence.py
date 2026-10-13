"""验证 L4 MemoryKnowledge 的持久化行为

对比两种初始化方式：
1. MemoryKnowledge()  - server.py 中使用的方式（默认 InMemoryStore）
2. get_l4_memory()    - 读取 .env 配置的方式（可能使用 FileMemoryStore）
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from src.l4 import MemoryKnowledge
from src.l4.config.l4_config import get_l4_memory


def test_default_memory():
    """测试默认 MemoryKnowledge（server.py 中使用的方式）"""
    print("=" * 60)
    print("[测试1] 默认 MemoryKnowledge() - server.py 中的方式")
    print("=" * 60)

    memory = MemoryKnowledge()
    print(f"memory_store 类型: {type(memory.memory_store).__name__}")

    session_id = "test-session-default"
    messages = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么可以帮你的？"}
    ]

    # 存储
    result = memory.store_conversation(session_id, messages)
    print(f"store_conversation 结果: {result}")

    # 读取
    history = memory.retrieve_history(session_id)
    print(f"retrieve_history 结果: {history}")

    # 检查是否有文件保存到磁盘
    print("\n检查磁盘文件...")
    storage_dir = Path("src/l4/data/conversations")
    conv_dir = storage_dir / "conversations"
    files = list(conv_dir.glob("test-session-default.json")) if conv_dir.exists() else []
    print(f"  找到文件: {files}")
    print(f"  是否持久化到磁盘: {'否 (InMemoryStore)' if not files else '是'}")

    return bool(files)


def test_configured_memory():
    """测试 get_l4_memory()（读取 .env 配置）"""
    print("\n" + "=" * 60)
    print("[测试2] get_l4_memory() - 读取 .env 配置的方式")
    print("=" * 60)

    memory = get_l4_memory()
    print(f"memory_store 类型: {type(memory.memory_store).__name__}")

    session_id = "test-session-configured"
    messages = [
        {"role": "user", "content": "测试持久化"},
        {"role": "assistant", "content": "持久化测试成功！"}
    ]

    # 存储
    result = memory.store_conversation(session_id, messages)
    print(f"store_conversation 结果: {result}")

    # 读取
    history = memory.retrieve_history(session_id)
    print(f"retrieve_history 结果: {history}")

    # 检查文件
    print("\n检查磁盘文件...")
    storage_dir = Path("src/l4/data/conversations")
    conv_dir = storage_dir / "conversations"
    files = list(conv_dir.glob("test-session-configured.json")) if conv_dir.exists() else []
    print(f"  找到文件: {files}")
    print(f"  是否持久化到磁盘: {'是' if files else '否'}")

    # 读取文件内容
    if files:
        import json
        with open(files[0], "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"  文件内容摘要: session_id={data['session_id']}, messages={len(data['messages'])}")

    return bool(files)


def test_cross_instance_persistence():
    """测试跨实例读取（验证真正的持久化）"""
    print("\n" + "=" * 60)
    print("[测试3] 跨实例读取持久化数据")
    print("=" * 60)

    # 实例 A 存储
    memory_a = get_l4_memory()
    session_id = "test-cross-instance"
    messages = [
        {"role": "user", "content": "跨实例测试"},
        {"role": "assistant", "content": "数据应该能被另一个实例读取"}
    ]
    memory_a.store_conversation(session_id, messages)
    print(f"[实例 A] 存储了 session_id={session_id}")

    # 实例 B 读取
    memory_b = get_l4_memory()
    history = memory_b.retrieve_history(session_id)
    print(f"[实例 B] 读取到 {len(history)} 条消息")
    if history:
        print(f"  内容: {history}")
        print("  跨实例持久化: 成功")
    else:
        print("  跨实例持久化: 失败")

    return bool(history)


def main():
    print("L4 MemoryKnowledge 持久化验证")

    # 显示环境变量配置
    print("\n.env 配置:")
    print(f"  L4_MEMORY_STORE_TYPE={os.getenv('L4_MEMORY_STORE_TYPE', '未配置')}")
    print(f"  L4_MEMORY_STORAGE_DIR={os.getenv('L4_MEMORY_STORAGE_DIR', '未配置')}")
    print(f"  L4_VECTOR_STORE_TYPE={os.getenv('L4_VECTOR_STORE_TYPE', '未配置')}")
    print(f"  L4_CHROMA_PERSIST_DIR={os.getenv('L4_CHROMA_PERSIST_DIR', '未配置')}")

    r1 = test_default_memory()
    r2 = test_configured_memory()
    r3 = test_cross_instance_persistence()

    print("\n" + "=" * 60)
    print("验证结论")
    print("=" * 60)
    print(f"[默认 MemoryKnowledge()]   持久化到磁盘: {'是' if r1 else '否 (InMemoryStore - 内存中)'}")
    print(f"[get_l4_memory()]          持久化到磁盘: {'是' if r2 else '否'}")
    print(f"[跨实例读取]               持久化有效:   {'是' if r3 else '否'}")
    print()
    print("server.py 中的问题:")
    print("  - L4 端点每次创建新的 MemoryKnowledge()，使用 InMemoryStore")
    print("  - E2E 端点使用全局 MemoryKnowledge()，但仍是 InMemoryStore")
    print("  - 数据仅在 server 运行期间存在，重启后丢失")
    print()
    print("修复建议:")
    print("  - 使用 get_l4_memory() 替代 MemoryKnowledge()")
    print("  - 或传入 memory_store={'store_type': 'file', 'storage_dir': '...'}")


if __name__ == "__main__":
    main()
