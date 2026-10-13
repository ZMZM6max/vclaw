"""L5: ConfirmationManager - 二次确认管理器.

对高危操作判断是否需用户确认。负责评估操作风险等级、生成确认提示语、
管理挂起操作的生命周期，以及协调预扫描（dry-run）获取统计摘要。
"""

import os
import time
import uuid
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.exceptions import ConfirmationExpiredError, InvalidConfirmationError


# ========== 数据类 ==========


@dataclass
class AgentAction:
    """工具调用指令（来自L3）."""

    action: str
    action_input: Dict[str, Any]
    thought: Optional[str] = None


@dataclass
class PreScanSummary:
    """预扫描统计摘要."""

    file_count: int
    directory_count: int = 0
    total_size: int = 0
    file_types: List[str] = field(default_factory=list)
    affected_paths: List[str] = field(default_factory=list)


@dataclass
class ConfirmationState:
    """挂起确认状态."""

    confirmation_id: str
    status: str
    action: AgentAction
    user_id: str
    session_id: str
    prompt: str
    created_at: float
    expires_at: float
    pre_scan_summary: Optional[PreScanSummary] = None
    risk_level: str = "medium"


@dataclass
class ConfirmationResponse:
    """用户确认响应."""

    confirmation_id: str
    decision: str
    new_name: Optional[str] = None
    responded_at: float = field(default_factory=time.time)


@dataclass
class PendingOperation:
    """兼容旧测试的简化挂起记录."""

    confirmation_id: str
    tool_name: str
    params: Dict[str, Any]
    created_at: float = field(default_factory=time.time)


class MaxPendingExceeded(Exception):
    """用户挂起确认数量超过限制."""

    pass


# ========== ConfirmationManager ==========


