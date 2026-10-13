# L4: Memory & Knowledge Layer 设计文档

> 本文档详细描述 L4 记忆与知识层的功能实现、数据流和架构设计。
> 对应 XML 规范: `docs/03_specs/L4_MemoryKnowledge.xml` + `docs/03_specs/l4/*.xml`

---

## 一、架构总览

L4 是 VClaw 六层架构中的第四层，负责 **RAG（检索增强生成）**、长期记忆持久化和语义搜索。它通过向量数据库、文本分块、Embedding 生成和缓存机制，为上层（L3 编排层）提供知识检索和对话历史管理能力。

```
┌─────────────────────────────────────────────────────────────────┐
│                        L4: Memory & Knowledge                    │
├─────────────────────────────────────────────────────────────────┤
│  Core Layer                                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ MemoryKnowledge (Facade)                                │    │
│  │  - search()    → 语义搜索（带缓存）                     │    │
│  │  - store()     → 文档存储（自动分块）                   │    │
│  │  - delete()    → 级联删除文档及全部 chunk               │    │
│  │  - store_conversation() → 对话持久化（自动压缩）        │    │
│  │  - store_knowledge() / retrieve_knowledge()             │    │
│  │  - create_index() / delete_index() / list_indices()     │    │
│  └─────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│  Services Layer                                                  │
│  ┌─────────────────────┐    ┌─────────────────────────────┐    │
│  │ EmbeddingService    │    │ TextChunker                 │    │
│  │  - OpenAI           │    │  - Recursive (递归分割)     │    │
│  │  - SentenceTransform│    │  - Token (按Token数)        │    │
│  │  - Mock             │    │  - Markdown (按标题)        │    │
│  └─────────────────────┘    │  - Character (固定长度)     │    │
│                             └─────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│  Storage Layer                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ VectorStore      │  │ MemoryStore      │  │ CacheManager │  │
│  │  - Memory        │  │  - InMemory      │  │  - LRU + TTL │  │
│  │  - ChromaDB      │  │  - File          │  │  - 线程安全  │  │
│  │  - FAISS         │  │  - 自动压缩      │  │  - Embedding │  │
│  │  - Pinecone      │  │  - 用户偏好      │  │  - Search    │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  Index Layer                                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ IndexManager                                            │    │
│  │  - create / update / delete / optimize / list           │    │
│  │  - ChromaIndexManager / MemoryIndexManager              │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、模块功能详解

### 2.1 Core — `l4_memory.py` (总入口门面)

`MemoryKnowledge` 是 L4 的唯一对外门面，实现了 `MemoryInterface`（来自 `src/core/interfaces.py`），供 L3 通过依赖注入使用。

**构造函数**支持两种传参模式：
- 直接传入实例：`MemoryKnowledge(embedding_service=OpenAIEmbeddingService(...))`
- 传入配置字典：`MemoryKnowledge(embedding_service={"provider": "openai", "model": "text-embedding-3-small"})`

未传参时默认使用 **Mock + Memory + Recursive + InMemory**，零外部依赖即可运行。

| 方法 | 功能 | 内部调用链 |
|------|------|-----------|
| `search(query, top_k=5, filters)` | 语义搜索 | SearchCache → _get_embedding → EmbeddingCache → embed → VectorStore.search |
| `store(document, metadata)` | 单文档存储 | validate → TextChunker.split → embed_batch → VectorStore.add_documents |
| `store_batch(documents)` | 批量文档存储 | 同上，批量处理 |
| `delete(document_id)` | 级联删除文档 | `_doc_chunks` 映射 → VectorStore.delete(全部 chunk_id) → KnowledgeMemory.delete_knowledge |
| `store_conversation(session_id, messages)` | 存储对话 | MemoryStore.save_conversation（含自动压缩） |
| `retrieve_history(session_id, limit=10)` | 检索对话 | MemoryStore.load_conversation |
| `save/load_user_preference` | 用户偏好 | MemoryStore.save/load_preference |
| `search_with_scores(...)` | 带分数的搜索 | 同 search，返回完整 dict（含 score、metadata） |
| `store_knowledge(id, content, metadata)` | 存储知识条目 | KnowledgeMemory.store_knowledge |
| `retrieve_knowledge(id)` | 检索知识条目 | KnowledgeMemory.retrieve_knowledge |
| `list_knowledge(category)` | 列出知识条目 | KnowledgeMemory.list_knowledge |
| `delete_knowledge(id)` | 删除知识条目 | KnowledgeMemory.delete_knowledge |
| `create_index(name, dimension, ...)` | 创建索引 | IndexManager.create_index |
| `delete_index(name)` | 删除索引 | IndexManager.delete_index |
| `list_indices()` | 列出所有索引 | IndexManager.list_indices |
| `get_index_stats(name)` | 获取索引统计 | IndexManager.get_index_stats |
| `optimize_index(name)` | 优化索引 | IndexManager.optimize_index |
| `index_exists(name)` | 检查索引是否存在 | IndexManager.index_exists |
| `get_full_history(session_id)` | 获取完整对话历史（含压缩部分） | MemoryStore.get_full_conversation |
| `compress_session(session_id)` | 强制压缩某会话历史 | MemoryStore.force_compress |
| `get_compression_stats(session_id)` | 获取会话压缩统计 | MemoryStore.get_compression_stats |
| `delete_session(session_id)` | 删除会话及所有数据 | MemoryStore.delete_session |
| `list_sessions(user_id)` | 列出会话（可按 user_id 过滤） | MemoryStore.list_sessions |
| `get_stats()` | 获取 L4 综合统计（向量数、缓存命中率等） | VectorStore.stats + Cache.stats |
| `clear_cache()` | 清空 EmbeddingCache 和 SearchCache | CacheManager.clear |

**便捷工厂函数：**
```python
from src.l4.core.l4_memory import create_memory_knowledge

