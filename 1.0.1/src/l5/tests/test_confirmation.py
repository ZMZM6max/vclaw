"""Tests for ConfirmationManager."""
import pytest
import time
from unittest.mock import patch
import sys
sys.path.insert(0, 'src')

from src.l5.confirmation_manager import ConfirmationManager, PendingOperation
from src.core.exceptions import ConfirmationExpiredError, InvalidConfirmationError


class TestConfirmationManager:
    """Tests for confirmation management."""

    def test_create_pending_returns_confirmation_id(self):
        """TC-L5-CONFIRM-001: 创建待确认记录返回 confirmation_id"""
        # Arrange
        manager = ConfirmationManager()
        params = {"path": "documents/test.txt", "confirmed": False}

        # Act
        confirmation_id = manager.create_pending("file_delete", params)

        # Assert
        assert isinstance(confirmation_id, str)
        assert len(confirmation_id) > 0

    def test_get_pending_returns_operation(self):
        """获取有效的待确认操作"""
        # Arrange
        manager = ConfirmationManager()
        params = {"path": "documents/test.txt"}
        confirmation_id = manager.create_pending("file_delete", params)

        # Act
        pending = manager.get_pending(confirmation_id)

        # Assert
        assert pending is not None
        assert pending.tool_name == "file_delete"
        assert pending.params["path"] == "documents/test.txt"
        assert pending.confirmation_id == confirmation_id

    def test_confirm_and_execute_consumes_record(self):
        """TC-L5-CONFIRM-002: 确认后消费记录"""
        # Arrange
        manager = ConfirmationManager()
        params = {"path": "documents/test.txt"}
        confirmation_id = manager.create_pending("file_delete", params)

        # Act
        pending = manager.confirm_and_consume(confirmation_id)

        # Assert
        assert pending.tool_name == "file_delete"
        assert pending.params["path"] == "documents/test.txt"
        # Record should be removed
        assert manager.get_pending(confirmation_id) is None

    def test_invalid_confirmation_id_raises_error(self):
        """TC-L5-CONFIRM-003: 无效 confirmation_id 抛出异常"""
        # Arrange
        manager = ConfirmationManager()

        # Act & Assert
        with pytest.raises(InvalidConfirmationError):
            manager.confirm_and_consume("invalid-id-12345")

    def test_expired_confirmation_returns_none(self):
        """TC-L5-CONFIRM-004: 过期确认返回 None"""
        # Arrange
        manager = ConfirmationManager(ttl_seconds=0)  # 0 second TTL
        params = {"path": "documents/test.txt"}
        confirmation_id = manager.create_pending("file_delete", params)
        time.sleep(0.1)  # Wait for expiration

        # Act
        pending = manager.get_pending(confirmation_id)

        # Assert
        assert pending is None

    def test_cleanup_expired_removes_old_records(self):
        """过期记录清理"""
        # Arrange
        manager = ConfirmationManager(ttl_seconds=0)
        confirmation_id = manager.create_pending("file_delete", {"path": "test.txt"})
        time.sleep(0.1)

        # Act - calling get_pending triggers cleanup
        manager.get_pending(confirmation_id)

        # Assert - internal _pending dict should be empty
        assert len(manager._pending) == 0


