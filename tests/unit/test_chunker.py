"""Tests for ai_code2doc text chunker."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code2doc.llm.chunker import Chunker, Chunk


class TestChunker:
    def test_short_text_no_split(self) -> None:
        chunker = Chunker(max_tokens=3000)
        text = "x = 1\ny = 2\n"
        chunks = chunker.chunk_content(text)
        assert len(chunks) == 1
        assert chunks[0].content == text

    def test_long_text_splits(self) -> None:
        chunker = Chunker(max_tokens=10, chars_per_token=4.0)
        # 40 chars max per chunk, make text much longer
        text = "\n".join(f"line {i}: some content here" for i in range(20))
        chunks = chunker.chunk_content(text)
        assert len(chunks) > 1

    def test_empty_text(self) -> None:
        chunker = Chunker()
        chunks = chunker.chunk_content("")
        assert len(chunks) == 1
        assert chunks[0].content == ""

    def test_chunk_has_index(self) -> None:
        chunker = Chunker(max_tokens=10, chars_per_token=4.0)
        text = "\n".join(f"line {i}" for i in range(50))
        chunks = chunker.chunk_content(text)
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_chunk_line_numbers(self) -> None:
        chunker = Chunker()
        text = "line1\nline2\nline3\n"
        chunks = chunker.chunk_content(text)
        assert chunks[0].start_line == 1
        assert chunks[0].end_line >= 1

    def test_chunk_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("def hello():\n    pass\n", encoding="utf-8")
        chunker = Chunker()
        chunks = chunker.chunk_file(f)
        assert len(chunks) >= 1
        assert "hello" in chunks[0].content

    def test_token_estimate(self) -> None:
        chunker = Chunker()
        text = "a" * 40  # 40 chars -> ~10 tokens
        chunks = chunker.chunk_content(text)
        assert chunks[0].token_estimate == 10
