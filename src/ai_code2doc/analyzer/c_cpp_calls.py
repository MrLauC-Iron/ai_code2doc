"""C/C++ call extractor using tree-sitter.

Walks a function/method body AST and extracts all function, method, and
constructor call sites, returning them as :class:`CallSite` models.
"""

from __future__ import annotations

from tree_sitter import Language, Node, Parser

import tree_sitter_cpp as tscpp

from ai_code2doc.models.graph import CallSite

# ---------------------------------------------------------------------------
# Module-level cached parser (created once for performance)
# ---------------------------------------------------------------------------

_CPP_LANGUAGE = Language(tscpp.language())
_PARSER: Parser | None = None


def _get_parser() -> Parser:
    """Return a cached tree-sitter ``Parser`` for C/C++."""
    global _PARSER  # noqa: PLW0603
    if _PARSER is None:
        _PARSER = Parser(_CPP_LANGUAGE)
    return _PARSER


# ---------------------------------------------------------------------------
# C/C++ standard library functions to skip
# ---------------------------------------------------------------------------

_CPP_STDLIB: frozenset[str] = frozenset({
    # stdio
    "printf", "fprintf", "sprintf", "snprintf",
    "scanf", "fscanf", "sscanf",
    "puts", "gets", "getchar", "putchar",
    "fopen", "fclose", "fwrite", "fread", "fgets", "fputs",
    # stdlib
    "malloc", "calloc", "realloc", "free",
    "exit", "abort", "atexit",
    "atoi", "atol", "atof", "strtol", "strtoul",
    # string / memory
    "memcpy", "memmove", "memset", "memcmp",
    "strlen", "strcpy", "strncpy", "strcat", "strcmp",
    # math / misc
    "rand", "srand", "qsort", "bsearch",
    "errno", "perror",
    # C++ keywords / operators
    "sizeof", "offsetof", "typeid",
})