class ConfirmationManager:
    """L5 层二次确认管理器.

    评估操作风险、触发二次确认、生成确认提示语、管理挂起状态、执行预扫描.
    """

    CONFIRMATION_EXPIRY_SECONDS = 300
    MAX_PENDING_PER_USER = 5
    PRE_SCAN_ENABLED = True
    PRE_SCAN_MAX_FILES = 100

    def __init__(
        self,
        ttl_seconds: Optional[int] = None,
        pre_scan_enabled: bool = True,
        permission_manager=None,
        bash_analyzer=None,
    ):
        self._ttl = ttl_seconds if ttl_seconds is not None else self.CONFIRMATION_EXPIRY_SECONDS
        self._pre_scan_enabled = pre_scan_enabled
        self._permission_manager = permission_manager
        self._bash_analyzer = bash_analyzer
        self._states: Dict[str, ConfirmationState] = {}
        self._lock = threading.RLock()

    # ----- 兼容旧测试的内部存储暴露 -----

    @property
    def _pending(self) -> Dict[str, ConfirmationState]:
        """兼容旧测试对 _pending 属性的访问."""
        return self._states

    # ----- 旧接口兼容层 -----

    def create_pending(self, tool_name: str, params: Dict[str, Any]) -> str:
        """旧接口：创建挂起确认，返回 confirmation_id."""
        action = AgentAction(action=tool_name, action_input=params)
        state = self.create_pending_confirmation(
            action=action,
            user_id=params.get("user_id", "default"),
            session_id=params.get("session_id", "default"),
            risk_level="high" if tool_name in ("file_delete", "terminal") else "medium",
        )
        return state.confirmation_id

    def get_pending(self, confirmation_id: str) -> Optional[PendingOperation]:
        """旧接口：获取有效的待确认操作."""
        self.cleanup_expired()
        state = self._states.get(confirmation_id)
        if state is None or state.status != "pending":
            return None
        if time.time() > state.expires_at:
            state.status = "expired"
            self._purge_finished()
            return None
        return PendingOperation(
            confirmation_id=state.confirmation_id,
            tool_name=state.action.action,
            params=state.action.action_input,
            created_at=state.created_at,
        )

    def confirm_and_consume(self, confirmation_id: str) -> PendingOperation:
        """旧接口：确认并消费记录."""
        self.cleanup_expired()
        state = self._states.get(confirmation_id)
        if state is None:
            raise InvalidConfirmationError(f"无效的 confirmation_id: {confirmation_id}")
        if state.status != "pending":
            raise InvalidConfirmationError(f"确认已被消费或过期: {confirmation_id}")
        if time.time() > state.expires_at:
            state.status = "expired"
            self._purge_finished()
            raise ConfirmationExpiredError(f"确认已过期: {confirmation_id}")
        state.status = "confirmed"
        return PendingOperation(
            confirmation_id=state.confirmation_id,
            tool_name=state.action.action,
            params=state.action.action_input,
            created_at=state.created_at,
        )

    # ----- XML 规范新方法 -----

    def needs_confirmation(
        self,
        action: AgentAction,
        user_permissions: Dict[str, Any],
        bash_analysis: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """评估操作是否需要二次确认.

        Args:
            action: 待评估的操作.
            user_permissions: 用户权限信息.
            bash_analysis: BashAnalyzer 分析结果（终端命令时提供）.

        Returns:
            是否需要二次确认.
        """
        tool = action.action
        params = action.action_input

        # TC-003: file_delete
        if tool == "file_delete":
            return True

        # TC-002: file_write 且目标文件已存在
        if tool == "file_write":
            path = params.get("path")
            if path and os.path.exists(path):
                return True

        # TC-001 / TC-005: terminal 写操作、网络操作、执行操作
        if tool == "terminal":
            if bash_analysis:
                cmd_type = bash_analysis.get("command_type", "")
                if cmd_type in ("WRITE", "NETWORK", "EXEC"):
                    return True
            command = params.get("command", "")
            if command and self._is_terminal_write_or_network(command):
                return True

        # TC-004: PermissionManager 标记为需确认
        if self._permission_manager:
            user_id = user_permissions.get("user_id", "default")
            perm_result = self._permission_manager.check_permission(user_id, tool, params)
            if perm_result.requires_confirmation:
                return True

        return False

    def generate_confirmation_prompt(
        self,
        action: AgentAction,
        pre_scan_summary: Optional[PreScanSummary] = None,
    ) -> str:
        """生成确认提示语.

        Args:
            action: 待确认的操作.
            pre_scan_summary: 预扫描统计摘要.

        Returns:
            向用户展示的确认提示语.
        """
        tool = action.action
        params = action.action_input

        if tool == "file_delete":
            path = params.get("path", "")
            if pre_scan_summary and pre_scan_summary.file_count > 1:
                file_types_str = ", ".join(pre_scan_summary.file_types) if pre_scan_summary.file_types else "多种类型"
                return (
                    f"{path} 里有 {pre_scan_summary.file_count} 个文件"
                    f"（{file_types_str}），确定要全部清空吗？[确认/取消]"
                )
            filename = os.path.basename(path) or path
            return f"确定要删除《{filename}》吗？删了就找不回了哦。[确认/取消]"

        if tool == "file_write":
            path = params.get("path", "")
            if path and os.path.exists(path):
                return "该位置已有同名文件，是否覆盖？[覆盖/重命名/取消]"
            filename = os.path.basename(path) or path
            return f"确定要写入《{filename}》吗？[确认/取消]"

        if tool == "terminal":
            command = params.get("command", "")
            if self._looks_like_network_command(command):
                return (
                    f"即将执行网络命令：{command}，"
                    f"这可能会访问外部网络，确定继续吗？[确认/取消]"
                )
            return (
                f"即将执行写操作命令：{command}，"
                f"这可能会修改系统文件，确定继续吗？[确认/取消]"
            )

        return f"操作《{tool}》需要二次确认，确定继续吗？[确认/取消]"

    def pre_scan(self, action: AgentAction) -> PreScanSummary:
        """高危操作前预扫描，获取统计摘要.

        第一版直接使用 os.walk / os.path 做元数据收集，不调用 ToolExecutor.

        Args:
            action: 待预扫描的操作.

        Returns:
            预扫描统计摘要.
        """
        path = action.action_input.get("path", "")
        if not path or not os.path.exists(path):
            return PreScanSummary(file_count=0)

        if os.path.isfile(path):
            size = os.path.getsize(path)
            ext = os.path.splitext(path)[1].lstrip(".")
            return PreScanSummary(
                file_count=1,
                directory_count=0,
                total_size=size,
                file_types=[ext] if ext else [],
                affected_paths=[path],
            )

        file_count = 0
        dir_count = 0
        total_size = 0
        file_types_set: set = set()
        affected_paths: List[str] = []

        for root, dirs, files in os.walk(path):
            dir_count += len(dirs)
            for f in files:
                if file_count >= self.PRE_SCAN_MAX_FILES:
                    break
                fp = os.path.join(root, f)
                try:
                    size = os.path.getsize(fp)
                    total_size += size
                    ext = os.path.splitext(f)[1].lstrip(".")
                    if ext:
                        file_types_set.add(ext)
                    affected_paths.append(fp)
                    file_count += 1
                except OSError:
                    continue
            if file_count >= self.PRE_SCAN_MAX_FILES:
                break

        return PreScanSummary(
            file_count=file_count,
            directory_count=dir_count,
            total_size=total_size,
            file_types=sorted(file_types_set),
            affected_paths=affected_paths[:10],
        )

    def create_pending_confirmation(
        self,
        action: AgentAction,
        user_id: str,
        session_id: str,
        risk_level: str,
    ) -> ConfirmationState:
        """创建挂起确认状态.

        Args:
            action: 待确认的操作.
            user_id: 操作用户ID.
            session_id: 会话ID.
            risk_level: 风险等级.

        Returns:
            创建的挂起确认状态.

        Raises:
            MaxPendingExceeded: 用户挂起确认数量超过限制.
        """
        with self._lock:
            user_pending = [
                s for s in self._states.values()
                if s.user_id == user_id and s.status == "pending"
            ]
            if len(user_pending) >= self.MAX_PENDING_PER_USER:
                raise MaxPendingExceeded(
                    f"用户 {user_id} 的挂起确认数量已达上限 ({self.MAX_PENDING_PER_USER})"
                )

            # 同一用户同一操作去重
            for s in user_pending:
                if s.action.action == action.action and s.action.action_input == action.action_input:
                    return s

            pre_scan_summary = None
            if self._pre_scan_enabled and risk_level in ("high", "critical"):
                pre_scan_summary = self.pre_scan(action)

            prompt = self.generate_confirmation_prompt(action, pre_scan_summary)
            cid = str(uuid.uuid4())
            now = time.time()
            state = ConfirmationState(
                confirmation_id=cid,
                status="pending",
                action=action,
                user_id=user_id,
                session_id=session_id,
                prompt=prompt,
                created_at=now,
                expires_at=now + self._ttl,
                pre_scan_summary=pre_scan_summary,
                risk_level=risk_level,
            )
            self._states[cid] = state
            return state

    def handle_response(self, response: ConfirmationResponse) -> ConfirmationState:
        """处理用户确认响应.

        Args:
            response: 用户确认响应.

        Returns:
            更新后的确认状态.

        Raises:
            InvalidConfirmationError: 确认ID无效或已被消费.
            ConfirmationExpiredError: 确认请求已过期.
        """
        self.cleanup_expired()
        with self._lock:
            state = self._states.get(response.confirmation_id)
            if state is None:
                raise InvalidConfirmationError(
                    f"无效的 confirmation_id: {response.confirmation_id}"
                )
            if state.status != "pending":
                raise InvalidConfirmationError(
                    f"确认已被处理: {response.confirmation_id}"
                )
            if time.time() > state.expires_at:
                state.status = "expired"
                self._purge_finished()
                raise ConfirmationExpiredError(
                    f"确认已过期: {response.confirmation_id}"
                )

            if response.decision == "confirm":
                state.status = "confirmed"
            elif response.decision == "cancel":
                state.status = "cancelled"
            elif response.decision == "rename":
                state.status = "confirmed"
                if response.new_name and "path" in state.action.action_input:
                    state.action.action_input["path"] = response.new_name
            else:
                raise InvalidConfirmationError(f"未知的决策: {response.decision}")

            return state

    def get_pending_confirmation(self, confirmation_id: str) -> Optional[ConfirmationState]:
        """获取挂起确认状态.

        Args:
            confirmation_id: 确认请求唯一标识.

        Returns:
            挂起确认状态，不存在或已过期返回 None.
        """
        self.cleanup_expired()
        state = self._states.get(confirmation_id)
        if state is None or state.status != "pending":
            return None
        if time.time() > state.expires_at:
            state.status = "expired"
            self._purge_finished()
            return None
        return state

    def expire_confirmation(self, confirmation_id: str) -> bool:
        """手动将确认标记为过期.

        Args:
            confirmation_id: 确认请求唯一标识.

        Returns:
            是否成功标记.
        """
        with self._lock:
            state = self._states.get(confirmation_id)
            if state and state.status == "pending":
                state.status = "expired"
                return True
            return False

    def cleanup_expired(self) -> int:
        """清理所有已过期的确认记录.

        Returns:
            清理的过期确认数量.
        """
        now = time.time()
        purged = 0
        with self._lock:
            for cid, state in list(self._states.items()):
                if state.status == "pending" and now > state.expires_at:
                    state.status = "expired"
            # 物理删除已结束（confirmed / cancelled / expired）的记录
            for cid in list(self._states.keys()):
                if self._states[cid].status in ("confirmed", "cancelled", "expired"):
                    del self._states[cid]
                    purged += 1
        return purged

    def _purge_finished(self) -> None:
        """内部方法：惰性清理已结束的记录."""
        with self._lock:
            for cid in list(self._states.keys()):
                if self._states[cid].status in ("confirmed", "cancelled", "expired"):
                    del self._states[cid]

    def _is_terminal_write_or_network(self, command: str) -> bool:
        """简单启发式判断终端命令是否涉及写操作或网络操作."""
        write_cmds = (
            "rm", "mv", "cp", "touch", "mkdir", "rmdir", "dd",
            "chmod", "chown", "chgrp", "ln", "truncate",
        )
        network_cmds = (
            "curl", "wget", "ssh", "scp", "sftp", "rsync",
            "nc", "netcat", "telnet", "ftp", "ping", "traceroute",
        )
        cmd_lower = command.strip().lower()
        for c in write_cmds:
            if cmd_lower.startswith(c + " ") or cmd_lower == c:
                return True
        for c in network_cmds:
            if cmd_lower.startswith(c + " ") or cmd_lower == c:
                return True
        return ">" in command or ">>" in command

    def _looks_like_network_command(self, command: str) -> bool:
        """判断终端命令是否属于网络操作类型."""
        network_cmds = (
            "curl", "wget", "ssh", "scp", "sftp", "rsync",
            "nc", "netcat", "telnet", "ftp", "ping", "traceroute",
            "host", "dig", "nslookup",
        )
        cmd_lower = command.strip().lower()
        for c in network_cmds:
            if cmd_lower.startswith(c + " ") or cmd_lower == c:
                return True
        return False
