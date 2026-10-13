"""L5: PermissionManager - 权限管理器.

管理用户对工具的访问权限，支持 Allowlist/Denylist 模式、
通配符规则匹配、优先级系统、审计日志和 confirm 动作标记.
"""

import fnmatch
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.exceptions import InvalidRuleError, PermissionDeniedError, RuleLimitExceeded


# ========== 数据类 ==========

@dataclass
class PermissionResult:
    """权限检查结果."""

    allowed: bool
    requires_confirmation: bool = False
    reason: Optional[str] = None
    matched_rule: Optional[str] = None


@dataclass
class PermissionRule:
    """权限规则定义."""

    id: str
    user_pattern: str
    tool_pattern: str
    action: str
    priority: int = 0
    description: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None

    def __post_init__(self):
        if self.action not in ("allow", "deny", "confirm"):
            raise InvalidRuleError(
                f"Rule action must be 'allow', 'deny' or 'confirm', got '{self.action}'"
            )


@dataclass
class UserPermissions:
    """用户权限集合."""

    user_id: str
    mode: str
    rules: List[PermissionRule] = field(default_factory=list)
    default_action: str = "deny"

    def __post_init__(self):
        if self.mode not in ("allowlist", "denylist"):
            raise InvalidRuleError(
                f"Permission mode must be 'allowlist' or 'denylist', got '{self.mode}'"
            )
        if self.default_action not in ("allow", "deny", "confirm"):
            raise InvalidRuleError(
                f"Default action must be 'allow', 'deny' or 'confirm', got '{self.default_action}'"
            )


@dataclass
class PermissionAuditLog:
    """权限审计日志条目."""

    timestamp: float
    user_id: str
    tool_name: str
    result: str
    rule_id: Optional[str] = None
    reason: Optional[str] = None


# ========== PermissionManager ==========

