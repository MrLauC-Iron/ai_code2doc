"""Shared helper utilities used across language extractors."""

from __future__ import annotations

from tree_sitter import Node


def get_text(node: Node, source: str) -> str:
    """Return the source text covered by *node*."""
    return source[node.start_byte : node.end_byte]


def get_line(node: Node) -> int:
    """Return the **1-indexed** start line of *node*."""
    return node.start_point[0] + 1


def get_end_line(node: Node) -> int:
    """Return the **1-indexed** end line of *node*."""
    return node.end_point[0] + 1


def child_by_field(node: Node, field_name: str) -> Node | None:
    """Return the first child matching *field_name*, or ``None``."""
    return node.child_by_field_name(field_name)


def strip_quotes(text: str) -> str:
    """Strip surrounding single, double, or backtick quotes from *text*."""
    if len(text) >= 2 and text[0] in ("'", '"', "`") and text[-1] == text[0]:
        return text[1:-1]
    return text


def find_parent_of_type(node: Node, node_type: str) -> Node | None:
    """Walk up the tree looking for an ancestor of *node_type*."""
    current = node.parent
    while current is not None:
        if current.type == node_type:
            return current
        current = current.parent
    return None
