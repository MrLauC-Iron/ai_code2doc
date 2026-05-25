"""Orchestrates extraction and resolution of function-level call sites."""

from __future__ import annotations

from pathlib import Path

from ai_code2doc.analyzer.call_extractor import PythonCallExtractor
from ai_code2doc.analyzer.symbol_registry import SymbolRegistry
from ai_code2doc.models.graph import CallSite
from ai_code2doc.models.module import FileInfo


class CallGraphBuilder:
    """Builds function/class-level call relationships across a project."""

    def __init__(self, project_root: Path) -> None:
        self.root = project_root
        self.registry = SymbolRegistry()

    def build_for_files(self, file_infos: list[FileInfo]) -> list[CallSite]:
        """Extract and resolve call sites across all files.

        Parameters
        ----------
        file_infos:
            Parsed FileInfo objects (must have source_text set for call extraction).
        """
        # Phase 1: Build symbol registry from all definitions
        for fi in file_infos:
            self.registry.add_from_file_info(fi)

        # Phase 2: Extract and resolve call sites
        all_sites: list[CallSite] = []
        for fi in file_infos:
            sites = self._extract_from_file(fi)
            resolved = self._resolve_sites(sites, fi)
            all_sites.extend(resolved)

        return all_sites

    def _extract_from_file(self, fi: FileInfo) -> list[CallSite]:
        """Extract raw call sites from a file's functions and methods."""
        source = getattr(fi, "source_text", None) or ""
        if not source:
            return []

        file_path = str(fi.path).replace("\\", "/")
        sites: list[CallSite] = []

        # Extract calls from top-level functions
        for func in fi.functions:
            fqn = f"{file_path}::{func.name}"
            func_source = self._extract_body(source, func.start_line, func.end_line)
            if func_source:
                func_sites = PythonCallExtractor.extract_calls(func_source, fqn, file_path)
                sites.extend(func_sites)

        # Extract calls from class methods
        for cls in fi.classes:
            cls_fqn = f"{file_path}::{cls.name}"
            for method in cls.methods:
                method_fqn = f"{cls_fqn}.{method.name}"
                method_source = self._extract_body(source, method.start_line, method.end_line)
                if method_source:
                    method_sites = PythonCallExtractor.extract_calls(
                        method_source, method_fqn, file_path,
                    )
                    sites.extend(method_sites)

        return sites

    def _resolve_sites(self, sites: list[CallSite], fi: FileInfo) -> list[CallSite]:
        """Resolve call site names to FQNs using the registry."""
        file_path = str(fi.path).replace("\\", "/")
        resolved: list[CallSite] = []
        for site in sites:
            r = self.registry.resolve_call_site(site, file_path)
            resolved.append(r)
        return resolved

    @staticmethod
    def _extract_body(source: str, start_line: int, end_line: int) -> str:
        """Extract the source text for a line range (1-indexed, inclusive)."""
        lines = source.splitlines()
        body_lines = lines[start_line - 1 : end_line]
        return "\n".join(body_lines)
