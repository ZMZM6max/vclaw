# L4 Memory & Knowledge Layer 生产环境配置指南

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件，确保以下配置：

```env
# OpenAI API Key (必需)
OPENAI_API_KEY=sk-your-api-key-here

# L4 Embedding 配置
L4_EMBEDDING_PROVIDER=openai
L4_EMBEDDING_MODEL=text-embedding-3-small

# L4 Vector Store 配置
L4_VECTOR_STORE_TYPE=chroma
L4_CHROMA_COLLECTION_NAME=vclaw_knowledge
L4_CHROMA_PERSIST_DIR=./src/l4/data/chroma_db

# L4 Memory Store 配置
L4_MEMORY_STORE_TYPE=file
L4_MEMORY_STORAGE_DIR=./src/l4/data/conversations

# 缓存配置
L4_CACHE_ENABLED=true
```

### 3. 初始化 L4

```bash
python init_l4.py
```

这将：
- 验证配置
- 创建数据目录
- 测试 L4 连接

### 4. 运行示例

```bash
python examples/l4_usage_example.py
```

## 代码中使用

### 方式一：使用配置模块（推荐）

```python
from src.l4.config.l4_config import get_l4_memory_production

# 获取生产环境配置的 L4 实例
memory = get_l4_memory_production()

# 存储文档
memory.store(
    "Python is a programming language.",
    {"doc_id": "py-001", "category": "programming"}
)

# 搜索
results = memory.search("programming", top_k=5)

# 存储对话
memory.store_conversation("session-1", [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi!"}
])

# 获取历史
history = memory.retrieve_history("session-1")
```

### 方式二：手动配置

```python
from src.l4 import MemoryKnowledge

memory = MemoryKnowledge(
    embedding_service={
        "provider": "openai",
        "model": "text-embedding-3-small",
        "api_key": "your-api-key"
    },
    vector_store={
        "store_type": "chroma",
        "collection_name": "my_collection",
        "persist_directory": "./src/l4/data/chroma_db"
    },
    text_chunker={
        "chunker_type": "recursive",
        "chunk_size": 1000,
        "chunk_overlap": 200
    },
    memory_store={
        "store_type": "file",
        "storage_dir": "./src/l4/data/conversations"
    },
    enable_caching=True
)
```

## 配置文件详解

### `.env` 文件

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | - | OpenAI API 密钥（必需） |
| `L4_EMBEDDING_PROVIDER` | `mock` | Embedding 提供商: `openai`, `sentence-transformers`, `mock` |
| `L4_EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI Embedding 模型 |
| `L4_VECTOR_STORE_TYPE` | `memory` | Vector Store 类型: `memory`, `chroma`, `faiss` |
| `L4_CHROMA_PERSIST_DIR` | `./src/l4/data/chroma_db` | ChromaDB 持久化目录 |
| `L4_MEMORY_STORE_TYPE` | `memory` | Memory Store 类型: `memory`, `file` |
| `L4_MEMORY_STORAGE_DIR` | `./src/l4/data/conversations` | 对话历史存储目录 |
| `L4_CACHE_ENABLED` | `true` | 是否启用缓存 |

### 配置模块

`src/l4/config/l4_config.py` 提供了：

- `L4_CONFIG`: 配置字典
- `get_l4_memory()`: 获取配置好的 L4 实例
- `get_l4_memory_production()`: 生产环境配置
- `get_l4_memory_development()`: 开发环境配置
- `validate_l4_config()`: 验证配置

## 数据目录结构

```
src/l4/data/
├── chroma_db/          # ChromaDB 向量数据库
│   ├── chroma.sqlite3
│   └── ...
└── conversations/      # 对话历史存储
    ├── session-1.json
    └── ...
```

## 与 L3 集成

```python
from src.l3.l3_orchestration import Orchestration
from src.l4.config.l4_config import get_l4_memory_production

# 创建 L4 实例
memory = get_l4_memory_production()

# 注入到 L3
orchestration = Orchestration(
    memory=memory,  # L4 实例
    tools=tools_capabilities  # L5 实例
)
```

## 故障排除

### 问题：OpenAI API Key 错误

```
ValueError: OPENAI_API_KEY environment variable is required
```

**解决**：在 `.env` 文件中设置 `OPENAI_API_KEY`

### 问题：ChromaDB 目录不存在

```
Warning: ChromaDB persistence directory does not exist
```

**解决**：运行 `python init_l4.py` 创建目录

### 问题：缺少依赖

```
ImportError: No module named 'chromadb'
```

**解决**：`pip install chromadb`

## 性能优化建议

1. **启用缓存**: `L4_CACHE_ENABLED=true`
2. **合适的 Chunk 大小**: 根据文档类型调整 `L4_CHUNK_SIZE`
3. **文件存储**: 生产环境使用 `L4_MEMORY_STORE_TYPE=file` 持久化对话
4. **定期清理**: 清理过期缓存和旧会话数据

## 更多示例

查看 `examples/l4_usage_example.py` 获取完整示例代码。
