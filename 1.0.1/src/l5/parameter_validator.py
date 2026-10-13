"""L5: ParameterValidator - 参数验证器组件.

负责校验LLM生成的工具参数是否符合JSON Schema规范，
同时执行参数保真校验以防止LLM幻觉篡改用户原始输入。
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union


# ========== 异常定义 ==========
class InvalidSchemaError(Exception):
    """提供的JSON Schema格式不合法."""
    pass


class FidelityCheckError(Exception):
    """参数保真校验失败（LLM篡改了用户输入）."""
    pass


class PathTraversalError(Exception):
    """检测到目录遍历攻击."""
    pass


# 内部兼容类：validate_sandbox_path 返回旧格式结果
class _CompatValidationResult:
    __slots__ = ("valid", "is_valid", "errors")

    def __init__(self, valid: bool, errors: List[str]):
        self.valid = valid
        self.is_valid = valid
        self.errors = errors

    def __bool__(self):
        return self.valid


# ========== 数据结构 ==========
@dataclass
class ValidationErrorDetail:
    """单个验证错误详情."""
    field: str
    error_type: str
    message: str
    suggestion: Optional[str] = None

    def __post_init__(self):
        valid_types = {
            "type_error", "missing_required", "format_error", "range_error",
            "path_traversal", "fidelity_mismatch", "custom_rule",
        }
        if self.error_type not in valid_types:
            raise ValueError(f"Invalid error_type: {self.error_type}")


@dataclass
class FidelityMismatch:
    """保真不一致项."""
    field: str
    raw_value: Any
    llm_value: Any
    mismatch_type: str

    def __post_init__(self):
        valid_types = {
            "path_modified", "content_modified", "value_added",
            "value_removed", "type_changed",
        }
        if self.mismatch_type not in valid_types:
            raise ValueError(f"Invalid mismatch_type: {self.mismatch_type}")


@dataclass
class FidelityCheckResult:
    """参数保真校验结果."""
    is_consistent: bool
    mismatches: List[FidelityMismatch]
    raw_payload: Optional[dict] = None


@dataclass
class ValidationResult:
    """参数验证结果."""
    is_valid: bool
    errors: List[ValidationErrorDetail]
    sanitized_params: Optional[dict] = None
    fidelity_check: Optional[FidelityCheckResult] = None

    def __bool__(self):
        return self.is_valid


# ========== 轻量级 JSON Schema 验证器 ==========
class _SchemaValidator:
    """基于Python标准库的轻量级JSON Schema验证器.

    覆盖V-SCHEMA-01~V-SCHEMA-08规则，无需外部jsonschema依赖。
    """

    def validate(self, value: Any, schema: dict, path: str = "") -> List[ValidationErrorDetail]:
        errors: List[ValidationErrorDetail] = []

        if not isinstance(schema, dict):
            errors.append(ValidationErrorDetail(
                field=path or "<root>",
                error_type="format_error",
                message="Schema定义必须是对象类型",
                suggestion="请检查工具的参数Schema定义",
            ))
            return errors

        schema_type = schema.get("type")

        # type校验
        if schema_type is not None:
            if not self._check_type(value, schema_type):
                type_names = {
                    "string": "字符串", "number": "数字", "integer": "整数",
                    "boolean": "布尔值", "array": "数组", "object": "对象",
                    "null": "null",
                }
                expected = type_names.get(schema_type, schema_type)
                actual = self._get_type_name(value)
                errors.append(ValidationErrorDetail(
                    field=path or "<root>",
                    error_type="type_error",
                    message=f"参数类型应为{expected}，实际收到{actual}",
                    suggestion=f"请提供{type_names.get(schema_type, schema_type)}类型的值",
                ))
                # 类型不匹配时，后续同字段校验可跳过（避免None报错）
                return errors

        # 字符串校验
        if schema_type == "string" and isinstance(value, str):
            errors.extend(self._validate_string(value, schema, path))

        # 数值校验
        if schema_type in ("number", "integer") and isinstance(value, (int, float)) and not isinstance(value, bool):
            errors.extend(self._validate_number(value, schema, path))

        # 数组校验
        if schema_type == "array" and isinstance(value, list):
            errors.extend(self._validate_array(value, schema, path))

        # 对象校验
        if schema_type == "object" and isinstance(value, dict):
            errors.extend(self._validate_object(value, schema, path))

        # enum校验（不限制类型）
        if "enum" in schema and value not in schema["enum"]:
            enum_str = ", ".join(repr(v) for v in schema["enum"])
            errors.append(ValidationErrorDetail(
                field=path or "<root>",
                error_type="format_error",
                message=f"参数值必须是以下之一：{enum_str}",
                suggestion="请从枚举列表中选择有效值",
            ))

        return errors

    def _check_type(self, value: Any, expected: str) -> bool:
        type_map = {
            "string": lambda v: isinstance(v, str),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
            "null": lambda v: v is None,
        }
        checker = type_map.get(expected)
        if checker is None:
            return True  # 未知类型不校验
        return checker(value)

    def _get_type_name(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "布尔值"
        if isinstance(value, int):
            return "整数"
        if isinstance(value, float):
            return "浮点数"
        if isinstance(value, str):
            return "字符串"
        if isinstance(value, list):
            return "数组"
        if isinstance(value, dict):
            return "对象"
        return type(value).__name__

    def _validate_string(self, value: str, schema: dict, path: str) -> List[ValidationErrorDetail]:
        errors: List[ValidationErrorDetail] = []

        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(ValidationErrorDetail(
                field=path,
                error_type="format_error",
                message=f"字符串长度不能少于{schema['minLength']}个字符",
                suggestion="请提供更长的字符串",
            ))

        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(ValidationErrorDetail(
                field=path,
                error_type="format_error",
                message=f"字符串长度不能超过{schema['maxLength']}个字符",
                suggestion="请缩短字符串长度",
            ))

        if "pattern" in schema:
            try:
                if not re.search(schema["pattern"], value):
                    errors.append(ValidationErrorDetail(
                        field=path,
                        error_type="format_error",
                        message=f"字符串格式不匹配正则表达式：{schema['pattern']}",
                        suggestion="请按要求的格式提供字符串",
                    ))
            except re.error as e:
                raise InvalidSchemaError(f"Schema中的正则表达式无效：{schema['pattern']}，错误：{e}")

        return errors

    def _validate_number(self, value: Union[int, float], schema: dict, path: str) -> List[ValidationErrorDetail]:
        errors: List[ValidationErrorDetail] = []

        if "minimum" in schema and value < schema["minimum"]:
            errors.append(ValidationErrorDetail(
                field=path,
                error_type="range_error",
                message=f"数值不能小于{schema['minimum']}",
                suggestion=f"请提供大于等于{schema['minimum']}的数值",
            ))

        if "maximum" in schema and value > schema["maximum"]:
            errors.append(ValidationErrorDetail(
                field=path,
                error_type="range_error",
                message=f"数值不能大于{schema['maximum']}",
                suggestion=f"请提供小于等于{schema['maximum']}的数值",
            ))

        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errors.append(ValidationErrorDetail(
                field=path,
                error_type="range_error",
                message=f"数值必须大于{schema['exclusiveMinimum']}",
                suggestion=f"请提供大于{schema['exclusiveMinimum']}的数值",
            ))

        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            errors.append(ValidationErrorDetail(
                field=path,
                error_type="range_error",
                message=f"数值必须小于{schema['exclusiveMaximum']}",
                suggestion=f"请提供小于{schema['exclusiveMaximum']}的数值",
            ))

        return errors

    def _validate_array(self, value: list, schema: dict, path: str) -> List[ValidationErrorDetail]:
        errors: List[ValidationErrorDetail] = []

        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(ValidationErrorDetail(
                field=path,
                error_type="format_error",
                message=f"数组元素不能少于{schema['minItems']}个",
                suggestion="请提供更多数组元素",
            ))

        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(ValidationErrorDetail(
                field=path,
                error_type="format_error",
                message=f"数组元素不能超过{schema['maxItems']}个",
                suggestion="请减少数组元素数量",
            ))

        if "items" in schema:
            items_schema = schema["items"]
            for idx, item in enumerate(value):
                item_path = f"{path}[{idx}]" if path else f"[{idx}]"
                errors.extend(self.validate(item, items_schema, item_path))

        return errors

    def _validate_object(self, value: dict, schema: dict, path: str) -> List[ValidationErrorDetail]:
        errors: List[ValidationErrorDetail] = []
        properties = schema.get("properties", {})

        # 校验properties中定义的字段
        for prop_name, prop_schema in properties.items():
            prop_path = f"{path}.{prop_name}" if path else prop_name
            if prop_name in value:
                errors.extend(self.validate(value[prop_name], prop_schema, prop_path))

        # additionalProperties校验
        additional = schema.get("additionalProperties", True)
        if additional is False:
            extra_keys = set(value.keys()) - set(properties.keys())
            for key in extra_keys:
                prop_path = f"{path}.{key}" if path else key
                errors.append(ValidationErrorDetail(
                    field=prop_path,
                    error_type="format_error",
                    message=f"对象包含未定义的属性'{key}'",
                    suggestion="请移除多余的属性",
                ))
        elif isinstance(additional, dict):
            extra_keys = set(value.keys()) - set(properties.keys())
            for key in extra_keys:
                prop_path = f"{path}.{key}" if path else key
                errors.extend(self.validate(value[key], additional, prop_path))

        return errors

    def check_required(self, params: dict, schema: dict, path: str = "") -> List[ValidationErrorDetail]:
        """检查必填字段是否存在且非None."""
        errors: List[ValidationErrorDetail] = []
        required = schema.get("required", [])
        for field_name in required:
            if field_name not in params or params[field_name] is None:
                field_path = f"{path}.{field_name}" if path else field_name
                errors.append(ValidationErrorDetail(
                    field=field_path,
                    error_type="missing_required",
                    message=f"缺少必填参数'{field_name}'",
                    suggestion="请提供该参数的值",
                ))
        return errors


# ========== ParameterValidator ==========
class ParameterValidator:
    """参数验证器，负责校验LLM生成的工具参数.

    核心交付：
    - JSON Schema校验（类型、必填、格式、范围）
    - 路径安全校验（防目录遍历）
    - 参数保真校验（对比L1的raw_user_payload，检测LLM幻觉）
    - 参数清洗（去除危险字符、规范化路径）
    """

    SCHEMA_VALIDATION_ENABLED = True
    PATH_VALIDATION_ENABLED = True
    FIDELITY_CHECK_ENABLED = True
    MAX_STRING_LENGTH = 10000
    SANDBOX_ROOT = "/sandbox"
    ALLOWED_ABSOLUTE_PATHS: List[str] = []

    DANGEROUS_PATH_PATTERNS = [
        r"\.",
    ]

    SENSITIVE_DIRECTORIES = [
        "/etc", "/proc", "/sys", "/root", "/boot",
        "C:\\Windows", "C:\\Program Files", "C:\\Windows\\System32",
    ]

    DANGEROUS_COMMANDS = [
        "rm -rf /", "eval(", "sudo", "shutdown", ":(){ :|:& };:",
    ]

    def __init__(self):
        self._schema_validator = _SchemaValidator()
        self._custom_rules: Dict[str, List[Callable]] = {}

    # ========== 公共接口 ==========

    def validate(
        self,
        params: dict,
        schema: dict,
        raw_user_payload: Optional[dict] = None,
        tool_name: Optional[str] = None,
    ) -> ValidationResult:
        """主验证入口.

        执行顺序：
        1. JSON Schema校验（类型、必填、格式、范围）
        2. 路径安全校验
        3. 保真校验（若raw_user_payload存在）
        4. 自定义校验规则
        5. 参数清洗（若全部通过）
        """
        errors: List[ValidationErrorDetail] = []

        # Step 1: JSON Schema校验
        if self.SCHEMA_VALIDATION_ENABLED:
            errors.extend(self._schema_validator.check_required(params, schema))
            errors.extend(self._schema_validator.validate(params, schema))

        # Step 2: 路径安全校验
        if self.PATH_VALIDATION_ENABLED:
            path_errors = self._validate_path_security(params)
            errors.extend(path_errors)

        # Step 3: 保真校验
        fidelity_result = None
        if self.FIDELITY_CHECK_ENABLED and raw_user_payload:
            fidelity_result = self.check_fidelity(params, raw_user_payload)
            if not fidelity_result.is_consistent:
                for mismatch in fidelity_result.mismatches:
                    errors.append(ValidationErrorDetail(
                        field=mismatch.field,
                        error_type="fidelity_mismatch",
                        message=f"参数与用户原始输入不一致，字段：{mismatch.field}，类型：{mismatch.mismatch_type}",
                        suggestion="请确认参数是否被LLM篡改",
                    ))

        # Step 4: 自定义规则
        custom_errors = self._run_custom_rules(params, tool_name)
        errors.extend(custom_errors)

        # Step 5: 内容安全校验
        content_errors = self._validate_content_safety(params)
        errors.extend(content_errors)

        # 返回结果
        if errors:
            return ValidationResult(
                is_valid=False,
                errors=errors,
                fidelity_check=fidelity_result,
            )

        # 全部通过，执行清洗
        sanitized = self.sanitize(params, schema)
        return ValidationResult(
            is_valid=True,
            errors=[],
            sanitized_params=sanitized,
            fidelity_check=fidelity_result,
        )

    def sanitize(self, params: dict, schema: dict) -> dict:
        """参数清洗.

        1. 去除参数字符串值的首尾空白
        2. 规范化路径参数（解析..和.，但保留在沙盒范围内）
        3. 将数字字符串转换为对应数字类型（若schema要求）
        4. 过滤schema中未定义的额外参数（根据additionalProperties设置）
        5. 为可选参数填充默认值（若schema定义了default）
        """
        result = {}
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)

        # 处理schema中定义的属性
        for key, prop_schema in properties.items():
            if key in params:
                result[key] = self._sanitize_value(params[key], prop_schema)
            elif "default" in prop_schema:
                result[key] = prop_schema["default"]

        # 处理额外属性
        if additional is True:
            for key in params:
                if key not in properties:
                    result[key] = params[key]
        elif isinstance(additional, dict):
            for key in params:
                if key not in properties:
                    result[key] = self._sanitize_value(params[key], additional)

        return result

    def check_fidelity(self, params: dict, raw_user_payload: dict) -> FidelityCheckResult:
        """参数保真校验.

        对比用户原始输入与LLM生成的参数，检测篡改。
        允许沙盒前缀转换，禁止内容篡改。
        """
        mismatches: List[FidelityMismatch] = []
        fidelity_fields = ["path", "content", "command", "query"]

        for field in fidelity_fields:
            if field not in raw_user_payload:
                continue

            raw_value = raw_user_payload[field]
            llm_value = params.get(field)

            # 字段被LLM删除
            if field not in params:
                mismatches.append(FidelityMismatch(
                    field=field,
                    raw_value=raw_value,
                    llm_value=None,
                    mismatch_type="value_removed",
                ))
                continue

            # 类型变化
            if type(raw_value) != type(llm_value) and not (isinstance(raw_value, (int, float)) and isinstance(llm_value, (int, float))):
                mismatches.append(FidelityMismatch(
                    field=field,
                    raw_value=raw_value,
                    llm_value=llm_value,
                    mismatch_type="type_changed",
                ))
                continue

            # 路径一致性检查
            if field == "path" and isinstance(raw_value, str) and isinstance(llm_value, str):
                if not self._paths_are_equivalent(raw_value, llm_value):
                    mismatches.append(FidelityMismatch(
                        field=field,
                        raw_value=raw_value,
                        llm_value=llm_value,
                        mismatch_type="path_modified",
                    ))
                continue

            # 内容/命令/查询一致性检查
            if isinstance(raw_value, str) and isinstance(llm_value, str):
                if raw_value.strip() != llm_value.strip():
                    mismatch_type = "content_modified"
                    if field == "command":
                        mismatch_type = "content_modified"
                    elif field == "query":
                        mismatch_type = "content_modified"
                    mismatches.append(FidelityMismatch(
                        field=field,
                        raw_value=raw_value,
                        llm_value=llm_value,
                        mismatch_type=mismatch_type,
                    ))
                continue

            # 其他类型直接比较
            if raw_value != llm_value:
                mismatches.append(FidelityMismatch(
                    field=field,
                    raw_value=raw_value,
                    llm_value=llm_value,
                    mismatch_type="content_modified",
                ))

        # 检查LLM擅自添加的字段
        for field in fidelity_fields:
            if field in params and field not in raw_user_payload:
                mismatches.append(FidelityMismatch(
                    field=field,
                    raw_value=None,
                    llm_value=params[field],
                    mismatch_type="value_added",
                ))

        return FidelityCheckResult(
            is_consistent=len(mismatches) == 0,
            mismatches=mismatches,
            raw_payload=dict(raw_user_payload),
        )

    def add_custom_rule(self, tool_name: str, rule: Callable) -> None:
        """为特定工具添加自定义校验规则.

        rule签名：fn(params: dict) -> Optional[ValidationErrorDetail]
        """
        if tool_name not in self._custom_rules:
            self._custom_rules[tool_name] = []
        self._custom_rules[tool_name].append(rule)

    # ========== 路径安全方法（向后兼容） ==========

    def is_path_safe(self, path: str) -> bool:
        """检查路径是否安全（向后兼容）."""
        try:
            self._check_single_path(path)
            return True
        except PathTraversalError:
            return False

    def validate_terminal_command(self, command: str) -> bool:
        """验证终端命令是否包含危险操作（向后兼容）."""
        cmd_lower = command.lower().strip()
        for dangerous in self.DANGEROUS_COMMANDS:
            if dangerous in cmd_lower:
                return False
        return True

    def validate_sandbox_path(self, path: str):
        """沙盒路径验证（兼容现有测试）.

        要求路径必须以 documents/ 开头，禁止目录遍历和绝对路径。
        返回兼容旧格式的结果对象（含 .valid 和 List[str] 的 .errors）。
        """
        # 检查空路径
        if not path or not path.strip():
            return _CompatValidationResult(
                valid=False,
                errors=["路径不能为空"],
            )

        # 检查目录遍历
        if ".." in path:
            return _CompatValidationResult(
                valid=False,
                errors=["路径包含目录遍历字符'..'"],
            )

        # 检查绝对路径
        if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
            return _CompatValidationResult(
                valid=False,
                errors=["禁止使用绝对路径，请使用以 documents/ 开头的相对路径"],
            )

        # 检查 documents/ 前缀
        if not path.startswith("documents/"):
            return _CompatValidationResult(
                valid=False,
                errors=["路径必须以 documents/ 开头"],
            )

        return _CompatValidationResult(valid=True, errors=[])

    # ========== 内部方法 ==========

    def _sanitize_value(self, value: Any, schema: dict) -> Any:
        """清洗单个值."""
        schema_type = schema.get("type")

        if schema_type == "string" and isinstance(value, str):
            cleaned = value.strip()
            # 规范化路径
            if self._looks_like_path(cleaned):
                cleaned = self._normalize_path(cleaned)
            return cleaned

        if schema_type in ("number", "integer") and isinstance(value, str):
            try:
                if schema_type == "integer":
                    return int(value)
                return float(value)
            except ValueError:
                return value

        if schema_type == "array" and isinstance(value, list):
            items_schema = schema.get("items", {})
            return [self._sanitize_value(item, items_schema) for item in value]

        if schema_type == "object" and isinstance(value, dict):
            properties = schema.get("properties", {})
            result = {}
            for k, v in value.items():
                prop_schema = properties.get(k, {})
                result[k] = self._sanitize_value(v, prop_schema)
            return result

        return value

    def _looks_like_path(self, value: str) -> bool:
        """判断字符串是否看起来像路径."""
        return "/" in value or "\\" in value or "." in value

    def _normalize_path(self, path: str) -> str:
        """规范化路径，保留在沙盒范围内."""
        # 统一使用正斜杠
        path = path.replace("\\", "/")
        # 去除首尾空白
        path = path.strip()
        # 如果包含..，规范化但保留沙盒前缀
        if ".." in path:
            parts = path.split("/")
            stack = []
            for part in parts:
                if part == "..":
                    if stack and stack[-1] != "..":
                        stack.pop()
                    else:
                        stack.append(part)
                elif part and part != ".":
                    stack.append(part)
            path = "/".join(stack)
        return path

    def _validate_path_security(self, params: dict) -> List[ValidationErrorDetail]:
        """对参数中所有看起来像路径的字段执行安全校验."""
        errors: List[ValidationErrorDetail] = []
        path_fields = ["path", "directory", "dir", "folder", "file"]

        for field_name in path_fields:
            if field_name not in params:
                continue
            value = params[field_name]
            if not isinstance(value, str):
                continue

            try:
                self._check_single_path(value)
            except PathTraversalError as e:
                errors.append(ValidationErrorDetail(
                    field=field_name,
                    error_type="path_traversal",
                    message=str(e),
                    suggestion="请使用安全的相对路径，避免目录遍历字符",
                ))

        return errors

    def _check_single_path(self, path: str) -> None:
        """检查单条路径的安全性，失败时抛出PathTraversalError."""
        if not isinstance(path, str):
            raise PathTraversalError("路径必须是字符串类型")

        if not path:
            raise PathTraversalError("路径不能为空")

        # V-PATH-03: 禁止空字节
        if "\x00" in path:
            raise PathTraversalError("路径包含空字节字符")

        # V-PATH-06: 最长路径长度限制
        if len(path) > 4096:
            raise PathTraversalError("路径长度超过最大限制4096字符")

        # V-PATH-01: 禁止..序列
        normalized = path.replace("\\", "/")
        # 检查路径遍历：规范化后若超出原范围则危险
        # 使用更严格的检查：任何包含..的路径都视为潜在风险
        # 但允许规范化后的沙盒内路径
        try:
            parsed = Path(normalized)
            # 如果路径中有..，检查规范化后是否越界
            if ".." in normalized:
                # 提取所有路径段
                parts = normalized.split("/")
                depth = 0
                for part in parts:
                    if part == "..":
                        depth -= 1
                    elif part and part != ".":
                        depth += 1
                    if depth < 0:
                        raise PathTraversalError("路径包含目录遍历字符'..'")
        except Exception as e:
            if isinstance(e, PathTraversalError):
                raise
            raise PathTraversalError(f"路径解析失败：{e}")

        # V-PATH-02: 禁止绝对路径（除非在白名单或在沙盒根目录内）
        if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
            sandbox_normalized = self.SANDBOX_ROOT.replace("\\", "/").rstrip("/")
            is_in_sandbox = path.startswith(sandbox_normalized + "/") or path == sandbox_normalized
            if not is_in_sandbox and path not in self.ALLOWED_ABSOLUTE_PATHS:
                raise PathTraversalError("禁止使用绝对路径")

        # V-PATH-04: 禁止指向系统敏感目录
        path_lower = normalized.lower()
        for sensitive in self.SENSITIVE_DIRECTORIES:
            sensitive_lower = sensitive.replace("\\", "/").lower()
            if path_lower.startswith(sensitive_lower):
                raise PathTraversalError(f"路径指向系统敏感目录：{sensitive}")

        # V-PATH-05: 路径必须位于沙盒根目录内（若设置了SANDBOX_ROOT）
        if self.SANDBOX_ROOT:
            sandbox_normalized = self.SANDBOX_ROOT.replace("\\", "/").rstrip("/")
            # 如果路径已经是绝对路径且在沙盒内，允许
            if path.startswith("/") and not path.startswith(sandbox_normalized + "/"):
                # 不在沙盒内，但前面已经检查了绝对路径
                # 这里主要是检查相对路径是否越界
                pass

    def _paths_are_equivalent(self, raw_path: str, llm_path: str) -> bool:
        """判断两个路径是否在保真校验中等价.

        允许沙盒前缀转换（如 test.txt ↔ /sandbox/test.txt）。
        路径规范化后对比。
        """
        raw = self._normalize_path(raw_path)
        llm = self._normalize_path(llm_path)

        # 完全相同
        if raw == llm:
            return True

        # 允许沙盒前缀转换
        sandbox_root = self.SANDBOX_ROOT.replace("\\", "/").rstrip("/")

        # raw不含沙盒前缀，llm含沙盒前缀
        if not raw.startswith(sandbox_root + "/") and llm.startswith(sandbox_root + "/"):
            llm_without_prefix = llm[len(sandbox_root) + 1:]
            if raw == llm_without_prefix or raw.lstrip("/") == llm_without_prefix.lstrip("/"):
                return True

        # raw含沙盒前缀，llm不含
        if raw.startswith(sandbox_root + "/") and not llm.startswith(sandbox_root + "/"):
            raw_without_prefix = raw[len(sandbox_root) + 1:]
            if llm == raw_without_prefix or llm.lstrip("/") == raw_without_prefix.lstrip("/"):
                return True

        # 去除前导/后比较
        if raw.lstrip("/") == llm.lstrip("/"):
            return True

        return False

    def _run_custom_rules(
        self, params: dict, tool_name: Optional[str]
    ) -> List[ValidationErrorDetail]:
        """执行自定义校验规则."""
        errors: List[ValidationErrorDetail] = []
        if not tool_name or tool_name not in self._custom_rules:
            return errors

        for rule in self._custom_rules[tool_name]:
            try:
                result = rule(params)
                if result is not None:
                    errors.append(result)
            except Exception as e:
                errors.append(ValidationErrorDetail(
                    field="<custom>",
                    error_type="custom_rule",
                    message=f"自定义规则执行失败：{e}",
                    suggestion="请检查自定义校验规则实现",
                ))

        return errors

    def _validate_content_safety(self, params: dict) -> List[ValidationErrorDetail]:
        """内容安全校验."""
        errors: List[ValidationErrorDetail] = []

        for key, value in params.items():
            if not isinstance(value, str):
                continue

            # V-CONTENT-01: 字符串参数最大长度
            if len(value) > self.MAX_STRING_LENGTH:
                errors.append(ValidationErrorDetail(
                    field=key,
                    error_type="format_error",
                    message=f"字符串参数长度不能超过{self.MAX_STRING_LENGTH}字符",
                    suggestion="请缩短参数内容",
                ))

            # V-CONTENT-02: 禁止包含不可见控制字符（除\n\t\r外）
            for i, ch in enumerate(value):
                code = ord(ch)
                if code < 32 and ch not in "\n\t\r":
                    errors.append(ValidationErrorDetail(
                        field=key,
                        error_type="format_error",
                        message=f"字符串包含不可见控制字符（位置{i}，ASCII {code}）",
                        suggestion="请移除字符串中的特殊控制字符",
                    ))
                    break  # 只报第一个

            # V-CONTENT-03: code/command类参数经过BashAnalyzer扫描
            if key in ("code", "command") and isinstance(value, str):
                # 这里只做基本的危险命令检查，详细分析留给调用方
                if not self.validate_terminal_command(value):
                    errors.append(ValidationErrorDetail(
                        field=key,
                        error_type="custom_rule",
                        message="命令包含已知的危险操作",
                        suggestion="请检查命令的安全性",
                    ))

        return errors
