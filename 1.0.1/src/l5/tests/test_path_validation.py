"""Tests for enhanced path validation."""
import pytest
import sys
sys.path.insert(0, 'src')

from src.l5.l5_tools import ParameterValidator, ValidationResult


class TestSandboxPathValidation:
    """Tests for sandbox path validation (TC-L5-PATH-002, TC-L5-PATH-003)."""

    def test_valid_documents_path_passes(self):
        """有效的 documents/ 路径通过验证"""
        # Arrange
        validator = ParameterValidator()

        # Act & Assert
        valid_paths = [
            "documents/file.txt",
            "documents/desktop/report.pdf",
            "documents/downloads/data.csv",
            "documents/subdir/nested/file.py"
        ]

        for path in valid_paths:
            result = validator.validate_sandbox_path(path)
            assert result.valid, f"Path '{path}' should be valid but got: {result.errors}"

    def test_missing_documents_prefix_fails(self):
        """TC-L5-PATH-002: 缺少 documents/ 前缀被拒绝"""
        # Arrange
        validator = ParameterValidator()

        # Act
        result = validator.validate_sandbox_path("file.txt")

        # Assert
        assert not result.valid
        assert "documents/" in result.errors[0].lower()

    def test_directory_traversal_fails(self):
        """TC-L5-PATH-003: 目录遍历攻击被拒绝"""
        # Arrange
        validator = ParameterValidator()

        # Act & Assert
        dangerous_paths = [
            "documents/../etc/passwd",
            "documents/subdir/../../../etc/shadow",
            "../windows/system32",
            "documents/..\\windows\\system32"
        ]

        for path in dangerous_paths:
            result = validator.validate_sandbox_path(path)
            assert not result.valid, f"Path '{path}' should be rejected"
            assert ".." in result.errors[0] or "traversal" in result.errors[0].lower()

    def test_absolute_path_fails(self):
        """绝对路径被拒绝"""
        # Arrange
        validator = ParameterValidator()

        # Act & Assert
        absolute_paths = [
            "/etc/passwd",
            "/usr/bin/python",
            "C:\\Windows\\system32",
            "D:\\data\\file.txt"
        ]

        for path in absolute_paths:
            result = validator.validate_sandbox_path(path)
            assert not result.valid, f"Absolute path '{path}' should be rejected"

    def test_path_safety_backward_compatible(self):
        """现有 is_path_safe() 方法保持向后兼容"""
        # Arrange
        validator = ParameterValidator()

        # Act & Assert - existing dangerous patterns
        dangerous = ["../../../etc/passwd", "..\\windows\\system32"]
        for path in dangerous:
            assert not validator.is_path_safe(path)

        safe = ["data/file.txt", "script.py"]
        for path in safe:
            assert validator.is_path_safe(path)
