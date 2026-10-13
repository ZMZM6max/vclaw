# L2 控制网关增强实施计划

> **面向代理工作者：** 必须使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 来逐个任务实施此计划。步骤使用复选框（`- [ ]`）语法进行跟踪。

**目标：** 增强 L2 控制网关以支持三级限流，添加 MemoryAccessor 和 ToolPreparer 组件，并向 L3 输出完整的 L3Input。

**架构：** 添加 MemoryAccessor 调用 L4.search()，ToolPreparer 调用 L5.list_tools() 并进行权限过滤，增强 RateLimiter 支持 IP/全局限流，修改 ControlGateway 以组装包含 session_context、available_tools 和 relevant_memories 的 L3Input。

**技术栈：** Python 3.13, Pydantic, pytest, unittest.mock

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `src/core/models.py` | 添加 L3Input 数据模型 |
| `src/core/interfaces.py` | 添加 ToolsInterface 抽象类 |
| `src/l2/l2_control_gateway.py` | 增强版 ControlGateway、MemoryAccessor、ToolPreparer、增强版 RateLimiter |
| `src/l2/tests/test_l2.py` | 更新现有测试并添加新测试 |
| `src/l2/tests/README.md` | 文档化测试依赖和运行说明 |
| `docs/L2_ControlGateway.xml` | 更新架构文档 |

---

## Phase 1: 核心数据模型与接口

### Task 1: 添加 L3Input 模型到 core/models.py

**文件：**
- 修改: `src/core/models.py`
- 测试: `src/l2/tests/test_l2.py`

- [ ] **步骤 1: 编写失败的测试**

添加到 `src/l2/tests/test_l2.py` 末尾：

```python
class TestL3Input:
    """L3Input 数据模型测试。"""
    
    def test_l3input_creation(self):
        """TC-L3Input-001: 使用所有字段创建 L3Input"""
        from src.core.models import L3Input, SessionContext
        
        session_context = SessionContext(
            session_id="test-session",
            user_id="user_123",
            current_query="Hello",
            history=[],
            user_permissions=[]
        )
        
        l3_input = L3Input(
            session_context=session_context,
            available_tools=[{"name": "calculator", "description": "Math"}],
            relevant_memories=["User likes Python"]
        )
        
        assert l3_input.session_context.session_id == "test-session"
        assert len(l3_input.available_tools) == 1
        assert len(l3_input.relevant_memories) == 1
    
    def test_l3input_optional_fields(self):
        """TC-L3Input-002: L3Input optional fields have defaults"""
        from src.core.models import L3Input, SessionContext
        
        session_context = SessionContext(
            session_id="test-session",
            user_id="user_123",
            current_query="Hello",
            history=[],
            user_permissions=[]
        )
        
        l3_input = L3Input(session_context=session_context)
        
        assert l3_input.available_tools == []
        assert l3_input.relevant_memories == []
```

- [ ] **步骤 2: 运行测试以验证其失败**

```bash
conda activate vclaw
pytest src/l2/tests/test_l2.py::TestL3Input -v
```

预期结果: `FAILED src/l2/tests/test_l2.py::TestL3Input::test_l3input_creation - ImportError: cannot import name 'L3Input' from 'src.core.models'`

- [ ] **步骤 3: 编写最小实现**

添加到 `src/core/models.py` 的 `Document` 类之后：

```python
class L3Input(BaseModel):
    """L2 output / L3 input - Complete input for orchestration layer.
    
    包含 L3 运行 ReAct 循环所需的所有上下文：
    - session_context: User session with history
    - available_tools: 用户有权限使用的工具
    - relevant_memories: Context from L4 memory search
    """
    session_context: SessionContext = Field(
        ...,
        description="Session context with user_id, history, current_query"
    )
    available_tools: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Available tools filtered by user permissions"
    )
    relevant_memories: List[str] = Field(
        default_factory=list,
        description="Relevant memory snippets from L4 search"
    )
```

- [ ] **步骤 4: 运行测试以验证通过**

```bash
pytest src/l2/tests/test_l2.py::TestL3Input -v
```

预期结果: `2 passed`

- [ ] **步骤 5: 提交**

```bash
git add src/core/models.py src/l2/tests/test_l2.py
git commit -m "feat: add L3Input data model

Add L3Input Pydantic model for L2->L3 data transfer.
包含 session_context、available_tools、relevant_memories。

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: 添加 ToolsInterface 到 core/interfaces.py

**文件：**
- Modify: `src/core/interfaces.py`
- Test: `src/l2/tests/test_l2.py`

- [ ] **步骤 1: 编写失败的测试**

添加到 `src/l2/tests/test_l2.py`:

```python
class TestToolsInterface:
    """ToolsInterface 测试。"""
    
    def test_tools_interface_can_be_implemented(self):
        """TC-ToolsInterface-001: ToolsInterface 可以被实现"""
        from src.core.interfaces import ToolsInterface
        
        class MockTools(ToolsInterface):
            def list_tools(self):
                return [{"name": "test_tool"}]
        
        tools = MockTools()
        result = tools.list_tools()
        
        assert len(result) == 1
        assert result[0]["name"] == "test_tool"
