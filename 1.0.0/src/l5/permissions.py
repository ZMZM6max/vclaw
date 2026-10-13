"""Permission system for L5 Tools & Capabilities.

Provides fine-grained access control for tool execution based on:
- Path patterns with wildcard support (** and *)
- Tool-specific permissions
- Permission modes (read-only, ask, auto-apply)
"""
import re
import fnmatch
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional, Set


class PermissionMode(Enum):
    """Permission mode for tool execution."""
    READ_ONLY = "read_only"      # Only read operations allowed
    ASK = "ask"                  # Requires user confirmation
    AUTO_APPLY = "auto_apply"    # Execute automatically


@dataclass
class PermissionResult:
    """Result of a permission check.

    Attributes:
        allowed: Whether the operation is allowed
        mode: The permission mode that applies
        reason: Optional reason for denial or ask mode
        rule: The matching rule (if any)
    """
    allowed: bool
    mode: PermissionMode
    reason: Optional[str] = None
    rule: Optional['PermissionRule'] = None

    @property
    def requires_confirmation(self) -> bool:
        """Check if this result requires user confirmation."""
        return self.allowed and self.mode == PermissionMode.ASK


@dataclass
class PermissionRule:
    """A permission rule defining access control for paths and tools.

    Attributes:
        pattern: Glob pattern for matching paths (e.g., "documents/**", "*.py")
        mode: The permission mode (read_only, ask, auto_apply)
        tools: Optional list of tool names this rule applies to.
               If empty, applies to all tools.
        priority: Rule priority (higher = more specific). Auto-calculated.
    """
    pattern: str
    mode: PermissionMode
    tools: List[str] = field(default_factory=list)
    priority: int = field(default=0, init=False)

    def __post_init__(self):
        """Calculate priority based on pattern specificity."""
        self.priority = self._calculate_priority()

    def _calculate_priority(self) -> int:
        """Calculate rule priority based on pattern specificity.

        More specific patterns (fewer wildcards, longer path) get higher priority.
        """
        priority = 0

        # Longer patterns are more specific
        priority += len(self.pattern) * 2

        # ** is less specific than *
        priority -= self.pattern.count("**") * 10

        # * is less specific than exact match
        priority -= self.pattern.count("*") * 5

        # Tool-specific rules are more specific
        if self.tools:
            priority += 20

        return priority

    def matches(self, path: str) -> bool:
        """Check if a path matches this rule's pattern.

        Args:
            path: The path to check

        Returns:
            True if the path matches the pattern
        """
        return wildcards_match(self.pattern, path)

    def applies_to_tool(self, tool_name: str) -> bool:
        """Check if this rule applies to a specific tool.

        Args:
            tool_name: The name of the tool

        Returns:
            True if the rule applies (no tool restriction or tool in list)
        """
        if not self.tools:
            return True
        return tool_name in self.tools

    def __repr__(self) -> str:
        tools_str = f", tools={self.tools}" if self.tools else ""
        return f"PermissionRule(pattern='{self.pattern}', mode={self.mode.value}{tools_str})"


