from __future__ import annotations

# Re-exported from code2doc-core for backward compatibility
from code2doc_core.constants import DEFAULT_IGNORE_PATTERNS, DEFAULT_IGNORE_EXTENSIONS  # noqa: F401

# Extensions to keep even if a broader pattern above would exclude them.
KEEP_EXTENSIONS: list[str] = [
    "__init__.py",
]
