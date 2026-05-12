"""Backward-compatible re-exports.

.. deprecated::
    Use the language-specific resolvers in :mod:`ai_code2doc.parser.languages`
    instead.
"""

# The original ImportResolver was TS/JS-only and has been removed.
# Code that needs import resolution should use the resolver from the
# appropriate LanguageAdapter via LanguageRegistry.

__all__ = []
