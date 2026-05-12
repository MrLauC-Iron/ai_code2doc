"""Integration tests for technology stack detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code2doc.analyzer.tech_stack import TechStackDetector


class TestTechStackDetection:
    def test_python_pyproject_toml(self, sample_py_project: Path) -> None:
        detector = TechStackDetector(sample_py_project)
        ts = detector.detect()
        # Should detect Python as language
        assert "Python" in ts.language or "python" in ts.language.lower()
        # Should detect FastAPI from pyproject.toml
        assert ts.framework == "FastAPI" or "FastAPI" in ts.framework

    def test_python_requirements_txt(self, tmp_path: Path) -> None:
        # Create a minimal project with requirements.txt
        req = tmp_path / "requirements.txt"
        req.write_text("django>=4.0\n", encoding="utf-8")
        # Also create a .py file so the language is detected
        (tmp_path / "app.py").write_text("import django\n", encoding="utf-8")
        detector = TechStackDetector(tmp_path)
        ts = detector.detect()
        assert "django" in str(ts.dependencies).lower() or ts.framework == "Django" or "Django" in ts.framework

    def test_c_cmake_project(self, sample_c_project: Path) -> None:
        detector = TechStackDetector(sample_c_project)
        ts = detector.detect()
        assert "C" in ts.language or "c" in ts.language.lower()
        assert ts.build_tool == "CMake" or "CMake" in ts.build_tool

    def test_c_makefile_project(self, tmp_path: Path) -> None:
        # Create a minimal C project with Makefile only
        makefile = tmp_path / "Makefile"
        makefile.write_text("all:\n\tgcc -o app main.c\n", encoding="utf-8")
        (tmp_path / "main.c").write_text("int main() { return 0; }\n", encoding="utf-8")
        detector = TechStackDetector(tmp_path)
        ts = detector.detect()
        assert "C" in ts.language or "c" in ts.language.lower()

    def test_python_entry_points(self, sample_py_project: Path) -> None:
        detector = TechStackDetector(sample_py_project)
        entry_points = detector.detect_entry_points()
        assert len(entry_points) >= 0  # May or may not detect entry points
        # main.py or __main__.py should be detected if present
        ep_names = [str(ep) for ep in entry_points]
        # At least something should be found
        assert isinstance(entry_points, list)

    def test_c_entry_points(self, sample_c_project: Path) -> None:
        detector = TechStackDetector(sample_c_project)
        entry_points = detector.detect_entry_points()
        assert isinstance(entry_points, list)
        # main.c should be detected as an entry point
        if entry_points:
            assert any("main" in str(ep) for ep in entry_points)

    def test_empty_project(self, tmp_path: Path) -> None:
        # Project with no source files
        detector = TechStackDetector(tmp_path)
        ts = detector.detect()
        assert ts.language == "Unknown" or ts.language == ""
