"""Shared fixtures for layer2_mcp tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_modules_dir(tmp_path: Path) -> Path:
    """Create a temporary modules directory with a sample module."""
    modules = tmp_path / "modules"
    modules.mkdir()
    (modules / "auth.md").write_text(
        "# Module: auth\n\nPath: `src/api/auth`\n\nAuthentication module.\n",
        encoding="utf-8",
    )
    return modules