# 快速创建（一行配置 provider + vector_store_type）
memory = create_memory_knowledge("openai", "chroma", persist_directory="./data")
```

---

### 2.2 Services — `embedding.py` (文本向量化)

将任意文本转换为固定维度的浮点向量，供相似度计算使用。

| 实现类 | 原理 | 维度 | 适用场景 |
|--------|------|------|---------|
| `OpenAIEmbeddingService` | 调用 OpenAI API | 1536/3072 | 生产环境，精度最高 |
| `SentenceTransformerService` | 本地模型 `all-MiniLM-L6-v2` | 384 | 无外网环境，隐私要求高 |
| `MockEmbeddingService` | MD5 作种子生成确定性随机向量 | 1536 | 测试/开发，零依赖 |

> **OpenAI 模型对照：** `text-embedding-3-small` (1536) / `text-embedding-3-large` (3072) / `text-embedding-ada-002` (1536)

**`embed_batch(texts)` 的关键处理：**
- 过滤空文本，插入零向量占位，保持输出顺序与输入一致
- OpenAI 实现中会合并有效文本为单批请求，减少 API 调用次数
- 所有异常统一包装为 `EmbeddingError`

---

### 2.3 Services — `text_chunker.py` (文本分块)

将长文档切分为语义连贯的小块，解决嵌入模型 token 上限问题和检索精度问题。

| 策略 | 分割依据 | 默认参数 | 特点 |
|------|---------|---------|------|
| `RecursiveTextChunker` | 分隔符优先级：`\n\n` → `\n` → `. ` → ` ` → 字符 | chunk_size=1000, overlap=200 | 最常用，保持段落/句子完整性 |
| `TokenTextChunker` | Token 数量（支持 tiktoken） | chunk_size=500, overlap=50 | 精确控制 token 数，适配模型限制 |
| `MarkdownTextChunker` | Markdown 标题 `#` / `##` / `###` | headers=`["#", "##", "###"]` | 保留文档结构，适合技术文档 |
| `CharacterTextChunker` | 固定字符数 | chunk_size=1000, overlap=200 | 最简单，无智能分割 |

**Overlap 机制：** 每个块（除第一个）前面追加前一块的最后 N 个字符，保证跨块边界语义不丢失。

