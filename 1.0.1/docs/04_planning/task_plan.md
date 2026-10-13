# VClaw 六层架构构建计划

## 当前状态分析

### 已完成的组件（基础实现）

| 层级 | 组件 | 状态 | 说明 |
|------|------|------|------|
| **L1** | UserInteraction | ✅ | 基础实现完成，支持Telegram/WebSocket/Webhook |
| | DataValidator | ✅ | 基础验证实现 |
| | EventNormalizer | ✅ | 三种渠道标准化实现 |
| **L2** | ControlGateway | ✅ | 基础实现完成，限流、会话管理 |
| | RateLimiter | ✅ | Token Bucket算法实现 |
| **L3** | Orchestration | ✅ | 基础ReAct循环实现 |
| | LLMManager | ⚠️ | Mock实现，需要真实LLM集成 |
| **L4** | MemoryKnowledge | ✅ | 基础实现完成 |
| | EmbeddingService | ⚠️ | Mock实现，需要真实Embedding |
| | MemoryVectorStore | ✅ | 内存实现，可选ChromaDB |
| **L5** | ToolsCapabilities | ✅ | 基础工具实现 |
| | Tool注册/验证 | ✅ | 实现完成 |
| **L6** | RuntimeEnvironment | ✅ | 基础沙盒实现 |
| | ProcessSandbox | ✅ | 进程级沙盒实现 |

### 存在的问题

1. **L5代码重复**: ValidationError和ExecutionTimeoutError重复定义
2. **Mock实现**: LLM、Embedding、向量存储都是Mock，需要真实实现
3. **缺少Web服务**: 没有HTTP API层
4. **缺少配置管理**: 没有.env或配置文件支持
5. **缺少日志系统**: 没有结构化日志
6. **缺少监控**: 没有健康检查和指标

---

## 构建阶段

### Phase 1: 修复现有问题 (优先级: P0)

#### Task 1.1: 修复L5重复定义
**文件**: `src/l5_tools.py`
**问题**: ValidationError和ExecutionTimeoutError重复定义
**预计时间**: 5分钟
**验收标准**: 代码无重复，测试通过

#### Task 1.2: 完善异常类定义
**文件**: `src/exceptions.py` (新建)
**目标**: 统一所有异常类，避免重复定义
**预计时间**: 15分钟
**验收标准**: 
- 所有异常类集中定义
- 每层从exceptions导入
- 保留向后兼容性

---

### Phase 2: 真实LLM集成 (优先级: P1)

#### Task 2.1: 集成OpenAI API
**文件**: 
- `src/l3_orchestration.py` (修改)
- `src/llm_providers/openai_provider.py` (新建)
**目标**: 替换Mock LLMManager为真实OpenAI调用
**功能**:
- 支持GPT-4/GPT-3.5
- 支持对话完成
- 支持流式响应
- 支持工具调用（Function Calling）
**配置**:
- OPENAI_API_KEY
- OPENAI_MODEL
- OPENAI_BASE_URL (可选)
**预计时间**: 1小时
**验收标准**:
- 能成功调用OpenAI API
- 支持ReAct循环中的工具决策
- 正确处理API错误和重试

#### Task 2.2: 添加LLM Provider抽象
**文件**: `src/llm_providers/base.py` (新建)
**目标**: 支持多LLM提供商
**接口**:
```python
class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages, tools=None, temperature=0.7) -> Union[str, AgentAction]
    @abstractmethod
    def stream(self, messages) -> Iterator[str]
```
**预计时间**: 30分钟
**验收标准**:
- 抽象接口定义清晰
- OpenAIProvider实现接口
- 易于扩展其他提供商(Claude、本地模型等)

---

### Phase 3: 真实Embedding和向量存储 (优先级: P1)

#### Task 3.1: 集成真实Embedding服务
**文件**:
- `src/l4_memory.py` (修改)
- `src/embeddings/openai_embedding.py` (新建)
**目标**: 替换Mock Embedding为真实服务
**选项**:
1. OpenAI Embedding API (text-embedding-ada-002/3)
2. 本地模型 (sentence-transformers)
**配置**:
- EMBEDDING_PROVIDER (openai/local)
- OPENAI_API_KEY
- LOCAL_MODEL_NAME (可选)
**预计时间**: 45分钟
**验收标准**:
- 能生成1536维向量
- 支持批量Embedding
- 有缓存机制避免重复计算

#### Task 3.2: 集成ChromaDB
**文件**:
- `src/l4_memory.py` (修改)
- `src/vector_stores/chroma_store.py` (新建)
**目标**: 提供持久化向量存储选项
**功能**:
- 文档存储和检索
- 相似度搜索
- 元数据过滤
- 持久化到磁盘
**配置**:
- VECTOR_STORE_TYPE (memory/chroma)
- CHROMA_PERSIST_DIR
**预计时间**: 1小时
**验收标准**:
- 能持久化存储文档
- 支持相似度检索
- 比内存存储更准确

#### Task 3.3: 向量存储抽象
**文件**: `src/vector_stores/base.py` (新建)
**目标**: 支持多种向量存储后端
**接口**:
```python
class VectorStore(ABC):
    @abstractmethod
    def add(self, doc_id, content, embedding, metadata)
    @abstractmethod
    def search(self, query_embedding, top_k=5, filters=None)
    @abstractmethod
    def delete(self, doc_id)
```
**预计时间**: 30分钟
**验收标准**:
- 抽象接口清晰
- MemoryVectorStore和ChromaVectorStore都实现接口

---

### Phase 4: Web服务层 (优先级: P1)

