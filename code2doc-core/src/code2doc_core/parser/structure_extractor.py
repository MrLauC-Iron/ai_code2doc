"""Backward-compatible re-exports.

.. deprecated::
    Use the language adapters in :mod:`code2doc_core.parser.languages` instead.
"""

# The original StructureExtractor was TS/JS-only and has been removed.
# Code that needs structure extraction should use TreeSitterParser, which
# delegates to the correct language adapter automatically.

__all__ = []
