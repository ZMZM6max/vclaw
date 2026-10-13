# L2 ControlGateway 增强设计文档

**日期**: 2026-04-12  
**版本**: 1.0  
**状态**: 待实施

---

## 1. 背景与目标

### 1.1 当前状态

L2 控制网关层已实现基础功能：
- ✅ `RateLimiter` - Token Bucket 限流（仅用户级）
- ✅ `SessionManager` - 基础会话管理
- ✅ `HistoryRetriever` - 从 L4 检索历史记录
- ✅ 基础 `ContextAssembler` - 组装 SessionContext

### 1.2 目标

按照 `docs/L2_ControlGateway.xml` 规范，完善 L2 组件，实现：
1. 完整的三级限流（用户/IP/全局）
2. 新增 `MemoryAccessor` 组件（调用 L4 检索相关记忆）
3. 新增 `ToolPreparer` 组件（调用 L5 获取可用工具）
4. 完善 `ContextAssembler` 输出完整的 `L3Input`
5. 实现 L1→L2→L3 完整数据流

---

## 2. 核心设计

### 2.1 数据模型

#### 新增 `L3Input` 模型

```python
# src/core/models.py

class L3Input(BaseModel):
    """L2 输出 / L3 输入 - 完整的逻辑编排层输入"""
    session_context: SessionContext = Field(
        ..., 
        description="会话上下文，包含 session_id, user_id, current_query, history 等"
    )
    available_tools: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="根据用户权限筛选的可用工具列表"
    )
    relevant_memories: List[str] = Field(
        default_factory=list,
        description="从 L4 检索的与用户查询相关的记忆片段"
    )
```

### 2.2 组件设计

#### 2.2.1 MemoryAccessor（新增）

**职责**: 从 L4 检索与用户当前查询相关的记忆片段

```python
class MemoryAccessor:
    """
    记忆访问器
    
    调用 L4.search() 检索与用户查询语义相关的记忆，
    用于增强 L3 的上下文理解。
    """
    
    def __init__(self, memory: MemoryInterface = None):
        self.memory = memory or MemoryKnowledge()
    
    def retrieve_relevant(
        self, 
        query: str, 
        user_id: str, 
        top_k: int = 5
    ) -> List[str]:
        """
        检索相关记忆片段
        
        Args:
            query: 用户当前查询内容
            user_id: 用户标识（用于过滤）
            top_k: 返回最相关的 k 条记忆
            
        Returns:
            记忆内容字符串列表
        """
        results = self.memory.search(
            query=query,
            top_k=top_k,
            filters={"user_id": user_id}
        )
        return [doc.content for doc in results]
```

**配置参数**:
- `top_k`: 5（默认检索 5 条相关记忆）
- `filters`: 按 user_id 过滤，确保隐私

---

#### 2.2.2 ToolPreparer（新增）

**职责**: 从 L5 获取工具定义，并根据用户权限筛选

```python
class ToolPreparer:
    """
    工具准备器
    
    从 L5.ToolRegistry 获取工具定义，
    根据 user_permissions 筛选用户有权限使用的工具。
    
    注意：L2 只负责权限筛选，不定义工具本身。
    """
    
    # 工具权限映射表
    TOOL_PERMISSION_MAP = {
        "calculator": None,           # 无需权限，始终可用
        "file_read": "file_read",     # 需要 file_read 权限
        "file_write": "file_write",   # 需要 file_write 权限
        "python_repl": "execute_code", # 需要 execute_code 权限
        "terminal": "execute_command", # 需要 execute_command 权限
        "search_web": "web_access"    # 需要 web_access 权限
    }
    
    def __init__(self, tools: ToolsInterface = None):
        self.tools = tools or ToolsCapabilities()
    
    def prepare_tools(self, user_permissions: List[str]) -> List[Dict[str, Any]]:
        """
        准备可用工具列表
        
        Args:
            user_permissions: 用户拥有的权限列表
            
        Returns:
            用户有权限使用的工具定义列表
        """
        all_tools = self.tools.list_tools()  # 从 L5 获取所有工具
        
        available = []
        for tool in all_tools:
            tool_name = tool.get("name")
            required_perm = self.TOOL_PERMISSION_MAP.get(tool_name)
            
            # 无需权限 或 用户有权限
            if required_perm is None or required_perm in user_permissions:
                available.append(tool)
        
        return available
```

---

