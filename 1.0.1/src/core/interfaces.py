"""Interface definitions for dependency injection."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.core.models import (
    SessionContext, Observation, ExecutionResult,
    Document, AgentAction
)


class MemoryInterface(ABC):
    """L4 interface - Memory and knowledge layer."""
    
    @abstractmethod
    def search(self, query: str, top_k: int = 5, 
               filters: Optional[Dict] = None) -> List[str]:
        """Search for relevant documents."""
        pass
    
    @abstractmethod
    def store(self, document: str, metadata: Dict[str, Any]) -> bool:
        """Store a document."""
        pass
    
    @abstractmethod
    def store_conversation(self, session_id: str, 
                          messages: List[Dict[str, str]]) -> bool:
        """Store conversation history."""
        pass
    
    @abstractmethod
    def retrieve_history(self, session_id: str,
                        limit: int = 10) -> List[Dict[str, str]]:
        """Retrieve conversation history."""
        pass

    @abstractmethod
    def save_user_preference(
        self, user_id: str, key: str, value: Any
    ) -> bool:
        """Save a user preference."""
        pass

    @abstractmethod
    def load_user_preference(
        self, user_id: str, key: str, default: Any = None
    ) -> Any:
        """Load a user preference."""
        pass


class ToolsInterface(ABC):
    """L5 interface - Tools and capabilities layer."""

    @abstractmethod
    def execute(self, action_name: str, params: Dict[str, Any],
                timeout: int = 30) -> Observation:
        """Execute a tool."""
        pass

    @abstractmethod
    def get_available_tools(self) -> List[Dict]:
        """Get list of available tools for LLM."""
        pass

    @abstractmethod
    def list_tools(self) -> List[Dict[str, Any]]:
        """Get all registered tool definitions.

        返回：
            工具定义列表，每个工具包含：
            - name: 工具名称
            - description: 工具描述
            - parameters: 参数定义（JSON Schema 格式）
            - required_permission: 所需权限标识（可选，None 表示无需权限）
        """
        pass


class RuntimeInterface(ABC):
    """L6 interface - Runtime and environment layer."""

    @abstractmethod
    def run_code(self, language: str, code: str,
                 timeout: int = 30,
                 environment_config: Optional[Dict] = None) -> ExecutionResult:
        """Execute code in sandbox."""
        pass

    @abstractmethod
    def run_command(self, command: str,
                    timeout: int = 30) -> ExecutionResult:
        """Execute a shell command in sandbox.

        Args:
            command: Shell command string to execute
            timeout: Execution timeout in seconds

        Returns:
            ExecutionResult with exit_code, stdout, stderr, execution_time
        """
        pass
