"""Lightweight type inference from assignment patterns in function bodies."""

from __future__ import annotations

from tree_sitter import Language, Node, Parser

import tree_sitter_cpp as tscpp
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


# ---------------------------------------------------------------------------
# C++ type inferrer
# ---------------------------------------------------------------------------

_CPP_LANGUAGE = Language(tscpp.language())
_cpp_parser_cache: Parser | None = None


def _get_cpp_parser() -> Parser:
    """Return a cached tree-sitter ``Parser`` for C++."""
    global _cpp_parser_cache  # noqa: PLW0603
    if _cpp_parser_cache is None:
        _cpp_parser_cache = Parser(_CPP_LANGUAGE)
    return _cpp_parser_cache


class CppTypeInferrer:
    """Infer variable types from C++ declarations using tree-sitter.

    This is a *lightweight* heuristic inferrer.  It parses C++ source
    and walks the AST looking for declarations and parameter declarations
    to extract type bindings.

    Supported patterns
    ------------------
    - ``Mat img;``               -> img: Mat
    - ``cv::Mat img;``           -> img: Mat  (namespace stripped)
    - ``Mat* ptr;``              -> ptr: Mat  (pointer stripped)
    - ``void f(Mat& ref)``       -> ref: Mat  (reference stripped)
    - ``auto result = compute();`` -> result: compute
    - ``int x = 5;``             -> x: None   (primitive ignored)
    - ``this`` inside a method   -> this: EnclosingClass
    """

    # C++ primitive types that should not produce type bindings.
    _PRIMITIVE_TYPES = frozenset({
        "void", "int", "char", "short", "long", "float", "double",
        "bool", "unsigned", "signed", "wchar_t", "char16_t", "char32_t",
        "char8_t", "size_t", "ssize_t",
    })

    @staticmethod
    def infer(
        source: str,
        file_path: str,  # noqa: ARG001  -- kept for future per-file import maps
        enclosing_class: str | None = None,
    ) -> TypeScope:
        """Parse *source* and return a :class:`TypeScope` of inferred types."""
        parser = _get_cpp_parser()
        tree = parser.parse(source.encode("utf-8"))
        scope = TypeScope(enclosing_class=enclosing_class)

        # Bind ``this`` to the enclosing class type (when inside a method).
        if enclosing_class:
            scope.set("this", enclosing_class)

        CppTypeInferrer._walk(tree.root_node, source, scope)
        return scope

    # ------------------------------------------------------------------
    # AST walking
    # ------------------------------------------------------------------

    @staticmethod
    def _walk(node: Node, source: str, scope: TypeScope) -> None:
        """Recursively walk the AST looking for declarations."""
        if node.type == "declaration":
            CppTypeInferrer._handle_declaration(node, source, scope)
        elif node.type == "parameter_declaration":
            CppTypeInferrer._handle_parameter(node, source, scope)

        for child in node.children:
            CppTypeInferrer._walk(child, source, scope)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_text(node: Node, source: str) -> str:
        return source[node.start_byte : node.end_byte]

    @staticmethod
    def _handle_declaration(node: Node, source: str, scope: TypeScope) -> None:
        """Extract type info from a C++ declaration statement.

        Handles patterns like:
        - ``Mat img;``
        - ``cv::Mat img;``
        - ``Mat* ptr;``
        - ``auto result = compute();``
        - ``int x = 5;`` (ignored)
        """
        type_node = None
        declarator_node = None
        init_node = None

        for child in node.children:
            if child.type == "type_identifier":
                type_node = child
            elif child.type == "qualified_identifier":
                type_node = child
            elif child.type == "primitive_type":
                # Primitive types are explicitly ignored.
                return
            elif child.type == "placeholder_type_specifier":
                # ``auto`` -- handle via init_declarator.
                type_node = child
            elif child.type in ("pointer_declarator", "reference_declarator"):
                declarator_node = child
            elif child.type == "init_declarator":
                # Contains the variable name and initializer.
                init_node = child
            elif child.type == "identifier" and declarator_node is None and init_node is None:
                # Bare identifier declarator: ``Mat img;``
                declarator_node = child

        # Determine the type name.
        if type_node is not None and type_node.type == "placeholder_type_specifier":
            # ``auto`` -- extract type from the initializer expression.
            if init_node is not None:
                var_name = CppTypeInferrer._find_var_name(init_node, source)
                init_type = CppTypeInferrer._infer_auto_init(init_node, source)
                if var_name is not None:
                    scope.set(var_name, init_type)
            return

        # Skip primitive types (already handled above, but be defensive).
        if type_node is None:
            return

        # Extract the type name from the type node.
        type_name = CppTypeInferrer._extract_type_name(type_node, source)
        if type_name is None:
            return

        # Find the variable name.
        if init_node is not None:
            # ``Mat img = ...;`` -- init_declarator contains the identifier.
            var_name = CppTypeInferrer._find_var_name(init_node, source)
        elif declarator_node is not None:
            # ``Mat* ptr;`` or ``Mat& ref;`` -- pointer/reference declarator.
            var_name = CppTypeInferrer._find_var_name(declarator_node, source)
        else:
            return

        if var_name is not None:
            scope.set(var_name, type_name)

    @staticmethod
    def _handle_parameter(node: Node, source: str, scope: TypeScope) -> None:
        """Extract type info from a C++ function parameter declaration.

        Handles patterns like:
        - ``Mat& ref``
        - ``Mat* ptr``
        - ``const Mat& ref``
        """
        type_node = None
        declarator_node = None

        for child in node.children:
            if child.type == "type_identifier":
                type_node = child
            elif child.type == "qualified_identifier":
                type_node = child
            elif child.type == "primitive_type":
                # Skip primitive-type parameters.
                return
            elif child.type in ("pointer_declarator", "reference_declarator"):
                declarator_node = child
            elif child.type == "identifier" and declarator_node is None:
                declarator_node = child

        if type_node is None:
            return

        type_name = CppTypeInferrer._extract_type_name(type_node, source)
        if type_name is None:
            return

        if declarator_node is not None:
            var_name = CppTypeInferrer._find_var_name(declarator_node, source)
            if var_name is not None:
                scope.set(var_name, type_name)

    @staticmethod
    def _extract_type_name(type_node: Node, source: str) -> str | None:
        """Get the type name from a type node, stripping namespace qualifiers.

        - ``type_identifier`` ("Mat") -> "Mat"
        - ``qualified_identifier`` ("cv::Mat") -> "Mat"
        - ``placeholder_type_specifier`` ("auto") -> "auto" (handled elsewhere)
        """
        if type_node.type == "type_identifier":
            name = CppTypeInferrer._get_text(type_node, source)
            if name in CppTypeInferrer._PRIMITIVE_TYPES:
                return None
            return name

        if type_node.type == "qualified_identifier":
            # Look for the innermost type_identifier within qualified_identifier.
            # ``cv::Mat`` -> qualified_identifier -> namespace_identifier("cv") + :: + type_identifier("Mat")
            for child in type_node.children:
                if child.type == "type_identifier":
                    name = CppTypeInferrer._get_text(child, source)
                    if name in CppTypeInferrer._PRIMITIVE_TYPES:
                        return None
                    return name
            return None

        return None

    @staticmethod
    def _find_var_name(declarator: Node, source: str) -> str | None:
        """Walk a declarator chain to find the identifier node.

        Handles:
        - ``identifier`` -> returns the identifier text directly
        - ``pointer_declarator`` -> recurses into its children
        - ``reference_declarator`` -> recurses into its children
        - ``init_declarator`` -> looks for identifier child first
        """
        if declarator.type == "identifier":
            return CppTypeInferrer._get_text(declarator, source)

        if declarator.type in ("pointer_declarator", "reference_declarator"):
            for child in declarator.children:
                if child.type == "identifier":
                    return CppTypeInferrer._get_text(child, source)

        if declarator.type == "init_declarator":
            # init_declarator: identifier = <expr>
            for child in declarator.children:
                if child.type == "identifier":
                    return CppTypeInferrer._get_text(child, source)

        return None

    @staticmethod
    def _infer_auto_init(init_node: Node, source: str) -> str | None:
        """Infer the type from an ``auto`` initializer expression.

        For ``auto result = compute();``, extract "compute" from the
        call_expression.
        """
        # Walk children of init_declarator looking for the value expression.
        for child in init_node.children:
            if child.type == "call_expression":
                # call_expression -> identifier("compute") + argument_list
                func = child.child_by_field_name("function")
                if func is not None and func.type == "identifier":
                    return CppTypeInferrer._get_text(func, source)
        return None
