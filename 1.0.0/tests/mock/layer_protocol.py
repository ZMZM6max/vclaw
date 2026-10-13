"""
VClaw 层次连接协议
==================
定义L1-L6之间的数据流转协议，确保六个层次能够正确串联运行。
"""

from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


# =============================================================================
# 枚举类型定义
# =============================================================================
class LayerStatus(str, Enum):
    """层次处理状态"""
    SUCCESS = "success"
    ERROR = "error"
    ACTION_REQUIRED = "action_required"
    DIRECT_RESPONSE = "direct_response"


class ErrorCode(str, Enum):
    """错误代码"""
    # L1错误
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNSUPPORTED_CHANNEL = "UNSUPPORTED_CHANNEL"
    PARSE_ERROR = "PARSE_ERROR"

    # L2错误
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    SESSION_ERROR = "SESSION_ERROR"

    # L3错误
    PLANNING_ERROR = "PLANNING_ERROR"
    LLM_ERROR = "LLM_ERROR"
    MAX_ITERATIONS_REACHED = "MAX_ITERATIONS_REACHED"

    # L4错误
    EMBEDDING_ERROR = "EMBEDDING_ERROR"
    VECTOR_STORE_ERROR = "VECTOR_STORE_ERROR"
    INVALID_FILTER = "INVALID_FILTER"

    # L5错误
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    PARAMETER_VALIDATION_ERROR = "PARAMETER_VALIDATION_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"

    # L6错误
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    RESOURCE_EXCEEDED = "RESOURCE_EXCEEDED"
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
    SANDBOX_ERROR = "SANDBOX_ERROR"


class ComponentTraceItem(BaseModel):
    """组件级执行状态追踪项"""
    component: str = Field(..., description="组件名称")
    status: str = Field(..., description="success / skipped / error")
    reason: Optional[str] = Field(None, description="状态说明")
    output_summary: Optional[str] = Field(None, description="输出摘要")


# =============================================================================
# L1 数据模型
# =============================================================================
class RawPayload(BaseModel):
    """L1输入：原始载荷"""
    channel: str = Field(..., description="渠道: telegram, websocket, webhook")
    raw_data: Dict[str, Any] = Field(..., description="原始数据")
    client_ip: Optional[str] = Field(None, description="客户端IP")


class StandardEvent(BaseModel):
    """L1输出/L2输入：标准化事件"""
    channel: str = Field(..., description="渠道来源")
    user_id: str = Field(..., description="用户ID")
    content: str = Field(..., description="内容")
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class L1Output(BaseModel):
    """L1层输出结构"""
    status: LayerStatus
    standard_event: Optional[StandardEvent] = None
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None
    processing_log: List[str] = Field(default_factory=list)
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)


# =============================================================================
# L2 数据模型
# =============================================================================
class RateLimitInfo(BaseModel):
    """限流信息"""
    remaining: int
    reset_time: float
    limit: int


class SessionContext(BaseModel):
    """L2输出/L3输入：会话上下文"""
    session_id: str = Field(..., description="会话ID")
    user_id: str = Field(..., description="用户ID")
    current_query: str = Field(..., description="当前查询")
    history: List[Dict[str, str]] = Field(default_factory=list, description="历史记录")
    user_permissions: List[str] = Field(default_factory=list, description="用户权限")
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class L2Output(BaseModel):
    """L2层输出结构"""
    status: LayerStatus
    session_context: Optional[SessionContext] = None
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None
    rate_limit: Optional[RateLimitInfo] = None
    processing_log: List[str] = Field(default_factory=list)
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)


# =============================================================================
# L3 数据模型
# =============================================================================
class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    description: str
    parameters: Dict[str, Any]


class AgentAction(BaseModel):
    """L3输出（内部）：代理行动"""
    action: str = Field(..., description="工具名称")
    action_input: Dict[str, Any] = Field(..., description="工具参数")
    thought: Optional[str] = Field(None, description="思考过程")


class L3Output(BaseModel):
    """L3层输出结构"""
    status: LayerStatus
    agent_action: Optional[AgentAction] = None
    response: Optional[str] = None  # 直接回复时使用
    reasoning_chain: List[str] = Field(default_factory=list)
    processing_log: List[str] = Field(default_factory=list)
    iteration_count: int = Field(0, description="ReAct迭代次数")
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)


