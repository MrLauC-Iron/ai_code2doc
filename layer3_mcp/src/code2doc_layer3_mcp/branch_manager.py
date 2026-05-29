"""Git repository manager for on-demand branch analysis."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BranchManager:
    """Manages git branches and Layer 3 DB lifecycle."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path.resolve()
        self._locks: dict[str, asyncio.Lock] = {}
        self._building: set[str] = set()

    def _get_lock(self, branch: str) -> asyncio.Lock:
        if branch not in self._locks:
            self._locks[branch] = asyncio.Lock()
        return self._locks[branch]

    def get_db_path(self, branch: str) -> Path:
        """Return the DB path for a given branch."""
        from code2doc_layer3_mcp.git import sanitize_branch_name

        return (
            self.repo_path
            / ".ai_code2doc"
            / "layer3"
            / "branches"
            / sanitize_branch_name(branch)
            / "dependency-graph.db"
        )

    def db_exists(self, branch: str) -> bool:
        """Check if the branch DB already exists."""
        return self.get_db_path(branch).exists()

    def _run_git(self, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
        """Run a git command in the repo directory."""
        return subprocess.run(
            ["git"] + list(args),
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def _run_analyze(self) -> subprocess.CompletedProcess:
        """Run ai-code2doc analyze for Layer 3 only."""
        return subprocess.run(
            [
                "ai-code2doc",
                "analyze",
                "--full",
                "--layers",
                "3",
                "--no-llm",
                "--no-vector-store",
                str(self.repo_path),
            ],
            capture_output=True,
            text=True,
            timeout=1800,
            cwd=str(self.repo_path.parent),
        )

    def ensure_repo(self) -> None:
        """Ensure the git repo exists and is valid."""
        if not (self.repo_path / ".git").exists():
            raise RuntimeError(
                f"Not a git repository: {self.repo_path}. "
                f"Use 'git clone' first."
            )

    async def ensure_branch(self, branch: str) -> Path:
        """Ensure a branch's DB is available. Build if needed.

        Thread-safe: concurrent calls for the same branch will wait
        for the first build to complete.
        """
        db_path = self.get_db_path(branch)

        if db_path.exists():
            return db_path

        lock = self._get_lock(branch)
        async with lock:
            # Double-check after acquiring lock
            if db_path.exists():
                return db_path

            logger.info("Building Layer 3 for branch '%s'...", branch)
            self._building.add(branch)
            try:
                await self._build_branch(branch)
            finally:
                self._building.discard(branch)

        if not db_path.exists():
            raise RuntimeError(
                f"Failed to build Layer 3 for branch '{branch}'. "
                f"Check server logs for details."
            )
        return db_path

    async def _build_branch(self, branch: str) -> None:
        """Fetch, checkout, and analyze a branch."""
        loop = asyncio.get_event_loop()

        # 1. git fetch
        logger.info("Fetching branch '%s'...", branch)
        result = await loop.run_in_executor(
            None, self._run_git, "fetch", "origin", branch
        )
        if result.returncode != 0:
            logger.warning("git fetch failed: %s", result.stderr.strip())

        # 2. git checkout
        logger.info("Checking out branch '%s'...", branch)
        result = await loop.run_in_executor(
            None, self._run_git, "checkout", branch
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git checkout failed: {result.stderr.strip()}"
            )

        # 3. Run ai-code2doc analyze
        logger.info("Running ai-code2doc analyze for branch '%s'...", branch)
        result = await loop.run_in_executor(None, self._run_analyze)
        if result.returncode != 0:
            raise RuntimeError(
                f"ai-code2doc analyze failed: {result.stderr.strip()}"
            )

        logger.info("Branch '%s' Layer 3 build complete.", branch)

    def is_building(self, branch: str) -> bool:
        """Check if a branch build is in progress."""
        return branch in self._building

    def get_branch_info(self, branch: str) -> dict[str, Any]:
        """Get status info for a branch."""
        return {
            "branch": branch,
            "db_exists": self.db_exists(branch),
            "is_building": self.is_building(branch),
            "db_path": str(self.get_db_path(branch)),
        }

    def list_branches(self) -> list[dict[str, Any]]:
        """List all branches that have DBs built."""
        branches_dir = (
            self.repo_path / ".ai_code2doc" / "layer3" / "branches"
        )
        if not branches_dir.exists():
            return []

        result = []
        for d in sorted(branches_dir.iterdir()):
            if not d.is_dir():
                continue
            db = d / "dependency-graph.db"
            if db.exists():
                result.append(
                    {
                        "branch": d.name,
                        "db_exists": True,
                        "db_path": str(db),
                    }
                )
        return result

    def get_current_branch(self) -> str | None:
        """Return the current git branch of the managed repo."""
        try:
            result = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
            if result.returncode == 0:
                branch = result.stdout.strip()
                return branch if branch else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None