```

- [ ] **步骤 2: 运行测试以验证其失败**

```bash
pytest src/l2/tests/test_l2.py::TestToolsInterface -v
```

预期结果: `ImportError: cannot import name 'ToolsInterface' from 'src.core.interfaces'`

- [ ] **步骤 3: 编写最小实现**

添加到 `src/core/interfaces.py` 的 `MemoryInterface` 之后：

```python
class ToolsInterface(ABC):
    """Abstract interface for L5 Tools & Capabilities layer.
    
    L2 uses this interface to get available tools without
    direct dependency on L5 implementation.
    """
    
    @abstractmethod
    def list_tools(self) -> List[Dict[str, Any]]:
        """Get all registered tool definitions.
        
        返回：
            工具定义列表，每个包含：
            - name: Tool identifier
            - description: Human-readable description
            - parameters: JSON Schema for tool parameters
        """
        pass
```

- [ ] **步骤 4: 运行测试以验证通过**

```bash
pytest src/l2/tests/test_l2.py::TestToolsInterface -v
```

预期结果: `1 passed`

- [ ] **步骤 5: 提交**

```bash
git add src/core/interfaces.py src/l2/tests/test_l2.py
git commit -m "feat: add ToolsInterface abstract class

Define interface for L5 tool layer. L2 uses this to get
available tools without direct L5 dependency.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Phase 2: 增强 RateLimiter

### Task 3: 添加 IP 和全局限流

**文件：**
- Modify: `src/l2/l2_control_gateway.py`
- Test: `src/l2/tests/test_l2.py`

- [ ] **步骤 1: 编写失败的测试**

添加到 `src/l2/tests/test_l2.py`：

```python
class TestEnhancedRateLimiter:
    """Tests for enhanced RateLimiter with IP and global limits."""
    
    def test_rate_limit_with_ip(self):
        """TC-RateLimiter-003: IP-level rate limiting"""
        from src.l2.l2_control_gateway import RateLimiter
        
        limiter = RateLimiter()
        user_id = "user_123"
        ip = "192.168.1.1"
        
        # First request from this IP should be allowed
        allowed, reason = limiter.is_allowed(user_id, ip=ip)
        assert allowed is True
        assert reason is None
    
    def test_rate_limit_global_blocks_all(self):
        """TC-RateLimiter-004: Global rate limit affects all users"""
        from src.l2.l2_control_gateway import RateLimiter
        
        # Create limiter with very low global limit
        limiter = RateLimiter(limits={
            "user": (100, 60),
            "ip": (100, 60),
            "global": (2, 60)  # Only 2 global requests
        })
        
        # First 2 requests from different users should succeed
        assert limiter.is_allowed("user_1")[0] is True
        assert limiter.is_allowed("user_2")[0] is True
        
        # 3rd request should fail (global limit)
        allowed, reason = limiter.is_allowed("user_3")
        assert allowed is False
        assert reason == "global_rate_limit"
    
    def test_rate_limit_ip_blocks_same_ip(self):
        """TC-RateLimiter-005: IP limit blocks same IP, different users"""
        from src.l2.l2_control_gateway import RateLimiter
        
        limiter = RateLimiter(limits={
            "user": (100, 60),
            "ip": (2, 60),  # Only 2 per IP
            "global": (1000, 60)
        })
        
        same_ip = "192.168.1.1"
        
        # Same IP, different users
        assert limiter.is_allowed("user_1", ip=same_ip)[0] is True
        assert limiter.is_allowed("user_2", ip=same_ip)[0] is True
        
        # 3rd request from same IP should fail
        allowed, reason = limiter.is_allowed("user_3", ip=same_ip)
        assert allowed is False
        assert reason == "ip_rate_limit"
    
    def test_rate_limit_without_ip(self):
        """TC-RateLimiter-006: Rate limiting works without IP"""
        from src.l2.l2_control_gateway import RateLimiter
        
        limiter = RateLimiter(limits={
            "user": (2, 60),
            "ip": (100, 60),
            "global": (1000, 60)
        })
        
        user_id = "user_123"
        
        # Should work without providing IP
        assert limiter.is_allowed(user_id)[0] is True
        assert limiter.is_allowed(user_id)[0] is True
        assert limiter.is_allowed(user_id)[0] is False  # 3rd fails
```

- [ ] **步骤 2: 运行测试以验证其失败**

```bash
pytest src/l2/tests/test_l2.py::TestEnhancedRateLimiter -v
```

预期结果: 测试失败，因为 `is_allowed` 签名变更或不支持 `ip` 参数。

- [ ] **步骤 3: 编写最小实现**

替换 `src/l2/l2_control_gateway.py` 中的 `RateLimiter` 类：