class WildcardPattern:
    """Compiled wildcard pattern for efficient matching.

    Supports:
    - * : Match any sequence of characters within a single directory
    - ** : Match any sequence of characters across directory boundaries
    - ? : Match any single character
    - [abc] : Match any character in the set
    """

    def __init__(self, pattern: str):
        """Initialize with a pattern string."""
        self.pattern = pattern
        self._regex = self._compile_pattern(pattern)

    def _compile_pattern(self, pattern: str) -> re.Pattern:
        """Compile glob pattern to regex.

        Args:
            pattern: Glob pattern string

        Returns:
            Compiled regex pattern
        """
        # Normalize path separators
        pattern = pattern.replace('\\', '/')

        # Handle special cases
        # ** matches zero or more complete path segments
        # src/**/*.py should match: src/test.py, src/a/test.py, src/a/b/test.py

        # Process the pattern
        # First, split by / to handle directory boundaries
        parts = pattern.split('/')

        regex_parts = []
        for i, part in enumerate(parts):
            if part == '**':
                # ** can match zero or more path segments
                # At start: can match nothing (empty prefix)
                # In middle/end: matches directories
                if i == 0 and len(parts) == 1:
                    # Just ** - matches anything
                    regex_parts.append('.*')
                elif i == 0:
                    # **/pattern - match at any depth (including current)
                    regex_parts.append('(?:.*/)?')
                elif i == len(parts) - 1:
                    # pattern/** - matches the directory and all subdirectories
                    regex_parts.append('(?:/.*)?')
                else:
                    # pattern/**/pattern - match zero or more directories
                    # Use .*? with lookahead to match anything up to the next part
                    # We need to handle this specially - ** matches any path segment sequence
                    regex_parts.append('(?:.*/)?')
            elif '**' in part:
                # Something like a**b - not standard but handle it
                # ** in middle of segment acts like .*
                part_regex = part.replace('**', '.*')
                part_regex = part_regex.replace('*', '[^/]*')
                part_regex = part_regex.replace('?', '[^/]')
                regex_parts.append(part_regex)
            else:
                # Regular segment
                part_regex = part.replace('*', '[^/]*')
                part_regex = part_regex.replace('?', '[^/]')
                # Handle character classes
                j = 0
                final_parts = []
                while j < len(part_regex):
                    if part_regex[j] == '[':
                        end = part_regex.find(']', j)
                        if end == -1:
                            final_parts.append(re.escape(part_regex[j]))
                            j += 1
                        else:
                            final_parts.append(part_regex[j:end+1])
                            j = end + 1
                    else:
                        final_parts.append(re.escape(part_regex[j]) if part_regex[j] in '.+^${}()' else part_regex[j])
                        j += 1
                regex_parts.append(''.join(final_parts))

                # Add / separator (except for last part or if next is **)
                if i < len(parts) - 1 and parts[i + 1] != '**':
                    regex_parts.append('/')

        regex = ''.join(regex_parts)

        # Handle trailing ** special case
        if pattern.endswith('/**'):
            regex = regex.rstrip('/') + '(?:/.*)?'

        # Ensure pattern matches the entire path
        if not regex.startswith('^'):
            regex = '^' + regex
        if not regex.endswith('$'):
            regex = regex + '$'

        return re.compile(regex, re.IGNORECASE)

    def match(self, path: str) -> bool:
        """Check if path matches the pattern.

        Args:
            path: Path to match

        Returns:
            True if path matches
        """
        # Normalize path separators
        path = path.replace('\\', '/')
        return bool(self._regex.match(path))


def wildcards_match(pattern: str, path: str) -> bool:
    """Check if a path matches a wildcard pattern.

    Supports:
    - * : Match any sequence within a directory
    - ** : Match across directories
    - ? : Match single character

    Args:
        pattern: Glob pattern (e.g., "**/*.py", "src/*")
        path: Path to check

    Returns:
        True if path matches pattern

    Examples:
        >>> wildcards_match("**/*.py", "src/test.py")
        True
        >>> wildcards_match("src/*.py", "src/deep/test.py")
        False
        >>> wildcards_match("documents/**", "documents/a/b/c.txt")
        True
    """
    compiled = WildcardPattern(pattern)
    return compiled.match(path)