# =============================================================================
# L4 数据模型
# =============================================================================
class SearchResult(BaseModel):
    """搜索结果"""
    content: str
    score: float
    metadata: Dict[str, Any]


class L4SearchOutput(BaseModel):
    """L4搜索输出"""
    status: LayerStatus
    results: List[SearchResult] = Field(default_factory=list)
    query_embedding: Optional[List[float]] = None
    cache_hit: bool = False
    processing_log: List[str] = Field(default_factory=list)
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)


class L4StoreOutput(BaseModel):
    """L4存储输出"""
    status: LayerStatus
    document_id: Optional[str] = None
    chunks_count: int = 0
    processing_log: List[str] = Field(default_factory=list)
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)


class L4HistoryOutput(BaseModel):
    """L4历史记录输出"""
    status: LayerStatus
    messages: List[Dict[str, str]] = Field(default_factory=list)
    processing_log: List[str] = Field(default_factory=list)
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)


# =============================================================================
# L5 数据模型
# =============================================================================
class Observation(BaseModel):
    """L5输出/L3输入：观察结果"""
    status: str = Field(..., description="success or error")
    result: str = Field(..., description="结果")
    execution_time: float = Field(..., description="执行时间")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class L5Output(BaseModel):
    """L5层输出结构"""
    status: LayerStatus
    observation: Optional[Observation] = None
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None
    processing_log: List[str] = Field(default_factory=list)
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)


# =============================================================================
# L6 数据模型
# =============================================================================
class ResourceUsage(BaseModel):
    """资源使用"""
    memory_peak: Optional[int] = None  # MB
    cpu_time: Optional[float] = None  # seconds


class ExecutionResult(BaseModel):
    """L6输出/L5输入：执行结果"""
    exit_code: int = Field(..., description="退出码")
    stdout: str = Field(default="", description="标准输出")
    stderr: str = Field(default="", description="标准错误")
    execution_time: float = Field(..., description="执行时间")
    resource_usage: ResourceUsage = Field(default_factory=ResourceUsage)
    environment_id: Optional[str] = None


class L6Output(BaseModel):
    """L6层输出结构"""
    status: LayerStatus
    execution_result: Optional[ExecutionResult] = None
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None
    processing_log: List[str] = Field(default_factory=list)
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)


