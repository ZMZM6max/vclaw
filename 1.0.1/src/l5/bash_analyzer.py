import re
import shlex
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SimpleCommand:
    command: str
    args: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)


@dataclass
class ParsedCommand:
    raw_command: str
    commands: List[SimpleCommand]
    has_pipe: bool = False
    has_redirection: bool = False
    has_subshell: bool = False
    has_command_substitution: bool = False


@dataclass
class DangerPattern:
    id: str
    name: str
    pattern: str
    command_type: str
    risk_level: str
    description: str
    suggestion: Optional[str] = None


@dataclass
class ClassificationResult:
    command_type: str
    risk_level: str
    matched_patterns: List[str] = field(default_factory=list)
    suggestion: Optional[str] = None
    parsed_command: Optional[ParsedCommand] = None


class BashAnalyzer:
    COMMAND_TYPE_MAP = {
        "ls": "SAFE", "pwd": "SAFE", "echo": "SAFE", "date": "SAFE",
        "whoami": "SAFE", "hostname": "SAFE", "clear": "SAFE",
        "history": "SAFE", "alias": "SAFE", "unalias": "SAFE",
        "env": "SAFE", "printenv": "SAFE",
        "cat": "READ", "head": "READ", "tail": "READ", "less": "READ",
        "more": "READ", "grep": "READ", "find": "READ", "stat": "READ",
        "file": "READ", "md5sum": "READ", "sha256sum": "READ", "diff": "READ",
        "cmp": "READ", "strings": "READ", "objdump": "READ", "ldd": "READ",
        "rm": "WRITE", "mv": "WRITE", "cp": "WRITE", "touch": "WRITE",
        "mkdir": "WRITE", "rmdir": "WRITE", "dd": "WRITE", "mkfs": "WRITE",
        "fdisk": "WRITE", "parted": "WRITE", "chmod": "WRITE", "chown": "WRITE",
        "chgrp": "WRITE", "ln": "WRITE", "truncate": "WRITE",
        "curl": "NETWORK", "wget": "NETWORK", "ssh": "NETWORK", "scp": "NETWORK",
        "sftp": "NETWORK", "rsync": "NETWORK", "nc": "NETWORK", "netcat": "NETWORK",
        "telnet": "NETWORK", "ftp": "NETWORK", "ping": "NETWORK",
        "traceroute": "NETWORK", "host": "NETWORK", "dig": "NETWORK", "nslookup": "NETWORK",
        "bash": "EXEC", "sh": "EXEC", "zsh": "EXEC", "python": "EXEC",
        "python3": "EXEC", "perl": "EXEC", "ruby": "EXEC", "node": "EXEC",
        "php": "EXEC", "lua": "EXEC", "awk": "EXEC", "sed": "EXEC",
        "expect": "EXEC", "eval": "EXEC", "exec": "EXEC", "source": "EXEC",
    }

    COMMAND_RISK_MAP = {
        "ls": "minimal", "pwd": "minimal", "echo": "minimal", "date": "minimal",
        "whoami": "minimal", "hostname": "minimal", "clear": "minimal",
        "history": "minimal", "alias": "minimal", "unalias": "minimal",
        "env": "minimal", "printenv": "minimal",
        "cat": "low", "head": "low", "tail": "low", "less": "low",
        "more": "low", "grep": "low", "find": "low", "stat": "low",
        "file": "low", "md5sum": "low", "sha256sum": "low", "diff": "low",
        "cmp": "low", "strings": "low", "objdump": "low", "ldd": "low",
        "cp": "medium", "mv": "medium", "mkdir": "medium", "touch": "medium",
        "rmdir": "medium", "ln": "medium", "truncate": "medium",
        "rm": "high", "chmod": "high", "chown": "high", "dd": "high", "chgrp": "high",
        "mkfs": "critical", "fdisk": "critical", "parted": "critical",
        "ping": "medium", "traceroute": "medium", "host": "medium",
        "dig": "medium", "nslookup": "medium",
        "curl": "medium", "wget": "medium", "fetch": "medium",
        "ssh": "high", "scp": "high", "sftp": "high", "rsync": "high",
        "nc": "high", "netcat": "high", "telnet": "high", "ftp": "high",
        "bash": "high", "sh": "high", "zsh": "high", "python": "high",
        "python3": "high", "perl": "high", "ruby": "high", "node": "high",
        "php": "high", "lua": "high", "expect": "high", "eval": "high",
        "exec": "high", "source": "high",
        "awk": "medium", "sed": "medium",
    }

    RISK_ORDER = ["minimal", "low", "medium", "high", "critical"]
    TYPE_PRIORITY = {"SAFE": 0, "READ": 1, "WRITE": 2, "NETWORK": 3, "EXEC": 4, "UNKNOWN": -1}
    REDIRECTION_RE = re.compile(r"^\d*[><]")

    DEFAULT_PATTERNS = [
        DangerPattern(
            id="DP-001",
            name="强制递归删除根目录",
            pattern=r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?(-[a-zA-Z]*r[a-zA-Z]*\s+)?/\s*$|rm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+)?(-[a-zA-Z]*f[a-zA-Z]*\s+)?/\s*$",
            command_type="WRITE",
            risk_level="critical",
            description="尝试删除整个文件系统",
            suggestion="此操作极其危险，会删除系统所有文件",
        ),
        DangerPattern(
            id="DP-002",
            name="强制递归删除",
            pattern=(
                r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+)(-[a-zA-Z]*f[a-zA-Z]*\s+)"
                r"|rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)(-[a-zA-Z]*r[a-zA-Z]*\s+)"
                r"|rm\s+(-(?=[a-zA-Z]*r)(?=[a-zA-Z]*f)[a-zA-Z]+)\s+"
            ),
            command_type="WRITE",
            risk_level="high",
            description="使用-rf强制递归删除，可能误删大量文件",
            suggestion="建议使用 rm -i 进行交互式删除",
        ),
        DangerPattern(
            id="DP-003",
            name="管道到shell执行",
            pattern=r"curl.*\|\s*(ba)?sh|wget.*\|\s*(ba)?sh|fetch.*\|\s*(ba)?sh",
            command_type="EXEC",
            risk_level="critical",
            description="从网络下载代码并直接执行，极易执行恶意脚本",
            suggestion="禁止直接执行网络下载的脚本，请先下载审查",
        ),
        DangerPattern(
            id="DP-004",
            name="磁盘格式化",
            pattern=r"mkfs\.|dd\s+if=/dev/zero|dd\s+if=/dev/random|dd\s+if=/dev/urandom",
            command_type="WRITE",
            risk_level="critical",
            description="格式化磁盘或覆盖磁盘数据",
            suggestion="此操作会销毁磁盘数据",
        ),
        DangerPattern(
            id="DP-005",
            name="远程shell访问",
            pattern=r'ssh\s+.*\s+"|ssh\s+.*\s+\'|ssh\s+.*bash|ssh\s+.*sh\s+-c',
            command_type="NETWORK",
            risk_level="high",
            description="通过SSH执行远程命令",
            suggestion="确认远程主机和命令的可信度",
        ),
        DangerPattern(
            id="DP-006",
            name="网络下载工具",
            pattern=r"curl\s+.*(-o|--output)|wget\s+|fetch\s+",
            command_type="NETWORK",
            risk_level="medium",
            description="从网络下载文件",
            suggestion="确认下载来源可信",
        ),
        DangerPattern(
            id="DP-007",
            name="权限修改",
            pattern=r"chmod\s+777|chmod\s+-R|chown\s+-R|chmod\s+.*\s+/",
            command_type="WRITE",
            risk_level="high",
            description="修改文件权限，可能暴露敏感文件",
            suggestion="谨慎修改权限，避免使用777",
        ),
        DangerPattern(
            id="DP-008",
            name="系统命令执行",
            pattern=r"bash\s+-c|sh\s+-c|eval\s+|exec\s+|source\s+|\.\s+",
            command_type="EXEC",
            risk_level="high",
            description="执行外部命令或脚本",
            suggestion="确认执行的脚本来源可信",
        ),
        DangerPattern(
            id="DP-009",
            name="系统信息探测",
            pattern=r"cat\s+/etc/passwd|cat\s+/etc/shadow|cat\s+/etc/hosts|uname\s+-a|id\s+|whoami",
            command_type="READ",
            risk_level="low",
            description="读取系统敏感信息",
            suggestion="注意保护系统信息不被泄露",
        ),
        DangerPattern(
            id="DP-010",
            name="子shell和命令替换",
            pattern=r"\$\(.*\)|`.*`|\(.*\)",
            command_type="EXEC",
            risk_level="medium",
            description="使用子shell或命令替换，可能隐藏危险命令",
            suggestion="仔细检查子shell中的命令",
        ),
        DangerPattern(
            id="DP-011",
            name="进程终止",
            pattern=r"kill\s+-9|killall|pkill",
            command_type="WRITE",
            risk_level="medium",
            description="强制终止进程",
            suggestion="确认目标进程，避免误杀系统进程",
        ),
        DangerPattern(
            id="DP-012",
            name="环境变量修改",
            pattern=r"export\s+PATH|export\s+LD_PRELOAD",
            command_type="WRITE",
            risk_level="medium",
            description="修改环境变量，可能影响后续命令执行",
            suggestion="谨慎修改PATH等关键环境变量",
        ),
    ]

    def __init__(
        self,
        strict_mode: bool = False,
        max_command_length: int = 10000,
        allow_custom_patterns: bool = True,
        log_analysis_results: bool = True,
    ):
        self.strict_mode = strict_mode
        self.max_command_length = max_command_length
        self.allow_custom_patterns = allow_custom_patterns
        self.log_analysis_results = log_analysis_results
        self._patterns: Dict[str, DangerPattern] = {}
        for p in self.DEFAULT_PATTERNS:
            self._patterns[p.id] = p
        self._cache: Dict[Tuple[Any, ...], ClassificationResult] = {}

    @staticmethod
    def _options_key(options: Dict[str, Any]) -> Tuple[Any, ...]:
        def conv(v: Any) -> Any:
            if isinstance(v, list):
                return tuple(v)
            return v
        return tuple(sorted((k, conv(v)) for k, v in options.items()))

    def analyze(self, command: str, options: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        options = options or {}
        cache_key = (command.strip(), self._options_key(options))
        if cache_key in self._cache:
            return self._cache[cache_key]
        result = self._do_analyze(command, options)
        self._cache[cache_key] = result
        return result

    def _do_analyze(self, command: str, options: Dict[str, Any]) -> ClassificationResult:
        strict_mode = options.get("strict_mode", self.strict_mode)
        max_len = options.get("max_command_length", self.max_command_length)
        whitelist = options.get("whitelist", [])
        blacklist = options.get("blacklist", [])

        if len(command) > max_len:
            return ClassificationResult(
                command_type="UNKNOWN",
                risk_level="critical",
                suggestion=f"命令长度超过最大限制 {max_len}",
                parsed_command=None,
            )

        parsed = self.parse_command(command)
        first_cmd = parsed.commands[0].command if parsed.commands else ""
        if whitelist and first_cmd not in whitelist:
            return ClassificationResult(
                command_type="UNKNOWN",
                risk_level="critical",
                suggestion="命令不在白名单中",
                parsed_command=parsed,
            )
        if blacklist and first_cmd in blacklist:
            return ClassificationResult(
                command_type="UNKNOWN",
                risk_level="critical",
                suggestion="命令在黑名单中",
                parsed_command=parsed,
            )

        types = [self._classify_simple_command(sc) for sc in parsed.commands]
        overall_type = "SAFE"
        for t in types:
            if self.TYPE_PRIORITY.get(t, -1) > self.TYPE_PRIORITY.get(overall_type, -1):
                overall_type = t

        normalized = re.sub(r"\s+", " ", command.strip().lower())
        matched_patterns: List[str] = []
        suggestions: List[str] = []
        for pid, pattern in self._patterns.items():
            if re.search(pattern.pattern, normalized):
                matched_patterns.append(pid)
                if pattern.suggestion:
                    suggestions.append(pattern.suggestion)

        risk = self._calculate_risk(parsed, matched_patterns)

        if strict_mode and risk != "critical":
            idx = self.RISK_ORDER.index(risk)
            risk = self.RISK_ORDER[min(idx + 1, len(self.RISK_ORDER) - 1)]

        suggestion = "；".join(suggestions) if suggestions else None
        result = ClassificationResult(
            command_type=overall_type,
            risk_level=risk,
            matched_patterns=matched_patterns,
            suggestion=suggestion,
            parsed_command=parsed,
        )
        return result

    def parse_command(self, command: str) -> ParsedCommand:
        raw = command
        has_pipe = False
        has_redirection = False
        has_subshell = False
        has_command_substitution = False

        in_single = False
        in_double = False
        for c in command:
            if c == "'" and not in_double:
                in_single = not in_single
            elif c == '"' and not in_single:
                in_double = not in_double
            elif not in_single and not in_double:
                if c == "|":
                    has_pipe = True
                elif c in "><":
                    has_redirection = True

        if not in_single and not in_double:
            if re.search(r"\$\(", command) or re.search(r"`[^`]*`", command):
                has_command_substitution = True
            if re.search(r"\$\(", command) or re.search(r"`[^`]*`", command) or re.search(r"\([^)]*\)", command):
                has_subshell = True

        segments = self._split_into_segments(command)
        simple_commands: List[SimpleCommand] = []
        for segment in segments:
            sc = self._parse_segment(segment)
            if sc:
                simple_commands.append(sc)

        return ParsedCommand(
            raw_command=raw,
            commands=simple_commands,
            has_pipe=has_pipe,
            has_redirection=has_redirection,
            has_subshell=has_subshell,
            has_command_substitution=has_command_substitution,
        )

    def _split_into_segments(self, command: str) -> List[str]:
        parts = []
        current = []
        in_single = False
        in_double = False
        for c in command:
            if c == "'" and not in_double:
                in_single = not in_single
            elif c == '"' and not in_single:
                in_double = not in_double
            elif c == "|" and not in_single and not in_double:
                if current:
                    parts.append("".join(current).strip())
                    current = []
                continue
            elif c == ";" and not in_single and not in_double:
                if current:
                    parts.append("".join(current).strip())
                    current = []
                continue
            current.append(c)
        if current:
            parts.append("".join(current).strip())
        return [p for p in parts if p]

    def _parse_segment(self, segment: str) -> Optional[SimpleCommand]:
        try:
            tokens = shlex.split(segment, posix=True)
        except ValueError:
            tokens = segment.split()

        if not tokens:
            return None

        filtered = []
        skip_next = False
        for token in tokens:
            if skip_next:
                skip_next = False
                continue
            if self.REDIRECTION_RE.match(token):
                skip_next = True
                continue
            filtered.append(token)

        if not filtered:
            return None

        cmd = filtered[0]
        flags = [t for t in filtered[1:] if t.startswith("-")]
        args = [t for t in filtered[1:] if not t.startswith("-")]
        return SimpleCommand(command=cmd, args=args, flags=flags)

    def _classify_simple_command(self, simple_command: SimpleCommand) -> str:
        return self.COMMAND_TYPE_MAP.get(simple_command.command.lower(), "UNKNOWN")

    def _calculate_risk(self, parsed_command: ParsedCommand, matched_patterns: List[str]) -> str:
        base_risk = "minimal"
        for sc in parsed_command.commands:
            cmd_risk = self.COMMAND_RISK_MAP.get(sc.command.lower(), "minimal")
            if self.RISK_ORDER.index(cmd_risk) > self.RISK_ORDER.index(base_risk):
                base_risk = cmd_risk

        pattern_risk = "minimal"
        for pid in matched_patterns:
            p = self._patterns.get(pid)
            if p and self.RISK_ORDER.index(p.risk_level) > self.RISK_ORDER.index(pattern_risk):
                pattern_risk = p.risk_level

        final_idx = max(
            self.RISK_ORDER.index(base_risk),
            self.RISK_ORDER.index(pattern_risk),
        )
        final_risk = self.RISK_ORDER[final_idx]

        if parsed_command.has_pipe:
            for sc in parsed_command.commands:
                if self._classify_simple_command(sc) == "EXEC":
                    if self.RISK_ORDER.index(final_risk) < self.RISK_ORDER.index("high"):
                        final_risk = "high"
                    break

        if parsed_command.has_command_substitution:
            if self.RISK_ORDER.index(final_risk) < self.RISK_ORDER.index("medium"):
                final_risk = "medium"

        return final_risk

    def add_pattern(self, pattern: DangerPattern) -> None:
        if not self.allow_custom_patterns:
            raise RuntimeError("自定义模式已禁用")
        self._patterns[pattern.id] = pattern
        self._cache.clear()

    def remove_pattern(self, pattern_id: str) -> bool:
        if not self.allow_custom_patterns:
            raise RuntimeError("自定义模式已禁用")
        if pattern_id in self._patterns:
            del self._patterns[pattern_id]
            self._cache.clear()
            return True
        return False

    def get_patterns(self, risk_level: Optional[str] = None) -> List[DangerPattern]:
        patterns = list(self._patterns.values())
        if risk_level:
            patterns = [p for p in patterns if p.risk_level == risk_level]
        return patterns
