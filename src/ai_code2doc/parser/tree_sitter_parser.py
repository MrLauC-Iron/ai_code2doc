"""Language-aware tree-sitter parser for ai_code2doc.

This module provides :class:`TreeSitterParser`, the main entry point for
parsing source files.  It delegates to the appropriate language adapter
registered in :class:`~ai_code2doc.parser.language_registry.LanguageRegistry`.
"""

from __future__ import annotations

from pathlib import Path

from tree_sitter import Parser

from ai_code2doc.models.module import FileInfo
from ai_code2doc.parser.base_parser import BaseParser
from ai_code2doc.parser.language_registry import LanguageRegistry
from ai_code2doc.utils.hashing import compute_file_hash

# Ensure built-in languages are registered.
import ai_code2doc.parser.languages  # noqa: F401


class TreeSitterParser(BaseParser):
    """Parse source files via tree-sitter and return structured :class:`FileInfo`.

    The parser automatically selects the correct tree-sitter grammar and
    structure extractor based on each file's extension, using the
    :class:`LanguageRegistry`.
    """

    def __init__(self) -> None:
        self._parsers: dict[str, Parser] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_parser(self, ext: str) -> Parser:
        """Return a cached :class:`Parser` for the given extension."""
        adapter = LanguageRegistry.get_by_extension(ext)
        if adapter is None:
            raise ValueError(f"No language adapter registered for extension: {ext}")
        if ext not in self._parsers:
            self._parsers[ext] = Parser(adapter.tree_sitter_language)
        return self._parsers[ext]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, file_path: Path, project_root: Path) -> FileInfo:
        """Parse *file_path* and return a fully populated :class:`FileInfo`."""
        content = file_path.read_text(encoding="utf-8", errors="replace")
        ext = file_path.suffix.lower()

        adapter = LanguageRegistry.get_by_extension(ext)
        if adapter is None:
            raise ValueError(f"No language adapter for extension: {ext}")

        parser = self._get_parser(ext)
        tree = parser.parse(content.encode("utf-8"))

        extractor = adapter.extractor
        functions = extractor.extract_functions(tree.root_node, content)
        classes = extractor.extract_classes(tree.root_node, content)
        interfaces = extractor.extract_interfaces(tree.root_node, content)
        imports = extractor.extract_imports(tree.root_node, content)
        exports = extractor.extract_exports(tree.root_node, content)

        line_count = content.count("\n") + 1

        return FileInfo(
            path=file_path.relative_to(project_root),
            name=file_path.name,
            size_bytes=file_path.stat().st_size,
            line_count=line_count,
            functions=functions,
            classes=classes,
            interfaces=interfaces,
            imports=imports,
            exports=exports,
            file_hash=compute_file_hash(file_path),
            source_text=content,
        )

    def supported_extensions(self) -> list[str]:
        """Return all file extensions this parser can handle."""
        return sorted(LanguageRegistry.all_extensions())
