"""Path mapper for resolving user-friendly paths to real OS paths."""
import os
from pathlib import Path
from typing import Dict, Optional


class PathMappingError(Exception):
    """Raised when a path cannot be resolved."""
    pass


class PathMapper:
    """Maps natural language paths to real operating system paths.

    Examples:
        >>> mapper = PathMapper()
        >>> mapper.resolve("桌面/文件.txt")
        'C:\\Users\\<user>\\Desktop\\文件.txt'
        >>> mapper.resolve("documents/sandbox/file.txt")
        'E:\\...\\vclaw\\documents\\sandbox\\file.txt'
    """

    ALIASES: Dict[str, str] = {
        "桌面": "~/Desktop",
        "desktop": "~/Desktop",
        "下载": "~/Downloads",
        "downloads": "~/Downloads",
        "文档": "~/Documents",
        "documents": "~/Documents",
        "图片": "~/Pictures",
        "pictures": "~/Pictures",
        "音乐": "~/Music",
        "music": "~/Music",
        "视频": "~/Videos",
        "videos": "~/Videos",
    }

    def __init__(self, sandbox_documents_root: Optional[str] = None):
        """Initialize PathMapper.

        Args:
            sandbox_documents_root: Base directory for 'documents/' backward compatibility.
                                   Defaults to project root.
        """
        if sandbox_documents_root:
            self.sandbox_root = Path(sandbox_documents_root).resolve()
        else:
            # Default to project root (parent of src/)
            self.sandbox_root = Path(__file__).resolve().parent.parent.parent

    def resolve(self, path: str) -> str:
        """Resolve a user-friendly path to a real OS path.

        Resolution order:
        1. Absolute path -> return as-is
        2. Starts with 'documents/' -> sandbox root
        3. Matches known alias -> real OS directory
        4. Single filename -> ~/Documents/filename
        5. Unknown -> raise PathMappingError
        """
        path = path.strip()

        # 1. Absolute path
        if self._is_absolute(path):
            return path

        # Normalize separators
        normalized = path.replace("\\", "/")
        first_segment = normalized.split("/")[0].lower()

        # 2. Backward-compatible sandbox paths
        if first_segment == "documents":
            relative = normalized[len("documents/"):] if normalized.startswith("documents/") else normalized[len("documents"):]
            relative = relative.lstrip("/")
            return str(self.sandbox_root / "documents" / relative)

        # 3. Alias mapping
        alias_target = self.ALIASES.get(first_segment)
        if alias_target:
            base = Path(alias_target).expanduser().resolve()
            remainder = "/".join(normalized.split("/")[1:])
            if remainder:
                return str(base / remainder)
            return str(base)

        # 4. Single filename -> default to Documents
        if "/" not in normalized and "\\" not in path:
            return str(Path("~/Documents").expanduser().resolve() / normalized)

        # 5. Unknown
        raise PathMappingError(f"无法解析路径: '{path}'。请使用已知别名（如桌面、下载、文档）或绝对路径。")

    @staticmethod
    def _is_absolute(path: str) -> bool:
        """Check if path is absolute on Windows, macOS, or Linux."""
        if len(path) >= 2 and path[1] == ":":
            return True
        if path.startswith("/") or path.startswith("\\"):
            return True
        return False