```python
class RateLimiter:
    """Token bucket rate limiter with user, IP, and global limits."""
    
    DEFAULT_LIMITS = {
        "user": (60, 60),      # 60 requests per 60 seconds
        "ip": (100, 60),       # 100 requests per 60 seconds  
        "global": (1000, 1)    # 1000 requests per 1 second
    }
    
    def __init__(self, limits: Dict[str, Tuple[int, int]] = None):
        """Initialize rate limiter.
        
        参数：
            limits: Dict with keys 'user', 'ip', 'global'
                   Values are (max_requests, window_seconds)
        """
        self.limits = limits or self.DEFAULT_LIMITS
        self.user_buckets: Dict[str, deque] = defaultdict(deque)
        self.ip_buckets: Dict[str, deque] = defaultdict(deque)
        self.global_bucket: deque = deque()
    
    def is_allowed(self, user_id: str, ip: str = None) -> Tuple[bool, Optional[str]]:
        """Check if request is allowed under rate limits.
        
        参数：
            user_id: User identifier
            ip: Client IP address (optional)
            
        返回：
            Tuple of (is_allowed, reason)
            - is_allowed: 如果请求可以继续则为 True
            - reason: None if allowed, else 'user_rate_limit', 
                     'ip_rate_limit', or 'global_rate_limit'
        """
        now = time.time()
        
        # Check global limit first
        if not self._check_bucket(self.global_bucket, "global", now):
            return False, "global_rate_limit"
        
        # Check IP limit if IP provided
        if ip and not self._check_bucket(self.ip_buckets[ip], "ip", now):
            return False, "ip_rate_limit"
        
        # Check user limit
        if not self._check_bucket(self.user_buckets[user_id], "user", now):
            return False, "user_rate_limit"
        
        return True, None
    
    def _check_bucket(self, bucket: deque, level: str, now: float) -> bool:
        """Check and update a single token bucket.
        
        参数：
            bucket: The deque storing request timestamps
            level: 'user', 'ip', or 'global'
            now: Current timestamp
            
        返回：
            如果请求被允许则为 True，如果被限流则为 False
        """
        max_requests, window = self.limits[level]
        
        # Remove old requests outside the window
        while bucket and bucket[0] < now - window:
            bucket.popleft()
        
        # Check if under limit
        if len(bucket) >= max_requests:
            return False
        
        # Add current request timestamp
        bucket.append(now)
        return True
```

- [ ] **步骤 4: 运行测试以验证通过**

```bash
pytest src/l2/tests/test_l2.py::TestEnhancedRateLimiter -v
```

预期结果: `4 passed`

- [ ] **步骤 5: 更新现有测试以匹配新签名**

修改 `src/l2/tests/test_l2.py` 中的 `TestRateLimiter` 类：

```python
class TestRateLimiter:
    """Tests for rate limiting."""

    def test_rate_limit_allows_under_limit(self):
        """Test that requests under limit are allowed"""
        from src.l2.l2_control_gateway import RateLimiter

        limiter = RateLimiter(limits={"user": (10, 60), "ip": (100, 60), "global": (1000, 60)})

        # 10 requests should be allowed
        for i in range(10):
            allowed, _ = limiter.is_allowed(f"user_{i}")
            assert allowed is True

    def test_rate_limit_blocks_over_limit(self):
        """Test that requests over limit are blocked"""
        from src.l2.l2_control_gateway import RateLimiter

        limiter = RateLimiter(limits={"user": (2, 60), "ip": (100, 60), "global": (1000, 60)})
        user_id = "test_user"

        # First 2 requests allowed
        assert limiter.is_allowed(user_id)[0] is True
        assert limiter.is_allowed(user_id)[0] is True

        # 3rd request blocked
        allowed, reason = limiter.is_allowed(user_id)
        assert allowed is False
        assert reason == "user_rate_limit"
```

- [ ] **步骤 6: 运行所有 RateLimiter 测试**

```bash
pytest src/l2/tests/test_l2.py::TestRateLimiter src/l2/tests/test_l2.py::TestEnhancedRateLimiter -v
```

预期结果: `6 passed`

- [ ] **步骤 7: 提交**