#### 2.2.3 增强 RateLimiter

**当前**: 仅支持用户级限流（60请求/分钟）  
**增强**: 支持三级限流

```python
class RateLimiter:
    """
    三级限流器（Token Bucket 算法）
    
    优先级：全局 > IP > 用户
    任一级别超限即拒绝请求。
    """
    
    DEFAULT_LIMITS = {
        "user": (60, 60),      # 60 requests per 60 seconds
        "ip": (100, 60),       # 100 requests per 60 seconds
        "global": (1000, 1)    # 1000 requests per 1 second
    }
    
    def __init__(self, limits: Dict[str, Tuple[int, int]] = None):
        self.limits = limits or self.DEFAULT_LIMITS
        
        # 三级存储
        self.user_buckets: Dict[str, deque] = defaultdict(deque)
        self.ip_buckets: Dict[str, deque] = defaultdict(deque)
        self.global_bucket: deque = deque()
    
    def is_allowed(
        self, 
        user_id: str, 
        ip: str = None
    ) -> Tuple[bool, Optional[str]]:
        """
        检查请求是否允许
        
        Returns:
            (is_allowed, reason)
            - is_allowed: True if allowed
            - reason: None if allowed, else rejection reason
        """
        now = time.time()
        
        # 1. 检查全局限流
        if not self._check_bucket(self.global_bucket, "global", now):
            return False, "global_rate_limit"
        
        # 2. 检查 IP 限流
        if ip and not self._check_bucket(self.ip_buckets[ip], "ip", now):
            return False, "ip_rate_limit"
        
        # 3. 检查用户限流
        if not self._check_bucket(self.user_buckets[user_id], "user", now):
            return False, "user_rate_limit"
        
        return True, None
    
    def _check_bucket(
        self, 
        bucket: deque, 
        level: str, 
        now: float
    ) -> bool:
        """检查单个令牌桶"""
        max_requests, window = self.limits[level]
        
        # 清理过期请求
        while bucket and bucket[0] < now - window:
            bucket.popleft()
        
        # 检查是否超限
        if len(bucket) >= max_requests:
            return False
        
        # 添加当前请求
        bucket.append(now)
        return True
```

---

#### 2.2.4 增强 ControlGateway

```python
class ControlGateway:
    """
    L2 控制网关（增强版）
    
    职责：
    1. 限流控制（用户/IP/全局）
    2. 会话管理
    3. 历史记录检索
    4. 相关记忆检索（新增）
    5. 工具准备（新增）
    6. 组装完整 L3Input（增强）
    """
    
    def __init__(
        self,
        memory: MemoryInterface = None,
        tools: ToolsInterface = None,
        session_max_age: int = 3600
    ):
        # 依赖注入
        self.memory = memory or MemoryKnowledge()
        self.tools = tools or ToolsCapabilities()
        
        # 组件初始化
        self.rate_limiter = RateLimiter()
        self.memory_accessor = MemoryAccessor(self.memory)
        self.tool_preparer = ToolPreparer(self.tools)
        
        # 会话管理
        self.sessions: Dict[str, Dict] = {}
        self.session_max_age = session_max_age
        self._request_count = 0
    
    def process_event(self, event: StandardEvent) -> L3Input:
        """
        处理 L1 输入事件，输出完整的 L3Input
        
        流程：
        1. 限流检查
        2. 获取/创建会话
        3. 检索历史记录
        4. 检索相关记忆（新增）
        5. 准备可用工具（新增）
        6. 组装 L3Input（增强）
        """
        # Step 1: 限流检查
        allowed, reason = self.rate_limiter.is_allowed(
            user_id=event.user_id,
            ip=event.metadata.get("client_ip")
        )
        if not allowed:
            raise RateLimitExceeded(f"Rate limit exceeded: {reason}")
        
        # Step 2: 获取或创建会话
        session_id = self._get_or_create_session(event)
        
        # Step 3: 检索历史记录
        history = self.memory.retrieve_history(session_id, limit=10)
        
        # Step 4: 检索相关记忆（新增）
        relevant_memories = self.memory_accessor.retrieve_relevant(
            query=event.content,
            user_id=event.user_id,
            top_k=5
        )
        
        # Step 5: 准备可用工具（新增）
        # TODO: 从 session 或配置文件获取 user_permissions
        user_permissions = []  # 暂时为空
        available_tools = self.tool_preparer.prepare_tools(user_permissions)
        
        # Step 6: 组装 SessionContext
        session_context = SessionContext(
            session_id=session_id,
            user_id=event.user_id,
            current_query=event.content,
            history=history,
            user_permissions=user_permissions,
            metadata={
                "channel": event.channel,
                "event_metadata": event.metadata
            }
        )
        
        # Step 7: 组装完整 L3Input（增强）
        return L3Input(
            session_context=session_context,
            available_tools=available_tools,
            relevant_memories=relevant_memories
        )
    
    def _get_or_create_session(self, event: StandardEvent) -> str:
        """获取现有会话或创建新会话"""
        session_id = event.metadata.get("session_id")
        
        if session_id and session_id in self.sessions:
            # 检查会话是否过期
            session_data = self.sessions[session_id]
            age = time.time() - session_data.get("created_at", 0)
            if age < self.session_max_age:
                return session_id
        
        # 创建新会话
        new_session_id = str(uuid.uuid4())
        self.sessions[new_session_id] = {
            "user_id": event.user_id,
            "created_at": time.time()
        }
        
        # 定期清理过期会话
        self._request_count += 1
        if self._request_count >= 100:
            self._cleanup_expired_sessions()
            self._request_count = 0
        
        return new_session_id
    
    def _cleanup_expired_sessions(self):
        """清理过期会话"""
        now = time.time()
        expired = [
            sid for sid, data in self.sessions.items()
            if now - data.get("created_at", 0) > self.session_max_age
        ]
        for sid in expired:
            del self.sessions[sid]
```

