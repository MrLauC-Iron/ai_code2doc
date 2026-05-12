"""Built-in language adapters.

Importing this module triggers registration of all built-in language
adapters with :class:`~ai_code2doc.parser.language_registry.LanguageRegistry`.
"""

from __future__ import annotations


def _register_builtin_languages() -> None:
    """Register all built-in language adapters."""
    from ai_code2doc.parser.languages.python import register_python
    from ai_code2doc.parser.languages.c_cpp import register_c_cpp

    register_python()
    register_c_cpp()


_register_builtin_languages()