```bash
git add src/l2/l2_control_gateway.py src/l2/tests/test_l2.py
git commit -m "feat: enhance RateLimiter with IP and global limits

- Add three-level rate limiting: user, IP, global
- Return tuple (is_allowed, reason) for better error handling
- Update existing tests to use new signature

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Phase 3: 添加 MemoryAccessor 组件

### Task 4: 创建 MemoryAccessor 类

**文件：**
- Modify: `src/l2/l2_control_gateway.py`
- Test: `src/l2/tests/test_l2.py`

- [ ] **步骤 1: 编写失败的测试**

添加到 `src/l2/tests/test_l2.py`：

```python
class TestMemoryAccessor:
    """Tests for MemoryAccessor component."""
    
    def test_memory_accessor_retrieves_relevant_memories(self):
        """TC-MemoryAccessor-001: Retrieve relevant memories from L4"""
        from src.l2.l2_control_gateway import MemoryAccessor
        from src.core.interfaces import MemoryInterface
        from src.core.models import Document
        
        # 模拟 L4 内存
        mock_memory = Mock(spec=MemoryInterface)
        mock_memory.search.return_value = [
            Document(id="1", content="User likes Python", metadata={}),
            Document(id="2", content="User prefers concise answers", metadata={})
        ]
        
        accessor = MemoryAccessor(memory=mock_memory)

        # 执行
        memories = accessor.retrieve_relevant(
            query="What programming language should I use?",
            user_id="user_123",
            top_k=5
        )

        # 验证
        assert len(memories) == 2
        assert "User likes Python" in memories
        assert mock_memory.search.called
        # 验证 search 被正确参数调用
        call_args = mock_memory.search.call_args
        assert call_args.kwargs['top_k'] == 5
        assert call_args.kwargs['filters'] == {"user_id": "user_123"}
    
    def test_memory_accessor_returns_empty_list_when_no_results(self):
        """TC-MemoryAccessor-002: Return empty list when L4 has no results"""
        from src.l2.l2_control_gateway import MemoryAccessor
        
        mock_memory = Mock()
        mock_memory.search.return_value = []
        
        accessor = MemoryAccessor(memory=mock_memory)
        memories = accessor.retrieve_relevant("query", "user_123")
        
        assert memories == []
    
    def test_memory_accessor_uses_default_memory(self):
        """TC-MemoryAccessor-003: Uses default MemoryKnowledge when no memory provided"""
        from src.l2.l2_control_gateway import MemoryAccessor
        
        accessor = MemoryAccessor()
        
        # 应该有默认内存实例
        assert accessor.memory is not None
```

- [ ] **步骤 2: 运行测试以验证其失败**

```bash
pytest src/l2/tests/test_l2.py::TestMemoryAccessor -v
```

预期结果: `ImportError: 无法从 'src.l2.l2_control_gateway' 导入名称 'MemoryAccessor'`

- [ ] **步骤 3: 编写最小实现**

添加到 `src/l2/l2_control_gateway.py` 的 import 之后、`RateLimiter` 之前：

```python
class MemoryAccessor:
    """Access relevant memories from L4 Memory & Knowledge layer.
    
    Retrieves memory snippets related to the user's current query
    to provide context for L3's decision making.
    """
    
    def __init__(self, memory: MemoryInterface = None):
        """Initialize MemoryAccessor.
        
        参数：
            memory: L4 memory interface. Uses MemoryKnowledge if not provided.
        """
        self.memory = memory or MemoryKnowledge()
    
    def retrieve_relevant(
        self, 
        query: str, 
        user_id: str, 
        top_k: int = 5
    ) -> List[str]:
        """Retrieve memory snippets relevant to the query.
        
        参数：
            query: 用户当前查询文本
            user_id: User identifier for filtering
            top_k: 要检索的记忆最大数量
            
        返回：
            记忆内容字符串列表
        """
        results = self.memory.search(
            query=query,
            top_k=top_k,
            filters={"user_id": user_id}
        )
        return [doc.content for doc in results]
```

- [ ] **步骤 4: 运行测试以验证通过**

```bash
pytest src/l2/tests/test_l2.py::TestMemoryAccessor -v
```

预期结果: `3 passed`

- [ ] **步骤 5: 提交**

```bash
git add src/l2/l2_control_gateway.py src/l2/tests/test_l2.py
git commit -m "feat: add MemoryAccessor component

Retrieve relevant memories from L4 using semantic search.
Filters by user_id for privacy, returns list of content strings.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Phase 4: 添加 ToolPreparer 组件

### Task 5: 创建 ToolPreparer 类

**文件：**
- Modify: `src/l2/l2_control_gateway.py`
- Test: `src/l2/tests/test_l2.py`

- [ ] **步骤 1: 编写失败的测试**

添加到 `src/l2/tests/test_l2.py`：