---

## 3. 数据流

### 3.1 完整数据流

```
┌─────────────────────────────────────────────────────────────────────┐
│                          L1 UserInteraction                          │
│                    (输出 StandardEvent)                               │
└────────────────────────┬────────────────────────────────────────────┘
                         │ StandardEvent
                         │ - user_id
                         │ - content
                         │ - metadata.session_id (可选)
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        L2 ControlGateway                             │
├─────────────────────────────────────────────────────────────────────┤
│  Step 1: RateLimiter.is_allowed()                                   │
│    ├── 检查全局限流 (1000 req/s)                                     │
│    ├── 检查 IP 限流 (100 req/min)                                    │
│    └── 检查用户限流 (60 req/min)                                     │
│                                                                     │
│  Step 2: SessionManager._get_or_create_session()                    │
│    ├── 从 metadata 获取 session_id                                  │
│    ├── 若存在且有效 → 复用                                           │
│    └── 否则 → 创建新 UUID                                            │
│                                                                     │
│  Step 3: HistoryRetriever (self.memory.retrieve_history)            │
│    └── 从 L4 检索最近 10 轮对话历史                                  │
│                                                                     │
│  Step 4: MemoryAccessor.retrieve_relevant()      [NEW]              │
│    └── 调用 L4.search(query, top_k=5)                                │
│    └── 返回相关记忆片段列表                                           │
│                                                                     │
│  Step 5: ToolPreparer.prepare_tools()            [NEW]              │
│    └── 调用 L5.list_tools()                                          │
│    └── 根据 user_permissions 筛选                                     │
│    └── 返回可用工具列表                                               │
│                                                                     │
│  Step 6: ContextAssembler                                          │
│    └── 组装 SessionContext                                           │
│    └── 组装 L3Input                  [ENHANCED]                     │
│                                                                     │
└────────────────────────┬────────────────────────────────────────────┘
                         │ L3Input
                         │ - session_context
                         │ - available_tools
                         │ - relevant_memories
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         L3 Orchestration                             │
│                    (接收 L3Input, 执行 ReAct 循环)                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. 接口抽象

### 4.1 MemoryInterface（已存在，需确认）

```python
class MemoryInterface(ABC):
    @abstractmethod
    def retrieve_history(self, session_id: str, limit: int) -> List[Dict[str, str]]:
        """检索会话历史记录"""
        pass
    
    @abstractmethod
    def search(self, query: str, top_k: int, filters: Dict) -> List[Document]:
        """语义搜索相关记忆"""
        pass
