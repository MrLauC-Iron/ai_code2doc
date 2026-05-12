"""Tests for ai_code2doc markdown utilities."""

from __future__ import annotations

import pytest

from ai_code2doc.utils.markdown_utils import (
    escape_markdown,
    format_code_block,
    format_table,
    format_toc,
)


class TestEscapeMarkdown:
    def test_special_chars(self) -> None:
        text = "\\`*_{}"
        result = escape_markdown(text)
        # Each special char should be preceded by backslash
        assert result.startswith("\\\\")

    def test_empty_string(self) -> None:
        assert escape_markdown("") == ""

    def test_no_special_chars(self) -> None:
        assert escape_markdown("hello world") == "hello world"

    def test_pipe_char(self) -> None:
        result = escape_markdown("a|b")
        assert "\\|" in result


class TestFormatCodeBlock:
    def test_default_language(self) -> None:
        result = format_code_block("x = 1")
        assert result.startswith("```python\n")
        assert result.endswith("\n```\n")
        assert "x = 1" in result

    def test_specified_language(self) -> None:
        result = format_code_block("int x;", "c")
        assert result.startswith("```c\n")
        assert "int x;" in result

    def test_no_language(self) -> None:
        result = format_code_block("code", "")
        assert result.startswith("```\n")


class TestFormatTable:
    def test_basic_table(self) -> None:
        headers = ["Name", "Type"]
        rows = [["foo", "int"], ["bar", "str"]]
        result = format_table(headers, rows)
        assert "Name" in result
        assert "Type" in result
        assert "foo" in result
        assert "---" in result
        # Should have header + separator + 2 data rows
        lines = result.strip().split("\n")
        assert len(lines) == 4

    def test_rows_shorter_than_headers(self) -> None:
        headers = ["A", "B", "C"]
        rows = [["1"]]
        result = format_table(headers, rows)
        lines = result.strip().split("\n")
        # Row should have empty cells padded; 3 headers -> 4 pipe chars per line
        row_line = lines[2]
        assert row_line.count("|") == 4


class TestFormatToc:
    def test_basic_toc(self) -> None:
        items = [("Introduction", "intro"), ("API", "api")]
        result = format_toc(items)
        assert "- [Introduction](#intro)" in result
        assert "- [API](#api)" in result

    def test_empty_toc(self) -> None:
        result = format_toc([])
        assert result.strip() == ""
