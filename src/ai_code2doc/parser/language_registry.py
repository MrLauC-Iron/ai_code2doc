"""Language registry for multi-language parser support.

Provides a central :class:`LanguageRegistry` where language adapters are
registered at startup and looked up by file extension at parse time.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from tree_sitter import Language

from ai_code2doc.models.project import TechStack
from ai_code2doc.parser.base_extractor import BaseStructureExtractor
from ai_code2doc.parser.base_resolver import BaseImportResolver


@dataclass(frozen=True)
class LanguageAdapter:
    """Bundles all language-specific components for one language (or family).

    Attributes
    ----------
    language_id:
        Unique identifier, e.g. ``"typescript"``, ``"python"``, ``"c_cpp"``.
    display_name:
        Human-readable name, e.g. ``"TypeScript / JavaScript"``.
    extensions:
        Supported file extensions **including** the leading dot.
    tree_sitter_language:
        The tree-sitter :class:`Language` object for this language.
    extractor:
        Concrete :class:`BaseStructureExtractor` instance.
    resolver:
        Concrete :class:`BaseImportResolver` instance.
    detect_tech_stack:
        Callable that takes a *project_root* and returns a :class:`TechStack`.
    detect_entry_points:
        Callable that takes a *project_root* and returns a list of
        entry-point paths (relative to root).
    """

    language_id: str
    display_name: str
    extensions: tuple[str, ...]
    tree_sitter_language: Language
    extractor: BaseStructureExtractor
    resolver: BaseImportResolver
    detect_tech_stack: Callable[[Path], TechStack]
    detect_entry_points: Callable[[Path], list[str]]


class LanguageRegistry:
    """Central registry mapping file extensions to :class:`LanguageAdapter` instances.

    Usage::

        from ai_code2doc.parser.language_registry import LanguageRegistry

        adapter = LanguageRegistry.get_by_extension(".py")
    """

    _adapters: dict[str, LanguageAdapter] = {}
    _ext_map: dict[str, str] = {}

    @classmethod
    def register(cls, adapter: LanguageAdapter) -> None:
        """Register a language adapter.

        If an adapter with the same ``language_id`` already exists it is
        replaced and its extensions are remapped.
        """
        cls._adapters[adapter.language_id] = adapter
        for ext in adapter.extensions:
            cls._ext_map[ext.lower()] = adapter.language_id

    @classmethod
    def get_by_extension(cls, ext: str) -> LanguageAdapter | None:
        """Look up an adapter by file extension (case-insensitive).

        Parameters
        ----------
        ext:
            File extension **including** the leading dot, e.g. ``".py"``.

        Returns
        -------
        LanguageAdapter | None
        """
        lang_id = cls._ext_map.get(ext.lower())
        if lang_id is None:
            return None
        return cls._adapters.get(lang_id)

    @classmethod
    def get_by_id(cls, language_id: str) -> LanguageAdapter | None:
        """Look up an adapter by its ``language_id``."""
        return cls._adapters.get(language_id)

    @classmethod
    def all_extensions(cls) -> set[str]:
        """Return the set of all registered file extensions."""
        return set(cls._ext_map.keys())

    @classmethod
    def all_adapters(cls) -> list[LanguageAdapter]:
        """Return all registered adapters."""
        return list(cls._adapters.values())
