"""Python call extractor using tree-sitter.

Walks a function/method body AST and extracts all function and method call
sites, returning them as :class:`CallSite` models.
"""

from __future__ import annotations

from tree_sitter import Language, Node, Parser

import tree_sitter_python as tspy

from ai_code2doc.models.graph import CallSite

# ---------------------------------------------------------------------------
# Module-level cached parser (created once for performance)
# ---------------------------------------------------------------------------

_PY_LANGUAGE = Language(tspy.language())
_PARSER: Parser | None = None


def _get_parser() -> Parser:
    """Return a cached tree-sitter ``Parser`` for Python."""
    global _PARSER  # noqa: PLW0603
    if _PARSER is None:
        _PARSER = Parser(_PY_LANGUAGE)
    return _PARSER


# ---------------------------------------------------------------------------
# Python builtins to skip (bare calls only, not method calls)
# ---------------------------------------------------------------------------

_PYTHON_BUILTINS: frozenset[str] = frozenset({
    "abs",
    "all",
    "any",
    "ascii",
    "bin",
    "bool",
    "breakpoint",
    "bytearray",
    "bytes",
    "callable",
    "chr",
    "classmethod",
    "compile",
    "complex",
    "delattr",
    "dict",
    "dir",
    "divmod",
    "enumerate",
    "eval",
    "exec",
    "filter",
    "float",
    "format",
    "frozenset",
    "getattr",
    "globals",
    "hasattr",
    "hash",
    "help",
    "hex",
    "id",
    "input",
    "int",
    "isinstance",
    "issubclass",
    "iter",
    "len",
    "list",
    "locals",
    "map",
    "max",
    "memoryview",
    "min",
    "next",
    "object",
    "oct",
    "open",
    "ord",
    "pow",
    "print",
    "property",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "setattr",
    "slice",
    "sorted",
    "staticmethod",
    "str",
    "sum",
    "super",
    "tuple",
    "type",
    "vars",
    "zip",
    "__import__",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_super_call(func_node: Node) -> bool:
    """Return ``True`` if *func_node* represents ``super()``."""
    return func_node.type == "call" and (
        func_node.child_by_field_name("function") is not None
        and func_node.child_by_field_name("function").type == "identifier"
        and func_node.child_by_field_name("function").text.decode() == "super"
    )


def _extract_callee_name(func_node: Node) -> str:
    """Extract the callee name from the ``function`` child of a ``call`` node.

    For ``identifier`` nodes, return the identifier text directly.
    For ``attribute`` nodes (e.g. ``self.validate``), return the full
    dotted expression text.
    """
    if func_node.type == "identifier":
        return func_node.text.decode()
    if func_node.type == "attribute":
        return func_node.text.decode()
    # Fallback: decode the whole text.
    return func_node.text.decode()


def _classify_call(
    func_node: Node,
    callee_name: str,
) -> str:
    """Classify a call site based on the function node and callee name.

    Returns one of: ``"super_call"``, ``"method"``, ``"function"``,
    ``"class_constructor"``.
    """
    # Check for super().__init__(...) pattern.
    if func_node.type == "attribute":
        obj = func_node.child_by_field_name("object")
        if obj is not None and _is_super_call(obj):
            return "super_call"

    # Check for self.X / cls.X patterns.
    if func_node.type == "attribute":
        obj = func_node.child_by_field_name("object")
        if obj is not None and obj.type == "identifier":
            obj_text = obj.text.decode()
            if obj_text in ("self", "cls"):
                return "method"

    # Method calls on objects (attribute access).
    if func_node.type == "attribute":
        return "method"

    # Class constructor heuristic: PascalCase identifier with no dots.
    if func_node.type == "identifier" and callee_name[0:1].isupper():
        return "class_constructor"

    return "function"


# ---------------------------------------------------------------------------
# Recursive call extraction
# ---------------------------------------------------------------------------


def _walk_for_calls(node: Node, results: list[CallSite], caller_fqn: str, file_path: str) -> None:
    """Recursively walk *node* looking for ``call`` nodes."""

    if node.type == "call":
        func_node = node.child_by_field_name("function")
        if func_node is None:
            # Walk children as fallback.
            for child in node.children:
                _walk_for_calls(child, results, caller_fqn, file_path)
            return

        callee_name = _extract_callee_name(func_node)
        call_type = _classify_call(func_node, callee_name)

        # Skip bare builtin calls (e.g. print(), len()) but NOT method calls.
        if call_type == "function" and callee_name in _PYTHON_BUILTINS:
            # Still need to recurse into arguments for nested calls.
            args = node.child_by_field_name("arguments")
            if args is not None:
                for child in args.children:
                    _walk_for_calls(child, results, caller_fqn, file_path)
            return

        # For super_call pattern, the callee_name is like "super().__init__"
        # which includes "super()". Clean it up.
        if call_type == "super_call":
            attr = func_node.child_by_field_name("attribute")
            if attr is not None:
                callee_name = f"super().{attr.text.decode()}"
            else:
                callee_name = "super()"

        line_number = node.start_point[0] + 1  # 1-indexed

        results.append(CallSite(
            caller_fqn=caller_fqn,
            callee_name=callee_name,
            file_path=file_path,
            line_number=line_number,
            call_type=call_type,
        ))

        # Recurse into the function node (for chained calls like
        # self.db.query().filter()) and into arguments.
        for child in func_node.children:
            _walk_for_calls(child, results, caller_fqn, file_path)
        args = node.child_by_field_name("arguments")
        if args is not None:
            for child in args.children:
                _walk_for_calls(child, results, caller_fqn, file_path)
        return

    # For non-call nodes, recurse into all children.
    for child in node.children:
        if child.is_named:
            _walk_for_calls(child, results, caller_fqn, file_path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class PythonCallExtractor:
    """Extract function/method call sites from Python source text.

    Designed to operate on a *function body* (a few lines of code), not a
    whole file.  The caller (e.g. :class:`CallGraphBuilder`) is responsible
    for providing the correct source snippet.
    """

    @staticmethod
    def extract_calls(
        source: str,
        caller_fqn: str,
        file_path: str,
    ) -> list[CallSite]:
        """Parse *source* and return all call sites found.

        Parameters
        ----------
        source:
            The raw source text (typically a function body).
        caller_fqn:
            Fully qualified name of the containing function/method
            (e.g. ``"MyClass.process"``).
        file_path:
            Path of the file the source comes from (for the ``CallSite``
            record).

        Returns
        -------
        list[CallSite]
            Deduplicated list of call sites ordered by line number.
        """
        parser = _get_parser()
        tree = parser.parse(source.encode("utf-8"))
        root = tree.root_node

        results: list[CallSite] = []
        _walk_for_calls(root, results, caller_fqn, file_path)

        # Deduplicate by (callee_name, line_number) while preserving order.
        seen: set[tuple[str, int]] = set()
        deduped: list[CallSite] = []
        for site in results:
            key = (site.callee_name, site.line_number)
            if key not in seen:
                seen.add(key)
                deduped.append(site)

        return deduped
