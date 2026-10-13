"""Tests for L5 ResultFormatter."""
import sys
sys.path.insert(0, 'src')

import pytest

from src.l5.result_formatter import ResultFormatter
from src.core.models import Observation


class TestResultFormatter:
    """ResultFormatter 单元测试，覆盖 XML 规格中 7 个测试用例."""

    def setup_method(self):
        self.formatter = ResultFormatter()

    # ------------------------------------------------------------------
    # RF-001: 文件读取成功格式化
    # ------------------------------------------------------------------
    def test_file_read_success(self):
        raw = "Hello World"
        obs = self.formatter.format(
            raw_result=raw,
            tool_name="file_read",
            execution_time=0.1,
            metadata={"filename": "test.txt"},
        )
        assert isinstance(obs, Observation)
        assert obs.status == "success"
        assert "文件《test.txt》内容如下：" in obs.result
        assert "Hello World" in obs.result

    # ------------------------------------------------------------------
    # RF-002: 空文件读取
    # ------------------------------------------------------------------
    def test_empty_file_read(self):
        obs = self.formatter.format(
            raw_result="",
            tool_name="file_read",
            execution_time=0.05,
        )
        assert obs.status == "success"
        assert obs.result == "该文档为空"
        assert obs.metadata.get("empty") is True

    def test_empty_file_read_none(self):
        obs = self.formatter.format(
            raw_result=None,
            tool_name="file_read",
            execution_time=0.05,
        )
        assert obs.result == "该文档为空"
        assert obs.metadata.get("empty") is True

    # ------------------------------------------------------------------
    # RF-003: 结果截断
    # ------------------------------------------------------------------
    def test_truncation(self):
        long_text = "x" * 20000
        obs = self.formatter.format(
            raw_result=long_text,
            tool_name="file_read",
            execution_time=0.5,
        )
        assert len(obs.result) <= 10000
        assert "...[内容已截断，共" in obs.result
        assert obs.metadata.get("truncated") is True
        assert obs.metadata.get("original_length") > 20000

    def test_truncate_method_directly(self):
        text = "a" * 15000
        truncated = self.formatter.truncate(text, max_length=10000)
        assert len(truncated) <= 10000
        assert "...[内容已截断" in truncated

    # ------------------------------------------------------------------
    # RF-004: 列表结果格式化
    # ------------------------------------------------------------------
    def test_list_result(self):
        raw = ["file1.txt", "file2.txt", "file3.txt"]
        obs = self.formatter.format(
            raw_result=raw,
            tool_name="file_search",
            execution_time=0.2,
        )
        assert "找到以下3项：" in obs.result
        assert "1. file1.txt" in obs.result
        assert "2. file2.txt" in obs.result
        assert "3. file3.txt" in obs.result
        assert "请确认是否需要打开？" in obs.result

    def test_list_result_empty(self):
        obs = self.formatter.format(
            raw_result=[],
            tool_name="file_search",
            execution_time=0.1,
        )
        assert obs.result == "找到0个结果，需要查看具体内容吗？"
        assert obs.metadata.get("empty") is True

    def test_list_result_over_10_items(self):
        raw = [f"item{i}.txt" for i in range(15)]
        obs = self.formatter.format(
            raw_result=raw,
            tool_name="file_search",
            execution_time=0.2,
        )
        assert "找到以下15项：" in obs.result
        assert "还有更多" in obs.result
        assert "请确认是否需要打开？" in obs.result
        # 只显示前 10 条
        lines = [l for l in obs.result.splitlines() if l.startswith("10.")]
        assert len(lines) == 1
        assert "11." not in obs.result

    # ------------------------------------------------------------------
    # RF-005: Mock 标识过滤
    # ------------------------------------------------------------------
    def test_mock_filter(self):
        obs = self.formatter.format(
            raw_result="这是mock data内容",
            tool_name="file_read",
            execution_time=0.1,
        )
        assert "mock" not in obs.result.lower()
        assert obs.result == "该文档为空"

    def test_mock_filter_placeholder(self):
        obs = self.formatter.format(
            raw_result="placeholder content here",
            tool_name="file_read",
            execution_time=0.1,
        )
        assert "placeholder" not in obs.result.lower()
        assert obs.result == "该文档为空"

    # ------------------------------------------------------------------
    # RF-006: 错误结果格式化
    # ------------------------------------------------------------------
    def test_error_formatting(self):
        obs = self.formatter.format_error(
            error_message="FileNotFoundError: No such file",
            tool_name="file_read",
            execution_time=0.1,
            error_type="FileNotFoundError",
        )
        assert obs.status == "error"
        assert "找不到指定文件" in obs.result
        assert obs.metadata.get("original_error") == "FileNotFoundError: No such file"
        assert obs.metadata.get("error_type") == "FileNotFoundError"

    def test_error_formatting_permission(self):
        obs = self.formatter.format_error(
            error_message="Permission denied",
            tool_name="file_read",
            execution_time=0.1,
        )
        assert obs.status == "error"
        assert "权限不足" in obs.result

    # ------------------------------------------------------------------
    # RF-007: 文件写入成功模板
    # ------------------------------------------------------------------
    def test_file_write_success(self):
        obs = self.formatter.format(
            raw_result=None,
            tool_name="file_write",
            execution_time=0.2,
            metadata={"bytes_written": 1024, "filename": "output.txt"},
        )
        assert obs.status == "success"
        assert obs.result == "已成功写入《output.txt》，共1024字"

    # ------------------------------------------------------------------
    # 额外边界测试
    # ------------------------------------------------------------------
    def test_whitespace_only_treated_as_empty(self):
        obs = self.formatter.format(
            raw_result="   \n\t  ",
            tool_name="file_read",
            execution_time=0.05,
        )
        assert obs.result == "该文档为空"
        assert obs.metadata.get("empty") is True

    def test_mock_patterns_filtered(self):
        """MockFilter Patterns 中定义的标识必须被过滤."""
        for phrase in ["模拟读取", "mock data", "placeholder", "dummy data", "test data", "示例数据"]:
            obs = self.formatter.format(
                raw_result=f"前缀 {phrase} 后缀",
                tool_name="file_read",
                execution_time=0.05,
            )
            assert phrase.lower() not in obs.result.lower(), f"phrase '{phrase}' should be filtered"

    def test_format_success_shortcut(self):
        obs = self.formatter.format_success(
            result="quick result",
            tool_name="calculator",
            execution_time=0.01,
        )
        assert obs.status == "success"
        assert obs.result == "quick result"

    def test_detect_scenario_for_calculator_empty(self):
        scenario = self.formatter._detect_scenario("", "calculator", {})
        assert scenario == "empty_calculator"

    def test_detect_scenario_for_list(self):
        scenario = self.formatter._detect_scenario([1, 2], "file_search", {})
        assert scenario == "list_result"

    def test_detect_scenario_for_error_exit_code(self):
        scenario = self.formatter._detect_scenario("some error", "terminal", {"exit_code": 1})
        assert scenario == "error"

    def test_search_web_empty(self):
        obs = self.formatter.format(
            raw_result="",
            tool_name="search_web",
            execution_time=0.3,
        )
        assert obs.result == "未找到相关内容"

    def test_calculator_empty(self):
        obs = self.formatter.format(
            raw_result=None,
            tool_name="calculator",
            execution_time=0.01,
        )
        assert obs.result == "计算结果为空"