# =============================================================================
# 层次连接协议定义
# =============================================================================
class LayerConnectionProtocol:
    """
    层次连接协议
    定义每一层如何接收输入和输出到下一层
    """

    # L1 -> L2
    @staticmethod
    def l1_to_l2(l1_output: L1Output) -> Optional[StandardEvent]:
        """L1输出转换为L2输入"""
        if l1_output.status == LayerStatus.SUCCESS and l1_output.standard_event:
            return l1_output.standard_event
        return None

    # L2 -> L3
    @staticmethod
    def l2_to_l3(l2_output: L2Output) -> Optional[SessionContext]:
        """L2输出转换为L3输入"""
        if l2_output.status == LayerStatus.SUCCESS and l2_output.session_context:
            return l2_output.session_context
        return None

    # L3 -> L5 (当需要工具调用时)
    @staticmethod
    def l3_to_l5(l3_output: L3Output) -> Optional[AgentAction]:
        """L3输出转换为L5输入"""
        if l3_output.status == LayerStatus.ACTION_REQUIRED and l3_output.agent_action:
            return l3_output.agent_action
        return None

    # L5 -> L6 (当需要执行代码时)
    @staticmethod
    def l5_to_l6(agent_action: AgentAction) -> Optional[Dict[str, Any]]:
        """L5的代码执行请求转换为L6输入"""
        if agent_action.action == "python_repl":
            return {
                "language": "python",
                "code": agent_action.action_input.get("code", ""),
                "timeout": 30
            }
        elif agent_action.action == "terminal":
            return {
                "language": "bash",
                "code": agent_action.action_input.get("command", ""),
                "timeout": 30
            }
        return None

    # L6 -> L5
    @staticmethod
    def l6_to_l5(l6_output: L6Output) -> Optional[Observation]:
        """L6输出转换为L5输入"""
        if l6_output.execution_result:
            result = l6_output.execution_result
            return Observation(
                status="success" if result.exit_code == 0 else "error",
                result=result.stdout if result.exit_code == 0 else result.stderr,
                execution_time=result.execution_time,
                metadata={
                    "exit_code": result.exit_code,
                    "environment_id": result.environment_id
                }
            )
        return None

    # L5 -> L3
    @staticmethod
    def l5_to_l3(l5_output: L5Output) -> Optional[Observation]:
        """L5输出转换回L3输入"""
        if l5_output.observation:
            return l5_output.observation
        return None

    # L3 -> L4 (记忆检索)
    @staticmethod
    def l3_to_l4_search(session_context: SessionContext, top_k: int = 5) -> Dict[str, Any]:
        """L3构造L4搜索请求"""
        return {
            "operation": "search",
            "query": session_context.current_query,
            "top_k": top_k,
            "filters": {"user_id": session_context.user_id}
        }

    # L3 -> L4 (历史存储)
    @staticmethod
    def l3_to_l4_store_history(
        session_id: str,
        messages: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """L3构造L4历史存储请求"""
        return {
            "operation": "store_conversation",
            "session_id": session_id,
            "messages": messages
        }


# =============================================================================
# 完整端到端数据流
# =============================================================================
class EndToEndFlow:
    """
    端到端数据流示例
    展示一个完整的请求如何流经所有层次
    """

    @staticmethod
    def example_flow() -> Dict[str, Any]:
        """示例：用户请求计算Fibonacci(10)"""
        return {
            "flow_name": "计算Fibonacci数列",
            "steps": [
                {
                    "layer": "L1",
                    "input": {
                        "channel": "telegram",
                        "raw_data": {
                            "message": {
                                "from": {"id": "12345"},
                                "text": "计算Fibonacci(10)"
                            }
                        }
                    },
                    "output_type": "StandardEvent",
                    "description": "将Telegram消息标准化为StandardEvent"
                },
                {
                    "layer": "L2",
                    "input": "StandardEvent",
                    "output_type": "SessionContext",
                    "description": "限流检查、会话创建、从L4检索历史和相关记忆、上下文组装"
                },
                {
                    "layer": "L4",
                    "input": "搜索请求 + session_id",
                    "output_type": "相关记忆 + 对话历史",
                    "description": "L2调用L4: retrieve_history + search"
                },
                {
                    "layer": "L3",
                    "input": "SessionContext",
                    "output_type": "AgentAction",
                    "description": "任务规划、ReAct循环、决定调用python_repl工具"
                },
                {
                    "layer": "L5",
                    "input": "AgentAction",
                    "output_type": "L6执行请求",
                    "description": "权限检查、参数验证、路由到L6执行代码"
                },
                {
                    "layer": "L6",
                    "input": "代码执行请求",
                    "output_type": "ExecutionResult",
                    "description": "创建沙盒、执行Python代码、返回结果"
                },
                {
                    "layer": "L5",
                    "input": "ExecutionResult",
                    "output_type": "Observation",
                    "description": "格式化执行结果为Observation"
                },
                {
                    "layer": "L3",
                    "input": "Observation",
                    "output_type": "最终回复",
                    "description": "接收观察结果，生成最终回复给用户"
                }
            ]
        }


# =============================================================================
# 协议验证器
# =============================================================================
class ProtocolValidator:
    """协议验证器 - 验证层间数据传输是否符合协议"""

    @staticmethod
    def validate_l1_output(data: Dict[str, Any]) -> bool:
        """验证L1输出"""
        try:
            L1Output(**data)
            return True
        except Exception:
            return False

    @staticmethod
    def validate_l2_output(data: Dict[str, Any]) -> bool:
        """验证L2输出"""
        try:
            L2Output(**data)
            return True
        except Exception:
            return False

    @staticmethod
    def validate_l3_output(data: Dict[str, Any]) -> bool:
        """验证L3输出"""
        try:
            L3Output(**data)
            return True
        except Exception:
            return False

    @staticmethod
    def validate_l5_output(data: Dict[str, Any]) -> bool:
        """验证L5输出"""
        try:
            L5Output(**data)
            return True
        except Exception:
            return False

    @staticmethod
    def validate_l6_output(data: Dict[str, Any]) -> bool:
        """验证L6输出"""
        try:
            L6Output(**data)
            return True
        except Exception:
            return False
