"""L2: Control Gateway Layer - Rate limiting, session management."""
import time
import uuid
from typing import Any, Dict, List, Optional
from collections import defaultdict, deque
from src.core.models import StandardEvent, SessionContext, L3Input
from src.core.interfaces import MemoryInterface, ToolsInterface
from src.l4 import MemoryKnowledge
from src.l5.l5_tools import ToolsCapabilities
from src.core.exceptions import (
    RateLimitExceeded, SessionError
)


class MemoryAccessor:
    """记忆访问器

    从 L4 检索与用户当前查询相关的记忆片段，
    用于增强 L3 的上下文理解。
    """

    def __init__(self, memory: MemoryInterface = None):
        """初始化 MemoryAccessor

        参数：
            memory: L4 内存接口。如未提供则使用 MemoryKnowledge。
        """
        self.memory = memory or MemoryKnowledge()

    def retrieve_relevant(
        self,
        query: str,
        user_id: str,
        top_k: int = 5
    ) -> List[str]:
        """检索相关记忆片段

        参数：
            query: 用户当前查询内容
            user_id: 用户标识（用于过滤）
            top_k: 返回最相关的 k 条记忆

        返回：
            记忆内容字符串列表
        """
        results = self.memory.search(
            query=query,
            top_k=top_k,
            filters={"user_id": user_id}
        )
        return [self._extract_content(doc) for doc in results]

    @staticmethod
    def _extract_content(doc) -> str:
        """从搜索结果中提取内容字符串，兼容 Document 对象和 str。"""
        if isinstance(doc, str):
            return doc
        if hasattr(doc, "content"):
            return doc.content
        return str(doc)


class ToolPreparer:
    """工具准备器

    从 L5.ToolRegistry 获取工具定义，
    根据 user_permissions 筛选用户有权限使用的工具。

    注意：L2 只负责权限筛选，不定义工具本身。
    """

    # 工具名称 -> 所需权限（None = 无需权限）
    TOOL_PERMISSION_MAP = {
        "calculator": None,           # 始终可用
        "file_read": "file_read",
        "file_write": "file_write",
        "python_repl": "execute_code",
        "terminal": "execute_command",
        "search_web": "web_access"
    }

    # 全部权限列表（MVP阶段：所有用户默认拥有全部权限）
    ALL_PERMISSIONS = ["file_read", "file_write", "execute_code", "execute_command", "web_access"]

    def __init__(self, tools: ToolsInterface = None):
        """初始化 ToolPreparer

        参数：
            tools: L5 工具接口。如未提供则使用 ToolsCapabilities。
        """
        self.tools = tools or ToolsCapabilities()

    def prepare_tools(self, user_permissions: List[str]) -> List[Dict[str, Any]]:
        """根据用户权限筛选工具

        权限解析优先级：
        1. 工具元数据中的 `required_permission` 字段（L5 为权威来源）
        2. 回退到本地 `TOOL_PERMISSION_MAP`（向后兼容）
        3. 均未命中则默认无需权限

        参数：
            user_permissions: 用户拥有的权限列表

        返回：
            用户有权限使用的工具定义列表
        """
        all_tools = self.tools.list_tools()

        available = []
        for tool in all_tools:
            tool_name = tool.get("name")
            # 优先从工具元数据读取，无则回退映射表，均未命中默认 None（无需权限）
            required_perm = tool.get("required_permission")
            if required_perm is None and tool_name in self.TOOL_PERMISSION_MAP:
                required_perm = self.TOOL_PERMISSION_MAP[tool_name]

            if required_perm is None or required_perm in user_permissions:
                available.append(tool)

        return available