#### Task 4.1: FastAPI应用
**文件**: `src/api/main.py` (新建)
**目标**: 创建HTTP API服务
**端点**:
```
POST /api/v1/chat              # 聊天接口
POST /api/v1/tools/execute     # 工具执行接口
GET  /api/v1/tools             # 获取可用工具
POST /api/v1/memory/store      # 存储文档
GET  /api/v1/memory/search     # 检索文档
GET  /health                   # 健康检查
```
**预计时间**: 1.5小时
**验收标准**:
- 所有端点可访问
- 有输入验证
- 有错误处理
- 有OpenAPI文档

#### Task 4.2: WebSocket支持
**文件**: `src/api/websocket.py` (新建)
**目标**: 支持实时双向通信
**功能**:
- 连接管理
- 消息处理
- 流式响应
**预计时间**: 1小时
**验收标准**:
- 能建立WebSocket连接
- 能发送/接收消息
- 支持流式输出

#### Task 4.3: 请求/响应模型
**文件**: `src/api/models.py` (新建)
**目标**: 定义API数据模型
**模型**:
- ChatRequest/ChatResponse
- ToolExecuteRequest/ToolExecuteResponse
- DocumentStoreRequest
**预计时间**: 30分钟
**验收标准**:
- 所有模型使用Pydantic
- 有字段验证
- 有示例值

---

### Phase 5: 配置管理 (优先级: P2)

#### Task 5.1: 配置系统
**文件**: `src/config.py` (新建)
**目标**: 集中管理所有配置
**配置项**:
```python
class Settings(BaseSettings):
    # LLM
    openai_api_key: str
    openai_model: str = "gpt-4"
    
    # Embedding
    embedding_provider: str = "openai"
    
    # Vector Store
    vector_store_type: str = "memory"
    chroma_persist_dir: str = "./chroma_db"
    
    # Rate Limiting
    rate_limit_requests: int = 60
    rate_limit_window: int = 60
    
    # Runtime
    sandbox_timeout: int = 30
    max_output_length: int = 10000
```
**预计时间**: 30分钟
**验收标准**:
- 支持.env文件
- 有默认值
- 类型安全

---

### Phase 6: 日志和监控 (优先级: P2)

#### Task 6.1: 日志系统
**文件**: `src/logging_config.py` (新建)
**目标**: 结构化日志记录
**功能**:
- 分层日志（DEBUG/INFO/WARNING/ERROR）
- JSON格式输出
- 包含请求ID追踪
**预计时间**: 30分钟
**验收标准**:
- 所有层都有日志
- 日志格式统一
- 可配置日志级别

#### Task 6.2: 健康检查
**文件**: `src/api/health.py` (新建)
**目标**: 系统健康监控
**检查项**:
- LLM服务可用性
- 向量存储连接
- 沙盒环境可用
**预计时间**: 20分钟
**验收标准**:
- /health端点返回状态
- 能检测各组件健康

---

### Phase 7: 端到端测试 (优先级: P1)

#### Task 7.1: 完整工作流测试
**文件**: `tests/test_e2e.py` (新建)
**目标**: 测试完整用户流程
**场景**:
1. 简单聊天
2. 工具调用流程
3. 带记忆的对话
4. 代码执行流程
**预计时间**: 1小时
**验收标准**:
- 所有场景通过
- 测试独立可运行
- 有Mock外部服务

#### Task 7.2: 性能测试
**文件**: `tests/test_performance.py` (新建)
**目标**: 测试系统性能
**指标**:
- 响应时间
- 并发处理能力
- 资源使用
**预计时间**: 30分钟
**验收标准**:
- 有基准性能数据
- 能检测性能退化

---

### Phase 8: 部署准备 (优先级: P2)

#### Task 8.1: Docker支持
**文件**:
- `Dockerfile`
- `docker-compose.yml`
**目标**: 容器化部署
**功能**:
- 多阶段构建
- 依赖隔离
- 环境变量注入
**预计时间**: 45分钟
**验收标准**:
- 能构建Docker镜像
- 能用docker-compose启动
- 包含所有依赖

#### Task 8.2: 部署文档
**文件**: `DEPLOYMENT.md` (新建)
**内容**:
- 环境要求
- 安装步骤
- 配置说明
- 监控和日志
**预计时间**: 30分钟
**验收标准**:
- 文档完整
- 步骤清晰
- 有故障排查

---

## 依赖关系图

```
Phase 1 (修复)
    ↓
Phase 2 (LLM) ─┬→ Phase 3 (Embedding/向量存储)
               │
               └→ Phase 4 (Web服务)
                       ↓
                  Phase 5 (配置)
                       ↓
                  Phase 6 (日志/监控)
                       ↓
                  Phase 7 (E2E测试)
                       ↓
                  Phase 8 (部署)
```

---

## 实施建议

### 第一批（核心功能）
1. Phase 1: 修复问题
2. Phase 2: LLM集成
3. Phase 4.1: FastAPI基础
4. Phase 7: E2E测试

**目标**: 让系统能跑通完整流程

### 第二批（增强功能）
1. Phase 3: Embedding和向量存储
2. Phase 4.2: WebSocket
3. Phase 5: 配置管理
4. Phase 6: 日志监控

### 第三批（生产就绪）
1. Phase 8: Docker和部署
2. 性能优化
3. 安全加固
4. 文档完善

---

## 验收清单

- [ ] 所有Phase 1任务完成
- [ ] OpenAI LLM能正常调用
- [ ] FastAPI服务能启动
- [ ] /chat端点能返回响应
- [ ] E2E测试全部通过
- [ ] Docker能构建和运行
- [ ] 文档完整

---

**创建时间**: 2024年
**更新**: 进行中
