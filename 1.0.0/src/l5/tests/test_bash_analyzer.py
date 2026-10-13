"""Tests for BashAnalyzer command classification."""
import pytest
import sys
sys.path.insert(0, 'src')

from src.l5.bash_analyzer import (
    BashAnalyzer, BashCommandType, ParsedCommand
)


class TestBashAnalyzerBasic:
    """Tests for basic command analysis."""

    def test_analyze_empty_command(self):
        """分析空命令"""
        result = BashAnalyzer.analyze_command("")
        assert result.command_type == BashCommandType.UNKNOWN
        assert result.main_command == ""

    def test_analyze_search_command(self):
        """分析搜索命令"""
        result = BashAnalyzer.analyze_command("grep pattern file.txt")
        assert result.command_type == BashCommandType.SEARCH
        assert result.main_command == "grep"

    def test_analyze_read_command(self):
        """分析读取命令"""
        result = BashAnalyzer.analyze_command("cat file.txt")
        assert result.command_type == BashCommandType.READ
        assert result.main_command == "cat"

    def test_analyze_list_command(self):
        """分析列表命令"""
        result = BashAnalyzer.analyze_command("ls -la")
        assert result.command_type == BashCommandType.LIST
        assert result.main_command == "ls"

    def test_analyze_write_command(self):
        """分析写入命令"""
        result = BashAnalyzer.analyze_command("rm file.txt")
        assert result.command_type == BashCommandType.WRITE
        assert result.main_command == "rm"

    def test_analyze_silent_command(self):
        """分析静默命令"""
        result = BashAnalyzer.analyze_command("cd /home/user")
        assert result.command_type == BashCommandType.SILENT
        assert result.main_command == "cd"

    def test_analyze_git_command(self):
        """分析 Git 命令"""
        result = BashAnalyzer.analyze_command("git status")
        assert result.command_type == BashCommandType.GIT
        assert result.main_command == "git"
        assert result.is_git_operation is True

    def test_analyze_unknown_command(self):
        """分析未知命令"""
        result = BashAnalyzer.analyze_command("custom_tool arg")
        assert result.command_type == BashCommandType.UNKNOWN
        assert result.main_command == "custom_tool"


class TestBashAnalyzerParsing:
    """Tests for command parsing."""

    def test_extract_flags(self):
        """提取命令行标志"""
        result = BashAnalyzer.analyze_command("ls -la --human-readable")
        assert "-la" in result.flags
        assert "--human-readable" in result.flags

    def test_extract_paths(self):
        """提取路径参数"""
        result = BashAnalyzer.analyze_command("cat /etc/passwd ./config.txt")
        assert "/etc/passwd" in result.paths
        assert "./config.txt" in result.paths

    def test_extract_paths_from_method(self):
        """使用 extract_paths 方法提取路径"""
        paths = BashAnalyzer.extract_paths("cp /src/file.txt /dest/")
        assert "/src/file.txt" in paths
        assert "/dest/" in paths

    def test_parse_simple_pipeline(self):
        """解析简单管道"""
        commands = BashAnalyzer.parse_pipeline("cat file.txt | grep pattern")
        assert len(commands) == 2
        assert "cat file.txt" in commands[0]
        assert "grep pattern" in commands[1]

    def test_parse_complex_pipeline(self):
        """解析复杂管道"""
        commands = BashAnalyzer.parse_pipeline("cat file.txt | grep pattern | wc -l")
        assert len(commands) == 3

    def test_analyze_pipeline(self):
        """分析整个管道"""
        results = BashAnalyzer.analyze_pipeline("cat file.txt | grep pattern")
        assert len(results) == 2
        assert results[0].command_type == BashCommandType.READ
        assert results[1].command_type == BashCommandType.SEARCH


class TestBashAnalyzerDestructive:
    """Tests for destructive operation detection."""

    def test_rm_rf_is_destructive(self):
        """rm -rf 是破坏性操作"""
        assert BashAnalyzer.is_destructive("rm -rf /") is True
        assert BashAnalyzer.is_destructive("rm -r /tmp") is True

    def test_rm_simple_is_not_destructive(self):
        """普通 rm 不是破坏性操作"""
        assert BashAnalyzer.is_destructive("rm file.txt") is False

    def test_dd_to_disk_is_destructive(self):
        """dd 到磁盘设备是破坏性操作"""
        assert BashAnalyzer.is_destructive("dd if=file of=/dev/sda") is True

    def test_git_reset_hard_is_destructive(self):
        """git reset --hard 是破坏性操作"""
        assert BashAnalyzer.is_destructive("git reset --hard HEAD~1") is True

    def test_git_clean_fd_is_destructive(self):
        """git clean -fd 是破坏性操作"""
        assert BashAnalyzer.is_destructive("git clean -fd") is True

    def test_git_force_push_is_destructive(self):
        """git push --force 是破坏性操作"""
        assert BashAnalyzer.is_destructive("git push origin main --force") is True

    def test_fork_bomb_is_destructive(self):
        """fork bomb 是破坏性操作"""
        assert BashAnalyzer.is_destructive(":(){ :|:& };:") is True

    def test_read_commands_not_destructive(self):
        """读取命令不是破坏性操作"""
        assert BashAnalyzer.is_destructive("cat file.txt") is False
        assert BashAnalyzer.is_destructive("ls -la") is False


