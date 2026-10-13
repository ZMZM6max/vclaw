"""L5: ToolExecutor - 工具执行器.

负责实际调用工具实现并管理执行生命周期。
对代码/命令类工具（python_repl、terminal、javascript）委派至L6执行，
对内部工具（file_read、search_web等）在L5层直接处理。
ToolExecutor是L5层的执行核心，协调ParameterValidator、PermissionManager、
ConfirmationManager完成完整执行链。
"""

import ast
import math
import operator
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

from src.core.exceptions import ExecutionTimeoutError
from src.core.models import ExecutionResult


# ========== 数据结构 ==========


@dataclass
class L5ExecutionResult:
    """工具执行结果（L5层内部使用）."""

    status: str
    result: str
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionContext:
    """执行上下文，携带执行所需的全部信息."""

    tool: Any
    params: Dict[str, Any]
    user_id: str
    session_id: str
    timeout: int = 30
    raw_user_payload: Optional[Dict[str, Any]] = None


@dataclass
class CheckDetail:
    """单项检查详情."""

    check_name: str
    passed: bool
    message: Optional[str] = None


@dataclass
class PreCheckResult:
    """前置检查结果."""

    passed: bool
    checks: List[CheckDetail] = field(default_factory=list)


# ========== ToolExecutor ==========


