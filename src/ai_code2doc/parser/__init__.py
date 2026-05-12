"""Parser sub-package for ai_code2doc.

Provides language-aware tree-sitter parsing of source files into structured
:class:`~ai_code2doc.models.module.FileInfo` objects.  Supported languages
are registered in the :class:`~ai_code2doc.parser.language_registry.LanguageRegistry`.
"""

from __future__ import annotations

from ai_code2doc.parser.base_extractor import BaseStructureExtractor
from ai_code2doc.parser.base_parser import BaseParser
from ai_code2doc.parser.base_resolver import BaseImportResolver
from ai_code2doc.parser.language_registry import LanguageAdapter, LanguageRegistry
from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser

__all__ = [
    "BaseParser",
    "BaseStructureExtractor",
    "BaseImportResolver",
    "LanguageAdapter",
    "LanguageRegistry",
    "TreeSitterParser",
]
