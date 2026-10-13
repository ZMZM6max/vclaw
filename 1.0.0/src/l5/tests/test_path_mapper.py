import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.l5.path_mapper import PathMapper, PathMappingError


def test_resolve_desktop_alias():
    mapper = PathMapper()
    result = mapper.resolve("桌面/周会提醒.txt")
    assert result.endswith("Desktop\\周会提醒.txt") or result.endswith("Desktop/周会提醒.txt")


def test_resolve_downloads_alias():
    mapper = PathMapper()
    result = mapper.resolve("downloads/report.pdf")
    assert result.endswith("Downloads\\report.pdf") or result.endswith("Downloads/report.pdf")


def test_resolve_documents_alias():
    mapper = PathMapper()
    result = mapper.resolve("文档/笔记.md")
    assert result.endswith("Documents\\笔记.md") or result.endswith("Documents/笔记.md")


def test_resolve_single_filename_defaults_to_documents():
    mapper = PathMapper()
    result = mapper.resolve("test.txt")
    assert result.endswith("Documents\\test.txt") or result.endswith("Documents/test.txt")


def test_resolve_absolute_path_unchanged():
    mapper = PathMapper()
    result = mapper.resolve("C:\\Windows\\System32\\notepad.exe")
    assert result == "C:\\Windows\\System32\\notepad.exe"


def test_resolve_documents_prefix_sandbox():
    mapper = PathMapper()
    result = mapper.resolve("documents/sandbox/file.txt")
    assert "documents" in result.lower()
    assert result.endswith("sandbox\\file.txt") or result.endswith("sandbox/file.txt")


def test_resolve_unknown_raises():
    import pytest
    mapper = PathMapper()
    with pytest.raises(PathMappingError):
        mapper.resolve("unknown_folder/file.txt")