class RateLimiter:
    """三级限流器（令牌桶算法）

    优先级：全局 > IP > 用户
    任一级别超限即拒绝请求。
    """

    DEFAULT_LIMITS = {
        "user": (60, 60),      # 60 请求 / 60 秒
        "ip": (100, 60),       # 100 请求 / 60 秒
        "global": (1000, 1)    # 1000 请求 / 1 秒
    }

    def __init__(self, limits: Dict[str, tuple] = None):
        self.limits = limits or self.DEFAULT_LIMITS

        # 三级存储
        self.user_buckets: Dict[str, deque] = defaultdict(deque)
        self.ip_buckets: Dict[str, deque] = defaultdict(deque)
        self.global_bucket: deque = deque()

    def is_allowed(self, user_id: str, ip: str = None) -> tuple[bool, Optional[str]]:
        """检查请求是否允许

        参数：
            user_id: 用户标识
            ip: 可选的客户端 IP，用于 IP 级限流

        返回：
            (is_allowed, reason)
            - is_allowed: 如果请求可以继续则为 True
            - reason: 如果允许则为 None，或被阻止的限流级别
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

    def _check_bucket(self, bucket: deque, level: str, now: float) -> bool:
        """检查单个令牌桶

        参数：
            bucket: 令牌桶（时间戳队列）
            level: 限流级别（"user", "ip", "global"）
            now: 当前时间戳

        返回：
            如果请求被允许则为 True，如果被限流则为 False
        """
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


class ControlGateway:
    """L2 控制网关（增强版）

    职责：
    1. 限流控制（用户/IP/全局）
    2. 会话管理
    3. 历史记录检索
    4. 相关记忆检索（新增）
    5. 工具准备（新增）
    6. 组装完整 L3Input（增强）
    """

    DEFAULT_SESSION_MAX_AGE = 3600  # 1 小时
    SESSION_CLEANUP_INTERVAL = 100  # 每 100 次请求清理
    PREFERENCE_KEY_SESSION_META = "l2_session_metadata"  # L4 存储键

    def __init__(
        self,
        memory: MemoryInterface = None,
        tools: ToolsInterface = None,
        l1_sender=None,
        session_max_age: int = DEFAULT_SESSION_MAX_AGE
    ):
        """初始化 ControlGateway 及所有组件

        参数：
            memory: L4 内存接口。如未提供则使用 MemoryKnowledge。
            tools: L5 工具接口。如未提供则使用 ToolsCapabilities。
            l1_sender: L1 发送器实例。如果提供，send_response 将委托给 L1。
            session_max_age: 会话有效期（秒）
        """
        # 依赖注入
        self.memory = memory or MemoryKnowledge()
        self.tools = tools or ToolsCapabilities()
        self.l1_sender = l1_sender

        # 组件初始化
        self.rate_limiter = RateLimiter()
        self.context_assembler = ContextAssembler(self.memory, self.tools)
        # 复用 ContextAssembler 内部组件，避免重复实例化
        self.memory_accessor = self.context_assembler.memory_accessor
        self.tool_preparer = self.context_assembler.tool_preparer

        # 会话管理
        self.sessions: Dict[str, Dict] = {}
        self.session_max_age = session_max_age
        self._request_count = 0

    def process_event(self, event: StandardEvent) -> L3Input:
        """处理 L1 输入事件，组装完整的 L3 输入上下文。

        职责：
        1. 限流检查
        2. 获取或创建会话
        3. 组装 SessionContext（委托 ContextAssembler）
        4. 获取可用工具和相关记忆
        5. 返回 L3Input

        参数：
            event: 来自 L1 的 StandardEvent

        返回：
            组装好的 L3Input，供上层调用 L3 使用

        异常：
            RateLimitExceeded: 如果任何限流被触发
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

        # 步骤 3: 准备权限（MVP阶段默认全部权限）
        user_permissions = ToolPreparer.ALL_PERMISSIONS

        # 步骤 4: 组装 SessionContext
        session_context = self.context_assembler.assemble(
            event=event,
            session_id=session_id,
            user_permissions=user_permissions
        )

        # 步骤 5: 获取可用工具和相关记忆（L3Input 顶层字段）
        # L5/L4 不可用时降级为空列表，避免阻塞用户请求
        try:
            available_tools = self.tool_preparer.prepare_tools(user_permissions)
        except Exception:
            available_tools = []

        try:
            relevant_memories = self.memory_accessor.retrieve_relevant(
                query=event.content,
                user_id=event.user_id,
                top_k=5
            )
        except Exception:
            relevant_memories = []

        # 步骤 6: 返回组装好的 L3Input
        return L3Input(
            session_context=session_context,
            available_tools=available_tools,
            relevant_memories=relevant_memories
        )

    def _get_or_create_session(self, event: StandardEvent) -> str:
        """获取现有会话或创建新会话。

        支持可选的 L4 持久化：
        - 有 memory 时：内存缓存 + L4 双写双删
        - 无 memory 时：纯内存（向后兼容）
        """
        user_id = event.user_id
        session_id = event.metadata.get("session_id")
        is_new_request = event.metadata.get("is_new_session_request", False)

        # 用户显式请求新会话 → 废弃旧会话上下文（内存 + L4 双删）
        if is_new_request and session_id and session_id in self.sessions:
            del self.sessions[session_id]
            self._persist_session_meta(user_id, None)
            session_id = None

        # 复用未过期的现有会话（先查内存，miss 时回查 L4）
        if session_id:
            session_data = self.sessions.get(session_id)
            if session_data is None and self.memory:
                # 内存 miss，尝试从 L4 恢复
                session_data = self._load_session_meta(user_id)
                if session_data and session_data.get("session_id") == session_id:
                    # 回填内存缓存
                    self.sessions[session_id] = session_data
            if session_data:
                age = time.time() - session_data.get("created_at", 0)
                if age < self.session_max_age:
                    return session_id

        # 创建新会话（内存 + L4 双写）
        new_session_id = str(uuid.uuid4())
        session_data = {
            "user_id": user_id,
            "created_at": time.time()
        }
        self.sessions[new_session_id] = session_data
        self._persist_session_meta(user_id, {
            "session_id": new_session_id,
            **session_data
        })

        # 定期清理
        self._request_count += 1
        if self._request_count >= self.SESSION_CLEANUP_INTERVAL:
            self._cleanup_expired_sessions()
            self._request_count = 0

        return new_session_id

    def _persist_session_meta(self, user_id: str, meta: Optional[Dict]) -> bool:
        """将会话元数据持久化到 L4。

        参数：
            user_id: 用户标识
            meta: 会话元数据字典，或 None 表示删除

        返回：
            持久化是否成功（无 memory 时返回 False）
        """
        if not self.memory:
            return False
        try:
            self.memory.save_user_preference(
                user_id,
                self.PREFERENCE_KEY_SESSION_META,
                meta
            )
            return True
        except Exception:
            return False

    def _load_session_meta(self, user_id: str) -> Optional[Dict]:
        """从 L4 加载会话元数据。

        参数：
            user_id: 用户标识

        返回：
            会话元数据字典，或 None
        """
        if not self.memory:
            return None
        try:
            meta = self.memory.load_user_preference(
                user_id,
                self.PREFERENCE_KEY_SESSION_META
            )
            if meta and isinstance(meta, dict) and meta.get("session_id"):
                return meta
            return None
        except Exception:
            return None

    def _cleanup_expired_sessions(self):
        """移除过期会话（内存 + L4）"""
        now = time.time()
        expired = [
            (sid, data) for sid, data in self.sessions.items()
            if now - data.get("created_at", 0) > self.session_max_age
        ]
        for sid, data in expired:
            del self.sessions[sid]
            # 同步清理 L4（容错：失败不影响内存）
            user_id = data.get("user_id")
            if user_id:
                self._persist_session_meta(user_id, None)

    def send_response(self, event: StandardEvent, result: str) -> bool:
        """将 L3 处理结果回传给 L1，由 L1 发送给用户。

        参数：
            event: 原始 StandardEvent（用于获取 user_id 和渠道信息）
            result: L3 返回的最终响应文本

        返回：
            发送是否成功
        """
        if self.l1_sender:
            return self.l1_sender.send_response(
                user_id=event.user_id,
                content=result,
                channel=event.channel,
                metadata=event.metadata
            )
        # 无 L1 时降级为打印（开发调试）
        print(f"[L2] 发送响应到用户 {event.user_id}: {result[:50]}...")
        return True


