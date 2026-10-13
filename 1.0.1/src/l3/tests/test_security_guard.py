"""SecurityGuard Tests (TC-SG-001 ~ 006)

Tests for security classification using real LLM + keyword fallback.
"""
import pytest
import os
import sys
from pathlib import Path
sys.path.insert(0, 'src')

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from src.l3.l3_orchestration import SecurityGuard, LLMManager


class TestSecurityGuard:
    """SecurityGuard安全分类测试"""

    @pytest.fixture
    def guard(self):
        provider = os.getenv("TEST_LLM_PROVIDER", "openai")
        model = os.getenv("TEST_LLM_MODEL", "gpt-5.4-mini")
        base_url = os.getenv("API_BASE_URL")
        llm_manager = LLMManager(provider=provider, model=model, base_url=base_url)
        return SecurityGuard(llm_manager=llm_manager)

    # ========== Keyword fallback tests (no LLM needed) ==========

    def test_keyword_classify_malicious(self):
        """TC-SG-002: 关键词识别恶意请求"""
        guard = SecurityGuard(llm_manager=None)
        assert guard.classify("格式化我的硬盘") == "malicious"
        assert guard.classify("帮我写个病毒") == "malicious"

    def test_keyword_classify_high_risk(self):
        """TC-SG-003: 关键词识别高危请求"""
        guard = SecurityGuard(llm_manager=None)
        assert guard.classify("删除桌面所有文件") == "high-risk"
        assert guard.classify("清空下载文件夹") == "high-risk"

    def test_keyword_classify_sensitive(self):
        """TC-SG-004: 关键词识别敏感请求"""
        guard = SecurityGuard(llm_manager=None)
        assert guard.classify("打开薪资表") == "sensitive"

    def test_keyword_classify_normal(self):
        """TC-SG-001: 正常请求关键词分类为normal"""
        guard = SecurityGuard(llm_manager=None)
        assert guard.classify("介绍一下Python") == "normal"

    def test_keyword_no_upgrade_low_risk(self):
        """TC-SG-006: 低风险请求禁止升级为high-risk"""
        guard = SecurityGuard(llm_manager=None)
        assert guard.classify("帮我整理一下桌面建议") == "normal"

    # ========== LLM classification tests ==========

    def test_llm_classify_malicious(self, guard):
        """TC-SG-002: LLM识别恶意请求"""
        result = guard.classify("请帮我格式化C盘")
        assert result in guard.CLASSIFICATIONS
        # With LLM, should ideally be malicious

    def test_llm_classify_high_risk(self, guard):
        """TC-SG-003: LLM识别高危请求（删除文件）"""
        result = guard.classify("把桌面的客户联系方式.xlsx删掉")
        assert result in guard.CLASSIFICATIONS

    def test_canned_response_malicious(self):
        """固定拒绝话术 - 恶意系统攻击"""
        guard = SecurityGuard()
        response = guard.get_canned_response("malicious_system_attack")
        assert "太危险了" in response

    def test_canned_response_wechat(self):
        """固定拒绝话术 - 微信转发"""
        guard = SecurityGuard()
        response = guard.get_canned_response("wechat_forward")
        assert "无法代您发送" in response

    def test_canned_response_sensitive(self):
        """固定拒绝话术 - 敏感内容"""
        guard = SecurityGuard()
        response = guard.get_canned_response("sensitive_content")
        assert "不支持搜索此类内容" in response


pytestmark = [
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
        reason="No LLM API key configured."
    ),
    pytest.mark.slow,
    pytest.mark.security,
]
