"""Abstract base class for language-specific structure extractors.

Every supported language must provide a concrete subclass that walks
its tree-sitter AST and returns the unified model objects
(:class:`FunctionInfo`, :class:`ClassInfo`, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from tree_sitter import Node

from ai_code2doc.models.module import (
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    InterfaceInfo,
)


class BaseStructureExtractor(ABC):
    """Language-agnostic interface for extracting structural information."""

    @abstractmethod
    def extract_functions(self, root: Node, source: str) -> list[FunctionInfo]:
        """Extract top-level function declarations / definitions."""
        ...

    @abstractmethod
    def extract_classes(self, root: Node, source: str) -> list[ClassInfo]:
        """Extract class / struct declarations with their members."""
        ...

    def extract_interfaces(self, root: Node, source: str) -> list[InterfaceInfo]:
        """Extract interface declarations.

        Default implementation returns an empty list.  Languages that
        support interfaces (e.g. TypeScript) should override this method.
        """
        return []

    @abstractmethod
    def extract_imports(self, root: Node, source: str) -> list[ImportInfo]:
        """Extract import / include statements."""
        ...

    def extract_exports(self, root: Node, source: str) -> list[str]:
        """Extract export names.

        Default implementation returns an empty list.  Languages with an
        explicit export mechanism (e.g. TypeScript ``export``) should
        override this method.
        """
        return []
