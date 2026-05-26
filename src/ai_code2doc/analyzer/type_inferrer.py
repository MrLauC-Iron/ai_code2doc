"""Lightweight type inference from assignment patterns in function bodies."""

from __future__ import annotations

from tree_sitter import Language, Node, Parser

import tree_sitter_python as tspy

# ---------------------------------------------------------------------------
# Module-level cached parser (created once for performance)
# ---------------------------------------------------------------------------

_PY_LANGUAGE = Language(tspy.language())
_parser_cache: Parser | None = None


def _get_parser() -> Parser:
    """Return a cached tree-sitter ``Parser`` for Python."""
    global _parser_cache  # noqa: PLW0603
    if _parser_cache is None:
        _parser_cache = Parser(_PY_LANGUAGE)
    return _parser_cache


class TypeScope:
    """Mutable type bindings for variables within a scope."""

    def __init__(self, enclosing_class: str | None = None) -> None:
        self._types: dict[str, str | None] = {}
        self.enclosing_class = enclosing_class

    def set(self, name: str, type_name: str | None) -> None:
        """Bind *name* to *type_name* (which may be ``None`` for untyped)."""
        self._types[name] = type_name

    def lookup(self, name: str) -> str | None:
        """Return the inferred type for *name*, or ``None`` if unknown/untyped."""
        return self._types.get(name)


class TypeInferrer:
    """Infer variable types from assignment statements using tree-sitter.

    This is a *lightweight* heuristic inferrer.  It parses the body of a
    single function or method and walks the AST looking for assignment
    statements whose right-hand side is a constructor call or similar
    pattern.

    Supported patterns
    ------------------
    - ``x = SomeClass()``          -> x: SomeClass
    - ``x = module.Func()``        -> x: module.Func
    - ``self._store = Cache()``    -> self._store: Cache
    - ``x = "literal"``           -> x: None  (untyped)
    - ``x = [1, 2, 3]``           -> x: None  (untyped)
    """

    @staticmethod
    def infer(
        source: str,
        file_path: str,  # noqa: ARG001  – kept for future per-file import maps
        enclosing_class: str | None = None,
    ) -> TypeScope:
        """Parse *source* and return a :class:`TypeScope` of inferred types."""
        parser = _get_parser()
        tree = parser.parse(source.encode("utf-8"))
        scope = TypeScope(enclosing_class=enclosing_class)

        # Bind ``self`` to the enclosing class type (when inside a method).
        if enclosing_class:
            scope.set("self", enclosing_class)

        TypeInferrer._walk(tree.root_node, source, scope)
        return scope

    # ------------------------------------------------------------------
    # AST walking
    # ------------------------------------------------------------------

    @staticmethod
    def _walk(node: Node, source: str, scope: TypeScope) -> None:
        """Recursively walk the AST looking for assignment statements."""
        if node.type == "assignment":
            TypeInferrer._handle_assignment(node, source, scope)

        for child in node.children:
            TypeInferrer._walk(child, source, scope)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_text(node: Node, source: str) -> str:
        return source[node.start_byte : node.end_byte]

    @staticmethod
    def _handle_assignment(node: Node, source: str, scope: TypeScope) -> None:
        """Extract type info from ``left = right``."""
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None:
            return

        name = TypeInferrer._extract_target_name(left, source)
        if name is None:
            return

        type_name = TypeInferrer._infer_rhs(right, source, scope)
        scope.set(name, type_name)

    @staticmethod
    def _extract_target_name(left: Node, source: str) -> str | None:
        """Extract the variable name from the left side of an assignment."""
        if left.type in ("identifier", "attribute"):
            return TypeInferrer._get_text(left, source)
        return None

    @staticmethod
    def _infer_rhs(right: Node, source: str, scope: TypeScope) -> str | None:
        """Infer the type of the right-hand side of an assignment."""
        # Call: SomeClass() or module.func()
        if right.type == "call":
            return TypeInferrer._infer_call_type(right, source, scope)

        # Attribute: self.X, obj.Y
        if right.type == "attribute":
            attr = TypeInferrer._get_text(right, source)
            if attr.startswith("self."):
                attr = attr[5:]
            if scope.enclosing_class:
                return None  # Would need full class analysis
            return attr

        # String/number literal -> untyped
        if right.type in ("string", "number", "integer", "float"):
            return None

        # List/tuple/set/dict literal -> untyped
        if right.type in ("list", "tuple", "set", "dict"):
            return None

        # Identifier: could be a type name or a variable alias
        if right.type == "identifier":
            text = TypeInferrer._get_text(right, source)
            if text in ("None", "True", "False", "NotImplemented"):
                return None
            return scope.lookup(text)

        # for-loop target: `for x in ...`
        if right.type == "for":
            return None

        return None

    @staticmethod
    def _infer_call_type(call_node: Node, source: str, scope: TypeScope) -> str | None:
        """Infer the type name from a call expression."""
        func = call_node.child_by_field_name("function")
        if func is None:
            return None

        # identifier: SomeClass() or bare function()
        if func.type == "identifier":
            return TypeInferrer._get_text(func, source)

        # attribute: module.Class() or obj.method()
        if func.type == "attribute":
            return TypeInferrer._get_text(func, source)

        return None