---

### 2.4 Storage — `vector_store.py` (向量存储与检索)

提供统一的向量增删查接口，底层支持多种向量数据库。

| 实现 | 存储介质 | 检索方式 | 适用场景 |
|------|---------|---------|---------|
| `MemoryVectorStore` | Python dict（内存） | 暴力遍历 + NumPy 余弦相似度 | 测试、小数据集 |
| `ChromaVectorStore` | ChromaDB（可持久化到磁盘） | Chroma 内置 ANN + 距离转换 | 生产默认 |
| `FaissVectorStore` | Facebook FAISS 索引（内存） | FAISS 近似最近邻 | 海量数据、高性能本地检索 |
| `PineconeVectorStore` | 未实现（stub） | — | 预留，云服务扩展 |

**元数据过滤：**
所有实现均支持统一过滤语法：
```python
filters = {
    "category": "tech",              # 精确匹配
    "score": {"gte": 8, "lte": 10}, # 范围
    "tags": {"in": ["a", "b"]}      # 列表包含
}
```

---

### 2.5 Storage — `memory_store.py` (对话与偏好存储)

管理对话历史、用户偏好和知识元数据，核心特性是 **自动压缩**。

#### 存储类型抽象

| 抽象类 | 职责 | 方法 |
|--------|------|------|
| `ConversationMemory` | 对话历史 | `save_conversation`, `load_conversation`, `delete_session`, `list_sessions` |
| `UserPreferenceMemory` | 用户偏好 | `save_preference`, `load_preference` |
| `KnowledgeMemory` | 知识元数据 | `store_knowledge`, `retrieve_knowledge`, `list_knowledge`, `delete_knowledge` |
| `MemoryStore` | 统一基类（兼容旧代码） | 继承 ConversationMemory + UserPreferenceMemory |

#### 压缩机制 (`MemoryCompressor`)

**触发条件：** 消息数 >= `max_messages`（默认 20）

**压缩过程：**
1. 保留最近 `compression_threshold`（默认 10）条消息不压缩
2. 对更老的消息生成提取式摘要：
   - 提取用户问题（截断 100 字符）
   - 提取助手首句回复
   - 超过 5 个要点时保留头 2 + 尾 2
3. 将摘要包装为一条 `role="system"` 的消息：
   ```json
   {
     "role": "system",
     "content": "[Earlier conversation summary]: User asked: ... | Assistant responded about: ...",
     "is_compressed": true,
     "original_count": 15
   }
   ```
4. 替换老消息为摘要消息，保留最近消息

**为什么用提取式而非 LLM 生成式？**
- 不依赖 LLM，避免递归 API 调用和费用
- O(n) 线性扫描，毫秒级完成
- 输出确定，无幻觉风险
- 代价：连贯性稍弱，但足够支撑对话上下文

#### 实现类

| 实现 | 持久化 | 特点 |
|------|--------|------|
| `InMemoryStore` | 否（进程内存） | 自动压缩、元数据跟踪、支持强制压缩 |
| `FileMemoryStore` | 是（JSON 文件） | 同 InMemory，数据写入 `./src/l4/data/conversations/{session_id}.json` |

**各实现类的额外方法：**
- `InMemoryStore.get_all_preferences(user_id)` — 获取某用户的全部偏好
- `InMemoryUserPreferenceMemory.delete_preference(user_id, key)` — 删除指定偏好
- `InMemoryKnowledgeMemory.get_knowledge_count()` — 获取知识条目总数

---

### 2.6 Storage — `cache_manager.py` (缓存管理)

基于 `OrderedDict` 的线程安全 LRU 缓存，支持 TTL 过期。

#### 核心类 `CacheManager`

- **数据结构：** `OrderedDict`（最近使用在末尾），O(1) 的 LRU 操作
- **线程安全：** `threading.RLock()` 保护所有读写
- **驱逐策略：** 容量满时从头部弹出最久未使用项
- **过期策略：** 访问时惰性检查 TTL，超期即删
- **统计：** hits、misses、evictions、hit_rate

