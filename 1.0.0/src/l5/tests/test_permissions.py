"""Tests for PermissionManager and wildcard matching."""
import pytest
import sys
sys.path.insert(0, 'src')

from src.l5.permissions import (
    PermissionMode, PermissionRule, PermissionManager, PermissionResult,
    wildcards_match, WildcardPattern
)


class TestWildcardPattern:
    """Tests for wildcard pattern matching."""

    def test_single_star_matches_any_filename(self):
        """* 匹配任意文件名"""
        assert wildcards_match("*.py", "test.py") is True
        assert wildcards_match("*.py", "script.py") is True
        assert wildcards_match("*.txt", "file.txt") is True
        assert wildcards_match("*.py", "test.txt") is False

    def test_single_star_matches_single_directory(self):
        """* 匹配单个目录层级"""
        assert wildcards_match("src/*.py", "src/test.py") is True
        assert wildcards_match("src/*.py", "src/deep/test.py") is False

    def test_double_star_matches_any_depth(self):
        """** 匹配任意目录深度"""
        assert wildcards_match("**/*.py", "test.py") is True
        assert wildcards_match("**/*.py", "src/test.py") is True
        assert wildcards_match("**/*.py", "src/deep/nested/test.py") is True
        assert wildcards_match("src/**/*.py", "src/test.py") is True
        assert wildcards_match("src/**/*.py", "src/deep/nested/test.py") is True
        assert wildcards_match("src/**/*.py", "test.py") is False

    def test_question_mark_matches_single_char(self):
        """? 匹配单个字符"""
        assert wildcards_match("test?.py", "test1.py") is True
        assert wildcards_match("test?.py", "testA.py") is True
        assert wildcards_match("test?.py", "test12.py") is False

    def test_exact_match(self):
        """精确匹配"""
        assert wildcards_match("test.py", "test.py") is True
        assert wildcards_match("test.py", "other.py") is False

    def test_directory_only_pattern(self):
        """目录专用模式"""
        assert wildcards_match("documents/**", "documents/file.txt") is True
        assert wildcards_match("documents/**", "documents/subdir/file.txt") is True
        assert wildcards_match("documents/**", "other/file.txt") is False

    def test_complex_pattern(self):
        """复杂模式"""
        assert wildcards_match("src/**/test_*.py", "src/test_main.py") is True
        assert wildcards_match("src/**/test_*.py", "src/utils/test_helpers.py") is True
        assert wildcards_match("src/**/test_*.py", "src/deep/nested/test_complex.py") is True
        assert wildcards_match("src/**/test_*.py", "src/main.py") is False


class TestPermissionRule:
    """Tests for PermissionRule class."""

    def test_rule_creation(self):
        """创建权限规则"""
        rule = PermissionRule("documents/**", PermissionMode.AUTO_APPLY)
        assert rule.pattern == "documents/**"
        assert rule.mode == PermissionMode.AUTO_APPLY
        assert rule.tools == []

    def test_rule_with_specific_tools(self):
        """针对特定工具的权限规则"""
        rule = PermissionRule(
            "**/*.key",
            PermissionMode.ASK,
            tools=["file_delete", "file_write"]
        )
        assert rule.tools == ["file_delete", "file_write"]

    def test_rule_matches_path(self):
        """规则匹配路径"""
        rule = PermissionRule("documents/**", PermissionMode.AUTO_APPLY)
        assert rule.matches("documents/file.txt") is True
        assert rule.matches("documents/subdir/file.txt") is True
        assert rule.matches("other/file.txt") is False

    def test_rule_matches_tool(self):
        """规则匹配工具"""
        rule = PermissionRule(
            "**/*.key",
            PermissionMode.ASK,
            tools=["file_delete"]
        )
        assert rule.applies_to_tool("file_delete") is True
        assert rule.applies_to_tool("file_read") is False

    def test_rule_without_tool_restriction_applies_to_all(self):
        """无工具限制的规则适用于所有工具"""
        rule = PermissionRule("documents/**", PermissionMode.AUTO_APPLY)
        assert rule.applies_to_tool("any_tool") is True


