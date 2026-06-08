"""Git utilities for branch detection and DB path resolution."""

from __future__ import annotations

import subprocess
from pathlib import Path


def get_current_branch(project_root: Path) -> str | None:
    """Return the current git branch name, or None if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return branch if branch else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def sanitize_branch_name(branch: str) -> str:
    """Sanitize branch name for use as directory name.

    Replaces '/' with '--' to avoid directory nesting.
    """
    return branch.replace("/", "--")


def get_layer3_db_path(
    project_root: Path, output_dir: str = ".ai_code2doc"
) -> Path:
    """Resolve the Layer 3 dependency graph DB path.

    Priority:
    1. Branch-specific: {project}/{output_dir}/layer3/branches/{branch}/dependency-graph.db
    2. Legacy fallback: {project}/{output_dir}/layer3/dependency-graph.db
    """
    branch = get_current_branch(project_root)
    base = project_root / output_dir / "layer3"

    if branch:
        branch_db = (
            base / "branches" / sanitize_branch_name(branch) / "dependency-graph.db"
        )
        if branch_db.exists():
            return branch_db

    # Fallback to legacy path
    return base / "dependency-graph.db"