**扩展方法（除基础 get/set/delete 外）：**
| 方法 | 功能 |
|------|------|
| `get_or_set(key, factory, ttl)` | 缓存未命中时调用 factory 生成值并写入 |
| `get_many(keys)` / `set_many(items, ttl)` / `delete_many(keys)` | 批量读写删，减少锁竞争 |
| `keys()` | 获取所有未过期的键 |
| `size()` | 当前缓存条目数 |
| `cleanup_expired()` | 主动清理全部过期条目 |

#### 专用缓存子类

| 子类 | 用途 | 默认容量 | 默认 TTL | 键生成规则 |
|------|------|---------|---------|-----------|
| `EmbeddingCache` | 缓存文本→向量 | 1000 | 3600s | `emb:{provider}:{model}:{md5(text)}` |
| `SearchCache` | 缓存搜索结果 | 500 | 600s | `search:{md5(query:top_k:filter_str)}` |

**为什么 EmbeddingCache TTL 比 SearchCache 长？**
- Embedding 是文本的固有属性，同一文本的向量永远不变 → 可长期缓存
- 搜索结果依赖底层数据，可能随文档增删而变化 → 短 TTL 保证新鲜度

---

### 2.7 Index — `index_manager.py` (索引生命周期)

管理向量索引的创建、更新、删除、优化，是比 `VectorStore` 更高层的抽象。

| 方法 | 功能 |
|------|------|
| `create_index(name, dimension, **kwargs)` | 创建新索引/集合 |
| `update_index(name, documents)` | 向现有索引追加/更新文档（upsert 语义） |
| `delete_index(name)` | 删除索引 |
| `list_indices()` | 列出所有索引 |
| `get_index_stats(name)` | 获取索引统计（文档数、维度等） |
| `optimize_index(name)` | 优化索引（Chroma 下执行 persist） |
| `index_exists(name)` | 检查索引是否存在 |

---

## 三、关键数据流

### 3.1 语义搜索 `search("query")` 完整流程

```
MemoryKnowledge.search("machine learning", top_k=5)

  │
  ▼
1. 空查询校验 → query.strip() == "" 则返回 []
  │
  ▼
2. SearchCache 检查
   key = md5("machine learning:5:None")
   命中 → 直接返回缓存的 List[str]
   未命中 → 继续
  │
  ▼
3. _get_embedding("machine learning")
   a. EmbeddingCache 检查
      key = emb:{provider}:{model}:{md5(text)}
      命中 → 返回缓存向量
   b. 调用 EmbeddingService.embed()
      Mock:  用 MD5 种子生成确定性随机向量
      OpenAI: client.embeddings.create() API 调用
      SentenceTransformers: model.encode() 本地推理
   c. 写入 EmbeddingCache (TTL=3600s)
  │
  ▼
4. vector_store.search(embedding, top_k=5)
   Memory:  遍历全部文档，NumPy 计算 cosine similarity
   Chroma:  collection.query()，distance → similarity 转换
   FAISS:   index.search()，L2 归一化后检索
   均支持元数据过滤（精确匹配 / 范围 / 列表包含）
  │
  ▼
5. 提取 content 字段，按 score 降序排列，取 top_k
  │
  ▼
6. SearchCache.set_search_results(...) (TTL=600s)
  │
  ▼
返回 List[str]（按相似度排序的文本片段）
```

### 3.2 文档存储 `store(document, metadata)` 完整流程

