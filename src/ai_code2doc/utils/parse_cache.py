"""File-level parse cache to avoid re-parsing unchanged files with tree-sitter.

Cache entries are stored as JSON files under ``.ai_code2doc/cache/file_infos/``,
keyed by the source file's path relative to the project root.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ai_code2doc.models.module import FileInfo
from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser

logger = logging.getLogger(__name__)


class ParseCache:
    """Cache parsed :class:`FileInfo` objects on disk.

    Typical usage::

        cache = ParseCache(output_dir)
        infos = cache.resolve_file_infos(
            target_files, changed_set, parser, project_root,
        )
    """

    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir / "file_infos"
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Low-level get / put
    # ------------------------------------------------------------------

    def _cache_path(self, relative_path: str) -> Path:
        """Return the cache file path for *relative_path*."""
        safe_key = relative_path.replace("/", "__").replace("\\", "__")
        return self._dir / f"{safe_key}.json"

    def get(self, relative_path: str) -> FileInfo | None:
        """Load a cached :class:`FileInfo`, or ``None`` if not found."""
        path = self._cache_path(relative_path)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return FileInfo.model_validate(data)
        except Exception:
            logger.debug("Failed to load cache for %s", relative_path, exc_info=True)
            return None

    def put(self, file_info: FileInfo) -> None:
        """Serialize *file_info* to the cache."""
        relative_path = str(file_info.path)
        path = self._cache_path(relative_path)
        try:
            path.write_text(file_info.model_dump_json(indent=2), encoding="utf-8")
        except Exception:
            logger.debug("Failed to write cache for %s", relative_path, exc_info=True)

    # ------------------------------------------------------------------
    # High-level resolve
    # ------------------------------------------------------------------

    def resolve_file_infos(
        self,
        target_files: list[Path],
        changed_files: set[Path] | None,
        parser: TreeSitterParser,
        project_root: Path,
    ) -> list[FileInfo]:
        """Return :class:`FileInfo` for every file in *target_files*.

        Files present in *changed_files* are re-parsed; all others are
        loaded from the cache.  When *changed_files* is ``None`` every file
        is parsed (full-analysis mode).

        Newly parsed results are written back to the cache automatically.
        """
        results: list[FileInfo] = []
        for fp in target_files:
            try:
                rel = str(fp.relative_to(project_root))
            except ValueError:
                rel = str(fp)

            if changed_files is not None and fp not in changed_files:
                cached = self.get(rel)
                if cached is not None:
                    results.append(cached)
                    continue

            info = parser.parse_file(fp, project_root)
            self.put(info)
            results.append(info)

        return results