class PermissionManager:
    """Manages permission rules and checks for tool execution.

    The permission manager maintains a list of rules and provides methods
to check if tool execution is allowed based on path and tool name.

    Rules are evaluated in order of specificity (most specific first).
    The first matching rule determines the permission.

    Example:
        manager = PermissionManager()

        # Allow auto-execute for documents
        manager.add_rule(PermissionRule("documents/**", PermissionMode.AUTO_APPLY))

        # Require confirmation for deleting keys
        manager.add_rule(PermissionRule(
            "**/*.key",
            PermissionMode.ASK,
            tools=["file_delete"]
        ))

        # Make config read-only
        manager.add_rule(PermissionRule("config/**", PermissionMode.READ_ONLY))

        # Check permission
        result = manager.check_permission("file_read", "documents/file.txt")
        if result.allowed:
            print("Allowed!")
    """

    # Commands that only read
    READ_COMMANDS: Set[str] = {
        'cat', 'head', 'tail', 'less', 'more',
        'ls', 'tree', 'find', 'grep', 'rg', 'ag', 'ack',
        'wc', 'stat', 'file', 'strings',
        'pwd', 'echo', 'printf'
    }

    # Commands that modify
    WRITE_COMMANDS: Set[str] = {
        'rm', 'mv', 'cp', 'mkdir', 'rmdir', 'touch',
        'chmod', 'chown', 'chgrp', 'ln', 'dd'
    }

    def __init__(self):
        """Initialize the permission manager."""
        self._rules: List[PermissionRule] = []
        self._default_mode = PermissionMode.ASK
        self._setup_default_rules()

    def _setup_default_rules(self) -> None:
        """Set up default permission rules for common OS path areas."""
        # Desktop: read auto, write/delete/terminal ask
        self.add_rule(PermissionRule(
            "**/Desktop/**",
            PermissionMode.AUTO_APPLY,
            tools=["file_reader"]
        ))
        self.add_rule(PermissionRule(
            "**/Desktop/**",
            PermissionMode.ASK,
            tools=["file_writer", "file_delete", "terminal"]
        ))

        # Downloads: read/write auto, delete/terminal ask
        self.add_rule(PermissionRule(
            "**/Downloads/**",
            PermissionMode.AUTO_APPLY,
            tools=["file_reader", "file_writer"]
        ))
        self.add_rule(PermissionRule(
            "**/Downloads/**",
            PermissionMode.ASK,
            tools=["file_delete", "terminal"]
        ))

        # Documents: read/write auto, delete/terminal ask
        self.add_rule(PermissionRule(
            "**/Documents/**",
            PermissionMode.AUTO_APPLY,
            tools=["file_reader", "file_writer"]
        ))
        self.add_rule(PermissionRule(
            "**/Documents/**",
            PermissionMode.ASK,
            tools=["file_delete", "terminal"]
        ))

        # Pictures, Music, Videos: read auto, write/delete/terminal ask
        for area in ["Pictures", "Music", "Videos"]:
            self.add_rule(PermissionRule(
                f"**/{area}/**",
                PermissionMode.AUTO_APPLY,
                tools=["file_reader"]
            ))
            self.add_rule(PermissionRule(
                f"**/{area}/**",
                PermissionMode.ASK,
                tools=["file_writer", "file_delete", "terminal"]
            ))

        # documents/** sandbox area: read/write auto, delete/terminal ask
        self.add_rule(PermissionRule(
            "documents/**",
            PermissionMode.AUTO_APPLY,
            tools=["file_reader", "file_writer"]
        ))
        self.add_rule(PermissionRule(
            "documents/**",
            PermissionMode.ASK,
            tools=["file_delete", "terminal"]
        ))

        # config/** read-only (no tool restriction)
        self.add_rule(PermissionRule(
            "config/**",
            PermissionMode.READ_ONLY
        ))

        # System directories read-only
        self.add_rule(PermissionRule(
            "/System/**",
            PermissionMode.READ_ONLY
        ))
        self.add_rule(PermissionRule(
            "C:/Windows/**",
            PermissionMode.READ_ONLY
        ))
        self.add_rule(PermissionRule(
            "C:/Program Files/**",
            PermissionMode.READ_ONLY
        ))

    def add_rule(self, rule: PermissionRule) -> None:
        """Add a permission rule.

        Rules are automatically sorted by priority (most specific first).

        Args:
            rule: The permission rule to add
        """
        self._rules.append(rule)
        # Sort by priority (descending) - most specific first
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rule(self, pattern: str, mode: PermissionMode = None) -> bool:
        """Remove a permission rule by pattern.

        Args:
            pattern: The pattern of the rule to remove
            mode: Optional mode filter

        Returns:
            True if a rule was removed
        """
        initial_count = len(self._rules)
        self._rules = [
            r for r in self._rules
            if not (r.pattern == pattern and (mode is None or r.mode == mode))
        ]
        return len(self._rules) < initial_count

    def clear_rules(self) -> None:
        """Remove all permission rules."""
        self._rules.clear()

    @property
    def rules(self) -> List[PermissionRule]:
        """Get all permission rules (sorted by priority)."""
        return self._rules.copy()

    def check_permission(self, tool_name: str, path: str) -> PermissionResult:
        """Check if a tool operation is allowed on a path.

        Args:
            tool_name: Name of the tool to execute
            path: Target path for the operation

        Returns:
            PermissionResult with allowed status and mode
        """
        # Find the most specific matching rule
        matching_rule = None
        for rule in self._rules:
            if rule.matches(path) and rule.applies_to_tool(tool_name):
                matching_rule = rule
                break

        if matching_rule is None:
            # No matching rule - use default
            return PermissionResult(
                allowed=True,
                mode=self._default_mode,
                reason="No matching permission rule"
            )

        # Handle read-only mode
        if matching_rule.mode == PermissionMode.READ_ONLY:
            # For bash/terminal, check command type
            if tool_name == 'terminal':
                # This will be handled differently in check_bash_permission
                return PermissionResult(
                    allowed=True,
                    mode=PermissionMode.READ_ONLY,
                    rule=matching_rule
                )
            is_read_op = self._is_read_operation(tool_name)
            if is_read_op:
                return PermissionResult(
                    allowed=True,
                    mode=PermissionMode.AUTO_APPLY,
                    rule=matching_rule
                )
            else:
                return PermissionResult(
                    allowed=False,
                    mode=PermissionMode.READ_ONLY,
                    reason="Read-only directory",
                    rule=matching_rule
                )

        # Handle other modes
        return PermissionResult(
            allowed=True,
            mode=matching_rule.mode,
            rule=matching_rule
        )

    def check_bash_permission(self, command: str) -> PermissionResult:
        """Check permission for a bash command.

        Analyzes the command to determine if it's a read or write operation
        and checks permissions accordingly.

        Args:
            command: The bash command to check

        Returns:
            PermissionResult with allowed status
        """
        # Extract the main command
        cmd_parts = command.strip().split()
        if not cmd_parts:
            return PermissionResult(
                allowed=False,
                mode=PermissionMode.READ_ONLY,
                reason="Empty command"
            )

        main_cmd = cmd_parts[0].lower()

        # Determine operation type
        if main_cmd in self.READ_COMMANDS:
            is_write = False
        elif main_cmd in self.WRITE_COMMANDS:
            is_write = True
        else:
            # Unknown command - be conservative
            is_write = True

        # Extract paths from command (simplified)
        paths = self._extract_paths_from_command(command)

        if not paths:
            # No paths detected - allow but ask
            return PermissionResult(
                allowed=True,
                mode=PermissionMode.ASK,
                reason="Could not determine target paths"
            )

        # Check permission for each path
        results = []
        for path in paths:
            result = self.check_permission("terminal", path)
            results.append(result)

        # Combine results (most restrictive wins)
        if any(not r.allowed for r in results):
            denied = next(r for r in results if not r.allowed)
            return denied

        # Check for READ_ONLY mode with write commands
        if is_write:
            read_only_results = [r for r in results if r.mode == PermissionMode.READ_ONLY]
            if read_only_results:
                return PermissionResult(
                    allowed=False,
                    mode=PermissionMode.READ_ONLY,
                    reason="Read-only directory",
                    rule=read_only_results[0].rule
                )

        if any(r.mode == PermissionMode.ASK for r in results):
            ask_result = next(r for r in results if r.mode == PermissionMode.ASK)
            return ask_result

        # All allowed with auto_apply
        return results[0]

    def _is_read_operation(self, tool_name: str) -> bool:
        """Check if a tool performs read-only operations.

        Args:
            tool_name: Name of the tool

        Returns:
            True if the tool is read-only
        """
        read_tools = {'file_reader', 'file_read', 'search_web', 'calculator'}
        return tool_name in read_tools or tool_name.endswith('_read')

    def _extract_paths_from_command(self, command: str) -> List[str]:
        """Extract file paths from a bash command.

        This is a simplified implementation. A full implementation would
        need proper shell parsing.

        Args:
            command: Bash command string

        Returns:
            List of potential file paths
        """
        paths = []
        parts = command.split()

        # Skip the command itself and common flags
        skip_args = {'-f', '-r', '-v', '-i', '-n', '-a', '-l', '-c', '-w',
                     '--force', '--recursive', '--verbose', '--interactive'}

        i = 1  # Skip command name
        while i < len(parts):
            part = parts[i]

            # Skip flags
            if part.startswith('-') or part in skip_args:
                i += 1
                continue

            # Skip redirections
            if part in {'>', '>>', '<', '|', '&&', '||', ';'}:
                i += 1
                continue

            # Check if it looks like a path
            if '/' in part or part.startswith('.'):
                # Clean up the path (remove quotes, etc.)
                clean_path = part.strip('"\'')
                paths.append(clean_path)

            i += 1

        return paths

    def __repr__(self) -> str:
        return f"PermissionManager(rules={len(self._rules)}, default={self._default_mode.value})"