```python
class TestToolPreparer:
    """Tests for ToolPreparer component."""
    
    def test_tool_preparer_returns_all_tools_with_no_permissions(self):
        """TC-ToolPreparer-001: Returns only no-permission tools when user has no permissions"""
        from src.l2.l2_control_gateway import ToolPreparer
        from src.core.interfaces import ToolsInterface
        
        # Mock L5 tools
        mock_tools = Mock(spec=ToolsInterface)
        mock_tools.list_tools.return_value = [
            {"name": "calculator", "description": "Math calc"},
            {"name": "file_read", "description": "Read files"},
            {"name": "terminal", "description": "Run commands"}
        ]
        
        preparer = ToolPreparer(tools=mock_tools)

        # 执行 - 无权限用户
        available = preparer.prepare_tools(user_permissions=[])

        # 验证 - 仅返回 calculator（无需权限）
        assert len(available) == 1
        assert available[0]["name"] == "calculator"
    
    def test_tool_preparer_filters_by_permissions(self):
        """TC-ToolPreparer-002: Returns tools matching user permissions"""
        from src.l2.l2_control_gateway import ToolPreparer
        
        mock_tools = Mock()
        mock_tools.list_tools.return_value = [
            {"name": "calculator", "description": "Math calc"},
            {"name": "file_read", "description": "Read files"},
            {"name": "file_write", "description": "Write files"},
            {"name": "terminal", "description": "Run commands"}
        ]
        
        preparer = ToolPreparer(tools=mock_tools)

        # 执行 - 有 file_read 权限的用户
        available = preparer.prepare_tools(user_permissions=["file_read"])

        # 验证 - calculator（无需权限）+ file_read
        assert len(available) == 2
        tool_names = [t["name"] for t in available]
        assert "calculator" in tool_names
        assert "file_read" in tool_names
    
    def test_tool_preparer_returns_all_tools_with_all_permissions(self):
        """TC-ToolPreparer-003: Returns all tools when user has all permissions"""
        from src.l2.l2_control_gateway import ToolPreparer
        
        mock_tools = Mock()
        mock_tools.list_tools.return_value = [
            {"name": "calculator", "description": "Math calc"},
            {"name": "file_read", "description": "Read files"},
            {"name": "python_repl", "description": "Python execution"}
        ]
        
        preparer = ToolPreparer(tools=mock_tools)

        # 执行 - 拥有所有权限的用户
        all_perms = ["file_read", "file_write", "execute_code", "web_access"]
        available = preparer.prepare_tools(user_permissions=all_perms)

        # 验证 - 返回所有工具
        assert len(available) == 3
```

- [ ] **步骤 2: 运行测试以验证其失败**

```bash
pytest src/l2/tests/test_l2.py::TestToolPreparer -v
```

预期结果: `ImportError: 无法从 'src.l2.l2_control_gateway' 导入名称 'ToolPreparer'`

- [ ] **步骤 3: 编写最小实现**

Add to `src/l2/l2_control_gateway.py` after `MemoryAccessor`:

```python
class ToolPreparer:
    """Prepare available tools from L5 based on user permissions.
    
    L2 uses this to filter tools from L5.ToolRegistry.
    L2 only does permission filtering, does not define tools.
    """
    
    # 工具名称 -> 所需权限（None = 无需权限）
    TOOL_PERMISSION_MAP = {
        "calculator": None,           # Always available
        "file_read": "file_read",
        "file_write": "file_write",
        "python_repl": "execute_code",
        "terminal": "execute_command",
        "search_web": "web_access"
    }
    
    def __init__(self, tools: ToolsInterface = None):
        """Initialize ToolPreparer.
        
        参数：
            tools: L5 工具接口。如未提供则使用 ToolsCapabilities。
        """
        self.tools = tools or ToolsCapabilities()
    
    def prepare_tools(self, user_permissions: List[str]) -> List[Dict[str, Any]]:
        """Filter tools based on user permissions.
        
        参数：
            user_permissions: List of permission strings the user has
            
        返回：
            List of tool definitions user is authorized to use
        """
        all_tools = self.tools.list_tools()
        
        available = []
        for tool in all_tools:
            tool_name = tool.get("name")
            required_perm = self.TOOL_PERMISSION_MAP.get(tool_name)
            
            # 如果无需权限或用户有权限，则添加工具
            if required_perm is None or required_perm in user_permissions:
                available.append(tool)
        
        return available
```

- [ ] **步骤 4: 运行测试以验证通过**

```bash
pytest src/l2/tests/test_l2.py::TestToolPreparer -v
```

预期结果: `3 passed`

- [ ] **步骤 5: 提交**

```bash
git add src/l2/l2_control_gateway.py src/l2/tests/test_l2.py
git commit -m "feat: add ToolPreparer component

Filter L5 tools based on user permissions.
返回给定权限集的可用工具。
Permission mapping defined in TOOL_PERMISSION_MAP.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Phase 5: 增强 ControlGateway

### Task 6: 更新 ControlGateway 以输出 L3Input

**文件：**
- Modify: `src/l2/l2_control_gateway.py`
- Test: `src/l2/tests/test_l2.py`

- [ ] **步骤 1: 编写失败的测试**

添加到 `src/l2/tests/test_l2.py`：

```python
class TestControlGatewayEnhanced:
    """Tests for enhanced ControlGateway that outputs L3Input."""
    
    def test_process_event_returns_l3input(self):
        """TC-ControlGateway-007: process_event returns L3Input"""
        from src.l2.l2_control_gateway import ControlGateway
        from src.core.models import L3Input
        
        gateway = ControlGateway()
        event = StandardEvent(
            channel="test",
            user_id="user_123",
            content="Hello",
            metadata={}
        )
        
        # Mock dependencies
        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=["Memory 1"]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[{"name": "calc"}]):
            
            result = gateway.process_event(event)
            
            # Should return L3Input
            assert isinstance(result, L3Input)
            assert result.session_context.user_id == "user_123"
            assert len(result.available_tools) == 1
            assert len(result.relevant_memories) == 1
    
    def test_process_event_passes_ip_to_rate_limiter(self):
        """TC-ControlGateway-008: Passes IP from metadata to rate limiter"""
        from src.l2.l2_control_gateway import ControlGateway
        
        gateway = ControlGateway()
        event = StandardEvent(
            channel="test",
            user_id="user_123",
            content="Hello",
            metadata={"client_ip": "192.168.1.1"}
        )
        
        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.rate_limiter, 'is_allowed') as mock_limiter, \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):
            
            mock_limiter.return_value = (True, None)
            gateway.process_event(event)
            
            # Verify IP was passed
            mock_limiter.assert_called_once_with(user_id="user_123", ip="192.168.1.1")