class TestPermissionManager:
    """Tests for PermissionManager class."""

    def test_add_rule(self):
        """添加权限规则"""
        manager = PermissionManager()
        manager.clear_rules()
        rule = PermissionRule("documents/**", PermissionMode.AUTO_APPLY)
        manager.add_rule(rule)
        assert len(manager.rules) == 1

    def test_check_auto_apply_permission(self):
        """检查自动执行权限"""
        manager = PermissionManager()
        manager.clear_rules()
        manager.add_rule(PermissionRule("documents/**", PermissionMode.AUTO_APPLY))

        result = manager.check_permission("file_read", "documents/file.txt")
        assert result.allowed is True
        assert result.mode == PermissionMode.AUTO_APPLY

    def test_check_read_only_denies_write(self):
        """只读权限拒绝写入操作"""
        manager = PermissionManager()
        manager.clear_rules()
        manager.add_rule(PermissionRule("config/**", PermissionMode.READ_ONLY))

        # 读取操作允许
        result = manager.check_permission("file_read", "config/settings.json")
        assert result.allowed is True

        # 写入操作拒绝
        result = manager.check_permission("file_write", "config/settings.json")
        assert result.allowed is False
        assert result.reason == "Read-only directory"

    def test_check_ask_permission(self):
        """检查需要确认的权限"""
        manager = PermissionManager()
        manager.clear_rules()
        manager.add_rule(
            PermissionRule("**/*.key", PermissionMode.ASK, tools=["file_delete"])
        )

        result = manager.check_permission("file_delete", "secrets.key")
        assert result.allowed is True
        assert result.mode == PermissionMode.ASK
        assert result.requires_confirmation is True

    def test_no_matching_rule_defaults_to_ask(self):
        """无匹配规则时默认需要确认"""
        manager = PermissionManager()
        manager.clear_rules()
        # 不添加任何规则

        result = manager.check_permission("file_delete", "unknown/path.txt")
        assert result.allowed is True
        assert result.mode == PermissionMode.ASK

    def test_multiple_rules_priority(self):
        """多个规则的优先级"""
        manager = PermissionManager()
        manager.clear_rules()
        # 先添加宽泛规则
        manager.add_rule(PermissionRule("**/*", PermissionMode.ASK))
        # 再添加具体规则
        manager.add_rule(PermissionRule("documents/**", PermissionMode.AUTO_APPLY))

        # 具体规则优先
        result = manager.check_permission("file_read", "documents/file.txt")
        assert result.mode == PermissionMode.AUTO_APPLY

    def test_tool_specific_rule_priority(self):
        """工具特定规则优先于通用规则"""
        manager = PermissionManager()
        manager.clear_rules()
        manager.add_rule(PermissionRule("documents/**", PermissionMode.AUTO_APPLY))
        manager.add_rule(
            PermissionRule("documents/*.key", PermissionMode.ASK, tools=["file_delete"])
        )

        # file_delete 需要确认
        result = manager.check_permission("file_delete", "documents/secrets.key")
        assert result.mode == PermissionMode.ASK

        # file_read 自动执行
        result = manager.check_permission("file_read", "documents/secrets.key")
        assert result.mode == PermissionMode.AUTO_APPLY

    def test_check_bash_command(self):
        """检查 Bash 命令权限"""
        manager = PermissionManager()
        manager.clear_rules()
        # 只添加读取权限，写入操作应该需要确认
        manager.add_rule(PermissionRule("documents/**", PermissionMode.AUTO_APPLY))

        # 读取命令允许
        result = manager.check_bash_permission("cat documents/file.txt")
        assert result.allowed is True

        # 写入命令（如 rm）应该返回 ASK 模式
        # 注意：由于 AUTO_APPLY 允许所有操作，我们需要测试 READ_ONLY 模式
        manager2 = PermissionManager()
        manager2.clear_rules()
        manager2.add_rule(PermissionRule("documents/**", PermissionMode.READ_ONLY))

        # 读取命令允许
        result = manager2.check_bash_permission("cat documents/file.txt")
        assert result.allowed is True

        # 写入命令被拒绝
        result = manager2.check_bash_permission("rm documents/file.txt")
        assert result.allowed is False


class TestPermissionResult:
    """Tests for PermissionResult class."""

    def test_allowed_result(self):
        """允许的结果"""
        result = PermissionResult(
            allowed=True,
            mode=PermissionMode.AUTO_APPLY,
            reason=None
        )
        assert result.allowed is True
        assert result.requires_confirmation is False

    def test_denied_result(self):
        """拒绝的结果"""
        result = PermissionResult(
            allowed=False,
            mode=PermissionMode.READ_ONLY,
            reason="Permission denied"
        )
        assert result.allowed is False
        assert result.requires_confirmation is False

    def test_ask_result(self):
        """需要确认的结果"""
        result = PermissionResult(
            allowed=True,
            mode=PermissionMode.ASK,
            reason="High-risk operation"
        )
        assert result.allowed is True
        assert result.requires_confirmation is True


def test_desktop_write_requires_ask():
    """Tests default rule: Desktop write requires ASK (intentionally uses default rules)."""
    manager = PermissionManager()
    result = manager.check_permission("file_writer", "C:\\Users\\Test\\Desktop\\file.txt")
    assert result.allowed is True
    assert result.mode == PermissionMode.ASK


def test_documents_read_auto_applied():
    """Tests default rule: Documents read is AUTO_APPLY (intentionally uses default rules)."""
    manager = PermissionManager()
    result = manager.check_permission("file_reader", "C:\\Users\\Test\\Documents\\file.txt")
    assert result.allowed is True
    assert result.mode == PermissionMode.AUTO_APPLY


def test_unknown_absolute_path_defaults_to_ask():
    """Tests default behavior: unknown absolute path defaults to ASK."""
    manager = PermissionManager()
    result = manager.check_permission("file_writer", "D:\\Random\\file.txt")
    assert result.allowed is True
    assert result.mode == PermissionMode.ASK


def test_config_read_only_default():
    """Tests default rule: config/** is READ_ONLY."""
    manager = PermissionManager()
    result = manager.check_permission("file_writer", "config/settings.json")
    assert result.allowed is False
    assert result.mode == PermissionMode.READ_ONLY