```
MemoryKnowledge.store("Python is...", {"doc_id": "py-001"})

  │
  ▼
1. 校验：document 为空或 metadata 无 doc_id → return False
  │
  ▼
2. TextChunker.split(document)
   RecursiveTextChunker（默认）:
   - chunk_size=1000, chunk_overlap=200
   - 按 \n\n → \n → . → 空格 → 字符 递归分割
   - 返回: ["Python is...", "It has dynamic..."]
  │
  ▼
3. EmbeddingService.embed_batch(chunks)
   一次性将所有 chunks 发给嵌入服务
   返回: [[0.1, 0.2, ...], [0.3, 0.1, ...]]
  │
  ▼
4. 组装文档对象
   对每个 chunk i:
     id = "py-001_0", "py-001_1", ...
     metadata += {"chunk_index": i, "chunk_count": N}
   结构: {"id": ..., "content": ..., "embedding": ..., "metadata": ...}
  │
  ▼
5. VectorStore.add_documents(docs)
   Memory: dict[doc_id] = doc_dict
   Chroma: collection.add(ids, embeddings, metadatas, documents)
   FAISS:  index.add(normalized_vectors), 更新 ID 映射
  │
  ▼
6. 记录 chunk 映射
   _doc_chunks["py-001"] = ["py-001_0", "py-001_1", ...]
   用于后续 delete() 时级联删除全部 chunk
  │
  ▼
7. KnowledgeMemory.store_knowledge("py-001", content[:500], metadata)
   将原始文档前 500 字符作为摘要存入知识库元数据（可选，当 knowledge_store 启用时）
  │
  ▼
返回 True
```

### 3.3 对话存储 `store_conversation(session_id, messages)` 完整流程

```
MemoryKnowledge.store_conversation("session-123", messages)

  │
  ▼
1. 委托 memory_store.save_conversation(session_id, messages)
  │
  ▼
2. 压缩检查: len(messages) >= max_messages(20)?
   否 → 直接存储
   是 → 触发压缩
  │
  ▼
3. 压缩执行 (MemoryCompressor)
   a. 拆分: oldest (messages[0:-10]) 待压缩, recent (messages[-10:]) 保留
   b. 生成提取式摘要:
      - User asked: {truncated_content}
      - Assistant responded about: {first_sentence}
      - 超过5个要点取头2+尾2
   c. 组装:
      [
        {"role": "system", "content": "[Earlier conversation summary]: ...", "is_compressed": true},
        ...recent messages...
      ]
   d. 记录压缩统计
  │
  ▼
4. 存储
   InMemory: dict[session_id] = messages
   File: 写 JSON 到 ./src/l4/data/conversations/{session_id}.json
  │
  ▼
返回 True
```

### 3.4 ReAct 循环（L3）如何使用 L4

```
L3 Orchestration.run(context, observation=None)

  │
  ▼
1. SecurityGuard.classify(query)           ← L3 内部安全判断
  │
  ▼
2. memory_accessor.retrieve_for_query(query, session_id)
   ├── memory.search(query, top_k=3)       ← L4 向量检索
   │   → 返回 ["相关知识片段1", "相关知识片段2"]
   └── memory.retrieve_history(session_id)  ← L4 对话历史
       → 返回最近 10 轮消息
   → 组装为 {knowledge: [...], history_summary: "..."}
  │
  ▼
3. react_engine.generate_thought(
       query=...,
       knowledge=retrieval_result["knowledge"],  ← L4 结果注入 LLM Prompt
       history=history,
       available_tools=...
   )
   → LLM 生成 Thought + Action
  │
  ▼
4. 如果 Action 是工具调用 → 返回 AgentAction → L2 → L5
   如果是最终答案 → 返回 str
  │
  ▼
5. L5 返回 Observation → L2 再次调用 L3.run(observation=...)
   → ReAct 循环继续，再次调用 L4.search() 获取知识
```

**关键设计：** L4 是完全被动的。L3 只在需要时主动调用 `search()` 和 `retrieve_history()`，L4 不会主动推送任何信息。

---

## 四、设计模式

| 模式 | 应用位置 | 作用 |
|------|---------|------|
| **工厂方法** | `create_embedding_service()` / `create_vector_store()` / `create_text_chunker()` / `create_memory_store()` / `create_index_manager()` | 运行时选择实现，开发用 Mock，生产用 OpenAI/Chroma |
| **策略模式** | `EmbeddingService` / `TextChunker` / `VectorStore` / `MemoryStore` / `IndexManager` | 算法与实现可替换，同一接口不同后端 |
| **模板方法** | `CacheManager` 基类 + `EmbeddingCache` / `SearchCache` | 通用缓存逻辑复用，子类 specialize 键生成 |
| **外观模式** | `MemoryKnowledge` | 统一门面，隐藏 6+ 子系统的复杂性 |
| **抽象基类 (ABC)** | 所有 service / storage / index 接口 | 强制契约，支持多态和依赖注入 |
| **依赖注入** | `MemoryInterface` | L3 不依赖 L4 具体实现，便于测试和替换 |

