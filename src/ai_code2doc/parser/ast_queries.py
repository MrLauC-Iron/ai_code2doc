"""Backward-compatible re-exports.

.. deprecated::
    Use the helpers in :mod:`ai_code2doc.parser.languages._common` instead.
"""

from ai_code2doc.parser.languages._common import (  # noqa: F401
    get_text as node_text,
    get_line as node_line,
    get_end_line as node_end_line,
)

__all__ = ["node_text", "node_line", "node_end_line"]