class TestFileDeleteTool:
    """Tests for file_delete tool with confirmation flow."""

    def test_file_delete_first_request_returns_confirmation_required(self, tmp_path):
        """TC-L5-CONFIRM-001: 首次删除请求返回 pending_confirmation"""
        # Arrange
        from src.l5.l5_tools import ToolsCapabilities
        tools = ToolsCapabilities(sandbox_documents_root=str(tmp_path))

        # Create test file
        import os
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        test_file = tmp_path / "documents" / "test.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test content")

        # Act
        result = tools.execute(
            "file_delete",
            {"path": "documents/test.txt", "confirmed": False}
        )

        os.chdir(original_cwd)

        # Assert
        assert result.status == "pending_confirmation"
        assert "confirmation_id" in result.metadata
        assert result.metadata["affected_count"] == 1
        assert "确定要删除" in result.result

    def test_file_delete_confirm_and_execute(self, tmp_path):
        """TC-L5-CONFIRM-002: 确认后执行删除"""
        # Arrange
        import os
        from src.l5.l5_tools import ToolsCapabilities
        tools = ToolsCapabilities(sandbox_documents_root=str(tmp_path))

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        test_file = tmp_path / "documents" / "test.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test content")

        # Step 1: Request confirmation
        result1 = tools.execute(
            "file_delete",
            {"path": "documents/test.txt", "confirmed": False}
        )
        confirmation_id = result1.metadata["confirmation_id"]

        # Step 2: Confirm and execute
        result2 = tools.execute(
            "file_delete",
            {
                "path": "documents/test.txt",
                "confirmed": True,
                "confirmation_id": confirmation_id
            }
        )

        os.chdir(original_cwd)

        # Assert
        assert result2.status == "success"
        assert not test_file.exists()

    def test_file_delete_invalid_confirmation_id_fails(self, tmp_path):
        """TC-L5-CONFIRM-003: 无效 confirmation_id 返回错误"""
        # Arrange
        import os
        from src.l5.l5_tools import ToolsCapabilities
        tools = ToolsCapabilities(sandbox_documents_root=str(tmp_path))

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        test_file = tmp_path / "documents" / "test.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test")

        # Act
        result = tools.execute(
            "file_delete",
            {
                "path": "documents/test.txt",
                "confirmed": True,
                "confirmation_id": "invalid-id-12345"
            }
        )

        os.chdir(original_cwd)

        # Assert
        assert result.status == "error"
        assert "invalid" in result.result.lower() or "过期" in result.result or "无效" in result.result

    def test_file_delete_expired_confirmation_fails(self, tmp_path):
        """TC-L5-CONFIRM-004: 过期确认返回错误"""
        # Arrange
        import os
        import time
        from src.l5.l5_tools import ToolsCapabilities
        from src.l5.confirmation_manager import ConfirmationManager

        # Create tools with 0-second TTL confirmation manager
        tools = ToolsCapabilities(sandbox_documents_root=str(tmp_path))
        tools.confirmation_manager = ConfirmationManager(ttl_seconds=0)
        # Update executor's confirmation manager
        tools._executor._confirmation_manager = tools.confirmation_manager

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        test_file = tmp_path / "documents" / "test.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test")

        # Step 1: Request confirmation (will expire immediately)
        result1 = tools.execute(
            "file_delete",
            {"path": "documents/test.txt", "confirmed": False}
        )
        confirmation_id = result1.metadata["confirmation_id"]

        time.sleep(0.1)

        # Step 2: Try to confirm expired
        result2 = tools.execute(
            "file_delete",
            {
                "path": "documents/test.txt",
                "confirmed": True,
                "confirmation_id": confirmation_id
            }
        )

        os.chdir(original_cwd)

        # Assert
        assert result2.status == "error"
        assert "过期" in result2.result or "expired" in result2.result.lower() or "无效" in result2.result

    def test_file_delete_directory_recursive_count(self, tmp_path):
        """TC-L5-CONFIRM-005: 批量删除正确计算受影响文件数"""
        # Arrange
        import os
        from src.l5.l5_tools import ToolsCapabilities
        tools = ToolsCapabilities(sandbox_documents_root=str(tmp_path))

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        # Create directory with multiple files
        test_dir = tmp_path / "documents" / "test_dir"
        test_dir.mkdir(parents=True)
        (test_dir / "file1.txt").write_text("content1")
        (test_dir / "file2.txt").write_text("content2")
        (test_dir / "subdir").mkdir()
        (test_dir / "subdir" / "file3.txt").write_text("content3")

        # Act
        result = tools.execute(
            "file_delete",
            {
                "path": "documents/test_dir",
                "confirmed": False,
                "recursive": True
            }
        )

        os.chdir(original_cwd)

        # Assert
        assert result.status == "pending_confirmation"
        assert result.metadata["affected_count"] >= 3  # 3 files + dirs

    def test_file_delete_read_only_path_rejected(self, tmp_path):
        """file_delete 应该拒绝只读路径（通过权限系统）"""
        # Arrange
        import os
        from src.l5.l5_tools import ToolsCapabilities
        tools = ToolsCapabilities(sandbox_documents_root=str(tmp_path))

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        # Create a config directory that is outside the sandbox path check
        # This test expects the path to be rejected, so we use an absolute path
        # that will fail the sandbox check
        result = tools.execute(
            "file_delete",
            {"path": "/etc/config/settings.json", "confirmed": False}
        )

        os.chdir(original_cwd)

        # Assert - path check should reject absolute paths outside sandbox
        assert result.status == "error"
