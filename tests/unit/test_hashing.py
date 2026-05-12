"""Tests for ai_code2doc hashing utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code2doc.utils.hashing import compute_file_hash, compute_content_hash


class TestComputeContentHash:
    def test_deterministic(self) -> None:
        h1 = compute_content_hash("hello world")
        h2 = compute_content_hash("hello world")
        assert h1 == h2

    def test_different_content_different_hash(self) -> None:
        h1 = compute_content_hash("hello")
        h2 = compute_content_hash("world")
        assert h1 != h2

    def test_hash_length(self) -> None:
        h = compute_content_hash("anything")
        # BLAKE2b with digest_size=16 -> 32 hex chars
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)

    def test_empty_content(self) -> None:
        h = compute_content_hash("")
        assert len(h) == 32
        assert h != ""

    def test_unicode_content(self) -> None:
        h = compute_content_hash("中文测试 🎉")
        assert len(h) == 32


class TestComputeFileHash:
    def test_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        h1 = compute_file_hash(f)
        h2 = compute_file_hash(f)
        assert h1 == h2

    def test_hash_length(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("content", encoding="utf-8")
        h = compute_file_hash(f)
        assert len(h) == 32

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello", encoding="utf-8")
        f2.write_text("world", encoding="utf-8")
        assert compute_file_hash(f1) != compute_file_hash(f2)

    def test_large_file(self, tmp_path: Path) -> None:
        """File > 64KiB should be hashed correctly in chunks."""
        f = tmp_path / "large.bin"
        # Write 128 KiB of data
        f.write_bytes(b"x" * (128 * 1024))
        h = compute_file_hash(f)
        assert len(h) == 32

    def test_file_not_found(self, tmp_path: Path) -> None:
        f = tmp_path / "nonexistent.txt"
        with pytest.raises((OSError, FileNotFoundError)):
            compute_file_hash(f)

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        h = compute_file_hash(f)
        assert len(h) == 32
