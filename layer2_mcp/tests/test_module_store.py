"""Tests for module_store."""

from __future__ import annotations

from pathlib import Path

import pytest

from code2doc_layer2_mcp.module_store import ModuleStore


class TestModuleStoreList:
    def test_list_empty(self, tmp_path: Path) -> None:
        store = ModuleStore(tmp_path / "modules")
        result = store.list_modules()
        assert result == []

    def test_list_modules(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        result = store.list_modules()
        assert len(result) == 1
        assert result[0]["name"] == "auth"
        assert "# Module: auth" in result[0]["content"]


class TestModuleStoreGet:
    def test_get_existing(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        doc = store.get_module("auth")
        assert doc is not None
        assert "auth" in doc["name"]
        assert "Authentication" in doc["content"]

    def test_get_missing(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        doc = store.get_module("nonexistent")
        assert doc is None

    def test_get_creates_modules_dir_if_missing(self, tmp_path: Path) -> None:
        store = ModuleStore(tmp_path / "new_modules")
        doc = store.get_module("anything")
        assert doc is None
        assert (tmp_path / "new_modules").exists()


class TestModuleStoreSearch:
    def test_search_by_name(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        results = store.search_modules("auth")
        assert len(results) == 1
        assert results[0]["name"] == "auth"

    def test_search_no_match(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        results = store.search_modules("database")
        assert results == []

    def test_search_in_content(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        results = store.search_modules("Authentication")
        assert len(results) == 1


class TestModuleStoreWrite:
    def test_write_new(self, tmp_path: Path) -> None:
        store = ModuleStore(tmp_path / "modules")
        store.save_module("user", "# Module: user\n\nUser management.")
        doc = store.get_module("user")
        assert doc is not None
        assert "# Module: user" in doc["content"]

    def test_write_overwrites(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        store.save_module("auth", "# Module: auth\n\nUpdated content.")
        doc = store.get_module("auth")
        assert "Updated content" in doc["content"]

    def test_write_sanitizes_name(self, tmp_path: Path) -> None:
        store = ModuleStore(tmp_path / "modules")
        store.save_module("../etc/passwd", "hacked")
        assert not (tmp_path / "modules" / "../etc/passwd.md").exists()


class TestModuleStoreDelete:
    def test_delete_existing(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        result = store.delete_module("auth")
        assert result is True
        assert store.get_module("auth") is None

    def test_delete_missing(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        result = store.delete_module("nonexistent")
        assert result is False
