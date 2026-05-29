"""Tests for BranchManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from code2doc_layer3_mcp.branch_manager import BranchManager


class TestBranchManager:
    def test_get_db_path(self, tmp_path: Path) -> None:
        """DB path follows the expected pattern with sanitized branch name."""
        manager = BranchManager(tmp_path)
        db = manager.get_db_path("feature/A")
        assert db == tmp_path / ".ai_code2doc" / "layer3" / "branches" / "feature--A" / "dependency-graph.db"

    def test_get_db_path_main(self, tmp_path: Path) -> None:
        """Main branch (no slashes) doesn't get sanitized."""
        manager = BranchManager(tmp_path)
        db = manager.get_db_path("main")
        assert db == tmp_path / ".ai_code2doc" / "layer3" / "branches" / "main" / "dependency-graph.db"

    def test_db_exists_false(self, tmp_path: Path) -> None:
        manager = BranchManager(tmp_path)
        assert not manager.db_exists("main")

    def test_db_exists_true(self, tmp_path: Path) -> None:
        manager = BranchManager(tmp_path)
        db = manager.get_db_path("main")
        db.parent.mkdir(parents=True)
        db.touch()
        assert manager.db_exists("main")

    def test_list_branches_empty(self, tmp_path: Path) -> None:
        manager = BranchManager(tmp_path)
        assert manager.list_branches() == []

    def test_list_branches_with_dbs(self, tmp_path: Path) -> None:
        manager = BranchManager(tmp_path)
        for branch in ["main", "feature--login"]:
            path = manager.get_db_path(branch)
            path.parent.mkdir(parents=True)
            path.touch()
        branches = manager.list_branches()
        assert len(branches) == 2
        names = {b["branch"] for b in branches}
        assert "main" in names
        assert "feature--login" in names

    def test_list_branches_ignores_empty_dirs(self, tmp_path: Path) -> None:
        manager = BranchManager(tmp_path)
        # Create a directory without a DB file
        (tmp_path / ".ai_code2doc" / "layer3" / "branches" / "orphan").mkdir(parents=True)
        # Create one valid branch
        db = manager.get_db_path("main")
        db.parent.mkdir(parents=True)
        db.touch()
        branches = manager.list_branches()
        assert len(branches) == 1
        assert branches[0]["branch"] == "main"

    def test_is_building(self, tmp_path: Path) -> None:
        manager = BranchManager(tmp_path)
        assert not manager.is_building("main")
        manager._building.add("main")
        assert manager.is_building("main")

    def test_get_branch_info_not_built(self, tmp_path: Path) -> None:
        manager = BranchManager(tmp_path)
        info = manager.get_branch_info("feature/x")
        assert info["branch"] == "feature/x"
        assert info["db_exists"] is False
        assert info["is_building"] is False
        assert info["db_path"] is not None

    def test_get_branch_info_built(self, tmp_path: Path) -> None:
        manager = BranchManager(tmp_path)
        db = manager.get_db_path("main")
        db.parent.mkdir(parents=True)
        db.touch()
        info = manager.get_branch_info("main")
        assert info["db_exists"] is True

    def test_ensure_repo_not_git(self, tmp_path: Path) -> None:
        manager = BranchManager(tmp_path)
        with pytest.raises(RuntimeError, match="Not a git repository"):
            manager.ensure_repo()

    def test_ensure_repo_valid(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        manager = BranchManager(tmp_path)
        manager.ensure_repo()  # Should not raise
