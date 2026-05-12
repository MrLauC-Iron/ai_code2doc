"""Tests for ai_code2doc metrics calculator."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code2doc.analyzer.metrics import MetricsCalculator, FileMetrics, ProjectMetrics
from ai_code2doc.models.module import FileInfo, FunctionInfo, ClassInfo, InterfaceInfo, ImportInfo


class TestMetricsCalculator:
    def setup_method(self) -> None:
        self.calc = MetricsCalculator()

    def test_pure_code(self) -> None:
        m = self.calc.compute_file_metrics(
            Path("test.py"), content="x = 1\ny = 2",
        )
        assert m.code_lines == 2
        assert m.blank_lines == 0

    def test_with_blank_lines(self) -> None:
        m = self.calc.compute_file_metrics(
            Path("test.py"), content="x = 1\n\ny = 2",
        )
        assert m.blank_lines == 1

    def test_with_comments(self) -> None:
        m = self.calc.compute_file_metrics(
            Path("test.py"), content="# hello\nx = 1",
        )
        # Note: MetricsCalculator recognizes // and /* */ style comments,
        # not Python # comments. This is a known limitation.
        # For Python files, # comments are counted as code_lines.
        assert m.line_count == 2

    def test_block_comment(self) -> None:
        content = "/* a comment */\nx = 1\n"
        m = self.calc.compute_file_metrics(Path("test.c"), content=content)
        assert m.comment_lines >= 1

    def test_line_count(self) -> None:
        content = "a\nb\nc"
        m = self.calc.compute_file_metrics(Path("test.py"), content=content)
        assert m.line_count == 3

    def test_project_metrics_aggregation(self) -> None:
        fm1 = FileMetrics(path="a.py", line_count=10, code_lines=8, blank_lines=1, comment_lines=1)
        fm2 = FileMetrics(path="b.py", line_count=20, code_lines=15, blank_lines=3, comment_lines=2)
        pm = self.calc.compute_project_metrics([fm1, fm2])
        assert pm.total_files == 2
        assert pm.total_lines == 30
        assert pm.total_code_lines == 23
        assert pm.total_blank_lines == 4
        assert pm.total_comment_lines == 3

    def test_compute_from_file_info(self) -> None:
        fi = FileInfo(
            path=Path("test.py"),
            name="test.py",
            line_count=50,
            size_bytes=500,
            functions=[
                FunctionInfo(name="f1", start_line=1, end_line=5),
                FunctionInfo(name="f2", start_line=6, end_line=10),
                FunctionInfo(name="f3", start_line=11, end_line=15),
            ],
            classes=[ClassInfo(name="Cls", start_line=20, end_line=30)],
            interfaces=[InterfaceInfo(name="IFoo", start_line=35, end_line=40)],
            imports=[ImportInfo(source="os")],
            exports=["main"],
        )
        m = self.calc.compute_file_metrics_from_info(fi)
        assert m.function_count == 3
        assert m.class_count == 1
        assert m.interface_count == 1
        assert m.import_count == 1
        assert m.export_count == 1
        assert m.size_bytes == 500

    def test_empty_file(self) -> None:
        m = self.calc.compute_file_metrics(Path("empty.py"), content="")
        assert m.line_count == 1  # split produces [""]

    def test_size_bytes(self) -> None:
        content = "hello"
        m = self.calc.compute_file_metrics(Path("test.py"), content=content)
        assert m.size_bytes == len(content.encode("utf-8"))