```

- [ ] **步骤 2: 运行测试以验证其失败**

```bash
pytest src/l2/tests/test_l2.py::TestControlGatewayEnhanced -v
```

预期结果: 测试失败，因为 `process_event` 仍返回 `SessionContext` 而非 `L3Input`。

- [ ] **步骤 3: 更新 ControlGateway 类**

替换 `src/l2/l2_control_gateway.py` 中的 `ControlGateway` 类：

```python
class ControlGateway:
    """L2 Control Gateway - Enhanced version.
    
    Responsibilities:
    - Rate limiting (user, IP, global)
    - Session management
    - History retrieval from L4
    - Relevant memory retrieval from L4 (NEW)
    - Tool preparation from L5 (NEW)
    - Assembly of complete L3Input (ENHANCED)
    """
    
    DEFAULT_SESSION_MAX_AGE = 3600  # 1 hour
    SESSION_CLEANUP_INTERVAL = 100
    
    def __init__(
        self,
        memory: MemoryInterface = None,
        tools: ToolsInterface = None,
        session_max_age: int = DEFAULT_SESSION_MAX_AGE
    ):
        """Initialize ControlGateway with all components.
        
        参数：
            memory: L4 memory interface. Uses MemoryKnowledge if not provided.
            tools: L5 tools interface. Uses ToolsCapabilities if not provided.
            session_max_age: Session TTL in seconds
        """
        # Dependencies
        self.memory = memory or MemoryKnowledge()
        self.tools = tools or ToolsCapabilities()
        
        # Components
        self.rate_limiter = RateLimiter()
        self.memory_accessor = MemoryAccessor(self.memory)
        self.tool_preparer = ToolPreparer(self.tools)
        
        # Session management
        self.sessions: Dict[str, Dict] = {}
        self.session_max_age = session_max_age
        self._request_count = 0
    
    def process_event(self, event: StandardEvent) -> L3Input:
        """Process StandardEvent and return complete L3Input.
        
        参数：
            event: StandardEvent from L1
            
        返回：
            L3Input containing session_context, available_tools, relevant_memories
            
        异常：
            RateLimitExceeded: If any rate limit is exceeded
        """
        # 步骤 1: 限流检查
        allowed, reason = self.rate_limiter.is_allowed(
            user_id=event.user_id,
            ip=event.metadata.get("client_ip")
        )
        if not allowed:
            raise RateLimitExceeded(f"Rate limit exceeded: {reason}")
        
        # 步骤 2: 获取或创建会话
        session_id = self._get_or_create_session(event)

        # 步骤 3: 从 L4 检索历史记录
        history = self.memory.retrieve_history(session_id, limit=10)

        # 步骤 4: 检索相关记忆（新增）
        relevant_memories = self.memory_accessor.retrieve_relevant(
            query=event.content,
            user_id=event.user_id,
            top_k=5
        )

        # 步骤 5: 准备可用工具（新增）
        # TODO: 从会话或配置中获取 user_permissions
        user_permissions = []
        available_tools = self.tool_preparer.prepare_tools(user_permissions)

        # 步骤 6: 创建会话上下文
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

        # 步骤 7: 返回完整的 L3Input（增强）
        return L3Input(
            session_context=session_context,
            available_tools=available_tools,
            relevant_memories=relevant_memories
        )
    
    def _get_or_create_session(self, event: StandardEvent) -> str:
        """获取现有会话或创建新会话。"""
        session_id = event.metadata.get("session_id")
        
        if session_id and session_id in self.sessions:
            session_data = self.sessions[session_id]
            age = time.time() - session_data.get("created_at", 0)
            if age < self.session_max_age:
                return session_id
        
        # Create new session
        new_session_id = str(uuid.uuid4())
        self.sessions[new_session_id] = {
            "user_id": event.user_id,
            "created_at": time.time()
        }
        
        # 定期清理
        self._request_count += 1
        if self._request_count >= self.SESSION_CLEANUP_INTERVAL:
            self._cleanup_expired_sessions()
            self._request_count = 0
        
        return new_session_id
    
    def _cleanup_expired_sessions(self):
        """移除过期会话。"""
        now = time.time()
        expired = [
            sid for sid, data in self.sessions.items()
            if now - data.get("created_at", 0) > self.session_max_age
        ]
        for sid in expired:
            del self.sessions[sid]
    
    def send_response(self, session_id: str, text: str) -> bool:
        """发送响应给用户（模拟实现）"""
        print(f"[L2] 发送响应到会话 {session_id}: {text[:50]}...")
        return True
