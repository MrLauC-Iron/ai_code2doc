"""File and project metrics calculation for ai_code2doc."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileMetrics:
    """Quantitative metrics for a single source file."""

    path: str
    line_count: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    function_count: int = 0
    class_count: int = 0
    interface_count: int = 0
    import_count: int = 0
    export_count: int = 0
    size_bytes: int = 0


@dataclass
class ProjectMetrics:
    """Aggregated quantitative metrics across an entire project."""

    total_files: int = 0
    total_lines: int = 0
    total_code_lines: int = 0
    total_comment_lines: int = 0
    total_blank_lines: int = 0
    total_functions: int = 0
    total_classes: int = 0
    total_interfaces: int = 0
    file_metrics: list[FileMetrics] = field(default_factory=list)


class MetricsCalculator:
    """Computes line-level and structural metrics for files and projects."""

    def compute_file_metrics(
        self,
        file_path: Path,
        content: str | None = None,
    ) -> FileMetrics:
        """Compute metrics for a single file from raw content.

        Parameters
        ----------
        file_path:
            Path to the source file.
        content:
            Optional pre-loaded file content.  When *None* the file is read
            from disk.
        """
        if content is None:
            content = file_path.read_text(encoding="utf-8", errors="replace")

        lines = content.split("\n")
        line_count = len(lines)
        blank = 0
        comment = 0
        in_block_comment = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank += 1
            elif in_block_comment:
                comment += 1
                if "*/" in stripped:
                    in_block_comment = False
            elif stripped.startswith("/*"):
                comment += 1
                if "*/" not in stripped:
                    in_block_comment = True
            elif stripped.startswith("//"):
                comment += 1

        return FileMetrics(
            path=str(file_path),
            line_count=line_count,
            code_lines=line_count - blank - comment,
            comment_lines=comment,
            blank_lines=blank,
            size_bytes=len(content.encode("utf-8")),
        )

    def compute_project_metrics(
        self,
        file_metrics: list[FileMetrics],
    ) -> ProjectMetrics:
        """Aggregate a list of FileMetrics into a ProjectMetrics summary."""
        pm = ProjectMetrics(total_files=len(file_metrics), file_metrics=file_metrics)
        for fm in file_metrics:
            pm.total_lines += fm.line_count
            pm.total_code_lines += fm.code_lines
            pm.total_comment_lines += fm.comment_lines
            pm.total_blank_lines += fm.blank_lines
            pm.total_functions += fm.function_count
            pm.total_classes += fm.class_count
            pm.total_interfaces += fm.interface_count
        return pm

    def compute_file_metrics_from_info(self, file_info) -> FileMetrics:
        """Compute metrics from a FileInfo model.

        This variant extracts structural counts (functions, classes, etc.)
        directly from a previously parsed FileInfo instance.
        """
        return FileMetrics(
            path=str(file_info.path),
            line_count=file_info.line_count,
            function_count=len(file_info.functions),
            class_count=len(file_info.classes),
            interface_count=len(file_info.interfaces),
            import_count=len(file_info.imports),
            export_count=len(file_info.exports),
            size_bytes=file_info.size_bytes,
        )
