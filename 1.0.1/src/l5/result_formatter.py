"""L5 ResultFormatter - 结果格式化器.

统一所有工具执行结果的输出格式，负责将原始执行结果转换为标准化的 Observation 对象，
同时处理空结果、超长结果截断、以及面向用户的自然语言模板渲染。
"""
import logging
from typing import Any, Dict, List, Optional

from src.core.models import Observation

logger = logging.getLogger(__name__)


class ResultFormatter:
    """L5层输出标准化引擎.

    核心职责:
    - 统一输出格式（将任意执行结果转为标准 Observation）
    - 空结果处理（禁止返回"模拟读取"等占位文本）
    - 结果长度控制（截断至最大长度）
    - 模板渲染（根据场景使用合适的用户提示语）
    - Mock/模拟标识过滤（禁止泄漏到用户可见回复）
    """

    MAX_RESULT_LENGTH: int = 10000
    TRUNCATION_INDICATOR: str = "\n...[内容已截断，共{original_length}字]"
    LIST_MAX_ITEMS: int = 10

    _EMPTY_TEMPLATES: Dict[str, str] = {
        "file_read": "该文档为空",
        "search_web": "未找到相关内容",
        "calculator": "计算结果为空",
        "file_search": "未找到相关文件",
    }

    _MOCK_PATTERNS: List[str] = [
        "模拟",
        "mock",
        "placeholder",
        "dummy",
        "test data",
        "示例数据",
    ]

    def format(
        self,
        raw_result: Any,
        tool_name: str,
        execution_time: float,
        metadata: Optional[Dict[str, Any]] = None,
        scenario: Optional[str] = None,
    ) -> Observation:
        """格式化工具执行结果为标准 Observation.

        执行流程:
        1. 检测 raw_result 类型和空状态
        2. 若为空，应用空结果处理规则
        3. 若为列表，应用枚举结果格式化
        4. 若为错误，应用错误结果格式化
        5. 应用场景模板渲染
        6. 执行长度截断（若超过 MaxResultLength）
        7. 过滤 Mock/模拟标识
        8. 组装并返回 Observation 对象
        """
        metadata = metadata or {}

        # 自动检测场景（若未提供）
        if scenario is None:
            scenario = self._detect_scenario(raw_result, tool_name, metadata)

        # 应用模板得到用户可见内容
        result_text = self._apply_template(scenario, raw_result, tool_name, metadata)

        # 标记空结果
        if self._is_empty(raw_result):
            metadata["empty"] = True

        # 长度截断
        result_text, metadata = self._truncate_result(result_text, metadata)

        # Mock 过滤
        result_text = self._filter_mock(result_text)

        # 根据场景决定 status：error 场景返回 "error"，其余返回 "success"
        status = "error" if scenario == "error" else "success"

        # 组装 Observation
        return Observation(
            status=status,
            result=result_text,
            execution_time=execution_time,
            metadata=metadata,
        )

    def format_success(
        self,
        result: str,
        tool_name: str,
        execution_time: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Observation:
        """格式化成功结果."""
        metadata = metadata or {}
        return self.format(
            raw_result=result,
            tool_name=tool_name,
            execution_time=execution_time,
            metadata=metadata,
        )

    def format_error(
        self,
        error_message: str,
        tool_name: str,
        execution_time: float,
        error_type: Optional[str] = None,
    ) -> Observation:
        """格式化错误结果.

        将 error_message 转换为用户友好的中文提示（若需要），
        保留原始错误信息在 metadata 中。
        """
        metadata: Dict[str, Any] = {
            "tool_name": tool_name,
            "original_error": error_message,
        }
        if error_type:
            metadata["error_type"] = error_type

        friendly = self._friendly_error_message(error_message)
        return Observation(
            status="error",
            result=friendly,
            execution_time=execution_time,
            metadata=metadata,
        )

    def truncate(self, text: str, max_length: int = 10000) -> str:
        """截断超长结果.

        1. 若 text 长度 <= max_length，直接返回
        2. 截取前 (max_length - indicator_length) 字符
        3. 追加截断提示
        4. 确保最终长度不超过 max_length
        """
        if len(text) <= max_length:
            return text

        original_length = len(text)
        indicator = self.TRUNCATION_INDICATOR.format(original_length=original_length)

        # 预留提示语空间
        available = max_length - len(indicator)
        if available < 0:
            available = 0

        truncated = text[:available] + indicator

        # 保险：若因字符边界导致超出，再做一次硬截断
        if len(truncated) > max_length:
            truncated = truncated[:max_length]

        return truncated

    # ------------------------------------------------------------------ #
    #  Private helpers
    # ------------------------------------------------------------------ #

    def _detect_scenario(
        self, raw_result: Any, tool_name: str, metadata: Dict[str, Any]
    ) -> str:
        """根据结果特征自动检测应用场景."""
        if metadata.get("exit_code", 0) != 0:
            return "error"

        if isinstance(raw_result, list):
            return "list_result"

        if tool_name == "file_write" and metadata.get("bytes_written") is not None:
            return "success_file_write"

        if self._is_empty(raw_result):
            return f"empty_{tool_name}"

        if tool_name == "file_read":
            return "success_file_read"

        return "default"

    def _apply_template(
        self,
        scenario: str,
        raw_result: Any,
        tool_name: str,
        metadata: Dict[str, Any],
    ) -> str:
        """根据场景渲染输出模板."""
        # 空结果处理
        if scenario.startswith("empty_"):
            return self._empty_template(scenario, tool_name)

        # 列表结果
        if scenario == "list_result":
            return self._list_template(raw_result)

        # 文件写入成功
        if scenario == "success_file_write":
            filename = metadata.get("filename", "未知文件")
            char_count = metadata.get("bytes_written", 0)
            return f"已成功写入《{filename}》，共{char_count}字"

        # 文件读取成功
        if scenario == "success_file_read":
            filename = metadata.get("filename", "未知文件")
            content = str(raw_result) if raw_result is not None else ""
            return f"文件《{filename}》内容如下：\n{content}"

        # 错误
        if scenario == "error":
            return str(raw_result) if raw_result is not None else "执行出错"

        # 默认：直接字符串化
        if raw_result is None:
            return ""
        return str(raw_result)

    def _empty_template(self, scenario: str, tool_name: str) -> str:
        """返回空结果对应模板."""
        # 优先按场景精确匹配
        if scenario in ("empty_file_read",):
            return self._EMPTY_TEMPLATES.get("file_read", "该文档为空")

        if scenario in ("empty_search_web", "empty_file_search"):
            key = "search_web" if "search_web" in scenario else "file_search"
            return self._EMPTY_TEMPLATES.get(key, "未找到相关内容")

        if scenario == "empty_calculator":
            return self._EMPTY_TEMPLATES.get("calculator", "计算结果为空")

        # 按工具名回退
        if tool_name in self._EMPTY_TEMPLATES:
            return self._EMPTY_TEMPLATES[tool_name]

        # 通用回退
        if tool_name == "file_read":
            return "该文档为空"
        if tool_name in ("search_web", "file_search"):
            return "未找到相关内容"
        if tool_name == "calculator":
            return "计算结果为空"

        return "未找到相关内容"

    def _list_template(self, raw_result: Any) -> str:
        """格式化列表结果."""
        if not isinstance(raw_result, list):
            raw_result = [raw_result] if raw_result is not None else []

        count = len(raw_result)
        if count == 0:
            return "找到0个结果，需要查看具体内容吗？"

        display_items = raw_result[: self.LIST_MAX_ITEMS]
        lines = []
        for idx, item in enumerate(display_items, start=1):
            item_str = str(item)
            lines.append(f"{idx}. {item_str}")

        if count > self.LIST_MAX_ITEMS:
            lines.append("还有更多")

        items_text = "\n".join(lines)
        return f"找到以下{count}项：\n{items_text}\n请确认是否需要打开？"

    def _truncate_result(self, text: str, metadata: Dict[str, Any]) -> tuple:
        """对结果文本执行截断并更新 metadata."""
        original_length = len(text)
        if original_length > self.MAX_RESULT_LENGTH:
            truncated_text = self.truncate(text, self.MAX_RESULT_LENGTH)
            metadata["truncated"] = True
            metadata["original_length"] = original_length
            return truncated_text, metadata
        return text, metadata

    def _filter_mock(self, text: str) -> str:
        """过滤 Mock/模拟标识.

        若发现包含 Mock 模式的内容，替换为空结果模板并记录警告日志。
        """
        text_lower = text.lower()
        for pattern in self._MOCK_PATTERNS:
            if pattern.lower() in text_lower:
                logger.warning("Mock pattern detected in result: %s", pattern)
                return "该文档为空"
        return text

    def _is_empty(self, raw_result: Any) -> bool:
        """判断结果是否为空.

        处理 None、空字符串、空列表、仅空白字符等情况。
        """
        if raw_result is None:
            return True
        if isinstance(raw_result, str) and raw_result.strip() == "":
            return True
        if isinstance(raw_result, list) and len(raw_result) == 0:
            return True
        return False

    def _friendly_error_message(self, error_message: str) -> str:
        """将技术错误转换为用户友好的中文提示."""
        msg_lower = error_message.lower()

        if "filenotfound" in msg_lower or "no such file" in msg_lower:
            return "找不到指定文件"
        if "permission denied" in msg_lower:
            return "权限不足，无法访问"
        if "timeout" in msg_lower:
            return "执行超时，请稍后重试"
        if "memory" in msg_lower:
            return "内存不足，无法完成操作"
        if "not found" in msg_lower:
            return "未找到相关内容"

        return f"操作失败: {error_message}"