class TestBashAnalyzerGitOperations:
    """Tests for Git operation detection."""

    def test_is_git_operation_true(self):
        """正确识别 Git 操作"""
        assert BashAnalyzer.is_git_operation("git status") is True
        assert BashAnalyzer.is_git_operation("git commit -m 'msg'") is True
        assert BashAnalyzer.is_git_operation("gh pr create") is True

    def test_is_git_operation_false(self):
        """正确识别非 Git 操作"""
        assert BashAnalyzer.is_git_operation("ls -la") is False
        assert BashAnalyzer.is_git_operation("cat file.txt") is False

    def test_get_git_subcommand_commit(self):
        """提取 git commit 子命令"""
        assert BashAnalyzer.get_git_subcommand("git commit -m 'message'") == "commit"

    def test_get_git_subcommand_push(self):
        """提取 git push 子命令"""
        assert BashAnalyzer.get_git_subcommand("git push origin main") == "push"

    def test_get_git_subcommand_with_options(self):
        """提取带选项的 git 子命令"""
        assert BashAnalyzer.get_git_subcommand("git -C /repo status") == "status"

    def test_get_git_subcommand_gh_pr(self):
        """提取 gh pr 子命令"""
        assert BashAnalyzer.get_git_subcommand("gh pr create") == "pr"

    def test_get_git_subcommand_none(self):
        """非 Git 命令返回 None"""
        assert BashAnalyzer.get_git_subcommand("ls -la") is None


class TestBashAnalyzerCommandTypes:
    """Tests for comprehensive command type coverage."""

    @pytest.mark.parametrize("cmd,expected_type", [
        ("grep pattern file", BashCommandType.SEARCH),
        ("find . -name '*.py'", BashCommandType.SEARCH),
        ("rg 'TODO'", BashCommandType.SEARCH),
        ("cat file.txt", BashCommandType.READ),
        ("head -20 log.txt", BashCommandType.READ),
        ("awk '{print $1}' file", BashCommandType.READ),
        ("ls -la", BashCommandType.LIST),
        ("tree", BashCommandType.LIST),
        ("du -sh", BashCommandType.LIST),
        ("rm file.txt", BashCommandType.WRITE),
        ("cp src dst", BashCommandType.WRITE),
        ("mkdir newdir", BashCommandType.WRITE),
        ("cd /tmp", BashCommandType.SILENT),
        ("export VAR=value", BashCommandType.SILENT),
        ("echo hello", BashCommandType.SILENT),
        ("git status", BashCommandType.GIT),
        ("gh pr list", BashCommandType.GIT),
    ])
    def test_command_types(self, cmd, expected_type):
        """测试各种命令类型分类"""
        result = BashAnalyzer.analyze_command(cmd)
        assert result.command_type == expected_type, f"Command '{cmd}' should be {expected_type.value}"


class TestBashAnalyzerPathExtraction:
    """Tests for path extraction functionality."""

    def test_extract_multiple_paths(self):
        """提取多个路径"""
        paths = BashAnalyzer.extract_paths("cp /src/file.txt /dest/file.txt")
        assert "/src/file.txt" in paths
        assert "/dest/file.txt" in paths

    def test_extract_quoted_paths(self):
        """提取带引号的路径"""
        result = BashAnalyzer.analyze_command('cat "/path/with spaces/file.txt"')
        assert "/path/with spaces/file.txt" in result.paths

    def test_skip_flags_in_path_extraction(self):
        """路径提取跳过标志"""
        paths = BashAnalyzer.extract_paths("rm -f -r /path/to/file")
        assert "-f" not in paths
        assert "-r" not in paths
        assert "/path/to/file" in paths

    def test_skip_operators_in_path_extraction(self):
        """路径提取跳过操作符"""
        paths = BashAnalyzer.extract_paths("cat ./file1.txt && cat ./file2.txt")
        assert "&&" not in paths
        assert "./file1.txt" in paths
        assert "./file2.txt" in paths
