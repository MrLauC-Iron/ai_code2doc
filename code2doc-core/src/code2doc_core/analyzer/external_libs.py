"""Known external library patterns for filtering unresolvable calls."""

from __future__ import annotations

# Standard library functions that appear frequently in code but can
# never resolve to project-internal definitions.
_PYTHON_STDLIB: frozenset[str] = frozenset({
    "print", "len", "range", "str", "int", "float", "list", "dict", "set",
    "tuple", "bool", "bytes", "type", "isinstance", "issubclass", "hasattr",
    "getattr", "setattr", "delattr", "property", "staticmethod", "classmethod",
    "super", "enumerate", "zip", "map", "filter", "sorted", "reversed",
    "any", "all", "min", "max", "sum", "abs", "round", "hash", "id",
    "repr", "format", "open", "input", "iter", "next", "dir", "vars",
    "exec", "eval", "compile", "breakpoint", "callable", "chr", "ord",
    "hex", "oct", "bin", "pow", "divmod", "complex", "frozenset",
    "object", "Exception", "ValueError", "TypeError", "KeyError",
    "IndexError", "AttributeError", "RuntimeError", "StopIteration",
    "NotImplementedError", "ImportError", "FileNotFoundError",
    "OSError", "IOError", "AssertionError", "classmethod",
    # Common typing annotations used as calls
    "Optional", "Union", "Literal",
    # Common stdlib types used as calls
    "Path",
})

# Test/mock library names that are external to any project.
_TEST_MOCKS: frozenset[str] = frozenset({
    "MagicMock", "AsyncMock", "NonCallableMock", "PropertyMock",
    "patch", "mock_open",
    "pytest", "fixture",
})

# Common third-party library names (user-configurable in future).
_THIRD_PARTY: frozenset[str] = frozenset({
    "console", "typer", "click", "rich", "loguru",
    "numpy", "np", "pandas", "pd", "requests",
    "flask", "django", "fastapi", "starlette",
})

_EXTERNAL_SET: frozenset[str] = _PYTHON_STDLIB | _TEST_MOCKS | _THIRD_PARTY


def is_external_call(callee_name: str, file_path: str) -> bool:
    """Return True if *callee_name* is a known external library call.

    Only filters bare names (no dots) -- ``obj.method()`` calls are never
    filtered because the type of *obj* is unknown without inference.
    """
    if "." in callee_name:
        return False
    return callee_name in _EXTERNAL_SET
