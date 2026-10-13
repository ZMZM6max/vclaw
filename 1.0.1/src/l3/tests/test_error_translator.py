"""ErrorTranslator Tests (TC-ET-001 ~ 005)

Tests for ErrorTranslator: fixed mappings and LLM fallback.
Uses Mock for LLM fallback tests.
"""
import pytest
import sys
sys.path.insert(0, 'src')

from unittest.mock import MagicMock
from src.l3.l3_orchestration import ErrorTranslator
from src.core.models import Observation


class TestErrorTranslator:
    """ErrorTranslator单元测试"""

    @pytest.fixture
    def translator(self):
        """Create ErrorTranslator without LLM."""
        return ErrorTranslator(llm_manager=None)

    @pytest.fixture
    def translator_with_llm(self):
        """Create ErrorTranslator with mock LLM."""
        llm = MagicMock()
        llm.complete.return_value = "网络好像出了点小问题，请稍后再试哦。"
        return ErrorTranslator(llm_manager=llm)

    def test_translate_file_not_found(self, translator):
        """TC-ET-001: FileNotFoundError匹配固定映射"""
        obs = Observation(
            status="error",
            result="FileNotFoundError: /path/to/file.txt",
            execution_time=0.1,
            metadata={}
        )
        result = translator.translate(obs)

        assert "找不到该文件" in result

    def test_translate_file_exists(self, translator):
        """TC-ET-002: FileExistsError匹配固定映射"""
        obs = Observation(
            status="error",
            result="FileExistsError: target.txt already exists",
            execution_time=0.1,
            metadata={}
        )
        result = translator.translate(obs)

        assert "已有同名文件" in result

    def test_translate_unknown_with_llm(self, translator_with_llm):
        """TC-ET-003: 未知错误调用LLM转译"""
        obs = Observation(
            status="error",
            result="Some weird unknown error happened",
            execution_time=0.1,
            metadata={}
        )
        result = translator_with_llm.translate(obs)

        assert result == "网络好像出了点小问题，请稍后再试哦。"
        translator_with_llm.llm_manager.complete.assert_called_once()

    def test_translate_success_observation(self, translator):
        """TC-ET-004: status=success时原样返回"""
        obs = Observation(
            status="success",
            result="Operation completed",
            execution_time=0.1,
            metadata={}
        )
        result = translator.translate(obs)

        assert result == "Operation completed"

    def test_translate_chinese_output(self, translator):
        """TC-ET-005: 固定映射结果为中文"""
        obs = Observation(
            status="error",
            result="PermissionError: access denied",
            execution_time=0.1,
            metadata={}
        )
        result = translator.translate(obs)

        assert "抱歉" in result or "权限" in result
        # Verify it's Chinese
        assert any('一' <= ch <= '鿿' for ch in result)
