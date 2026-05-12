"""Tests for ai_code2doc path utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code2doc.utils.path_utils import (
    relative_path,
    module_name_from_path,
    ensure_dir,
    safe_filename,
)


class TestRelativePath:
    def test_normal_relative(self) -> None:
        result = relative_path(Path("/a/b/c.py"), Path("/a"))
        assert result == "b/c.py"

    def test_unrelated_path(self) -> None:
        # On Windows, /x/y is not under /a so it falls back
        result = relative_path(Path("/x/y"), Path("/a"))
        assert isinstance(result, str)

    def test_same_dir(self) -> None:
        result = relative_path(Path("/a/file.py"), Path("/a"))
        assert result == "file.py"

    def test_nested_path(self) -> None:
        result = relative_path(Path("/a/b/c/d.py"), Path("/a"))
        assert result == "b/c/d.py"


class TestModuleNameFromPath:
    def test_python_module(self) -> None:
        result = module_name_from_path(Path("src/analyzer/parse.py"), Path("src"))
        assert result == "analyzer.parse"

    def test_c_file(self) -> None:
        result = module_name_from_path(Path("src/main.c"), Path("src"))
        assert result == "main"

    def test_init_file(self) -> None:
        result = module_name_from_path(Path("pkg/__init__.py"), Path("."))
        assert result == "pkg"

    def test_cpp_file(self) -> None:
        result = module_name_from_path(Path("src/utils.cpp"), Path("src"))
        assert result == "utils"

    def test_nested_module(self) -> None:
        result = module_name_from_path(
            Path("src/api/routes.py"), Path("src"),
        )
        assert result == "api.routes"


class TestSafeFilename:
    def test_normal_name(self) -> None:
        assert safe_filename("hello world") == "hello world"

    def test_special_chars(self) -> None:
        result = safe_filename('a<>b:c')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result

    def test_consecutive_underscores(self) -> None:
        result = safe_filename("a___b")
        assert "___" not in result

    def test_empty_string(self) -> None:
        # Falls back to "unnamed"
        assert safe_filename("") == "unnamed"

    def test_only_special_chars(self) -> None:
        result = safe_filename('<>:"/\\|?*')
        # Should produce a safe name, not crash
        assert isinstance(result, str)
        assert "<" not in result


class TestEnsureDir:
    def test_creates_new_dir(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "new" / "nested" / "dir"
        result = ensure_dir(new_dir)
        assert result.exists()
        assert result.is_dir()

    def test_existing_dir(self, tmp_path: Path) -> None:
        # tmp_path already exists
        result = ensure_dir(tmp_path)
        assert result == tmp_path
        assert result.exists()

    def test_returns_path(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "sub"
        assert ensure_dir(new_dir) == new_dir
