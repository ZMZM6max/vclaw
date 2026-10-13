"""Tests for ParameterValidator component.

覆盖ParameterValidator.xml规范中的全部测试用例PV-001~PV-007，
以及路径安全、内容安全、参数清洗等边界测试。
"""

import sys

sys.path.insert(0, "src")

import pytest

from src.l5.parameter_validator import (
    FidelityCheckResult,
    FidelityMismatch,
    InvalidSchemaError,
    ParameterValidator,
    PathTraversalError,
    ValidationErrorDetail,
    ValidationResult,
)


class TestSchemaValidation:
    """JSON Schema验证测试 (PV-001, PV-002)."""

    def test_basic_schema_validation_passes(self):
        """PV-001: 基本Schema验证-通过"""
        validator = ParameterValidator()
        params = {"code": "print('hello')"}
        schema = {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        }

        result = validator.validate(params, schema)

        assert result.is_valid is True
        assert result.sanitized_params is not None
        assert "code" in result.sanitized_params

    def test_missing_required_field_fails(self):
        """PV-002: 基本Schema验证-缺少必填字段"""
        validator = ParameterValidator()
        params = {}
        schema = {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False
        assert any(e.error_type == "missing_required" for e in result.errors)
        assert any("code" in e.message for e in result.errors)

    def test_type_mismatch_fails(self):
        """参数类型不匹配应失败"""
        validator = ParameterValidator()
        params = {"code": 123}
        schema = {
            "type": "object",
            "properties": {"code": {"type": "string"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False
        assert any(e.error_type == "type_error" for e in result.errors)

    def test_integer_type_validation(self):
        """整数类型验证"""
        validator = ParameterValidator()
        params = {"count": "not_a_number"}
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False
        assert any(e.error_type == "type_error" for e in result.errors)

    def test_number_type_validation(self):
        """数字类型验证（整数和浮点数都允许）"""
        validator = ParameterValidator()
        schema = {
            "type": "object",
            "properties": {"value": {"type": "number"}},
        }

        result_int = validator.validate({"value": 42}, schema)
        assert result_int.is_valid is True

        result_float = validator.validate({"value": 3.14}, schema)
        assert result_float.is_valid is True

    def test_enum_validation(self):
        """枚举值验证"""
        validator = ParameterValidator()
        params = {"mode": "invalid"}
        schema = {
            "type": "object",
            "properties": {"mode": {"type": "string", "enum": ["read", "write"]}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False
        assert any(e.error_type == "format_error" for e in result.errors)
        assert any("以下之一" in e.message for e in result.errors)

    def test_pattern_validation(self):
        """正则格式验证"""
        validator = ParameterValidator()
        params = {"email": "not-an-email"}
        schema = {
            "type": "object",
            "properties": {"email": {"type": "string", "pattern": r"^\S+@\S+\.\S+$"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False
        assert any(e.error_type == "format_error" for e in result.errors)

    def test_min_max_length_validation(self):
        """字符串长度限制验证"""
        validator = ParameterValidator()
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string", "minLength": 2, "maxLength": 10}},
        }

        result_short = validator.validate({"name": "a"}, schema)
        assert result_short.is_valid is False
        assert any(e.error_type == "format_error" for e in result_short.errors)

        result_long = validator.validate({"name": "a" * 20}, schema)
        assert result_long.is_valid is False
        assert any(e.error_type == "format_error" for e in result_long.errors)

    def test_min_max_validation(self):
        """数值范围验证"""
        validator = ParameterValidator()
        schema = {
            "type": "object",
            "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}},
        }

        result_low = validator.validate({"score": -1}, schema)
        assert result_low.is_valid is False
        assert any(e.error_type == "range_error" for e in result_low.errors)

        result_high = validator.validate({"score": 101}, schema)
        assert result_high.is_valid is False
        assert any(e.error_type == "range_error" for e in result_high.errors)

    def test_array_validation(self):
        """数组类型验证"""
        validator = ParameterValidator()
        schema = {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {"type": "string"},
                }
            },
        }

        result_empty = validator.validate({"tags": []}, schema)
        assert result_empty.is_valid is False
        assert any(e.error_type == "format_error" for e in result_empty.errors)

        result_too_many = validator.validate({"tags": ["a", "b", "c", "d"]}, schema)
        assert result_too_many.is_valid is False

        result_wrong_type = validator.validate({"tags": [1, 2]}, schema)
        assert result_wrong_type.is_valid is False
        assert any(e.error_type == "type_error" for e in result_wrong_type.errors)

    def test_additional_properties_validation(self):
        """额外属性控制验证"""
        validator = ParameterValidator()
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        }

        result = validator.validate({"name": "test", "extra": "value"}, schema)

        assert result.is_valid is False
        assert any("extra" in e.message for e in result.errors)

    def test_invalid_schema_raises_error(self):
        """非法Schema应抛出InvalidSchemaError"""
        validator = ParameterValidator()
        params = {"code": "test"}
        schema = {
            "type": "object",
            "properties": {"code": {"type": "string", "pattern": "[invalid"}},
        }

        with pytest.raises(InvalidSchemaError):
            validator.validate(params, schema)

    def test_boolean_type_validation(self):
        """布尔类型验证（注意：True/False不应被当作整数）"""
        validator = ParameterValidator()
        schema = {
            "type": "object",
            "properties": {"active": {"type": "boolean"}},
        }

        result_bool = validator.validate({"active": True}, schema)
        assert result_bool.is_valid is True

        result_int = validator.validate({"active": 1}, schema)
        assert result_int.is_valid is False
        assert any(e.error_type == "type_error" for e in result_int.errors)


class TestPathSecurity:
    """路径安全校验测试 (PV-003)."""

    def test_directory_traversal_fails(self):
        """PV-003: 路径安全校验-目录遍历"""
        validator = ParameterValidator()
        params = {"path": "../../../etc/passwd"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False
        assert any(e.error_type == "path_traversal" for e in result.errors)

    def test_backslash_traversal_fails(self):
        """反斜杠目录遍历"""
        validator = ParameterValidator()
        params = {"path": "..\\windows\\system32"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False
        assert any(e.error_type == "path_traversal" for e in result.errors)

    def test_absolute_path_fails(self):
        """绝对路径被拒绝"""
        validator = ParameterValidator()
        params = {"path": "/etc/passwd"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False
        assert any(e.error_type == "path_traversal" for e in result.errors)

    def test_windows_absolute_path_fails(self):
        """Windows绝对路径被拒绝"""
        validator = ParameterValidator()
        params = {"path": "C:\\Windows\\system32"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False
        assert any(e.error_type == "path_traversal" for e in result.errors)

    def test_sensitive_directory_fails(self):
        """系统敏感目录被拒绝"""
        validator = ParameterValidator()
        params = {"path": "/etc/passwd"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False

    def test_null_byte_in_path_fails(self):
        """路径中包含空字节被拒绝"""
        validator = ParameterValidator()
        params = {"path": "file\x00.txt"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False
        assert any(e.error_type == "path_traversal" for e in result.errors)

    def test_empty_path_fails(self):
        """空路径被拒绝"""
        validator = ParameterValidator()
        params = {"path": ""}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False
        assert any(e.error_type == "path_traversal" for e in result.errors)

    def test_long_path_fails(self):
        """超长路径被拒绝"""
        validator = ParameterValidator()
        params = {"path": "a" * 4097}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False

    def test_safe_relative_path_passes(self):
        """安全的相对路径通过验证"""
        validator = ParameterValidator()
        params = {"path": "documents/file.txt"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is True


class TestFidelityCheck:
    """参数保真校验测试 (PV-004, PV-005)."""

    def test_path_modification_detected(self):
        """PV-004: 保真校验-路径篡改"""
        validator = ParameterValidator()
        params = {"path": "/sandbox/other.txt"}
        raw_user_payload = {"path": "/sandbox/original.txt"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.validate(params, schema, raw_user_payload=raw_user_payload)

        assert result.is_valid is False
        assert result.fidelity_check is not None
        assert result.fidelity_check.is_consistent is False
        assert any(m.mismatch_type == "path_modified" for m in result.fidelity_check.mismatches)

    def test_sandbox_prefix_allowed(self):
        """PV-005: 保真校验-允许沙盒前缀转换"""
        validator = ParameterValidator()
        params = {"path": "/sandbox/test.txt"}
        raw_user_payload = {"path": "test.txt"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.validate(params, schema, raw_user_payload=raw_user_payload)

        assert result.is_valid is True
        if result.fidelity_check:
            assert result.fidelity_check.is_consistent is True

    def test_content_modification_detected(self):
        """内容篡改检测"""
        validator = ParameterValidator()
        params = {"content": "modified content"}
        raw_user_payload = {"content": "original content"}
        schema = {
            "type": "object",
            "properties": {"content": {"type": "string"}},
        }

        result = validator.validate(params, schema, raw_user_payload=raw_user_payload)

        assert result.is_valid is False
        assert any(
            m.mismatch_type == "content_modified"
            for m in result.fidelity_check.mismatches
        )

    def test_command_modification_detected(self):
        """命令篡改检测"""
        validator = ParameterValidator()
        params = {"command": "ls -la /tmp"}
        raw_user_payload = {"command": "ls -la"}
        schema = {
            "type": "object",
            "properties": {"command": {"type": "string"}},
        }

        result = validator.validate(params, schema, raw_user_payload=raw_user_payload)

        assert result.is_valid is False

    def test_value_added_detected(self):
        """LLM擅自添加字段检测"""
        validator = ParameterValidator()
        params = {"path": "/sandbox/test.txt", "content": "hello"}
        raw_user_payload = {"path": "/sandbox/test.txt"}
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
        }

        result = validator.validate(params, schema, raw_user_payload=raw_user_payload)

        assert result.is_valid is False
        assert any(
            m.mismatch_type == "value_added"
            for m in result.fidelity_check.mismatches
        )

    def test_value_removed_detected(self):
        """LLM删除字段检测"""
        validator = ParameterValidator()
        params = {}
        raw_user_payload = {"path": "/sandbox/test.txt"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.validate(params, schema, raw_user_payload=raw_user_payload)

        assert result.is_valid is False
        assert any(
            m.mismatch_type == "value_removed"
            for m in result.fidelity_check.mismatches
        )

    def test_no_fidelity_check_when_no_raw_payload(self):
        """不提供raw_user_payload时不执行保真校验"""
        validator = ParameterValidator()
        params = {"path": "/sandbox/test.txt"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is True
        assert result.fidelity_check is None


class TestSanitize:
    """参数清洗测试 (PV-006)."""

    def test_trim_whitespace(self):
        """PV-006: 去除首尾空白"""
        validator = ParameterValidator()
        params = {"path": "  /tmp/test.txt  ", "content": "  hello  "}
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
        }

        result = validator.sanitize(params, schema)

        assert result["path"] == "/tmp/test.txt"
        assert result["content"] == "hello"

    def test_string_to_number_conversion(self):
        """数字字符串转换为数字类型"""
        validator = ParameterValidator()
        params = {"count": "42", "price": "3.14"}
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "price": {"type": "number"},
            },
        }

        result = validator.sanitize(params, schema)

        assert result["count"] == 42
        assert isinstance(result["count"], int)
        assert result["price"] == 3.14
        assert isinstance(result["price"], float)

    def test_default_value_filled(self):
        """为可选参数填充默认值"""
        validator = ParameterValidator()
        params = {"name": "test"}
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer", "default": 10},
            },
        }

        result = validator.sanitize(params, schema)

        assert result["count"] == 10

    def test_extra_properties_filtered(self):
        """过滤未定义的额外参数"""
        validator = ParameterValidator()
        params = {"name": "test", "extra": "value"}
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        }

        result = validator.sanitize(params, schema)

        assert "extra" not in result

    def test_path_normalization(self):
        """路径规范化"""
        validator = ParameterValidator()
        params = {"path": "a/b/../c"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.sanitize(params, schema)

        assert result["path"] == "a/c"

    def test_backslash_to_slash_conversion(self):
        """反斜杠转换为正斜杠"""
        validator = ParameterValidator()
        params = {"path": "a\\b\\c"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.sanitize(params, schema)

        assert result["path"] == "a/b/c"


class TestCustomRules:
    """自定义规则测试 (PV-007)."""

    def test_custom_rule_registration_and_execution(self):
        """PV-007: 自定义规则注册与执行"""
        validator = ParameterValidator()

        def no_secret_files(params):
            path = params.get("path", "")
            if path.endswith(".secret"):
                return ValidationErrorDetail(
                    field="path",
                    error_type="custom_rule",
                    message="禁止访问.secret文件",
                    suggestion="请提供其他文件路径",
                )
            return None

        validator.add_custom_rule("file_read", no_secret_files)

        params = {"path": "/tmp/test.secret"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.validate(params, schema, tool_name="file_read")

        assert result.is_valid is False
        assert any(e.error_type == "custom_rule" for e in result.errors)

    def test_custom_rule_not_applied_to_other_tools(self):
        """自定义规则不影响其他工具"""
        validator = ParameterValidator()

        def no_secret_files(params):
            path = params.get("path", "")
            if path.endswith(".secret"):
                return ValidationErrorDetail(
                    field="path",
                    error_type="custom_rule",
                    message="禁止访问.secret文件",
                )
            return None

        validator.add_custom_rule("file_read", no_secret_files)

        params = {"path": "tmp/test.secret"}
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }

        result = validator.validate(params, schema, tool_name="other_tool")

        assert result.is_valid is True

    def test_multiple_custom_rules(self):
        """多个自定义规则同时生效"""
        validator = ParameterValidator()

        def rule1(params):
            return ValidationErrorDetail(
                field="field1", error_type="custom_rule", message="规则1错误"
            )

        def rule2(params):
            return ValidationErrorDetail(
                field="field2", error_type="custom_rule", message="规则2错误"
            )

        validator.add_custom_rule("test_tool", rule1)
        validator.add_custom_rule("test_tool", rule2)

        result = validator.validate({}, {}, tool_name="test_tool")

        assert result.is_valid is False
        assert len(result.errors) == 2


class TestContentSafety:
    """内容安全校验测试."""

    def test_max_string_length(self):
        """字符串最大长度限制"""
        validator = ParameterValidator()
        params = {"content": "x" * 10001}
        schema = {
            "type": "object",
            "properties": {"content": {"type": "string"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False
        assert any(e.error_type == "format_error" and "长度" in e.message for e in result.errors)

    def test_control_characters_rejected(self):
        """不可见控制字符被拒绝"""
        validator = ParameterValidator()
        params = {"content": "hello\x01world"}
        schema = {
            "type": "object",
            "properties": {"content": {"type": "string"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False
        assert any("控制字符" in e.message for e in result.errors)

    def test_allowed_control_characters_pass(self):
        """允许的换行符、制表符、回车符通过"""
        validator = ParameterValidator()
        params = {"content": "line1\nline2\ttabbed\rcarriage"}
        schema = {
            "type": "object",
            "properties": {"content": {"type": "string"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is True

    def test_dangerous_command_detected(self):
        """危险命令检测"""
        validator = ParameterValidator()
        params = {"command": "rm -rf /"}
        schema = {
            "type": "object",
            "properties": {"command": {"type": "string"}},
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False


class TestBackwardCompatibility:
    """向后兼容性测试."""

    def test_is_path_safe_dangerous(self):
        """is_path_safe对危险路径返回False"""
        validator = ParameterValidator()
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\windows\\system32",
            "/etc/shadow",
        ]

        for path in dangerous_paths:
            assert validator.is_path_safe(path) is False, f"Path {path} should be unsafe"

    def test_is_path_safe_safe(self):
        """is_path_safe对安全路径返回True"""
        validator = ParameterValidator()
        safe_paths = [
            "data/file.txt",
            "script.py",
            "subdir/document.md",
        ]

        for path in safe_paths:
            assert validator.is_path_safe(path) is True, f"Path {path} should be safe"

    def test_validate_terminal_command_dangerous(self):
        """validate_terminal_command对危险命令返回False"""
        validator = ParameterValidator()
        dangerous = [
            "rm -rf /",
            "sudo rm -rf",
            "eval('malicious')",
        ]

        for cmd in dangerous:
            assert validator.validate_terminal_command(cmd) is False

    def test_validate_terminal_command_safe(self):
        """validate_terminal_command对安全命令返回True"""
        validator = ParameterValidator()
        safe = [
            "ls -la",
            "pwd",
            "python script.py",
        ]

        for cmd in safe:
            assert validator.validate_terminal_command(cmd) is True

    def test_validate_sandbox_path_valid(self):
        """沙盒路径验证-有效路径"""
        validator = ParameterValidator()
        valid_paths = [
            "documents/file.txt",
            "documents/desktop/report.pdf",
            "documents/subdir/nested/file.py",
        ]

        for path in valid_paths:
            result = validator.validate_sandbox_path(path)
            assert result.is_valid is True, f"Path {path} should be valid"

    def test_validate_sandbox_path_missing_prefix(self):
        """沙盒路径验证-缺少documents前缀"""
        validator = ParameterValidator()
        result = validator.validate_sandbox_path("file.txt")

        assert result.is_valid is False
        assert "documents/" in result.errors[0]

    def test_validate_sandbox_path_traversal(self):
        """沙盒路径验证-目录遍历"""
        validator = ParameterValidator()
        dangerous_paths = [
            "documents/../etc/passwd",
            "documents/subdir/../../../etc/shadow",
        ]

        for path in dangerous_paths:
            result = validator.validate_sandbox_path(path)
            assert result.is_valid is False, f"Path {path} should be rejected"

    def test_validate_sandbox_path_absolute(self):
        """沙盒路径验证-绝对路径"""
        validator = ParameterValidator()
        absolute_paths = [
            "/etc/passwd",
            "C:\\Windows\\system32",
        ]

        for path in absolute_paths:
            result = validator.validate_sandbox_path(path)
            assert result.is_valid is False, f"Path {path} should be rejected"


class TestValidationResult:
    """ValidationResult数据结构测试."""

    def test_bool_conversion_true(self):
        """验证通过时布尔值为True"""
        result = ValidationResult(is_valid=True, errors=[])
        assert bool(result) is True

    def test_bool_conversion_false(self):
        """验证失败时布尔值为False"""
        result = ValidationResult(
            is_valid=False,
            errors=[ValidationErrorDetail(field="x", error_type="type_error", message="error")],
        )
        assert bool(result) is False


class TestFidelityCheckDirect:
    """直接调用check_fidelity的测试."""

    def test_identical_values_consistent(self):
        """完全相同的值视为一致"""
        validator = ParameterValidator()
        result = validator.check_fidelity(
            {"path": "/sandbox/test.txt"},
            {"path": "/sandbox/test.txt"},
        )
        assert result.is_consistent is True
        assert len(result.mismatches) == 0

    def test_sandbox_prefix_equivalence(self):
        """沙盒前缀转换视为等价"""
        validator = ParameterValidator()
        result = validator.check_fidelity(
            {"path": "/sandbox/test.txt"},
            {"path": "test.txt"},
        )
        assert result.is_consistent is True

    def test_reverse_sandbox_prefix_equivalence(self):
        """反向沙盒前缀转换也视为等价"""
        validator = ParameterValidator()
        result = validator.check_fidelity(
            {"path": "test.txt"},
            {"path": "/sandbox/test.txt"},
        )
        assert result.is_consistent is True

    def test_query_consistency(self):
        """查询词一致性检查"""
        validator = ParameterValidator()
        result = validator.check_fidelity(
            {"query": "python tutorial"},
            {"query": "python tutorial"},
        )
        assert result.is_consistent is True

    def test_query_modification_detected(self):
        """查询词篡改检测"""
        validator = ParameterValidator()
        result = validator.check_fidelity(
            {"query": "modified query"},
            {"query": "original query"},
        )
        assert result.is_consistent is False
        assert any(m.field == "query" for m in result.mismatches)

    def test_fields_not_in_raw_payload_skipped(self):
        """raw_user_payload中不存在的字段跳过校验"""
        validator = ParameterValidator()
        result = validator.check_fidelity(
            {"path": "/sandbox/test.txt", "content": "hello"},
            {"path": "/sandbox/test.txt"},
        )
        # content不在raw_user_payload中，但被LLM添加了，应检测到value_added
        assert any(m.mismatch_type == "value_added" for m in result.mismatches)


class TestErrorMessages:
    """错误信息中文本地化测试."""

    def test_error_messages_are_chinese(self):
        """错误信息应为中文"""
        validator = ParameterValidator()
        params = {}
        schema = {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        }

        result = validator.validate(params, schema)

        assert result.is_valid is False
        error = result.errors[0]
        # 应包含中文字符
        assert any("一" <= ch <= "鿿" for ch in error.message)
        # 应有修复建议
        assert error.suggestion is not None
        assert any("一" <= ch <= "鿿" for ch in error.suggestion)
