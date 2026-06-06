"""Periodic git poller for automatic Layer 3 DB updates."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from code2doc_layer3_mcp.branch_manager import BranchManager

logger = logging.getLogger(__name__)


class GitPoller:
    """Periodically checks git remotes for changes and triggers rebuilds."""

    def __init__(
        self,
        repo_path: Path,
        branch_manager: BranchManager,
        poll_interval: int = 300,
        branches: list[str] | None = None,
    ) -> None:
        self.repo_path = repo_path
        self.branch_manager = branch_manager
        self.poll_interval = poll_interval
        self.branches = branches
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_poll: datetime | None = None
        self._last_rebuild: datetime | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            "GitPoller started (interval=%ds, repo=%s)",
            self.poll_interval,
            self.repo_path,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("GitPoller stopped")

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._poll_once()
            except Exception:
                logger.exception("Poll cycle failed")
            await asyncio.sleep(self.poll_interval)

    async def _poll_once(self) -> None:
        branches = self.branches or self._get_tracked_branches()
        if not branches:
            logger.debug("No branches to poll")
            return

        logger.info("Polling %d branches...", len(branches))
        self._last_poll = datetime.now(timezone.utc)

        changed = await self.branch_manager.fetch_remote_heads(branches)
        for branch, has_changes in changed.items():
            if has_changes:
                logger.info("Changes detected on '%s', rebuilding...", branch)
                try:
                    await self.branch_manager.ensure_branch(branch)
                    self._last_rebuild = datetime.now(timezone.utc)
                    logger.info("Rebuild complete for '%s'", branch)
                except Exception:
                    logger.exception("Rebuild failed for '%s'", branch)
            else:
                logger.debug("No changes on '%s'", branch)

    def _get_tracked_branches(self) -> list[str]:
        result = subprocess.run(
            ["git", "branch", "--list"],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        return [b.strip().lstrip("* ") for b in result.stdout.strip().splitlines() if b.strip()]

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "poll_interval": self.poll_interval,
            "branches": self.branches or "auto",
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
            "last_rebuild": self._last_rebuild.isoformat() if self._last_rebuild else None,
        }