class HistoryRetriever:
    """L2 历史记录检索器

    从 L4 获取用户历史对话，用于上下文组装。
    """

    def __init__(self, memory: MemoryInterface = None):
        self.memory = memory or MemoryKnowledge()

    def retrieve(self, session_id: str, limit: int = 10) -> List[Dict]:
        """检索会话历史记录

        Args:
            session_id: 会话ID
            limit: 最大返回条数

        Returns:
            OpenAI格式的消息列表。L4 不可用时返回空列表。
        """
        try:
            return self.memory.retrieve_history(session_id, limit=limit)
        except Exception:
            return []


class ContextAssembler:
    """L2 上下文组装器

    将 StandardEvent 转换为完整的 SessionContext。
    """

    def __init__(self, memory: MemoryInterface = None, tools: ToolsInterface = None):
        self.memory = memory or MemoryKnowledge()
        self.tools = tools or ToolsCapabilities()
        self.history_retriever = HistoryRetriever(self.memory)
        self.memory_accessor = MemoryAccessor(self.memory)
        self.tool_preparer = ToolPreparer(self.tools)

    def assemble(
        self,
        event: StandardEvent,
        session_id: str,
        user_permissions: List[str]
    ) -> SessionContext:
        """组装完整的 SessionContext

        Args:
            event: L1标准化事件
            session_id: 会话ID
            user_permissions: 用户权限列表

        Returns:
            完整的 SessionContext
        """
        history = self.history_retriever.retrieve(session_id, limit=10)

        return SessionContext(
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