class PermissionManager:
    """L5 层权限管理器，负责工具访问控制.

    支持 Allowlist/Denylist 模式、通配符匹配、动态规则管理和审计日志.
    """

    DEFAULT_CONFIG = {
        "DEFAULT_MODE": "allowlist",
        "DEFAULT_ACTION": "deny",
        "AUDIT_LOG_ENABLED": True,
        "AUDIT_LOG_MAX_ENTRIES": 10000,
        "RULE_MAX_PER_USER": 100,
    }

    DEFAULT_POLICIES = {
        "anonymous_user": {
            "mode": "allowlist",
            "default_action": "deny",
            "rules": [
                ("search_web", "allow"),
                ("calculator", "allow"),
                ("terminal", "deny"),
                ("file_write", "deny"),
                ("file_delete", "deny"),
            ],
        },
        "standard_user": {
            "mode": "denylist",
            "default_action": "allow",
            "rules": [
                ("*", "allow"),
                ("terminal", "deny"),
                ("file_write", "confirm"),
                ("file_delete", "confirm"),
            ],
        },
        "admin_user": {
            "mode": "denylist",
            "default_action": "allow",
            "rules": [
                ("*", "allow"),
                ("file_delete", "confirm"),
            ],
        },
    }

    # 路径遍历模式（匹配后立即拒绝）
    PATH_TRAVERSAL_PATTERNS = (
        "..",
        "%2e%2e",
        "%2E%2E",
        "..%2f",
        "..%2F",
        "%2e%2e/",
        "%2E%2E/",
        "..\\",
        "%2e%2e\\",
    )

    # 敏感目录前缀（绝对路径访问需要拒绝）
    SENSITIVE_DIRECTORY_PREFIXES = (
        "/etc/",
        "/root/",
        "/sys/",
        "/proc/",
        "/boot/",
        "/dev/",
        "/var/log/",
        "/var/run/",
        "C:\\Windows\\",
        "C:\\Program Files\\",
        "C:\\Users\\Administrator\\",
    )

    # 涉及路径检查的工具及其路径字段
    PATH_FIELD_MAPPING = {
        "file_read": ("path",),
        "file_write": ("path",),
        "file_delete": ("path",),
        "file_search": ("directory",),
    }

    def __init__(self, tool_registry=None, config: Optional[Dict[str, Any]] = None):
        """初始化权限管理器.

        Args:
            tool_registry: 可选的 ToolRegistry 实例，用于后续扩展过滤能力.
            config: 配置字典，覆盖默认配置.
        """
        self._config = {**self.DEFAULT_CONFIG, **(config or {})}
        self._tool_registry = tool_registry
        self._user_permissions: Dict[str, UserPermissions] = {}
        self._global_rules: List[PermissionRule] = []
        self._audit_logs: deque = deque(maxlen=self._config["AUDIT_LOG_MAX_ENTRIES"])
        self._lock = threading.RLock()

    @staticmethod
    def _is_wildcard_pattern(pattern: str) -> bool:
        """判断模式是否包含通配符."""
        return any(c in pattern for c in "*?[")

    # ----- 核心权限检查 -----

    def check_permission(
        self,
        user_id: str,
        tool_name: str,
        action_params: Optional[Dict[str, Any]] = None,
    ) -> PermissionResult:
        """检查用户是否有权执行特定工具.

        Args:
            user_id: 用户唯一标识.
            tool_name: 工具名称.
            action_params: 操作参数，用于路径遍历检查等细粒度判断.

        Returns:
            PermissionResult: 权限检查结果.
        """
        # Step 1: 路径遍历与敏感目录检查（基于 action_params）
        if action_params:
            path_check = self._check_path_safety(tool_name, action_params)
            if path_check is not None:
                if self._config["AUDIT_LOG_ENABLED"]:
                    self._append_audit_log(user_id, tool_name, path_check)
                return path_check

        # Step 2: 规则匹配
        permissions = self.get_user_permissions(user_id)
        matched_rule = None
        result_action = permissions.default_action

        all_rules = list(permissions.rules)
        for rule in self._global_rules:
            if fnmatch.fnmatch(user_id, rule.user_pattern):
                all_rules.append(rule)

        sorted_rules = sorted(
            all_rules,
            key=lambda r: (r.priority, r.created_at),
            reverse=True,
        )

        for rule in sorted_rules:
            if self._match_rule(user_id, tool_name, rule):
                matched_rule = rule
                result_action = rule.action
                break

        if result_action == "allow":
            perm_result = PermissionResult(
                allowed=True,
                matched_rule=matched_rule.id if matched_rule else None,
            )
        elif result_action == "deny":
            perm_result = PermissionResult(
                allowed=False,
                reason="权限不足，操作被拒绝",
                matched_rule=matched_rule.id if matched_rule else None,
            )
        elif result_action == "confirm":
            perm_result = PermissionResult(
                allowed=True,
                requires_confirmation=True,
                matched_rule=matched_rule.id if matched_rule else None,
            )
        else:
            perm_result = PermissionResult(
                allowed=False,
                reason="未知的默认动作",
            )

        if self._config["AUDIT_LOG_ENABLED"]:
            self._append_audit_log(user_id, tool_name, perm_result)

        return perm_result

    def _check_path_safety(
        self, tool_name: str, action_params: Dict[str, Any]
    ) -> Optional[PermissionResult]:
        """检查工具参数中的路径是否安全.

        检测以下风险：
        1. 路径遍历：`..` 作为独立路径段出现（如 `../../etc`）
        2. 敏感目录：绝对路径指向 /etc、/root、/sys 等系统敏感目录

        Args:
            tool_name: 工具名称
            action_params: 工具参数字典

        Returns:
            若发现风险返回拒绝的 PermissionResult，否则返回 None
        """
        path_fields = self.PATH_FIELD_MAPPING.get(tool_name)
        if not path_fields:
            return None

        for field in path_fields:
            path_value = action_params.get(field)
            if not isinstance(path_value, str) or not path_value:
                continue

            normalized = path_value.replace("\\", "/")

            # 路径遍历检测：检查 .. 作为独立路径段
            parts = normalized.split("/")
            for part in parts:
                if part == "..":
                    return PermissionResult(
                        allowed=False,
                        reason=f"检测到路径遍历模式 '..' 在字段 '{field}'",
                    )

            # URL 编码的遍历检测
            for pattern in self.PATH_TRAVERSAL_PATTERNS:
                if pattern in path_value:
                    return PermissionResult(
                        allowed=False,
                        reason=f"检测到路径遍历模式 '{pattern}' 在字段 '{field}'",
                    )

            # 敏感目录检测：确保前缀匹配后紧跟 / 或结束
            normalized_lower = normalized.lower()
            for sensitive in self.SENSITIVE_DIRECTORY_PREFIXES:
                sensitive_norm = sensitive.replace("\\", "/").lower()
                if normalized_lower.startswith(sensitive_norm):
                    # 确保是完整前缀，不是 /etc 匹配 /etcetera
                    rest = normalized_lower[len(sensitive_norm):]
                    if rest == "" or rest.startswith("/"):
                        return PermissionResult(
                            allowed=False,
                            reason=f"禁止访问敏感目录 '{sensitive}'",
                        )

        return None

    def _match_rule(self, user_id: str, tool_name: str, rule: PermissionRule) -> bool:
        """检查单条规则是否匹配用户和工具.

        Args:
            user_id: 用户唯一标识.
            tool_name: 工具名称.
            rule: 权限规则.

        Returns:
            规则是否匹配.
        """
        if rule.expires_at is not None and rule.expires_at < time.time():
            return False
        user_match = fnmatch.fnmatch(user_id, rule.user_pattern)
        tool_match = fnmatch.fnmatch(tool_name, rule.tool_pattern)
        return user_match and tool_match

    # ----- 规则管理 -----

    def add_rule(self, rule: PermissionRule) -> None:
        """添加权限规则.

        Args:
            rule: 权限规则对象.

        Raises:
            InvalidRuleError: 规则格式非法.
            RuleLimitExceeded: 用户规则数量超过限制.
        """
        if not rule.id:
            rule.id = str(uuid.uuid4())

        if not isinstance(rule.user_pattern, str) or not rule.user_pattern:
            raise InvalidRuleError("Rule user_pattern must be a non-empty string")
        if not isinstance(rule.tool_pattern, str) or not rule.tool_pattern:
            raise InvalidRuleError("Rule tool_pattern must be a non-empty string")

        with self._lock:
            if self._is_wildcard_pattern(rule.user_pattern):
                self._global_rules.append(rule)
                self._global_rules.sort(
                    key=lambda r: (r.priority, r.created_at), reverse=True
                )
            else:
                permissions = self._user_permissions.setdefault(
                    rule.user_pattern,
                    UserPermissions(
                        user_id=rule.user_pattern,
                        mode=self._config["DEFAULT_MODE"],
                        default_action=self._config["DEFAULT_ACTION"],
                    ),
                )

                if len(permissions.rules) >= self._config["RULE_MAX_PER_USER"]:
                    raise RuleLimitExceeded(
                        f"User '{rule.user_pattern}' has reached the max rule limit "
                        f"({self._config['RULE_MAX_PER_USER']})"
                    )

                permissions.rules.append(rule)
                permissions.rules.sort(
                    key=lambda r: (r.priority, r.created_at), reverse=True
                )

    def remove_rule(self, rule_id: str) -> bool:
        """移除权限规则.

        Args:
            rule_id: 规则唯一标识.

        Returns:
            是否成功移除.
        """
        with self._lock:
            for user_id, permissions in self._user_permissions.items():
                for idx, rule in enumerate(permissions.rules):
                    if rule.id == rule_id:
                        permissions.rules.pop(idx)
                        return True
            for idx, rule in enumerate(self._global_rules):
                if rule.id == rule_id:
                    self._global_rules.pop(idx)
                    return True
            return False

    # ----- 用户权限配置 -----

    def set_user_permissions(self, user_id: str, permissions: UserPermissions) -> None:
        """设置用户完整权限配置.

        Args:
            user_id: 用户唯一标识.
            permissions: 用户权限配置.
        """
        with self._lock:
            permissions.rules.sort(key=lambda r: (r.priority, r.created_at), reverse=True)
            self._user_permissions[user_id] = permissions

    def get_user_permissions(self, user_id: str) -> UserPermissions:
        """获取用户权限配置.

        Args:
            user_id: 用户唯一标识.

        Returns:
            用户权限配置（不存在返回默认配置）.
        """
        with self._lock:
            if user_id in self._user_permissions:
                return self._user_permissions[user_id]

            default = UserPermissions(
                user_id=user_id,
                mode=self._config["DEFAULT_MODE"],
                default_action=self._config["DEFAULT_ACTION"],
            )
            self._user_permissions[user_id] = default
            return default

    def apply_default_policy(self, user_id: str, policy_name: str) -> None:
        """为用户应用预定义的默认权限策略.

        Args:
            user_id: 用户唯一标识.
            policy_name: 策略名称（anonymous_user / standard_user / admin_user）.

        Raises:
            InvalidRuleError: 未知策略名称.
        """
        if policy_name not in self.DEFAULT_POLICIES:
            raise InvalidRuleError(f"Unknown default policy: '{policy_name}'")

        policy = self.DEFAULT_POLICIES[policy_name]
        rules = []
        for tool_pattern, action in policy["rules"]:
            rules.append(
                PermissionRule(
                    id=str(uuid.uuid4()),
                    user_pattern=user_id,
                    tool_pattern=tool_pattern,
                    action=action,
                    priority=0,
                    description=f"Default policy: {policy_name}",
                )
            )

        permissions = UserPermissions(
            user_id=user_id,
            mode=policy["mode"],
            rules=rules,
            default_action=policy["default_action"],
        )
        self.set_user_permissions(user_id, permissions)

    # ----- 审计日志 -----

    def _append_audit_log(self, user_id: str, tool_name: str, result: PermissionResult) -> None:
        """追加审计日志条目（内部方法）."""
        audit_entry = PermissionAuditLog(
            timestamp=time.time(),
            user_id=user_id,
            tool_name=tool_name,
            result="allowed" if result.allowed else "denied",
            rule_id=result.matched_rule,
            reason=result.reason,
        )
        if result.requires_confirmation:
            audit_entry.result = "confirmed"
        self._audit_logs.append(audit_entry)

    def get_audit_logs(
        self,
        user_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
    ) -> List[PermissionAuditLog]:
        """查询权限审计日志.

        Args:
            user_id: 按用户过滤（可选）.
            start_time: 起始时间戳（可选）.
            end_time: 结束时间戳（可选）.
            limit: 返回最大条目数，默认 100.

        Returns:
            审计日志条目列表（按时间降序）.
        """
        results = []
        for log in reversed(self._audit_logs):
            if user_id is not None and log.user_id != user_id:
                continue
            if start_time is not None and log.timestamp < start_time:
                continue
            if end_time is not None and log.timestamp > end_time:
                continue
            results.append(log)
            if len(results) >= limit:
                break
        return results

    # ----- 工具列表过滤（扩展能力） -----

    def filter_allowed_tools(self, user_id: str, tool_names: List[str]) -> List[str]:
        """从工具列表中过滤出用户有权执行的工具.

        Args:
            user_id: 用户唯一标识.
            tool_names: 工具名称列表.

        Returns:
            用户被允许执行的工具名称列表（不含需 confirm 的标记）.
        """
        allowed = []
        for name in tool_names:
            result = self.check_permission(user_id, name)
            if result.allowed:
                allowed.append(name)
        return allowed
