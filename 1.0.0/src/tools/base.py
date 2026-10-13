"""工具基础类和接口定义"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel, Field


class ToolError(Exception):
    """工具执行错误"""
    
    def __init__(self, message: str, error_code: int = 0, details: Dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class ToolResult(BaseModel):
    """工具执行结果"""
    
    success: bool = Field(True, description="执行是否成功")
    content: str = Field("", description="文本内容结果")
    data: Dict[str, Any] = Field(default_factory=dict, description="结构化数据")
    error: Optional[str] = Field(None, description="错误信息")
    
    class Config:
        arbitrary_types_allowed = True


InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class Tool(ABC):
    """
    工具基类
    
    所有工具都应继承此类并实现必要的方法
    """
    
    # 工具元数据
    name: str = ""
    description: str = ""
    search_hint: str = ""
    
    # 输入输出模式
    input_schema: Type[BaseModel] = None
    output_schema: Type[BaseModel] = None
    
    # 配置选项
    max_result_size: int = 100_000
    read_only: bool = False
    
    def __init__(self):
        if not self.name:
            raise ValueError(f"Tool {self.__class__.__name__} must have a name")
    
    @abstractmethod
    async def call(self, **kwargs) -> ToolResult:
        """
        执行工具
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            ToolResult: 工具执行结果
        """
        pass
    
    def validate_input(self, **kwargs) -> tuple[bool, Optional[str]]:
        """
        验证输入参数
        
        Returns:
            (是否有效, 错误信息)
        """
        if self.input_schema is None:
            return True, None
        
        try:
            self.input_schema(**kwargs)
            return True, None
        except Exception as e:
            return False, str(e)
    
    def get_description(self) -> str:
        """获取工具描述（用于 LLM）"""
        return self.description
    
    def to_function_def(self) -> Dict[str, Any]:
        """
        转换为 OpenAI Function 定义格式
        
        Returns:
            Function definition dict
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema.model_json_schema() if self.input_schema else {"type": "object"}
            }
        }
