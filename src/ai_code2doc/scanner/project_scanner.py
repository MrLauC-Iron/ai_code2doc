from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ai_code2doc.scanner.file_filter import FileFilter


@dataclass
class ScanResult:
    root: Path
    all_files: list[Path] = field(default_factory=list)
    target_files: list[Path] = field(default_factory=list)
    directories: list[Path] = field(default_factory=list)
    ignored_count: int = 0


class ProjectScanner:
    def __init__(
        self,
        project_root: Path,
        file_filter: FileFilter | None = None,
        max_file_size_kb: int = 500,
    ):
        self.project_root = project_root.resolve()
        self.file_filter = file_filter or FileFilter(self.project_root)
        self.max_file_size_kb = max_file_size_kb

    def scan(self) -> ScanResult:
        result = ScanResult(root=self.project_root)
        for path in sorted(self.project_root.rglob("*")):
            if self.file_filter.should_ignore(path):
                continue
            if path.is_dir():
                result.directories.append(path)
            elif path.is_file():
                result.all_files.append(path)
                if self.file_filter.is_target_file(path):
                    size_kb = path.stat().st_size / 1024
                    if size_kb <= self.max_file_size_kb:
                        result.target_files.append(path)
                    else:
                        result.ignored_count += 1
        return result