---

## 五、开发 → 生产切换路径

所有组件通过配置字典或 `.env` 环境变量切换，**无需修改代码**。

| 组件 | 开发环境 | 生产环境 |
|------|---------|---------|
| 向量化 | `MockEmbeddingService` | `OpenAIEmbeddingService` |
| 向量存储 | `MemoryVectorStore`（内存，重启丢失） | `ChromaVectorStore`（磁盘持久化到 `./src/l4/data/chroma_db`） |
| 对话存储 | `InMemoryStore` | `FileMemoryStore`（持久化到 `./src/l4/data/conversations`） |
| 缓存 | 开启（默认 TTL） | 开启（Embedding 1h / Search 10min） |
| 索引管理 | `MemoryIndexManager` | `ChromaIndexManager` |

配置入口：`src/l4/config/l4_config.py`

```python
# 开发环境（零外部依赖）
memory = get_l4_memory_development()

# 生产环境（需要 OPENAI_API_KEY，自动创建数据目录）
memory = get_l4_memory_production()
# 生产配置会自动创建以下目录（如不存在）：
#   - ./src/l4/data/chroma_db      (ChromaDB 持久化)
#   - ./src/l4/data/conversations  (对话历史)
#   - ./src/l4/data/preferences    (用户偏好)
```

---

## 六、测试覆盖

| 测试文件 | 测试内容 | 用例数 |
|---------|---------|--------|
| `test_embedding.py` | Mock / OpenAI / SentenceTransformers | ~20 |
| `test_text_chunker.py` | 4 种分块策略 + 工厂 + 集成 | ~35 |
| `test_vector_store.py` | Memory / Chroma / FAISS / Pinecone stub | 26 |
| `test_memory_store.py` | InMemory / File / 压缩 / 3 种存储类型 | 44 |
| `test_cache_manager.py` | LRU / TTL / EmbeddingCache / SearchCache | 26 |
| `test_index_manager.py` | MemoryIndexManager / 工厂 / update_index | 20 |
| `test_l4_memory.py` | MemoryKnowledge 集成测试 | ~30 |
| `test_l4.py` | L4 端到端工作流 | ~20 |

**总计：199 passed, 4 skipped**（4 个跳过为可选外部依赖 `sentence-transformers` / `faiss` 条件测试）

---

## 七、与 XML 规范的对应关系

| XML 规范 | 代码实现 | 对齐状态 |
|---------|---------|---------|
| `docs/03_specs/l4/VectorStore.xml` | `src/l4/storage/vector_store.py` | 对齐（4 种实现 + stub） |
| `docs/03_specs/l4/EmbeddingService.xml` | `src/l4/services/embedding.py` | 对齐（3 种 provider） |
| `docs/03_specs/l4/TextChunker.xml` | `src/l4/services/text_chunker.py` | 对齐（4 种策略） |
| `docs/03_specs/l4/MemoryStore.xml` | `src/l4/storage/memory_store.py` | 对齐（3 种存储类型 + 压缩） |
| `docs/03_specs/l4/IndexManager.xml` | `src/l4/index/index_manager.py` | 对齐（CRUD + optimize） |
| `docs/03_specs/l4/CacheManager.xml` | `src/l4/storage/cache_manager.py` | 对齐（LRU + TTL + 专用缓存） |
| `docs/03_specs/l4/integration.xml` | `src/l4/core/l4_memory.py` | 对齐（数据流 + 调用边） |
| `docs/03_specs/L4_MemoryKnowledge.xml` | 全部 L4 代码 | 对齐（架构总纲） |

---

*最后更新: 2026-04-23*
