"""Tests for ai_code2doc parse cache."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_code2doc.models.module import FileInfo, FunctionInfo
from ai_code2doc.utils.parse_cache import ParseCache


@pytest.fixture
def cache(tmp_path: Path) -> ParseCache:
    """Create a ParseCache in a temporary directory."""
    return ParseCache(tmp_path)


@pytest.fixture
def sample_file_info() -> FileInfo:
    """Create a sample FileInfo for testing."""
    return FileInfo(
        path=Path("src/main.py"),
        name="main.py",
        size_bytes=100,
        line_count=10,
        functions=[FunctionInfo(name="main", start_line=1, end_line=5)],
    )


class TestParseCache:
    def test_put_and_get(self, cache: ParseCache, sample_file_info: FileInfo) -> None:
        cache.put(sample_file_info)
        result = cache.get(str(sample_file_info.path))
        assert result is not None
        assert result.name == "main.py"
        assert len(result.functions) == 1

    def test_get_nonexistent(self, cache: ParseCache) -> None:
        result = cache.get("nonexistent.py")
        assert result is None

    def test_get_corrupted_cache(self, cache: ParseCache) -> None:
        # Write invalid JSON to cache
        cache_path = cache._cache_path("bad.py")
        cache_path.write_text("not valid json{{", encoding="utf-8")
        result = cache.get("bad.py")
        assert result is None

    def test_resolve_file_infos_full(
        self, cache: ParseCache, tmp_path: Path,
    ) -> None:
        """Full mode (changed_files=None) parses all files."""
        py_file = tmp_path / "test.py"
        py_file.write_text("def hello(): pass\n", encoding="utf-8")

        parser = MagicMock()
        parser.parse_file.return_value = FileInfo(
            path=py_file, name="test.py", line_count=1,
        )

        results = cache.resolve_file_infos(
            target_files=[py_file],
            changed_files=None,
            parser=parser,
            project_root=tmp_path,
        )
        assert len(results) == 1
        assert results[0].name == "test.py"
        parser.parse_file.assert_called_once()

    def test_resolve_file_infos_incremental(
        self, cache: ParseCache, tmp_path: Path,
    ) -> None:
        """Incremental mode: unchanged files loaded from cache."""
        py_file = tmp_path / "cached.py"
        py_file.write_text("x = 1\n", encoding="utf-8")

        # Pre-populate cache using the same relative path that resolve_file_infos uses
        rel_path = str(py_file.relative_to(tmp_path))
        cached_info = FileInfo(path=Path(rel_path), name="cached.py", line_count=1)
        cache.put(cached_info)

        parser = MagicMock()

        results = cache.resolve_file_infos(
            target_files=[py_file],
            changed_files=set(),  # empty = no changed files
            parser=parser,
            project_root=tmp_path,
        )
        assert len(results) == 1
        parser.parse_file.assert_not_called()

    def test_resolve_file_infos_changed_files_re_parsed(
        self, cache: ParseCache, tmp_path: Path,
    ) -> None:
        """Changed files should be re-parsed even if cached."""
        py_file = tmp_path / "changed.py"
        py_file.write_text("y = 2\n", encoding="utf-8")

        # Pre-populate cache with stale data
        stale_info = FileInfo(path=py_file, name="changed.py", line_count=1)
        cache.put(stale_info)

        parser = MagicMock()
        parser.parse_file.return_value = FileInfo(
            path=py_file, name="changed.py", line_count=1,
            functions=[FunctionInfo(name="new_func", start_line=1, end_line=1)],
        )

        results = cache.resolve_file_infos(
            target_files=[py_file],
            changed_files={py_file},  # file marked as changed
            parser=parser,
            project_root=tmp_path,
        )
        assert len(results) == 1
        parser.parse_file.assert_called_once()
