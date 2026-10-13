"""Bash command analyzer for semantic classification and safety checks.

Provides command classification, pipeline parsing, and destructive operation detection.
"""
import re
from enum import Enum, auto
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


class BashCommandType(Enum):
    """Command type classification."""
    SEARCH = "search"           # Search/grep/find operations
    READ = "read"              # Read/display operations
    LIST = "list"              # List/directory operations
    WRITE = "write"            # Write/modify operations
    SILENT = "silent"          # Silent/state operations (cd, export)
    GIT = "git"                # Git operations
    UNKNOWN = "unknown"        # Unknown/unclassified


@dataclass
class ParsedCommand:
    """Parsed command with metadata."""
    raw_command: str
    command_type: BashCommandType
    main_command: str
    args: List[str]
    flags: List[str]
    is_destructive: bool
    is_git_operation: bool
    paths: List[str]


class BashAnalyzer:
    """Bash command analyzer for semantic classification."""

    # Command classifications
    SEARCH_COMMANDS = {
        'grep', 'find', 'rg', 'ag', 'ack', 'locate', 'which', 'whereis'
    }

    READ_COMMANDS = {
        'cat', 'head', 'tail', 'less', 'more', 'wc', 'stat', 'file',
        'strings', 'read', 'cut', 'awk', 'sed', 'tr', 'sort', 'uniq',
        'diff', 'cmp', 'comm', 'hexdump', 'od', 'xxd'
    }

    LIST_COMMANDS = {
        'ls', 'tree', 'du', 'df', 'pwd', 'id', 'who', 'w', 'ps',
        'top', 'htop', 'free', 'uptime', 'uname', 'hostname'
    }

    WRITE_COMMANDS = {
        'rm', 'mv', 'cp', 'mkdir', 'rmdir', 'touch', 'chmod', 'chown',
        'chgrp', 'ln', 'dd', 'mkfs', 'mount', 'umount', 'tar', 'zip',
        'unzip', 'gzip', 'gunzip', 'rsync', 'scp'
    }

    SILENT_COMMANDS = {
        'cd', 'export', 'unset', 'alias', 'unalias', 'source', '.',
        'eval', 'exec', 'shift', 'set', 'shopt', 'history', 'clear',
        'true', 'false', 'echo', 'printf'
    }

    GIT_COMMANDS = {
        'git', 'gh'
    }

    # Destructive command patterns (command + dangerous flag combinations)
    DESTRUCTIVE_PATTERNS = [
        (r'\brm\s+.*-rf?\s+/', 'rm with root target'),           # rm -rf /
        (r'\brm\s+.*-rf?\s+\*', 'rm with wildcard'),             # rm -rf *
        (r'\bdd\s+.*if=.*of=/dev/[sh]d', 'dd to disk device'),   # dd to disk
        (r'\bmv\s+.*\s+/dev/null', 'mv to null'),                # mv to /dev/null
        (r'\bmkfs\.', 'filesystem formatting'),                   # mkfs.*
        (r'\bformat\b', 'format command'),                        # format
        (r':\s*\(\)\s*\{\s*:\s*\|', 'fork bomb'),               # fork bomb
        (r'\bgit\s+reset\s+--hard', 'git reset hard'),           # git reset --hard
        (r'\bgit\s+clean\s+-fd', 'git clean force'),              # git clean -fd
        (r'\bgit\s+push\s+.*--force', 'git force push'),          # git push --force
        (r'>\s*/dev/[sh]d', 'redirect to disk device'),           # > /dev/sd*
    ]

    @staticmethod
    def analyze_command(command: str) -> ParsedCommand:
        """Analyze a command and return parsed metadata.

        Args:
            command: The bash command to analyze

        Returns:
            ParsedCommand with classification and metadata
        """
        # Handle empty command
        if not command or not command.strip():
            return ParsedCommand(
                raw_command=command,
                command_type=BashCommandType.UNKNOWN,
                main_command="",
                args=[],
                flags=[],
                is_destructive=False,
                is_git_operation=False,
                paths=[]
            )

        # Extract main command and parts
        cmd_parts = command.strip().split()
        main_cmd = cmd_parts[0].lower()

        # Parse arguments and flags (handling quoted strings)
        args = []
        flags = []
        paths = []

        i = 1
        while i < len(cmd_parts):
            part = cmd_parts[i]

            # Handle quoted strings (may span multiple parts)
            if part.startswith('"') or part.startswith("'"):
                quote_char = part[0]
                if part.endswith(quote_char) and len(part) > 1:
                    # Single word quoted
                    clean_part = part[1:-1]
                    args.append(clean_part)
                    if '/' in clean_part or clean_part.startswith('.'):
                        paths.append(clean_part)
                else:
                    # Multi-word quoted string
                    quoted_parts = [part]
                    i += 1
                    while i < len(cmd_parts) and not cmd_parts[i].endswith(quote_char):
                        quoted_parts.append(cmd_parts[i])
                        i += 1
                    if i < len(cmd_parts):
                        quoted_parts.append(cmd_parts[i])
                    full_quoted = ' '.join(quoted_parts)[1:-1]  # Remove quotes
                    args.append(full_quoted)
                    if '/' in full_quoted or full_quoted.startswith('.'):
                        paths.append(full_quoted)
            elif part.startswith('-'):
                flags.append(part)
            elif '/' in part or part.startswith('.'):
                paths.append(part.strip('"\''))
                args.append(part)
            else:
                args.append(part)
            i += 1

        # Determine command type
        command_type = BashAnalyzer._classify_command(main_cmd, command)

        # Check if destructive
        is_destructive = BashAnalyzer.is_destructive(command)

        # Check if git operation
        is_git_operation = main_cmd in BashAnalyzer.GIT_COMMANDS

        return ParsedCommand(
            raw_command=command,
            command_type=command_type,
            main_command=main_cmd,
            args=args,
            flags=flags,
            is_destructive=is_destructive,
            is_git_operation=is_git_operation,
            paths=paths
        )

    @staticmethod
    def _classify_command(main_cmd: str, full_command: str) -> BashCommandType:
        """Classify a command into a type category."""
        if main_cmd in BashAnalyzer.SEARCH_COMMANDS:
            return BashCommandType.SEARCH
        elif main_cmd in BashAnalyzer.READ_COMMANDS:
            return BashCommandType.READ
        elif main_cmd in BashAnalyzer.LIST_COMMANDS:
            return BashCommandType.LIST
        elif main_cmd in BashAnalyzer.WRITE_COMMANDS:
            return BashCommandType.WRITE
        elif main_cmd in BashAnalyzer.SILENT_COMMANDS:
            return BashCommandType.SILENT
        elif main_cmd in BashAnalyzer.GIT_COMMANDS:
            return BashCommandType.GIT
        else:
            return BashCommandType.UNKNOWN

    @staticmethod
    def parse_pipeline(command: str) -> List[str]:
        """Parse a pipeline command into individual commands.

        Args:
            command: Pipeline command like 'cat file | grep pattern | wc -l'

        Returns:
            List of individual commands
        """
        # Split by pipe, handling quoted strings
        commands = []
        current = []
        in_quotes = False
        quote_char = None

        for char in command:
            if char in '"\'':
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                current.append(char)
            elif char == '|' and not in_quotes:
                commands.append(''.join(current).strip())
                current = []
            else:
                current.append(char)

        if current:
            commands.append(''.join(current).strip())

        return commands

    @staticmethod
    def is_destructive(command: str) -> bool:
        """Check if a command is destructive (can cause data loss).

        Args:
            command: The bash command to check

        Returns:
            True if the command is potentially destructive
        """
        cmd_lower = command.lower()

        # Check destructive patterns
        for pattern, description in BashAnalyzer.DESTRUCTIVE_PATTERNS:
            if re.search(pattern, cmd_lower):
                return True

        # Check for rm with recursive flag
        if re.search(r'\brm\s+(-[rf].*|--recursive)', cmd_lower):
            return True

        # Check for redirect to disk devices
        if re.search(r'>\s*/dev/[sh]d[a-z]', cmd_lower):
            return True

        return False

    @staticmethod
    def extract_paths(command: str) -> List[str]:
        """Extract file paths from a command.

        Args:
            command: Bash command string

        Returns:
            List of potential file paths
        """
        paths = []

        # First split by logical operators to handle command chains
        # Handle && and || by splitting and processing each command separately
        import re

        # Split by logical operators while keeping context
        # This regex splits on && || ; but not when in quotes
        command_parts = re.split(r'\s*(&&|\|\||;)\s*', command)

        for cmd_part in command_parts:
            if not cmd_part or cmd_part in ('&&', '||', ';'):
                continue

            parts = cmd_part.strip().split()
            if not parts:
                continue

            # Skip the command itself and common flags
            skip_args = {
                '-f', '-r', '-v', '-i', '-n', '-a', '-l', '-c', '-w', '-e',
                '--force', '--recursive', '--verbose', '--interactive',
                '--help', '--version'
            }

            i = 1  # Skip command name
            while i < len(parts):
                part = parts[i]

                # Skip flags
                if part.startswith('-') or part in skip_args:
                    i += 1
                    continue

                # Skip redirections and operators
                if part in {'>', '>>', '<', '|', '&&', '||', ';', '&'}:
                    i += 1
                    continue

                # Check if it looks like a path
                if '/' in part or part.startswith('.'):
                    # Clean up the path (remove quotes, etc.)
                    clean_path = part.strip('"\'')
                    paths.append(clean_path)

                i += 1

        return paths

    @staticmethod
    def analyze_pipeline(command: str) -> List[ParsedCommand]:
        """Analyze a full pipeline command.

        Args:
            command: Pipeline command like 'cat file | grep pattern'

        Returns:
            List of ParsedCommand for each stage
        """
        pipeline_commands = BashAnalyzer.parse_pipeline(command)
        return [BashAnalyzer.analyze_command(cmd) for cmd in pipeline_commands]

    @staticmethod
    def is_git_operation(command: str) -> bool:
        """Check if a command is a git operation.

        Args:
            command: The bash command to check

        Returns:
            True if the command involves git
        """
        cmd_lower = command.lower().strip()
        return cmd_lower.startswith('git ') or cmd_lower.startswith('gh ')

    @staticmethod
    def get_git_subcommand(command: str) -> Optional[str]:
        """Extract the git subcommand from a git operation.

        Args:
            command: Git command like 'git commit -m "message"'

        Returns:
            The subcommand (e.g., 'commit', 'push') or None
        """
        if not BashAnalyzer.is_git_operation(command):
            return None

        parts = command.strip().split()
        if len(parts) < 2:
            return None

        # Handle 'git' or 'gh' commands
        if parts[0] == 'git':
            # Skip options like -C, -c and their arguments
            i = 1
            while i < len(parts):
                part = parts[i]
                # Skip flags and their arguments
                if part.startswith('-'):
                    # Options like -C take an argument
                    if part in ('-C', '-c') and i + 1 < len(parts):
                        i += 2  # Skip flag and its argument
                    else:
                        i += 1  # Just skip the flag
                    continue
                return part.lower()
            return None
        elif parts[0] == 'gh':
            # gh pr create -> 'pr'
            return parts[1].lower() if len(parts) > 1 else None

        return None