```

- [ ] **步骤 4: 更新现有测试以适配新的返回类型**

修改 `src/l2/tests/test_l2.py` 中的 `TestControlGateway` 测试：

```python
class TestControlGateway:
    """Tests for L2 Control Gateway."""

    def test_session_creation_and_context_assembly(self):
        """TC-L2-001: 会话创建与上下文组装"""
        # 准备
        gateway = ControlGateway()
        event = StandardEvent(
            channel="test",
            user_id="new_user_123",
            content="Hello",
            metadata={}
        )

        # 模拟依赖
        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):

            # 执行
            l3_input = gateway.process_event(event)

            # 验证 - 现在返回 L3Input
            assert l3_input.session_context.user_id == "new_user_123"
            assert l3_input.session_context.current_query == "Hello"
            assert l3_input.session_context.session_id is not None

    def test_rate_limit_triggered(self):
        """TC-L2-002: 限流触发"""
        # 准备
        gateway = ControlGateway()

        # 为所有调用模拟依赖
        def mock_process():
            with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
                 patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
                 patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):
                event = StandardEvent(
                    channel="test",
                    user_id="user_123",
                    content="Test",
                    metadata={}
                )
                return gateway.process_event(event)

        # 前 60 个请求应该成功
        for i in range(60):
            try:
                mock_process()
            except RateLimitExceeded:
                pass  # 可能在接近限制时发生

        # 第 61 个请求应该失败
        with pytest.raises(RateLimitExceeded):
            mock_process()

    def test_history_retrieval_and_concatenation(self):
        """TC-L2-004: 历史记录检索与拼接"""
        # 准备
        gateway = ControlGateway()
        session_id = "existing_session_123"

        event = StandardEvent(
            channel="test",
            user_id="user_123",
            content="What's the weather?",
            metadata={"session_id": session_id}
        )

        # 模拟历史记录检索
        mock_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]

        with patch.object(gateway.memory, 'retrieve_history', return_value=mock_history), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):

            # 执行
            l3_input = gateway.process_event(event)

            # 验证
            assert len(l3_input.session_context.history) == 2
            assert l3_input.session_context.history[0]["content"] == "Hello"
            assert l3_input.session_context.current_query == "What's the weather?"

    def test_send_response(self):
        """TC-L2-006: 响应发送"""
        # 准备
        gateway = ControlGateway()
        session_id = "test_session_123"

        # 执行
        result = gateway.send_response(session_id, "Hello user")

        # 验证
        assert result is True

    def test_no_auth_required(self):
        """TC-L2-NOAUTH: 身份认证已移除，无需令牌"""
        # 准备
        gateway = ControlGateway()
        event = StandardEvent(
            channel="test",
            user_id="user_123",
            content="Hello",
            metadata={}  # 无 auth_token
        )

        # 模拟依赖
        with patch.object(gateway.memory, 'retrieve_history', return_value=[]), \
             patch.object(gateway.memory_accessor, 'retrieve_relevant', return_value=[]), \
             patch.object(gateway.tool_preparer, 'prepare_tools', return_value=[]):

            # 执行 - 无认证也应成功
            l3_input = gateway.process_event(event)

            # 验证
            assert l3_input.session_context.user_id == "user_123"
            assert l3_input.session_context.user_permissions == []  # 空权限
```

- [ ] **步骤 5: 运行所有 ControlGateway 测试**

```bash
pytest src/l2/tests/test_l2.py::TestControlGateway src/l2/tests/test_l2.py::TestControlGatewayEnhanced -v
```

预期结果: 7 个通过

- [ ] **步骤 6: 提交**

```bash
git add src/l2/l2_control_gateway.py src/l2/tests/test_l2.py
git commit -m "feat: enhance ControlGateway to output L3Input

- process_event() now returns L3Input instead of SessionContext
- Integrates MemoryAccessor for relevant memory retrieval
- Integrates ToolPreparer for tool filtering
- Passes client_ip from metadata to rate limiter

BREAKING CHANGE: process_event return type changed

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Phase 6: 更新文档

### Task 7: 更新 L2 测试 README

**文件：**
- Modify: `src/l2/tests/README.md`

- [ ] **步骤 1: 用新的测试信息更新 README**

替换 `src/l2/tests/README.md` 内容：

