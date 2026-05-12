"""Tests for ai_code2doc file scanner and filter."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code2doc.scanner.file_filter import FileFilter
from ai_code2doc.scanner.project_scanner import ProjectScanner


class TestFileFilter:
    def test_ignores_pycache(self, sample_py_project: Path) -> None:
        f = FileFilter(sample_py_project)
        assert f.should_ignore(sample_py_project / "__pycache__" / "foo.pyc")

    def test_ignores_git(self, sample_py_project: Path) -> None:
        f = FileFilter(sample_py_project)
        assert f.should_ignore(sample_py_project / ".git" / "config")

    def test_ignores_node_modules(self, sample_py_project: Path) -> None:
        f = FileFilter(sample_py_project)
        assert f.should_ignore(sample_py_project / "node_modules" / "x.js")

    def test_accepts_py_file(self, sample_py_project: Path) -> None:
        f = FileFilter(sample_py_project)
        py_file = sample_py_project / "src" / "main.py"
        assert f.is_target_file(py_file)

    def test_accepts_c_file(self, sample_c_project: Path) -> None:
        f = FileFilter(sample_c_project)
        c_file = sample_c_project / "src" / "main.c"
        assert f.is_target_file(c_file)

    def test_accepts_cpp_file(self, sample_c_project: Path) -> None:
        f = FileFilter(sample_c_project)
        # Create a .cpp file for testing
        cpp_file = sample_c_project / "src" / "test.cpp"
        cpp_file.write_text("int main() {}", encoding="utf-8")
        assert f.is_target_file(cpp_file)

    def test_rejects_pyc(self, sample_py_project: Path) -> None:
        f = FileFilter(sample_py_project)
        pyc_file = sample_py_project / "src" / "__pycache__" / "main.cpython-310.pyc"
        # The directory should be ignored, and .pyc extension should be rejected
        assert f.should_ignore(pyc_file) or not f.is_target_file(pyc_file)

    def test_rejects_txt(self, sample_py_project: Path) -> None:
        f = FileFilter(sample_py_project)
        txt_file = sample_py_project / "README.txt"
        txt_file.write_text("readme", encoding="utf-8")
        assert not f.is_target_file(txt_file)

    def test_gitignore_patterns(self, tmp_path: Path) -> None:
        # Create a project with .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\n", encoding="utf-8")
        f = FileFilter(tmp_path)
        log_file = tmp_path / "debug.log"
        log_file.write_text("log", encoding="utf-8")
        assert f.should_ignore(log_file)


class TestProjectScanner:
    def test_scan_py_project(self, sample_py_project: Path) -> None:
        scanner = ProjectScanner(sample_py_project)
        result = scanner.scan()
        assert len(result.target_files) > 0
        # All target files should be .py
        assert all(f.suffix == ".py" for f in result.target_files)

    def test_scan_c_project(self, sample_c_project: Path) -> None:
        scanner = ProjectScanner(sample_c_project)
        result = scanner.scan()
        assert len(result.target_files) > 0
        suffixes = {f.suffix for f in result.target_files}
        assert suffixes.issubset({".c", ".h", ".cpp", ".hpp"})

    def test_scan_finds_directories(self, sample_py_project: Path) -> None:
        scanner = ProjectScanner(sample_py_project)
        result = scanner.scan()
        assert len(result.directories) > 0

    def test_scan_root_set(self, sample_py_project: Path) -> None:
        scanner = ProjectScanner(sample_py_project)
        result = scanner.scan()
        assert result.root == sample_py_project.resolve()

    def test_scan_file_size_limit(self, tmp_path: Path) -> None:
        # Create a file that exceeds the default 500KB limit
        big_file = tmp_path / "huge.py"
        big_file.write_text("x = 1\n" * 200000, encoding="utf-8")  # ~400KB+
        scanner = ProjectScanner(tmp_path, max_file_size_kb=1)
        result = scanner.scan()
        # File should be skipped due to size
        assert big_file not in result.target_files
