"""Tests for BashAnalyzer command classification."""
import pytest
import sys
sys.path.insert(0, 'src')

from src.l5.bash_analyzer import (
    BashAnalyzer, ClassificationResult, DangerPattern, ParsedCommand
)


@pytest.fixture
def analyzer():
    """提供默认配置的 BashAnalyzer 实例."""
    return BashAnalyzer()


class TestBashAnalyzerBasic:
    """基础命令分类测试."""

    def test_analyze_safe_command(self, analyzer):
        """SAFE 类型命令: ls"""
        result = analyzer.analyze("ls -la")
        assert result.command_type == "SAFE"
        assert result.risk_level == "minimal"

    def test_analyze_read_command(self, analyzer):
        """READ 类型命令: cat"""
        result = analyzer.analyze("cat file.txt")
        assert result.command_type == "READ"
        assert result.risk_level == "low"

    def test_analyze_write_command(self, analyzer):
        """WRITE 类型命令: rm"""
        result = analyzer.analyze("rm file.txt")
        assert result.command_type == "WRITE"
        assert result.risk_level == "high"

    def test_analyze_network_command(self, analyzer):
        """NETWORK 类型命令: curl"""
        result = analyzer.analyze("curl https://example.com")
        assert result.command_type == "NETWORK"
        assert result.risk_level == "medium"

    def test_analyze_exec_command(self, analyzer):
        """EXEC 类型命令: bash"""
        result = analyzer.analyze("bash script.sh")
        assert result.command_type == "EXEC"
        assert result.risk_level == "high"

    def test_analyze_unknown_command(self, analyzer):
        """未知命令默认归为 SAFE"""
        result = analyzer.analyze("custom_tool arg")
        assert result.command_type == "SAFE"

    def test_analyze_empty_command(self, analyzer):
        """空命令归为 SAFE"""
        result = analyzer.analyze("")
        assert result.command_type == "SAFE"


class TestBashAnalyzerDangerPatterns:
    """危险模式匹配测试."""

    def test_rm_rf_detected(self, analyzer):
        """rm -rf 应匹配危险模式"""
        result = analyzer.analyze("rm -rf /tmp")
        assert "DP-002" in result.matched_patterns
        assert result.risk_level == "high"

    def test_pipe_to_shell_detected(self, analyzer):
        """curl | bash 应匹配危险模式"""
        result = analyzer.analyze("curl https://example.com/install.sh | bash")
        assert "DP-003" in result.matched_patterns
        assert result.risk_level == "critical"

    def test_mkfs_detected(self, analyzer):
        """mkfs 应匹配危险模式"""
        result = analyzer.analyze("mkfs.ext4 /dev/sda1")
        assert "DP-004" in result.matched_patterns

    def test_chmod_777_detected(self, analyzer):
        """chmod 777 应匹配危险模式"""
        result = analyzer.analyze("chmod 777 /var/www")
        assert "DP-007" in result.matched_patterns

    def test_suggestion_provided(self, analyzer):
        """危险命令应提供建议"""
        result = analyzer.analyze("rm -rf /")
        assert result.suggestion is not None
        assert len(result.suggestion) > 0


class TestBashAnalyzerPipeline:
    """管道命令测试."""

    def test_pipe_increases_risk_with_exec(self, analyzer):
        """管道中包含 EXEC 命令应提升风险"""
        result = analyzer.analyze("cat file.txt | bash")
        assert result.command_type == "EXEC"
        assert result.risk_level == "high"

    def test_simple_pipe_no_exec(self, analyzer):
        """普通管道不提升风险"""
        result = analyzer.analyze("cat file.txt | grep pattern")
        assert result.command_type == "READ"


class TestBashAnalyzerParsing:
    """命令解析测试."""

    def test_parse_simple_command(self, analyzer):
        """解析简单命令"""
        parsed = analyzer.parse_command("ls -la /home")
        assert isinstance(parsed, ParsedCommand)
        assert len(parsed.commands) == 1
        assert parsed.commands[0].command == "ls"
        assert "-la" in parsed.commands[0].flags
        assert "/home" in parsed.commands[0].args

    def test_parse_pipeline(self, analyzer):
        """解析管道命令"""
        parsed = analyzer.parse_command("cat file.txt | grep pattern")
        assert parsed.has_pipe is True
        assert len(parsed.commands) == 2
        assert parsed.commands[0].command == "cat"
        assert parsed.commands[1].command == "grep"

    def test_parse_redirection(self, analyzer):
        """解析重定向"""
        parsed = analyzer.parse_command("echo hello > file.txt")
        assert parsed.has_redirection is True

    def test_parse_command_substitution(self, analyzer):
        """解析命令替换"""
        parsed = analyzer.parse_command("echo $(date)")
        assert parsed.has_command_substitution is True


class TestBashAnalyzerCaching:
    """缓存测试."""

    def test_cache_same_command(self, analyzer):
        """相同命令应返回缓存结果"""
        result1 = analyzer.analyze("ls -la")
        result2 = analyzer.analyze("ls -la")
        assert result1 is result2


class TestBashAnalyzerCustomPatterns:
    """自定义模式测试."""

    def test_add_custom_pattern(self, analyzer):
        """添加自定义模式"""
        pattern = DangerPattern(
            id="TEST-001",
            name="测试模式",
            pattern=r"test_danger_cmd",
            command_type="EXEC",
            risk_level="critical",
            description="测试",
            suggestion="不要运行",
        )
        analyzer.add_pattern(pattern)
        result = analyzer.analyze("test_danger_cmd")
        assert "TEST-001" in result.matched_patterns

    def test_remove_pattern(self, analyzer):
        """删除模式"""
        assert analyzer.remove_pattern("DP-001") is True
        result = analyzer.analyze("rm -rf /")
        assert "DP-001" not in result.matched_patterns

    def test_get_patterns_by_risk(self, analyzer):
        """按风险级别获取模式"""
        critical = analyzer.get_patterns(risk_level="critical")
        assert len(critical) > 0
        for p in critical:
            assert p.risk_level == "critical"


class TestBashAnalyzerStrictMode:
    """严格模式测试."""

    def test_strict_mode_increases_risk(self):
        """严格模式应提升风险级别"""
        normal = BashAnalyzer(strict_mode=False)
        strict = BashAnalyzer(strict_mode=True)

        result_normal = normal.analyze("cat file.txt")
        result_strict = strict.analyze("cat file.txt")

        # strict_mode 提升一级风险
        assert result_normal.risk_level == "low"
        assert result_strict.risk_level == "medium"