_COMMON_CPP_MACROS: frozenset[str] = frozenset({
    "CV_Assert", "CV_Error", "CV_Error_", "CV_DbgAssert",
    "CV_TRACE_FUNCTION", "CV_TRACE_REGION",
    "CV_LOG_INFO", "CV_LOG_WARNING", "CV_LOG_ERROR", "CV_LOG_DEBUG", "CV_LOG_FATAL",
    "CV_INSTRUMENT_REGION", "CV_INSTRUMENT_REGION_MT_FORK",
    "CV_UNUSED", "CV_PARSE_ERROR_CPP", "CV_ELEM_SIZE", "CV_MAT_DEPTH",
    "CV_MAT_CN", "CV_MAT_TYPE", "CV_CPU_DISPATCH", "CV_OCL_CODE",
    "OCL_NOT_AVAILABLE", "OCL_ON", "OCL_OFF",
    "GET_OPTIMIZED",
    "LOG", "LOG_INFO", "LOG_WARNING", "LOG_ERROR", "LOG_DEBUG", "LOG_FATAL",
    "DLOG", "DLOG_INFO", "DLOG_WARNING", "DLOG_ERROR",
    "VLOG", "LOG_IF", "LOG_EVERY_N", "LOG_FIRST_N",
    "CHECK", "CHECK_EQ", "CHECK_NE", "CHECK_LE", "CHECK_LT",
    "CHECK_GE", "CHECK_GT", "CHECK_NOTNULL", "CHECK_OK",
    "DCHECK", "DCHECK_EQ", "DCHECK_NE", "DCHECK_LE", "DCHECK_LT",
    "DCHECK_GE", "DCHECK_GT", "DCHECK_NOTNULL",
    "ASSERT", "ASSERT_EQ", "ASSERT_NE", "ASSERT_TRUE", "ASSERT_FALSE",
    "ASSERT_LE", "ASSERT_LT", "ASSERT_GE", "ASSERT_GT",
    "EXPECT_EQ", "EXPECT_NE", "EXPECT_TRUE", "EXPECT_FALSE",
    "EXPECT_LE", "EXPECT_LT", "EXPECT_GE", "EXPECT_GT",
    "MIN", "MAX", "ABS", "CLAMP", "SWAP",
    "LIKELY", "UNLIKELY", "UNUSED", "UNUSED_PARAM",
    "CUDA_CHECK", "CUDA_SAFE_CALL",
    "EIGEN_STATIC_ASSERT", "EIGEN_STRONG_INLINE",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_text(node: Node, source: bytes) -> str:
    """Decode the text of a node from the raw source bytes."""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _extract_callee_name(func_node: Node, source: bytes) -> str | None:
    """Extract the callee name from the function field of a ``call_expression``.

    Handles:
    - ``identifier`` nodes (e.g. ``foo()``)
    - ``field_expression`` nodes (e.g. ``obj->method()``, ``obj.method()``)
    - ``qualified_identifier`` nodes (e.g. ``std::sort()``)
    """
    if func_node.type == "identifier":
        return _get_text(func_node, source)
    if func_node.type == "field_expression":
        return _get_text(func_node, source)
    if func_node.type == "qualified_identifier":
        return _get_text(func_node, source)
    return None


def _classify_call(func_node: Node | None) -> str:
    """Classify a call site based on the function node.

    Returns one of: ``"method"``, ``"function"``, ``"constructor"``.
    """
    if func_node is None:
        return "function"
    if func_node.type == "field_expression":
        return "method"
    return "function"


def _get_first_identifier(callee_name: str) -> str:
    """Extract the first identifier from a callee name.

    For ``data->validate`` returns ``data``.
    For ``obj.process`` returns ``obj``.
    For ``std::sort`` returns ``std``.
    For ``printf`` returns ``printf``.
    """
    for sep in ("::", "->", "."):
        if sep in callee_name:
            return callee_name.split(sep)[0]
    return callee_name


# ---------------------------------------------------------------------------
# Macro collection
# ---------------------------------------------------------------------------


def collect_macro_names(source_bytes: bytes) -> set[str]:
    """Extract function-like macro names from C/C++ source bytes."""
    parser = _get_parser()
    tree = parser.parse(source_bytes)
    names: set[str] = set()
    _walk_for_macros(tree.root_node, source_bytes, names)
    return names


def _walk_for_macros(node: Node, source: bytes, names: set[str]) -> None:
    """Targeted walk: only top-level preproc_function_def nodes."""
    if node.type == "preproc_function_def":
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            names.add(_get_text(name_node, source))
    for child in node.children:
        _walk_for_macros(child, source, names)


# ---------------------------------------------------------------------------
# Recursive call extraction
# ---------------------------------------------------------------------------


def _walk_for_calls(
    node: Node,
    source: bytes,
    caller_fqn: str,
    file_path: str,
    results: list[CallSite],
    known_macros: set[str] | None = None,
) -> None:
    """Recursively walk *node* looking for call sites."""

    # Handle regular function/method calls.
    if node.type == "call_expression":
        func_node = node.child_by_field_name("function")
        if func_node is None:
            for child in node.children:
                _walk_for_calls(child, source, caller_fqn, file_path, results, known_macros)
            return

        callee_name = _extract_callee_name(func_node, source)
        if callee_name is not None:
            # Skip standard library calls.
            first_ident = _get_first_identifier(callee_name)
            if first_ident in _CPP_STDLIB:
                for child in node.children:
                    _walk_for_calls(child, source, caller_fqn, file_path, results, known_macros)
                return

            # Skip known macro calls (function-like macros with no definition).
            if known_macros and first_ident in known_macros:
                for child in node.children:
                    _walk_for_calls(child, source, caller_fqn, file_path, results, known_macros)
                return

            # Skip calls to known external namespaces (std::, __gnu_cxx::).
            if callee_name.startswith("std::") or callee_name.startswith("__gnu_cxx::"):
                for child in node.children:
                    _walk_for_calls(child, source, caller_fqn, file_path, results, known_macros)
                return

            call_type = _classify_call(func_node)
            line_number = node.start_point[0] + 1  # 1-indexed

            results.append(CallSite(
                caller_fqn=caller_fqn,
                callee_name=callee_name,
                file_path=file_path,
                line_number=line_number,
                call_type=call_type,
            ))

        # Recurse into children for nested/chained calls.
        for child in node.children:
            _walk_for_calls(child, source, caller_fqn, file_path, results, known_macros)
        return

    # Handle ``new`` expressions (constructor calls).
    if node.type == "new_expression":
        # The type being constructed is typically a type_identifier child.
        type_node = None
        for child in node.children:
            if child.type == "type_identifier":
                type_node = child
                break
            # For qualified types like std::string
            if child.type == "qualified_identifier":
                type_node = child
                break

        if type_node is not None:
            callee_name = _get_text(type_node, source)
            line_number = node.start_point[0] + 1

            results.append(CallSite(
                caller_fqn=caller_fqn,
                callee_name=callee_name,
                file_path=file_path,
                line_number=line_number,
                call_type="constructor",
            ))

        # Recurse into children for nested expressions.
        for child in node.children:
            _walk_for_calls(child, source, caller_fqn, file_path, results, known_macros)
        return

    # For all other nodes, recurse into named children.
    for child in node.children:
        if child.is_named:
            _walk_for_calls(child, source, caller_fqn, file_path, results, known_macros)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class CCppCallExtractor:
    """Extract function/method call sites from C/C++ source text.

    Designed to operate on a *function body* (a few lines of code), not a
    whole file.  The caller (e.g. :class:`CallGraphBuilder`) is responsible
    for providing the correct source snippet.
    """

    @staticmethod
    def extract_calls(
        source: str,
        caller_fqn: str,
        file_path: str,
        known_macros: set[str] | None = None,
    ) -> list[CallSite]:
        """Parse *source* and return all call sites found.

        Parameters
        ----------
        source:
            The raw C/C++ source text (typically a function body).
        caller_fqn:
            Fully qualified name of the containing function/method
            (e.g. ``"Counter.increment"``).
        file_path:
            Path of the file the source comes from (for the ``CallSite``
            record).
        known_macros:
            Optional set of function-like macro names to skip.

        Returns
        -------
        list[CallSite]
            Deduplicated list of call sites ordered by line number.
        """
        parser = _get_parser()
        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)
        root = tree.root_node

        results: list[CallSite] = []
        _walk_for_calls(root, source_bytes, caller_fqn, file_path, results, known_macros)

        # Deduplicate by (callee_name, line_number) while preserving order.
        seen: set[tuple[str, int]] = set()
        deduped: list[CallSite] = []
        for site in results:
            key = (site.callee_name, site.line_number)
            if key not in seen:
                seen.add(key)
                deduped.append(site)

        return deduped