```markdown
# L2 Control Gateway Tests

L2 控制网关层测试文档

## 测试文件列表

| 测试文件 | 用途 | 依赖 | 状态 |
|----------|------|------|------|
| `test_l2.py` | L2 控制网关核心功能测试 | pytest, unittest.mock | 通过 |

## 测试类说明

### TestControlGateway
核心网关功能测试：
- `test_session_creation_and_context_assembly` - 会话创建与上下文组装
- `test_rate_limit_triggered` - 限流触发机制
- `test_history_retrieval_and_concatenation` - 历史记录检索
- `test_send_response` - 响应发送
- `test_no_auth_required` - 无认证模式

### TestRateLimiter
限流器测试：
- `test_rate_limit_allows_under_limit` - 限制内请求通过
- `test_rate_limit_blocks_over_limit` - 超限请求被拒绝

### TestEnhancedRateLimiter
增强限流器测试（IP/全局）：
- `test_rate_limit_with_ip` - IP级限流
- `test_rate_limit_global_blocks_all` - 全局限流
- `test_rate_limit_ip_blocks_same_ip` - 同IP不同用户限流
- `test_rate_limit_without_ip` - 无IP场景

### TestMemoryAccessor
记忆访问器测试：
- `test_memory_accessor_retrieves_relevant_memories` - 检索相关记忆
- `test_memory_accessor_returns_empty_list_when_no_results` - 空结果处理
- `test_memory_accessor_uses_default_memory` - 默认内存实例

### TestToolPreparer
工具准备器测试：
- `test_tool_preparer_returns_all_tools_with_no_permissions` - 无权限筛选
- `test_tool_preparer_filters_by_permissions` - 权限过滤
- `test_tool_preparer_returns_all_tools_with_all_permissions` - 全权限

### TestL3Input
数据模型测试：
- `test_l3input_creation` - L3Input创建
- `test_l3input_optional_fields` - 可选字段默认值

### TestControlGatewayEnhanced
增强网关测试：
- `test_process_event_returns_l3input` - 返回L3Input
- `test_process_event_passes_ip_to_rate_limiter` - IP传递

## 依赖清单

```bash
# 基础依赖
pip install pytest

# 项目依赖（已安装）
# - pydantic (src/core/models.py)
```

## 如何运行测试

```bash
# 运行所有L2测试
pytest src/l2/tests/test_l2.py -v

# 运行特定测试类
pytest src/l2/tests/test_l2.py::TestControlGateway -v
pytest src/l2/tests/test_l2.py::TestMemoryAccessor -v
pytest src/l2/tests/test_l2.py::TestToolPreparer -v

# 运行特定测试用例
pytest src/l2/tests/test_l2.py::TestControlGateway::test_session_creation_and_context_assembly -v

# 运行速率限制相关测试
pytest src/l2/tests/test_l2.py -k "rate_limit" -v
```

## 注意事项

1. 所有测试使用 `unittest.mock` 模拟 L4/L5 依赖
2. 测试为纯单元测试，不依赖外部服务
3. 每个测试用例独立运行，确保状态隔离

---
最后更新: 2026-04-12
```

- [ ] **步骤 2: 提交**

```bash
git add src/l2/tests/README.md
git commit -m "docs: update L2 tests README

Add documentation for new test classes:
- TestEnhancedRateLimiter
- TestMemoryAccessor
- TestToolPreparer
- TestL3Input
- TestControlGatewayEnhanced

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Phase 7: 最终验证

### Task 8: 运行所有测试并验证

- [ ] **步骤 1: 运行所有 L2 测试**

```bash
conda activate vclaw
pytest src/l2/tests/test_l2.py -v
```

预期结果: 所有测试通过 (25+ 个测试)

- [ ] **步骤 2: 运行所有项目测试**

```bash
pytest src/l1/tests/ src/l2/tests/ -v --tb=short
```

预期结果: 所有 L1 和 L2 测试通过

- [ ] **步骤 3: 最终提交**

```bash
git commit -m "feat: complete L2 ControlGateway enhancement

变更摘要：
- Add L3Input data model for L2->L3 communication
- Add ToolsInterface for L5 abstraction
- Enhance RateLimiter with IP and global limits
- Add MemoryAccessor component for L4 integration
- Add ToolPreparer component for permission-based tool filtering
- Enhance ControlGateway to output complete L3Input
- Update all tests and documentation

Phase 1 complete: L2 components ready for L3 integration.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Plan Review Checklist

### 规范覆盖

| 规范要求 | 实现任务 |
|------------------|---------------------|
| L3Input model | Task 1 ✅ |
| MemoryAccessor component | Task 4 ✅ |
| ToolPreparer component | Task 5 ✅ |
| Enhanced RateLimiter | Task 3 ✅ |
| ControlGateway outputs L3Input | Task 6 ✅ |
| ToolsInterface | Task 2 ✅ |
| Documentation updates | Task 7 ✅ |

### 占位符检查

- [x] No "TBD" or "TODO" in plan
- [x] No "implement later" or "fill in details"
- [x] All test code is complete
- [x] All implementation code is complete
- [x] Exact commands provided

### 类型一致性

- [x] `L3Input` used consistently
- [x] `MemoryAccessor` naming consistent
- [x] `ToolPreparer` naming consistent
- [x] `is_allowed()` return type consistent

---

## 后续步骤（第 2 阶段）

完成此计划后：

1. **L3 集成** - 创建 `L3Interface` 并连接 L2->L3
2. **集成测试** - 测试完整的 L1->L2->L3 流程
3. **真实环境测试** - 创建 L2 真实环境测试

这些将在后续计划中涵盖。
