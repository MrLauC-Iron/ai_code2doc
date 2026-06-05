"""Parser sub-package for ai_code2doc.

Provides language-aware tree-sitter parsing of source files into structured
:class:`~ai_code2doc.models.module.FileInfo` objects.  Supported languages
are registered in the :class:`~ai_code2doc.parser.language_registry.LanguageRegistry`.
"""

from __future__ import annotations

from code2doc_core.parser.base_extractor import BaseStructureExtractor
from code2doc_core.parser.base_parser import BaseParser
from code2doc_core.parser.base_resolver import BaseImportResolver
from code2doc_core.parser.language_registry import LanguageAdapter, LanguageRegistry
from code2doc_core.parser.tree_sitter_parser import TreeSitterParser

__all__ = [
    "BaseParser",
    "BaseStructureExtractor",
    "BaseImportResolver",
    "LanguageAdapter",
    "LanguageRegistry",
    "TreeSitterParser",
]