class ToolExecutor:
    """L5层工具执行器.

    核心交付：
    - 工具执行路由（内部执行 vs L6委派）
    - 执行超时控制（默认30s，最大300s）
    - 前置检查（文件存在性检查、路径安全检查）
    - 异常捕获与包装
    """

    DEFAULT_TIMEOUT = 30
    MAX_TIMEOUT = 300
    MIN_TIMEOUT = 1
    TIMEOUT_GRACE_PERIOD = 5
    ENABLE_L6_DELEGATION = True
    L6_FALLBACK_ON_ERROR = False
    SANDBOX_ROOT = "/sandbox"
    MAX_RESULT_LENGTH = 10000

    # 每个工具的默认超时和最大超时
    TOOL_TIMEOUT_OVERRIDES = {
        "python_repl": {"default": 30, "max": 300},
        "terminal": {"default": 30, "max": 300},
        "search_web": {"default": 30, "max": 60},
        "file_read": {"default": 10, "max": 30},
        "file_write": {"default": 10, "max": 30},
        "file_delete": {"default": 10, "max": 30},
        "calculator": {"default": 5, "max": 10},
        "file_search": {"default": 15, "max": 60},
    }

    def __init__(
        self,
        tool_registry=None,
        parameter_validator=None,
        permission_manager=None,
        confirmation_manager=None,
        bash_analyzer=None,
        result_formatter=None,
        runtime=None,
    ):
        self._tool_registry = tool_registry
        self._parameter_validator = parameter_validator
        self._permission_manager = permission_manager
        self._confirmation_manager = confirmation_manager
        self._bash_analyzer = bash_analyzer
        self._result_formatter = result_formatter
        self._runtime = runtime  # L6 RuntimeInterface
        self._thread_pool = ThreadPoolExecutor(max_workers=4)

    # ----- 公共接口 -----

    def execute(
        self,
        tool: Union[str, Any],
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> L5ExecutionResult:
        """执行工具.

        执行链：
        1. 获取工具定义（若tool为名称字符串）
        2. 参数验证
        3. 权限检查
        4. 前置检查（路径安全、存在性检查）
        5. Bash风险分析（terminal工具）
        6. 二次确认判断
        7. 路由执行（内部执行 vs L6委派）
        8. 返回结果
        """
        start_time = time.time()

        # Step 1: 获取工具定义
        if isinstance(tool, str):
            tool_name = tool
            tool = self._get_tool_from_registry(tool_name)
            if tool is None:
                return self._error_result(f"工具 '{tool_name}' 不存在", 0.0)

        context.tool = tool

        # Step 2: 参数验证
        validated = self._validate_params(tool, params, context)
        if isinstance(validated, L5ExecutionResult):
            return validated
        params = validated
        context.params = params

        # Step 3: 权限检查
        perm_error = self._check_permission(tool, params, context)
        if isinstance(perm_error, L5ExecutionResult):
            return perm_error

        # Step 4: 前置检查
        precheck = self._run_pre_checks(tool, params, context)
        if not precheck.passed:
            error_msgs = [
                c.message for c in precheck.checks if not c.passed and c.message
            ]
            return self._error_result("; ".join(error_msgs), time.time() - start_time)

        # 4.1: existence_check 路由 - 若目标已存在，强制走确认流程
        existence_detected = any(
            c.check_name == "existence_check" and c.passed and "已存在" in (c.message or "")
            for c in precheck.checks
        )

        # Step 5: Bash风险分析（terminal工具）
        bash_analysis = None
        if tool.name == "terminal" and self._bash_analyzer:
            command = params.get("command", "")
            bash_analysis = self._bash_analyzer.analyze(command)

        # Step 5.5: 处理已确认操作（如果提供了confirmation_id）
        confirmed = params.get("confirmed", False)
        confirmation_id = params.get("confirmation_id")
        if confirmed and confirmation_id and self._confirmation_manager:
            try:
                self._confirmation_manager.confirm_and_consume(confirmation_id)
                # 验证通过，跳过确认流程继续执行
            except Exception as e:
                return self._error_result(str(e), time.time() - start_time)
        else:
            # Step 6: 二次确认判断
            confirm_result = self._check_confirmation(
                tool, params, context, bash_analysis, existence_detected
            )
            if isinstance(confirm_result, L5ExecutionResult):
                return confirm_result

        # Step 7: 执行路由
        effective_timeout = self._resolve_timeout(tool, context.timeout)

        try:
            if tool.handler == "L6_DELEGATE":
                if not self.ENABLE_L6_DELEGATION:
                    return self._error_result(
                        "L6委派已禁用", time.time() - start_time
                    )
                result = self._execute_in_l6(
                    tool, params, context, effective_timeout
                )
            elif callable(tool.handler):
                result = self._execute_internal(
                    tool, params, context, effective_timeout
                )
            else:
                # handler为None或内部工具，使用内部handler映射
                result = self._execute_by_name(
                    tool.name, params, effective_timeout
                )
        except ExecutionTimeoutError as e:
            return self._error_result(
                f"执行超时: {str(e)}",
                time.time() - start_time,
                error_type="timeout",
            )
        except Exception as e:
            return self._error_result(
                f"执行失败: {str(e)}",
                time.time() - start_time,
                error_type="execution_error",
            )

        return result

    def run_with_timeout(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Any:
        """带超时的函数执行包装器.

        实现两阶段超时控制：
        1. 主超时阶段：等待 timeout 秒，期望函数正常完成
        2. 优雅期阶段：超时后再等待 TIMEOUT_GRACE_PERIOD 秒，
           允许任务做清理工作（关闭文件、释放资源等）
        3. 强制终止阶段：优雅期结束仍未完成则取消 future 并抛出超时异常

        对于 L6 委派的子进程任务，L6 RuntimeInterface 应实现真正的
        SIGTERM/SIGKILL 信号控制；本方法用于 L5 内部工具的合作式取消。
        """
        kwargs = kwargs or {}
        future = self._thread_pool.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError:
            # 主超时：进入优雅期，让任务有机会自行清理
            try:
                return future.result(timeout=self.TIMEOUT_GRACE_PERIOD)
            except FutureTimeoutError:
                # 优雅期结束：强制取消 future（SIGKILL 等价）
                future.cancel()
                raise ExecutionTimeoutError(
                    f"函数执行超过 {timeout} 秒（含 {self.TIMEOUT_GRACE_PERIOD} 秒优雅期）"
                )

    # ----- 私有执行方法 -----

    def _execute_internal(
        self,
        tool: Any,
        params: Dict[str, Any],
        context: ExecutionContext,
        timeout: int,
    ) -> L5ExecutionResult:
        """执行内部工具（非L6委派）."""
        start_time = time.time()

        result = self.run_with_timeout(
            tool.handler, (params,), timeout=timeout
        )

        execution_time = time.time() - start_time
        return self._wrap_handler_result(result, tool.name, execution_time)

    def _execute_in_l6(
        self,
        tool: Any,
        params: Dict[str, Any],
        context: ExecutionContext,
        timeout: int,
    ) -> L5ExecutionResult:
        """委派至L6执行（沙盒隔离）."""
        if self._runtime is None:
            return self._error_result("L6 RuntimeInterface 未配置", 0.0)

        start_time = time.time()

        try:
            if tool.name == "python_repl":
                code = params.get("code", "")
                l6_result = self._runtime.run_code(
                    "python", code, timeout=timeout
                )
            elif tool.name == "terminal":
                command = params.get("command", "")
                l6_result = self._runtime.run_command(
                    command, timeout=timeout
                )
            elif tool.name == "javascript":
                code = params.get("code", "")
                l6_result = self._runtime.run_code(
                    "javascript", code, timeout=timeout
                )
            else:
                return self._error_result(
                    f"不支持的L6委派工具: {tool.name}", 0.0
                )
        except Exception as e:
            return self._error_result(
                f"L6执行失败: {str(e)}", time.time() - start_time
            )

        execution_time = time.time() - start_time
        return self._convert_l6_result(l6_result, execution_time)

    # ----- 内部工具handler -----

    def _execute_by_name(
        self,
        tool_name: str,
        params: Dict[str, Any],
        timeout: int,
    ) -> L5ExecutionResult:
        """通过工具名执行内部handler."""
        handlers: Dict[str, Callable] = {
            "file_read": self._handle_file_read,
            "file_write": self._handle_file_write,
            "file_delete": self._handle_file_delete,
            "file_search": self._handle_file_search,
            "search_web": self._handle_search_web,
            "calculator": self._handle_calculator,
        }

        handler = handlers.get(tool_name)
        if handler is None:
            return self._error_result(
                f"工具 '{tool_name}' 没有可用的执行器", 0.0
            )

        start_time = time.time()
        try:
            result = self.run_with_timeout(handler, (params,), timeout=timeout)
            execution_time = time.time() - start_time
            if isinstance(result, L5ExecutionResult):
                return result
            return self._wrap_handler_result(result, tool_name, execution_time)
        except ExecutionTimeoutError:
            raise
        except Exception as e:
            execution_time = time.time() - start_time
            return self._error_result(str(e), execution_time)

    def _handle_file_read(self, params: Dict[str, Any]) -> str:
        path = params.get("path", "")
        if not path:
            raise ValueError("路径不能为空")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError as e:
            raise ValueError(f"文件不是有效的UTF-8文本文件: {e}")

    def _handle_file_write(self, params: Dict[str, Any]) -> str:
        path = params.get("path", "")
        content = params.get("content", "")
        if not path:
            raise ValueError("路径不能为空")
        parent_dir = os.path.dirname(path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"已写入文件: {path}"

    def _handle_file_delete(self, params: Dict[str, Any]) -> str:
        path = params.get("path", "")
        if not path:
            raise ValueError("路径不能为空")
        # 符号链接单独处理：避免误删链接目标目录
        if os.path.islink(path):
            os.remove(path)
        elif os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
        else:
            os.remove(path)
        return f"已删除: {path}"

    def _handle_file_search(self, params: Dict[str, Any]) -> List[str]:
        keyword = params.get("keyword", "")
        directory = params.get("directory", ".")
        if not keyword:
            raise ValueError("搜索关键词不能为空")
        results = []
        for root, dirs, files in os.walk(directory):
            for f in files:
                if keyword.lower() in f.lower():
                    results.append(os.path.join(root, f))
        return results

    def _handle_search_web(self, params: Dict[str, Any]) -> str:
        query = params.get("query", "")
        return f"搜索 '{query}' 的结果（暂无实时数据）"

    def _handle_calculator(self, params: Dict[str, Any]) -> str:
        expression = params.get("expression", "")
        if not expression:
            raise ValueError("表达式不能为空")
        result = self._safe_eval(expression)
        return str(result)

    # 允许调用的数学函数（均来自 math 模块）
    ALLOWED_MATH_FUNCTIONS = {
        "sin", "cos", "tan", "asin", "acos", "atan",
        "sqrt", "log", "log10", "exp", "abs", "round",
        "ceil", "floor", "trunc", "pow", "max", "min",
        "pi", "e",
    }

    def _safe_eval(self, expression: str) -> Any:
        """安全地评估数学表达式.

        支持基本运算、常用数学函数（sin/cos/sqrt/log 等）和常量（pi/e）。
        """
        allowed_operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
        }

        def _eval(node):
            if hasattr(ast, "Num") and isinstance(node, ast.Num):
                return node.n
            elif hasattr(ast, "Constant") and isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return node.value
                raise ValueError(f"不支持的常量类型: {type(node.value)}")
            elif isinstance(node, ast.BinOp):
                op = allowed_operators.get(type(node.op))
                if op is None:
                    raise ValueError(
                        f"不支持的运算符: {type(node.op).__name__}"
                    )
                return op(_eval(node.left), _eval(node.right))
            elif isinstance(node, ast.UnaryOp):
                op = allowed_operators.get(type(node.op))
                if op is None:
                    raise ValueError(
                        f"不支持的运算符: {type(node.op).__name__}"
                    )
                return op(_eval(node.operand))
            elif isinstance(node, ast.Call):
                # 函数调用：仅允许白名单中的 math 函数
                if not isinstance(node.func, ast.Name):
                    raise ValueError("不支持的函数调用形式")
                func_name = node.func.id
                if func_name not in self.ALLOWED_MATH_FUNCTIONS:
                    raise ValueError(f"不支持的函数: {func_name}")
                # 计算参数
                args = [_eval(arg) for arg in node.args]
                # 常量 pi / e 作为无参调用也允许
                if func_name == "pi":
                    return math.pi
                if func_name == "e":
                    return math.e
                func = getattr(math, func_name, None)
                if func is None:
                    # abs/round/max/min/pow 是内置函数
                    func = getattr(__builtins__, func_name, None)
                if func is None:
                    raise ValueError(f"无法解析函数: {func_name}")
                return func(*args)
            elif isinstance(node, ast.Name):
                # 常量引用：pi / e
                if node.id == "pi":
                    return math.pi
                if node.id == "e":
                    return math.e
                raise ValueError(f"不支持的变量引用: {node.id}")
            elif isinstance(node, ast.Expression):
                return _eval(node.body)
            else:
                raise ValueError(
                    f"不支持的表达式类型: {type(node).__name__}"
                )

        tree = ast.parse(expression, mode="eval")
        return _eval(tree)

    # ----- 辅助方法 -----

    def _get_tool_from_registry(self, name: str) -> Optional[Any]:
        if self._tool_registry is None:
            return None
        return self._tool_registry.get(name)

    def _validate_params(
        self,
        tool: Any,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> Union[Dict[str, Any], L5ExecutionResult]:
        if self._parameter_validator is None:
            return params
        validation_result = self._parameter_validator.validate(
            params,
            tool.parameters,
            getattr(context, "raw_user_payload", None),
            tool.name,
        )
        if not validation_result.is_valid:
            error_msg = "; ".join(
                [e.message for e in validation_result.errors]
            )
            return self._error_result(error_msg, 0.0)
        return validation_result.sanitized_params or params

    def _check_permission(
        self,
        tool: Any,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> Optional[L5ExecutionResult]:
        if self._permission_manager is None:
            return None
        perm_result = self._permission_manager.check_permission(
            context.user_id, tool.name, params
        )
        if not perm_result.allowed:
            return self._error_result("权限不足", 0.0)
        return None

    def _run_pre_checks(
        self,
        tool: Any,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> PreCheckResult:
        checks = []

        # path_in_sandbox 检查
        if tool.name in ("file_read", "file_write", "file_delete", "file_search"):
            path_fields = ["path", "directory"]
            for field in path_fields:
                if field in params and isinstance(params[field], str):
                    path = params[field]
                    passed = self._is_path_in_sandbox(path)
                    checks.append(
                        CheckDetail(
                            check_name=f"path_in_sandbox:{field}",
                            passed=passed,
                            message=None
                            if passed
                            else f"文件路径超出允许范围: {path}",
                        )
                    )

        # existence_check (file_write)
        if tool.name == "file_write":
            path = params.get("path", "")
            if path:
                exists = os.path.exists(path)
                checks.append(
                    CheckDetail(
                        check_name="existence_check",
                        passed=True,
                        message=f"目标路径{'已存在' if exists else '不存在'}",
                    )
                )

        passed = all(c.passed for c in checks)
        return PreCheckResult(passed=passed, checks=checks)

    def _is_path_in_sandbox(self, path: str) -> bool:
        """检查路径是否在沙盒范围内."""
        if not path:
            return False
        if self.SANDBOX_ROOT:
            sandbox = os.path.abspath(self.SANDBOX_ROOT)
            try:
                target = os.path.abspath(path)
                return target.startswith(sandbox + os.sep) or target == sandbox
            except Exception:
                return False
        return True

    def _check_confirmation(
        self,
        tool: Any,
        params: Dict[str, Any],
        context: ExecutionContext,
        bash_analysis: Any = None,
        existence_detected: bool = False,
    ) -> Optional[L5ExecutionResult]:
        if self._confirmation_manager is None:
            return None

        from src.l5.confirmation_manager import AgentAction

        action = AgentAction(action=tool.name, action_input=params)
        user_permissions = {"user_id": context.user_id}

        bash_analysis_dict = None
        if bash_analysis:
            bash_analysis_dict = {
                "command_type": getattr(bash_analysis, "command_type", ""),
                "risk_level": getattr(
                    bash_analysis, "risk_level", "medium"
                ),
            }

        needs_confirm = self._confirmation_manager.needs_confirmation(
            action, user_permissions, bash_analysis_dict
        )

        # existence_check 触发：file_write 目标已存在时强制确认
        if existence_detected:
            needs_confirm = True

        if needs_confirm:
            if existence_detected:
                # 文件覆盖风险高，使用 high 风险等级
                risk_level = "high"
            elif bash_analysis_dict:
                risk_level = bash_analysis_dict.get("risk_level", "medium")
            elif tool.name == "file_delete":
                risk_level = "high"
            else:
                risk_level = "medium"
            state = self._confirmation_manager.create_pending_confirmation(
                action=action,
                user_id=context.user_id,
                session_id=context.session_id,
                risk_level=risk_level,
            )
            metadata = {
                "tool_name": tool.name,
                "params": params,
                "confirmation_id": state.confirmation_id,
            }
            if existence_detected:
                metadata["existence_detected"] = True
            if state.pre_scan_summary:
                metadata["affected_count"] = state.pre_scan_summary.file_count
            return L5ExecutionResult(
                status="pending_confirmation",
                result=state.prompt,
                execution_time=0.0,
                metadata=metadata,
            )

        return None

    def _resolve_timeout(self, tool: Any, requested_timeout: Optional[int]) -> int:
        """解析有效超时时间.

        根据工具类型返回合法的超时值，确保在[MIN_TIMEOUT, max]范围内。
        """
        overrides = self.TOOL_TIMEOUT_OVERRIDES.get(tool.name, {})
        default = overrides.get("default", self.DEFAULT_TIMEOUT)
        max_timeout = overrides.get("max", self.MAX_TIMEOUT)

        if requested_timeout is None:
            timeout = default
        else:
            timeout = requested_timeout

        timeout = max(self.MIN_TIMEOUT, min(timeout, max_timeout))
        return timeout

    def _convert_l6_result(
        self,
        l6_result: ExecutionResult,
        execution_time: float,
    ) -> L5ExecutionResult:
        """将L6 ExecutionResult转换为L5 ExecutionResult."""
        status = "success" if l6_result.exit_code == 0 else "error"
        result = l6_result.stdout
        if status == "error" and l6_result.stderr:
            result = l6_result.stderr

        # 优先使用L6返回的execution_time（如果有效）
        effective_execution_time = getattr(l6_result, "execution_time", 0.0) or execution_time

        # 截断结果
        if len(result) > self.MAX_RESULT_LENGTH:
            indicator = "\n...[结果已截断]"
            available = max(0, self.MAX_RESULT_LENGTH - len(indicator))
            result = result[:available] + indicator

        return L5ExecutionResult(
            status=status,
            result=result,
            execution_time=effective_execution_time,
            metadata={
                "exit_code": l6_result.exit_code,
                "stderr": l6_result.stderr,
                "resource_usage": l6_result.resource_usage,
            },
        )

    def _wrap_handler_result(
        self,
        result: Any,
        tool_name: str,
        execution_time: float,
    ) -> L5ExecutionResult:
        """将handler返回值包装为L5ExecutionResult."""
        if isinstance(result, L5ExecutionResult):
            return result

        result_str = str(result) if result is not None else ""

        # 截断
        if len(result_str) > self.MAX_RESULT_LENGTH:
            indicator = "\n...[结果已截断]"
            available = max(0, self.MAX_RESULT_LENGTH - len(indicator))
            result_str = result_str[:available] + indicator

        return L5ExecutionResult(
            status="success",
            result=result_str,
            execution_time=execution_time,
            metadata={"tool_name": tool_name},
        )

    def _error_result(
        self,
        message: str,
        execution_time: float,
        error_type: str = "execution_error",
    ) -> L5ExecutionResult:
        return L5ExecutionResult(
            status="error",
            result=message,
            execution_time=execution_time,
            metadata={"error_type": error_type},
        )
