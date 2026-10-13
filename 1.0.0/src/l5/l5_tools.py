"""L5: Tools & Capabilities Layer - Tool routing and execution."""
import re
from typing import List, Dict, Any, Optional, Callable
from src.core.models import Observation
from src.core.interfaces import ToolsInterface, RuntimeInterface
from src.l6.l6_runtime import RuntimeEnvironment
from src.core.exceptions import (
    ToolNotFoundError, ValidationError, ExecutionTimeoutError,
    PermissionDeniedError,  # Deprecated but kept for compatibility
    InvalidConfirmationError
)
from src.l5.confirmation_manager import ConfirmationManager
from src.l5.permissions import PermissionManager, PermissionMode, PermissionRule
from src.l5.path_mapper import PathMapper, PathMappingError
from src.tools.manager import ToolManager


class Tool:
    """Tool definition with enhanced descriptions."""

    def __init__(self, name: str, description: str,
                 parameters: Dict, required_permission: str = None,
                 handler: Callable = None):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.required_permission = required_permission  # Kept for compatibility but not enforced
        self.handler = handler  # Optional custom handler


class ToolRegistry:
    """Tool registry for dynamic tool management."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """Register built-in tools."""
        builtins = {
            "python_repl": Tool(
                name="python_repl",
                description="Execute Python code in a sandboxed environment. Use this for calculations, data processing, or any Python programming task.",
                parameters={
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code to execute. Can include multiple lines and imports."
                        }
                    },
                    "required": ["code"]
                },
                required_permission=None
            ),
            "calculator": Tool(
                name="calculator",
                description="Perform mathematical calculations. Supports basic arithmetic, scientific functions, and complex expressions.",
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical expression to evaluate (e.g., '2+2', 'sqrt(16)', 'sin(pi/2)')"
                        }
                    },
                    "required": ["expression"]
                },
                required_permission=None
            ),
            "search_web": Tool(
                name="search_web",
                description="Search the web for information. Returns search results from the internet.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string"
                        }
                    },
                    "required": ["query"]
                },
                required_permission=None
            ),
            "file_reader": Tool(
                name="file_reader",
                description="Read content from a file. Supports text files, code files, and documents.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to read"
                        },
                        "encoding": {
                            "type": "string",
                            "description": "File encoding (default: utf-8)"
                        }
                    },
                    "required": ["path"]
                },
                required_permission=None
            ),
            "file_writer": Tool(
                name="file_writer",
                description="Write content to a file. Creates the file if it doesn't exist.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to write"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file"
                        },
                        "encoding": {
                            "type": "string",
                            "description": "File encoding (default: utf-8)"
                        }
                    },
                    "required": ["path", "content"]
                },
                required_permission=None
            ),
            "file_delete": Tool(
                name="file_delete",
                description="删除文件或目录。警告: 高危操作，需要二次确认。",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要删除的文件或目录路径（必须以 documents/ 开头）"
                        },
                        "confirmed": {
                            "type": "boolean",
                            "description": "是否已确认删除（首次调用不传或传 false）"
                        },
                        "confirmation_id": {
                            "type": "string",
                            "description": "确认 ID（confirmed=true 时必填）"
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "是否递归删除目录"
                        }
                    },
                    "required": ["path"]
                },
                required_permission=None
            ),
            "terminal": Tool(
                name="terminal",
                description="Execute terminal/shell commands. Use with caution - only safe commands are allowed.",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Shell command to execute (e.g., 'ls -la', 'pwd')"
                        },
                        "working_dir": {
                            "type": "string",
                            "description": "Working directory for the command (default: current directory)"
                        }
                    },
                    "required": ["command"]
                },
                required_permission=None
            )
        }
        for name, tool in builtins.items():
            self._tools[name] = tool

    def register(self, name: str, tool: Tool) -> None:
        """Register a new tool."""
        self._tools[name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def clear(self) -> None:
        """Clear all tools."""
        self._tools.clear()


class ParameterValidator:
    """Parameter validator with security checks."""

    # Dangerous path patterns for directory traversal prevention
    DANGEROUS_PATH_PATTERNS = [
        r"\.\./",           # ../
        r"\.\.\\",          # ..\
        r"^/etc/",          # /etc/
        r"^/proc/",         # /proc/
        r"^/sys/",          # /sys/
        r"^/root/",         # /root/
        r"^/boot/",         # /boot/
        r"^C:\\Windows",    # Windows system
        r"%",               # Environment variable
        r"~",               # Home directory shortcut
    ]

    # Safe terminal commands (whitelist approach)
    SAFE_TERMINAL_COMMANDS = [
        "ls", "dir", "pwd", "cd", "cat", "type", "echo", "head", "tail",
        "find", "grep", "wc", "sort", "uniq", "date", "whoami", "uname",
        "python", "python3", "node", "npm", "pip", "git status", "git log",
        "mkdir", "touch", "cp", "copy", "mv", "move", "rm", "del"
    ]

    # Dangerous terminal commands
    DANGEROUS_COMMANDS = [
        "rm -rf /", "del /f /s /q", "format", "mkfs", "dd if",
        ":(){ :|:& };:",  # Fork bomb
        "shutdown", "reboot", "halt", "poweroff",
        "sudo", "su -", "passwd", "chpasswd",
        "eval"
    ]

    @staticmethod
    def validate(params: Dict, schema: Dict) -> "ValidationResult":
        """Validate parameters against JSON Schema."""
        errors = []
        properties = schema.get("properties", {})
        required_params = schema.get("required", [])

        for param_name, param_def in properties.items():
            # Check required fields
            if param_name in required_params and param_name not in params:
                errors.append(f"Missing required parameter: {param_name}")
                continue

            if param_name not in params:
                continue

            value = params[param_name]
            expected_type = param_def.get("type")

            # Type checking
            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"Parameter '{param_name}' must be a string")
            elif expected_type == "integer" and not isinstance(value, int):
                errors.append(f"Parameter '{param_name}' must be an integer")
            elif expected_type == "boolean" and not isinstance(value, bool):
                errors.append(f"Parameter '{param_name}' must be a boolean")

            # String length validation
            if expected_type == "string" and isinstance(value, str):
                max_length = param_def.get("maxLength")
                if max_length and len(value) > max_length:
                    errors.append(f"Parameter '{param_name}' exceeds max length of {max_length}")

                # Path safety check for path parameters
                if "path" in param_name.lower() or "file" in param_name.lower():
                    if not ParameterValidator.is_path_safe(value):
                        errors.append(f"Parameter '{param_name}' contains unsafe path: {value}")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    @staticmethod
    def is_path_safe(path: str) -> bool:
        """Check if a path is safe (no directory traversal)."""
        for pattern in ParameterValidator.DANGEROUS_PATH_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                return False
        return True

    @staticmethod
    def sanitize_path(path: str, base_dir: str = ".") -> str:
        """Sanitize a path to prevent directory traversal."""
        import os
        # Normalize the path
        normalized = os.path.normpath(path)
        # Join with base directory and normalize again
        full_path = os.path.normpath(os.path.join(base_dir, normalized))
        # Ensure it's still within base directory
        base_abs = os.path.abspath(base_dir)
        full_abs = os.path.abspath(full_path)
        if not full_abs.startswith(base_abs):
            raise ValidationError(f"Path '{path}' attempts directory traversal")
        return full_path

    @staticmethod
    def validate_sandbox_path(path: str) -> "ValidationResult":
        """Validate that a path is within the sandbox (documents/ prefix required).

        According to XML spec, file operations must use paths starting with 'documents/'.

        Args:
            path: The path to validate

        Returns:
            ValidationResult with valid flag and error messages
        """
        errors = []

        # Rule 1: No directory traversal (check first for security)
        if ".." in path:
            errors.append("检测到目录遍历攻击，路径包含非法字符 '..'")

        # Rule 2: No absolute paths
        if path.startswith("/") or re.match(r'^[A-Za-z]:\\', path):
            errors.append("禁止使用绝对路径")

        # Rule 3: Must start with documents/
        if not path.startswith("documents/"):
            errors.append("路径必须在沙盒范围内，必须以 'documents/' 开头")

        # Rule 4: Check against existing dangerous patterns
        for pattern in ParameterValidator.DANGEROUS_PATH_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                errors.append(f"路径包含非法模式")
                break

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    @staticmethod
    def validate_terminal_command(command: str) -> bool:
        """Validate if a terminal command is safe."""
        cmd_lower = command.lower().strip()

        # Check for dangerous commands
        for dangerous in ParameterValidator.DANGEROUS_COMMANDS:
            if dangerous in cmd_lower:
                return False

        # Check for command chaining that could be dangerous
        dangerous_patterns = [
            ";", "&&", "||", "|", "`", "$", "\n", "\r"
        ]
        for pattern in dangerous_patterns:
            if pattern in command:
                # Allow pipe for safe commands like 'ls | grep'
                if pattern == "|" and not ParameterValidator._is_safe_pipe(command):
                    return False
                elif pattern != "|":
                    return False

        return True

    @staticmethod
    def _is_safe_pipe(command: str) -> bool:
        """Check if a piped command is safe."""
        parts = command.split("|")
        for part in parts:
            part = part.strip().lower()
            base_cmd = part.split()[0] if part.split() else ""
            if base_cmd and not any(
                safe in base_cmd for safe in ParameterValidator.SAFE_TERMINAL_COMMANDS
            ):
                return False
        return True


class ValidationResult:
    """Validation result object."""

    def __init__(self, valid: bool, errors: List[str] = None):
        self.valid = valid
        self.errors = errors or []

    def __bool__(self):
        return self.valid


class ToolContextBuilder:
    """Builds context with tool descriptions for LLM."""

    @staticmethod
    def build_tool_context(tools: List[Tool], include_examples: bool = True) -> str:
        """Build a comprehensive tool description context.

        Returns a formatted string describing all available tools
        that can be included in the LLM context.
        """
        context_parts = ["Available Tools:"]
        context_parts.append("=" * 50)

        for i, tool in enumerate(tools, 1):
            context_parts.append(f"\n{i}. Tool: {tool.name}")
            context_parts.append(f"   Description: {tool.description}")

            if tool.parameters:
                context_parts.append("   Parameters:")
                props = tool.parameters.get("properties", {})
                required_set = set(tool.parameters.get("required", []))
                for param_name, param_def in props.items():
                    param_type = param_def.get("type", "any")
                    param_desc = param_def.get("description", "")
                    required = " (required)" if param_name in required_set else " (optional)"
                    context_parts.append(f"     - {param_name}: {param_type}{required}")
                    if param_desc:
                        context_parts.append(f"       {param_desc}")

            if include_examples:
                example = ToolContextBuilder._generate_example(tool)
                if example:
                    context_parts.append(f"   Example: {example}")

        context_parts.append("\n" + "=" * 50)
        context_parts.append("\nHow to use tools:")
        context_parts.append("To use a tool, respond with a JSON object in this format:")
        context_parts.append('{"action": "tool_name", "action_input": {"param1": "value1"}}')

        return "\n".join(context_parts)

    @staticmethod
    def _generate_example(tool: Tool) -> str:
        """Generate an example usage for a tool."""
        if tool.name == "python_repl":
            return '{"action": "python_repl", "action_input": {"code": "print(2+2)"}}'
        elif tool.name == "calculator":
            return '{"action": "calculator", "action_input": {"expression": "15 * 23"}}'
        elif tool.name == "search_web":
            return '{"action": "search_web", "action_input": {"query": "latest AI news"}}'
        elif tool.name == "file_reader":
            return '{"action": "file_reader", "action_input": {"path": "data.txt"}}'
        elif tool.name == "file_writer":
            return '{"action": "file_writer", "action_input": {"path": "output.txt", "content": "Hello"}}'
        elif tool.name == "terminal":
            return '{"action": "terminal", "action_input": {"command": "ls -la"}}'
        return ""

    @staticmethod
    def format_tools_for_llm(tools: List[Tool]) -> str:
        """Format tools in a simple text format for LLM context.

        This is an alternative format that's more compact.
        """
        lines = ["You have access to the following tools:"]

        for tool in tools:
            lines.append(f"\n{tool.name}: {tool.description}")
            if tool.parameters:
                props = tool.parameters.get("properties", {})
                params_str = ", ".join([
                    f"{k}({v.get('type', 'any')})"
                    for k, v in props.items()
                ])
                lines.append(f"  Parameters: {params_str}")

        lines.append("\nWhen you need to use a tool, output:")
        lines.append('TOOL_CALL: {"tool": "name", "params": {...}}')

        return "\n".join(lines)


class ToolsCapabilities(ToolsInterface):
    """L5 implementation - Tools and capabilities management with permission control."""

    def __init__(self, runtime: RuntimeInterface = None, enable_permissions: bool = True, sandbox_documents_root: str = None):
        self.runtime = runtime or RuntimeEnvironment()
        self.registry = ToolRegistry()
        self.validator = ParameterValidator()
        self.context_builder = ToolContextBuilder()
        self.confirmation_manager = ConfirmationManager()
        self.permission_manager = PermissionManager()
        self.path_mapper = PathMapper(sandbox_documents_root=sandbox_documents_root)
        self.advanced_tools = ToolManager()
        self._enable_permissions = enable_permissions

        # Setup default permission rules
        if enable_permissions:
            self._setup_default_permissions()

    def _setup_default_permissions(self):
        """Setup default permission rules for sandbox security."""
        # documents/ directory: allow auto-apply for most operations
        self.permission_manager.add_rule(
            PermissionRule("documents/**", PermissionMode.AUTO_APPLY)
        )

        # config/ directory: read-only (if it exists)
        self.permission_manager.add_rule(
            PermissionRule("config/**", PermissionMode.READ_ONLY)
        )

        # .key files: require confirmation for delete
        self.permission_manager.add_rule(
            PermissionRule("**/*.key", PermissionMode.ASK, tools=["file_delete"])
        )

        # Deny paths outside documents/ (must be last to allow documents/** to match first)
        # This is a fallback to catch paths without documents/ prefix
        self.permission_manager.add_rule(
            PermissionRule("**", PermissionMode.READ_ONLY)
        )

    def execute(self, action_name: str, params: Dict[str, Any],
                user_permissions: List[str] = None, timeout: int = 30) -> Observation:
        """Execute a tool with optional permission checking."""
        # Find tool
        tool = self.registry.get(action_name)
        if not tool:
            raise ToolNotFoundError(f"Tool '{action_name}' not found")

        # Validate parameters first (includes sandbox path validation for file operations)
        validation = self.validator.validate(params, tool.parameters)
        if not validation.valid:
            raise ValidationError(f"Validation failed: {'; '.join(validation.errors)}")

        # Check permissions if enabled
        if self._enable_permissions:
            permission_result = self._check_tool_permission(action_name, params)
            if not permission_result.allowed:
                return Observation(
                    status="error",
                    result=f"Permission denied: {permission_result.reason}",
                    execution_time=0.0,
                    metadata={"permission_denied": True}
                )
            if permission_result.requires_confirmation:
                # file_delete has its own built-in confirmation manager
                if action_name != "file_delete":
                    return Observation(
                        status="confirmation_required",
                        result=f"This operation requires confirmation: {permission_result.reason or action_name}",
                        execution_time=0.0,
                        metadata={"confirmation_required": True, "tool": action_name}
                    )

        # Execute
        if action_name == "python_repl":
            return self._execute_python(params, timeout)
        elif action_name == "calculator":
            return self._execute_calculator(params)
        elif action_name == "search_web":
            return self._execute_search(params)
        elif action_name == "file_reader":
            return self._execute_file_read(params)
        elif action_name == "file_writer":
            return self._execute_file_write(params)
        elif action_name == "file_delete":
            return self._execute_file_delete(params)
        elif action_name == "terminal":
            return self._execute_terminal(params, timeout)
        else:
            # Check for custom handler
            if tool.handler:
                return tool.handler(params)
            raise ToolNotFoundError(f"Execution logic not implemented for '{action_name}'")

    def _execute_python(self, params: Dict, timeout: int) -> Observation:
        """Execute Python code."""
        code = params.get("code", "")

        result = self.runtime.run_code("python", code, timeout)

        # Format result
        output = result.stdout
        if result.stderr:
            output += f"\n[Error] {result.stderr}"

        # Truncate if needed
        truncated = len(output) > 10000
        if truncated:
            output = output[:9970] + "\n[Output truncated...]"

        return Observation(
            status="success" if result.exit_code == 0 else "error",
            result=output,
            execution_time=result.execution_time,
            metadata={
                "exit_code": result.exit_code,
                "truncated": truncated
            }
        )

    def _execute_calculator(self, params: Dict) -> Observation:
        """Execute calculator using safe evaluation."""
        expression = params.get("expression", "")

        # Security: validate expression contains only allowed characters
        # Allowed: digits, operators, parentheses, whitespace, and math functions
        allowed_pattern = r'^[\d\+\-\*\/\%\(\)\.\s\,]+$|^(sqrt|sin|cos|tan|log|log10|exp|pow|abs)\s*\('
        if not re.match(allowed_pattern, expression.strip(), re.IGNORECASE):
            return Observation(
                status="error",
                result="Invalid characters in expression. Only numbers, operators, and math functions allowed.",
                execution_time=0.0,
                metadata={}
            )

        try:
            # Use numexpr if available (safer and faster)
            try:
                import numexpr as ne
                result = ne.evaluate(expression).item()
            except ImportError:
                # Fallback: use eval with restricted globals/locals
                import math
                safe_dict = {
                    'sqrt': math.sqrt,
                    'sin': math.sin,
                    'cos': math.cos,
                    'tan': math.tan,
                    'pi': math.pi,
                    'e': math.e,
                    'log': math.log,
                    'log10': math.log10,
                    'exp': math.exp,
                    'pow': math.pow,
                    'abs': abs
                }
                # Compile to limit to expression only
                code = compile(expression, '<string>', 'eval')
                result = eval(code, {"__builtins__": {}}, safe_dict)

            return Observation(
                status="success",
                result=str(result),
                execution_time=0.0,
                metadata={}
            )
        except Exception as e:
            return Observation(
                status="error",
                result=str(e),
                execution_time=0.0,
                metadata={}
            )

    def _execute_search(self, params: Dict) -> Observation:
        """Execute web search using advanced tool if available."""
        # 优先使用高级 web_search 工具
        if "web_search" in self.advanced_tools.list_tools():
            return self._execute_advanced_tool("web_search", params, 30)
        
        # 回退到 mock 实现
        query = params.get("query", "")
        return Observation(
            status="success",
            result=f"Search results for: {query}\n[Configure GOOGLE_API_KEY for real results]",
            execution_time=0.5,
            metadata={}
        )

    def _execute_file_read(self, params: Dict) -> Observation:
        """Read file content."""
        import os
        path = params.get('path', '')
        encoding = params.get('encoding', 'utf-8')

        try:
            resolved_path = self.path_mapper.resolve(path)
            safe_path = resolved_path if os.path.isabs(resolved_path) else self.validator.sanitize_path(resolved_path)

            if not os.path.exists(safe_path):
                return Observation(
                    status='error',
                    result=f'File not found: {path}',
                    execution_time=0.0,
                    metadata={}
                )

            with open(safe_path, 'r', encoding=encoding) as f_read:
                content = f_read.read()

            truncated = len(content) > 10000
            if truncated:
                content = content[:9970] + '\n[Content truncated...]'

            return Observation(
                status='success',
                result=content,
                execution_time=0.1,
                metadata={'truncated': truncated, 'path': path}
            )
        except Exception as e:
            return Observation(
                status='error',
                result=str(e),
                execution_time=0.0,
                metadata={'path': path}
            )

    def _execute_file_write(self, params: Dict) -> Observation:
        """Write content to file."""
        import os
        path = params.get('path', '')
        content = params.get('content', '')
        encoding = params.get('encoding', 'utf-8')

        try:
            resolved_path = self.path_mapper.resolve(path)
            safe_path = resolved_path if os.path.isabs(resolved_path) else self.validator.sanitize_path(resolved_path)

            dir_path = os.path.dirname(safe_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path)

            with open(safe_path, 'w', encoding=encoding) as f_write:
                f_write.write(content)

            return Observation(
                status='success',
                result=f'Successfully wrote {len(content)} characters to {path}',
                execution_time=0.1,
                metadata={'path': path, 'bytes_written': len(content)}
            )
        except Exception as e:
            return Observation(
                status='error',
                result=str(e),
                execution_time=0.0,
                metadata={'path': path}
            )

    def _execute_file_delete(self, params: Dict) -> Observation:
        """Execute file delete with confirmation mechanism."""
        import os
        import time

        path = params.get('path', '')
        confirmed = params.get('confirmed', False)
        confirmation_id = params.get('confirmation_id')
        recursive = params.get('recursive', False)

        try:
            resolved_path = self.path_mapper.resolve(path)
            full_path = resolved_path if os.path.isabs(resolved_path) else self.validator.sanitize_path(resolved_path)
        except Exception as e:
            return Observation(
                status='error',
                result=str(e),
                execution_time=0.0,
                metadata={'path': path}
            )

        if not os.path.exists(full_path):
            return Observation(
                status='error',
                result=f'文件或目录不存在: {path}',
                execution_time=0.0,
                metadata={'path': path}
            )

        if not confirmed:
            affected_count = self._count_affected_files(full_path, recursive)
            new_confirmation_id = self.confirmation_manager.create_pending(
                'file_delete', params
            )
            return Observation(
                status='confirmation_required',
                result=f'确定要删除《{path}》吗？该操作不可恢复。\n将影响 {affected_count} 个文件/目录。',
                execution_time=0.0,
                metadata={
                    'confirmation_id': new_confirmation_id,
                    'affected_count': affected_count,
                    'expires_in': 300
                }
            )

        if not confirmation_id:
            return Observation(
                status='error',
                result='缺少 confirmation_id，请提供确认 ID',
                execution_time=0.0,
                metadata={'path': path}
            )

        try:
            pending = self.confirmation_manager.confirm_and_consume(confirmation_id)
            if pending.params.get('path') != path:
                return Observation(
                    status='error',
                    result='参数不匹配，请重新发起删除请求',
                    execution_time=0.0,
                    metadata={'path': path}
                )

            start_time = time.time()
            affected_count = self._count_affected_files(full_path, recursive)

            if os.path.isfile(full_path):
                os.remove(full_path)
            elif os.path.isdir(full_path):
                if recursive:
                    import shutil
                    shutil.rmtree(full_path)
                else:
                    os.rmdir(full_path)

            execution_time = time.time() - start_time

            return Observation(
                status='success',
                result=f'已成功删除 {path}（共 {affected_count} 个文件/目录）',
                execution_time=execution_time,
                metadata={
                    'path': path,
                    'affected_count': affected_count
                }
            )
        except InvalidConfirmationError:
            return Observation(
                status='error',
                result='确认 ID 无效或已过期，请重新发起删除请求',
                execution_time=0.0,
                metadata={'path': path, 'expired': True}
            )

    def _execute_terminal(self, params: Dict, timeout: int) -> Observation:
        """Execute terminal command."""
        import subprocess
        import os
        import time

        command = params.get('command', '')
        working_dir = params.get('working_dir', '.')

        try:
            if not self.validator.validate_terminal_command(command):
                return Observation(
                    status='error',
                    result=f"Command '{command}' is not allowed for security reasons",
                    execution_time=0.0,
                    metadata={'command': command}
                )

            if working_dir != '.':
                resolved_dir = self.path_mapper.resolve(working_dir)
                safe_dir = resolved_dir if os.path.isabs(resolved_dir) else self.validator.sanitize_path(resolved_dir)
            else:
                safe_dir = '.'

            start_time = time.time()
            result = subprocess.run(
                command,
                shell=True,
                cwd=safe_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            execution_time = time.time() - start_time

            output = result.stdout
            if result.stderr:
                output += f"\n[stderr] {result.stderr}"

            truncated = len(output) > 10000
            if truncated:
                output = output[:9970] + '\n[Output truncated...]'

            return Observation(
                status='success' if result.returncode == 0 else 'error',
                result=output,
                execution_time=execution_time,
                metadata={
                    'exit_code': result.returncode,
                    'truncated': truncated,
                    'command': command
                }
            )
        except subprocess.TimeoutExpired:
            return Observation(
                status='error',
                result=f'Command timed out after {timeout} seconds',
                execution_time=timeout,
                metadata={'command': command, 'timeout': True}
            )
        except Exception as e:
            return Observation(
                status='error',
                result=str(e),
                execution_time=0.0,
                metadata={'command': command}
            )

    def _check_tool_permission(self, tool_name: str, params: Dict) -> 'PermissionResult':
        """Check permission for a tool operation."""
        path = params.get('path') or params.get('file') or params.get('working_dir')

        if path:
            try:
                resolved = self.path_mapper.resolve(path)
                return self.permission_manager.check_permission(tool_name, resolved)
            except Exception as e:
                from src.l5.permissions import PermissionResult
                return PermissionResult(
                    allowed=False,
                    mode=PermissionMode.READ_ONLY,
                    reason=f"Path resolution failed: {e}"
                )
        elif tool_name == 'terminal':
            command = params.get('command', '')
            return self.permission_manager.check_bash_permission(command)
        else:
            from src.l5.permissions import PermissionResult
            return PermissionResult(
                allowed=True,
                mode=PermissionMode.AUTO_APPLY,
                reason='No path to check'
            )

    def _execute_advanced_tool(self, tool_name: str, params: Dict, timeout: int) -> Observation:
        """Execute a tool using the advanced tool manager."""
        import asyncio
        import concurrent.futures

        async def _call():
            return await self.advanced_tools.call(tool_name, **params)

        try:
            # FastAPI already has a running event loop; run_until_complete would fail.
            # Run the coroutine in a separate thread with its own event loop.
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, _call())
                result = future.result(timeout=timeout)
        except RuntimeError:
            # No running loop — safe to use the current thread's event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_call())

        try:
            return Observation(
                status='success' if result.success else 'error',
                result=result.content or result.error or '',
                execution_time=0.0,
                metadata=result.data or {}
            )
        except Exception as e:
            return Observation(
                status='error',
                result=str(e),
                execution_time=0.0,
                metadata={}
            )

    def list_tools(self) -> List[Dict[str, Any]]:
        """Get all registered tool definitions."""
        tools = self.registry.list_tools()
        return [
            {
                'name': tool.name,
                'description': tool.description,
                'parameters': tool.parameters
            }
            for tool in tools
        ]

    def get_available_tools(self, user_permissions: List[str] = None) -> List[Dict]:
        """Get list of all available tools in OpenAI function calling format."""
        return self.get_tool_descriptions_openai_format()

    def get_tools_with_descriptions(self) -> str:
        """Get formatted tool descriptions for LLM context."""
        tools = self.registry.list_tools()
        return self.context_builder.build_tool_context(tools)

    def format_tools_for_llm(self) -> str:
        """Format tools in compact text format for LLM context."""
        tools = self.registry.list_tools()
        return self.context_builder.format_tools_for_llm(tools)

    def get_tool_descriptions_openai_format(self) -> List[Dict]:
        """Get tool descriptions in OpenAI function calling format."""
        tools = self.registry.list_tools()
        result = []
        for tool in tools:
            # JSON Schema properties must not contain 'required' key
            properties = {}
            for k, v in tool.parameters.items():
                prop = dict(v)
                prop.pop('required', None)
                properties[k] = prop

            result.append({
                'type': 'function',
                'function': {
                    'name': tool.name,
                    'description': tool.description,
                    'parameters': tool.parameters
                }
            })
        return result

    def register_tool(self, name: str, tool: Tool) -> None:
        """Register a new tool dynamically."""
        self.registry.register(name, tool)

    def unregister_tool(self, name: str) -> None:
        """Unregister a tool."""
        self.registry.unregister(name)

    def add_permission_rule(self, pattern: str, mode: str, tools: List[str] = None):
        """Add a permission rule dynamically."""
        from src.l5.permissions import PermissionRule, PermissionMode
        permission_mode = PermissionMode(mode)
        self.permission_manager.add_rule(
            PermissionRule(pattern, permission_mode, tools=tools or [])
        )

    def _count_affected_files(self, path: str, recursive: bool) -> int:
        """Count affected files/directories for deletion."""
        import os
        if os.path.isfile(path):
            return 1
        elif os.path.isdir(path):
            if recursive:
                count = 0
                for root, dirs, files in os.walk(path):
                    count += len(files) + len(dirs)
                return count + 1
            else:
                return 1
        return 0


class ToolExecutor:
    """L5 工具执行器

    实际调用工具实现。对代码/命令类工具委派至L6执行。
    """

    def __init__(self, runtime: RuntimeInterface = None):
        self.runtime = runtime or RuntimeEnvironment()

    def execute(self, tool: "Tool", params: Dict) -> "ExecutionResult":
        """执行工具

        Args:
            tool: 工具定义
            params: 工具参数

        Returns:
            ExecutionResult对象
        """
        # TODO: 实现工具执行，对python/javascript/bash/terminal委派至L6
        from src.core.models import ExecutionResult
        return ExecutionResult(
            exit_code=0,
            stdout="Tool execution placeholder",
            stderr="",
            execution_time=0.0
        )


class ResultFormatter:
    """L5 结果格式化器

    统一工具执行结果的输出格式。
    """

    MAX_RESULT_LENGTH = 10000

    def format(self, status: str, result: str, metadata: Dict = None) -> Dict:
        """格式化执行结果

        Args:
            status: 执行状态 success / error
            result: 结果字符串
            metadata: 附加元数据

        Returns:
            标准化的结果字典
        """
        formatted = result[:self.MAX_RESULT_LENGTH] if result else ""
        is_empty = not formatted.strip()
        return {
            "status": status,
            "result": formatted,
            "is_empty": is_empty,
            "metadata": metadata or {}
        }

    def handle_empty(self, tool_name: str) -> str:
        """处理空结果场景

        Args:
            tool_name: 工具名称

        Returns:
            空结果固定话术
        """
        if tool_name in ("file_read", "file_reader"):
            return "该文档为空"
        return "操作完成，无返回内容"

