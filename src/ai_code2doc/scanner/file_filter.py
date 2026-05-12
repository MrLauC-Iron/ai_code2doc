from __future__ import annotations

from pathlib import Path

import pathspec

from ai_code2doc.config.defaults import DEFAULT_IGNORE_PATTERNS, DEFAULT_IGNORE_EXTENSIONS


class FileFilter:
    """Filters files based on ignore patterns and gitignore."""

    def __init__(self, project_root: Path, extra_ignore: list[str] | None = None):
        self.project_root = project_root
        self._specs = self._load_specs(extra_ignore)

    def _load_specs(self, extra_ignore: list[str] | None) -> pathspec.PathSpec:
        patterns = list(DEFAULT_IGNORE_PATTERNS)
        if extra_ignore:
            patterns.extend(extra_ignore)
        gitignore_path = self.project_root / ".gitignore"
        if gitignore_path.exists():
            for line in gitignore_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    patterns.append(stripped)
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def should_ignore(self, path: Path) -> bool:
        """Check if a file/directory should be ignored."""
        try:
            relative = path.relative_to(self.project_root)
            return self._specs.match_file(str(relative).replace("\\", "/"))
        except ValueError:
            return True

    def is_target_file(self, path: Path) -> bool:
        """Check if file is a target source file for any registered language."""
        if not path.is_file():
            return False
        suffix = path.suffix.lower()
        # Lazy import to avoid circular dependency at module level.
        from ai_code2doc.parser.language_registry import LanguageRegistry

        if suffix not in LanguageRegistry.all_extensions():
            return False
        name = path.name.lower()
        for ext in DEFAULT_IGNORE_EXTENSIONS:
            if name.endswith(ext):
                return False
        return True
