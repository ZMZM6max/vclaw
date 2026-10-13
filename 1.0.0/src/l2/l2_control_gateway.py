"""L2: Control Gateway Layer - Rate limiting, session management."""
import time
import uuid
from typing import Any, Dict, List, Optional
from collections import defaultdict, deque
from src.core.models import StandardEvent, SessionContext, L3Input, StandardResponse
from src.core.interfaces import MemoryInterface, ToolsInterface
from src.l4 import MemoryKnowledge
from src.l5.l5_tools import ToolsCapabilities
from src.core.exceptions import (
    RateLimitExceeded, SessionError,
    AuthenticationError, ForbiddenError  # Deprecated but kept for compatibility
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
        return results


class ToolPreparer:
    """工具准备器

    从 L5.ToolRegistry 获取工具定义，
    根据 user_permissions 筛选用户有权限使用的工具。

    注意：L2 只负责权限筛选，不定义工具本身。
    """

    # 工具名称 -> 所需权限（None = 无需权限）
    TOOL_PERMISSION_MAP = {
        "calculator": None,           # 始终可用
        "file_reader": "file_read",
        "file_writer": "file_write",
        "file_delete": "file_delete",
        "python_repl": "execute_code",
        "terminal": "execute_command",
        "search_web": "web_access"
    }

    def __init__(self, tools: ToolsInterface = None):
        """初始化 ToolPreparer

        参数：
            tools: L5 工具接口。如未提供则使用 ToolsCapabilities。
        """
        self.tools = tools or ToolsCapabilities()

    def prepare_tools(self, user_permissions: List[str]) -> List[Dict[str, Any]]:
        """根据用户权限筛选工具

        参数：
            user_permissions: 用户拥有的权限列表

        返回：
            用户有权限使用的工具定义列表
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
    2. 会话管理（创建、复用、持久化到 L4）
    3. 历史记录检索
    4. 相关记忆检索（新增）
    5. 工具准备（新增）
    6. 组装完整 L3Input（增强）
    """

    NEW_SESSION_COMMANDS = {"/new", "/reset", "/start", "新会话"}

    def __init__(
        self,
        memory: MemoryInterface = None,
        tools: ToolsInterface = None,
        l1=None,
    ):
        """初始化 ControlGateway 及所有组件

        参数：
            memory: L4 内存接口。如未提供则使用 MemoryKnowledge。
            tools: L5 工具接口。如未提供则使用 ToolsCapabilities。
            l1: L1 UserInteraction 实例，用于发送响应。
        """
        # 依赖注入
        # 默认使用 file 模式持久化会话映射和对话历史到磁盘
        self.memory = memory or MemoryKnowledge(
            embedding_service={"provider": "mock"},
            vector_store={"store_type": "memory"},
            memory_store={"store_type": "file", "storage_dir": "./src/l4/data/conversations"}
        )
        self.tools = tools or ToolsCapabilities()
        self.l1 = l1

        # 组件初始化
        self.rate_limiter = RateLimiter()
        self.memory_accessor = MemoryAccessor(self.memory)
        self.tool_preparer = ToolPreparer(self.tools)

        # 会话管理（session 永不过期，持久化到 L4，用户随时回来都能恢复历史）
        self.sessions: Dict[str, Dict] = {}

    def process_event(self, event: StandardEvent) -> L3Input:
        """处理 L1 输入事件，输出完整的 L3Input

        参数：
            event: 来自 L1 的 StandardEvent

        返回：
            包含 session_context、available_tools、relevant_memories 的 L3Input

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
        """获取现有会话或创建新会话（通过 L4 持久化映射，session 永不过期）"""
        user_id = event.user_id
        content = event.content.strip() if event.content else ""

        # 1. 检查是否是新建会话命令
        if content in self.NEW_SESSION_COMMANDS:
            # 清除 L4 中的旧映射
            self.memory.save_user_preference(user_id, "active_session_id", None)
            # 创建新 session
            new_session_id = str(uuid.uuid4())
            self.sessions[new_session_id] = {
                "user_id": user_id,
                "created_at": time.time()
            }
            self.memory.save_user_preference(user_id, "active_session_id", new_session_id)
            return new_session_id

        # 2. 尝试从 L4 读取活跃 session
        active_session_id = self.memory.load_user_preference(user_id, "active_session_id")

        # 3. 检查 L2 内存中是否存在（session 永不过期）
        if active_session_id:
            if active_session_id in self.sessions:
                return active_session_id
            else:
                # 存在于 L4 但不在 L2 内存中（例如服务重启后），恢复到 L2
                self.sessions[active_session_id] = {
                    "user_id": user_id,
                    "created_at": time.time()
                }
                return active_session_id

        # 4. 创建新 session
        new_session_id = str(uuid.uuid4())
        self.sessions[new_session_id] = {
            "user_id": user_id,
            "created_at": time.time()
        }
        self.memory.save_user_preference(user_id, "active_session_id", new_session_id)
        return new_session_id

    def send_response(self, event: StandardEvent, final_answer: str) -> bool:
        """将 L3 的最终答案包装为标准格式并交给 L1 发送。

        同时保存本轮对话（user query + assistant answer）到 L4。

        参数：
            event: 原始 StandardEvent，包含 channel 和 metadata
            final_answer: L3 返回的最终答案文本

        返回：
            True if sent successfully, False otherwise
        """
        # 保存对话历史到 L4（静默失败，不影响发送）
        try:
            self._store_exchange(event, final_answer)
        except Exception as e:
            print(f"[L2] Warning: Failed to store conversation: {e}")

        response = StandardResponse(
            channel=event.channel,
            user_id=event.user_id,
            content=final_answer,
            metadata=dict(event.metadata)
        )
        print(f"[L2] 发送响应给用户 {event.user_id[:20]}...: {final_answer[:50]}...")
        if self.l1 is not None:
            return self.l1.send_response(response)
        print("[L2] Warning: L1 instance not available, response not sent to user.")
        return False

    def _store_exchange(self, event: StandardEvent, final_answer: str) -> bool:
        """保存一轮对话到 L4。

        参数：
            event: 原始 StandardEvent（包含 user query）
            final_answer: L3 返回的最终答案

        返回：
            True if stored successfully, False otherwise
        """
        session_id = self._get_or_create_session(event)
        if not session_id:
            return False

        # 读取已有历史，追加本轮消息
        history = self.memory.retrieve_history(session_id, limit=1000)
        history.append({"role": "user", "content": event.content})
        history.append({"role": "assistant", "content": final_answer})

        return self.memory.store_conversation(session_id, history)
