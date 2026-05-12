"""Tests for ai_code2doc markdown writer."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from ai_code2doc.generator.markdown_writer import MarkdownWriter
from ai_code2doc.models.knowledge import KnowledgeDocument


@pytest.fixture
def writer() -> MarkdownWriter:
    return MarkdownWriter()


@pytest.fixture
def sample_doc() -> KnowledgeDocument:
    return KnowledgeDocument(
        id="doc-1",
        layer=1,
        source_path="src/main.py",
        title="Project Overview",
        content="This is the overview content.",
        tags=["overview", "docs"],
    )


class TestMarkdownWriter:
    def test_write_doc(self, writer: MarkdownWriter, tmp_path: Path, sample_doc: KnowledgeDocument) -> None:
        out = tmp_path / "output.md"
        result = writer.write_doc(out, sample_doc)
        assert result == out
        content = out.read_text(encoding="utf-8")
        assert "# Project Overview" in content
        assert "This is the overview content." in content

    def test_write_doc_creates_directories(self, writer: MarkdownWriter, tmp_path: Path, sample_doc: KnowledgeDocument) -> None:
        out = tmp_path / "deep" / "nested" / "output.md"
        writer.write_doc(out, sample_doc)
        assert out.exists()

    def test_write_doc_includes_tags(self, writer: MarkdownWriter, tmp_path: Path, sample_doc: KnowledgeDocument) -> None:
        out = tmp_path / "tagged.md"
        writer.write_doc(out, sample_doc)
        content = out.read_text(encoding="utf-8")
        assert "overview" in content
        assert "docs" in content

    def test_write_raw(self, writer: MarkdownWriter, tmp_path: Path) -> None:
        out = tmp_path / "raw.md"
        writer.write_raw(out, "# Raw Title\n\nContent here.")
        content = out.read_text(encoding="utf-8")
        assert content == "# Raw Title\n\nContent here."

    def test_write_raw_creates_directories(self, writer: MarkdownWriter, tmp_path: Path) -> None:
        out = tmp_path / "a" / "b" / "c" / "file.md"
        writer.write_raw(out, "content")
        assert out.exists()