```

### 4.2 ToolsInterface（新增）

```python
class ToolsInterface(ABC):
    @abstractmethod
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        获取所有注册的工具定义
        
        Returns:
            工具定义列表，每个工具包含：
            - name: 工具名称
            - description: 工具描述
            - parameters: 参数定义（JSON Schema 格式）
        """
        pass
```

---

## 5. 测试策略

### 5.1 单元测试

| 组件 | 测试用例 | 描述 |
|------|----------|------|
| RateLimiter | `test_rate_limit_user` | 用户级限流 |
| RateLimiter | `test_rate_limit_ip` | IP 级限流 |
| RateLimiter | `test_rate_limit_global` | 全局限流 |
| MemoryAccessor | `test_retrieve_relevant` | 检索相关记忆 |
| ToolPreparer | `test_prepare_tools_with_permissions` | 权限筛选工具 |
| ToolPreparer | `test_prepare_tools_no_permissions` | 无权限时仅返回无权限工具 |
| ControlGateway | `test_process_event_returns_l3input` | 验证输出 L3Input |

### 5.2 集成测试

| 测试用例 | 描述 |
|----------|------|
| `test_l1_l2_l3_flow` | 验证 L1→L2→L3 完整数据流 |
| `test_l2_calls_l4_search` | 验证 L2 正确调用 L4.search() |
| `test_l2_calls_l5_list_tools` | 验证 L2 正确调用 L5.list_tools() |

---

## 6. 实施阶段

### Phase 1: 基础组件完善（1-2 天）

**目标**: 可独立测试的 L2 组件

| 任务 | 描述 | 优先级 |
|------|------|--------|
| 1.1 | 添加 `L3Input` 数据模型 | P0 |
| 1.2 | 增强 `RateLimiter`（IP/全局） | P0 |
| 1.3 | 创建 `MemoryAccessor` | P0 |
| 1.4 | 创建 `ToolPreparer` | P0 |
| 1.5 | 增强 `ControlGateway.process_event()` | P0 |
| 1.6 | 单元测试 | P0 |
| 1.7 | 更新 XML 文档 | P1 |
| 1.8 | 更新 README 文档 | P1 |

### Phase 2: L3 集成（1 天）

**目标**: 打通 L1→L2→L3 数据流

| 任务 | 描述 | 优先级 |
|------|------|--------|
| 2.1 | 创建 `L3Interface` 抽象 | P0 |
| 2.2 | 实现 L3 调用（或 Mock） | P0 |
| 2.3 | 集成测试 | P0 |

### Phase 3: 真实环境测试（1-2 天）

**目标**: 在真实场景中验证 L2

| 任务 | 描述 | 优先级 |
|------|------|--------|
| 3.1 | 创建 L2 真实测试脚本 | P1 |
| 3.2 | 配合 L1 Telegram 测试 | P1 |
| 3.3 | 验证完整链路 | P1 |

---

## 7. 文档同步要求

根据 CLAUDE.md 的文档同步规则：

| 修改内容 | 需更新的文档 |
|----------|--------------|
| `src/l2/l2_control_gateway.py` | `docs/L2_ControlGateway.xml` + `src/l2/tests/README.md` |
| `src/core/models.py` (L3Input) | 所有引用 L3Input 的层 XML 文档 |
| `src/core/interfaces.py` (ToolsInterface) | `docs/L5_ToolsCapabilities.xml` |
| 新增测试文件 | `src/l2/tests/README.md` + `docs/L2_ControlGateway.xml` |

---

## 8. 风险与注意事项

### 8.1 已知风险

1. **L4 Mock 实现**: 当前 L4 是 Mock，检索结果可能不够真实
2. **权限系统**: user_permissions 来源尚未确定（Session？配置？）
3. **并发安全**: 当前实现非线程安全，生产环境需要 Redis

### 8.2 兼容性

- 保持与现有 L1 的兼容性
- 保持与现有 L4 接口的兼容性
- 新增功能通过依赖注入，不破坏现有代码

---

## 9. 附录

### 9.1 术语表

| 术语 | 说明 |
|------|------|
| L3Input | L2 输出给 L3 的完整输入结构 |
| MemoryAccessor | 记忆访问器，从 L4 检索相关记忆 |
| ToolPreparer | 工具准备器，从 L5 获取并筛选工具 |
| Token Bucket | 令牌桶限流算法 |

### 9.2 参考文档

- `docs/L2_ControlGateway.xml` - L2 架构规范
- `docs/L4_MemoryKnowledge.xml` - L4 接口规范
- `docs/L5_ToolsCapabilities.xml` - L5 工具规范
- `CLAUDE.md` - 项目开发指南

---

**设计确认**: 待用户确认后进入实施计划阶段
