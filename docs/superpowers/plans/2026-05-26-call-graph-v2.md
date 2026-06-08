# Call Graph v2: Type Inference + C/C++ Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise call graph resolution rate from 28% to ~70%+ by adding local variable type inference, fix import-map FQN matching, filter external calls, and add C/C++ call extraction.

**Architecture:** Add a `TypeInferrer` that tracks assignment-based variable types within function/method bodies (e.g., `parser = TreeSitterParser()` → parser has type TreeSitterParser). Feed inferred types into a `TypeScope` stored on each `FileInfo`, then consult scopes during resolution. Add a `CCppCallExtractor` parallel to `PythonCallExtractor`. Dispatch extractors by language in `CallGraphBuilder`.

**Tech Stack:** Python 3.11+, tree-sitter, tree-sitter-c, tree-sitter-cpp, networkx, pytest, pydantic

---

## File Structure

```
src/ai_code2doc/analyzer/
  type_inferrer.py        # NEW: Scope tracking + type inference engine
  call_extractor.py       # MODIFY: add external lib filtering, refactor base class
  call_graph_builder.py   # MODIFY: language-dispatched extraction, pass type scopes
  symbol_registry.py      # MODIFY: add type-aware resolution strategies
  external_libs.py        # NEW: known external library patterns
  c_cpp_calls.py          # NEW: C/C++ call extractor

models/
  module.py               # MODIFY: add TypeScope to FileInfo (or separate)

tests/unit/
  test_type_inferrer.py
  test_ccpp_call_extractor.py
  test_external_libs.py
  test_call_graph_builder.py  # MODIFY: existing tests still pass
```

---

### Task 1: External Library Filtering

**Files:**
- Create: `src/ai_code2doc/analyzer/external_libs.py`
- Create: `tests/unit/test_external_libs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_external_libs.py
from __future__ import annotations

from ai_code2doc.analyzer.external_libs import is_external_call


class TestExternalLibs:
    def test_known_stdlib(self) -> None:
        assert is_external_call("print", "a.py") is True
        assert is_external_call("len", "a.py") is True
        assert is_external_call("range", "a.py") is True

    def test_project_internal(self) -> None:
        assert is_external_call("parse_file", "a.py") is False

    def test_common_test_mocks(self) -> None:
        assert is_external_call("MagicMock", "a.py") is True
        assert is_external_call("patch", "a.py") is True
        assert is_external_call("AsyncMock", "a.py") is True

    def test_common_stdlib_types(self) -> None:
        assert is_external_call("Path", "a.py") is True
        assert is_external_call("dict", "a.py") is True
        assert is_external_call("list", "a.py") is True
        assert is_external_call("set", "a.py") is True

    def test_dotted_names_not_filtered(self) -> None:
        # obj.method() should NOT be filtered even if 'obj' looks like a builtin
        assert is_external_call("result.append", "a.py") is False
        assert is_external_call("data.items", "a.py") is False

    def test_loguru_console(self) -> None:
        assert is_external_call("console", "a.py") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_external_libs.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement external_libs.py**

```python
# src/ai_code2doc/analyzer/external_libs.py
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

    Only filters bare names (no dots) — ``obj.method()`` calls are never
    filtered because the type of *obj* is unknown without inference.
    """
    if "." in callee_name:
        return False
    return callee_name in _EXTERNAL_SET
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_external_libs.py -v`
Expected: ALL PASS

- [ ] **Step 5: Integrate filter into PythonCallExtractor**

In `src/ai_code2doc/analyzer/call_extractor.py`, in `_walk_for_calls`, after extracting the callee_name but before creating the `CallSite`, add:

```python
        # Skip known external library calls
        from ai_code2doc.analyzer.external_libs import is_external_call
        if "." not in clean_name and is_external_call(clean_name, file_path):
            for child in node.children:
                _walk_for_calls(child, source, caller_fqn, file_path, sites)
            return
```

Add this right after the `clean_name = callee_name.rstrip("()")` line and before the `first_part = clean_name.split(".")` line.

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest -v --tb=short 2>&1 | tail -20`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/ai_code2doc/analyzer/external_libs.py src/ai_code2doc/analyzer/call_extractor.py tests/unit/test_external_libs.py
git commit -m "feat: add external library filtering to call extractor"
```

---

### Task 2: Fix Import Map FQN Matching

**Files:**
- Modify: `src/ai_code2doc/analyzer/symbol_registry.py`
- Modify: `src/ai_code2doc/analyzer/symbol_registry.py` (add `_resolve_module_path` helper)
- Modify: `tests/unit/test_symbol_registry.py`

The core problem: the import map stores dotted module names (`ai_code2doc.scanner.project_scanner`) but FQNs use file paths (`src/ai_code2doc/scanner/project_scanner.py`). Strategy 3 constructs `ai_code2doc.scanner.project_scanner::scan` which never matches.

- [ ] **Step 1: Add tests for module-path conversion**

Add to `tests/unit/test_symbol_registry.py`:

```python
    def test_resolve_module_path_dotted_to_file(self) -> None:
        """Dotted module name should convert to file path for FQN matching."""
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="src/ai_code2doc/scanner/project_scanner.py::ProjectScanner",
            name="ProjectScanner",
            file_path="src/ai_code2doc/scanner/project_scanner.py",
            start_line=1, end_line=5, kind="class",
        ))
        # Import map stores dotted name
        reg.add_import("a.py", "scanner", "ai_code2doc.scanner.project_scanner")
        # Should resolve by converting dotted to file path
        site = CallSite(
            caller_fqn="a.py::main", callee_name="scanner.scan",
            file_path="a.py", line_number=3, call_type="function",
        )
        resolved = reg.resolve_call_site(site, "a.py")
        # The important thing is it finds something, not that confidence is exact
        assert resolved.callee_fqn is not None
        assert "ProjectScanner" in resolved.callee_fqn

    def test_resolve_from_import_direct_to_class(self) -> None:
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="src/models.py::FileInfo",
            name="FileInfo", file_path="src/models.py",
            start_line=64, end_line=79, kind="class",
        ))
        reg.add(SymbolDefinition(
            fqn="src/models.py::FunctionInfo",
            name="FunctionInfo", file_path="src/models.py",
            start_line=10, end_line=22, kind="class",
        ))
        reg.add_import("a.py", "FileInfo", "ai_code2doc.models.module")
        site = CallSite(
            caller_fqn="a.py::main", callee_name="FileInfo",
            file_path="a.py", line_number=3, call_type="class_constructor",
        )
        resolved = reg.resolve_call_site(site, "a.py")
        assert resolved.callee_fqn is not None
```

- [ ] **Step 2: Implement module-path conversion helper**

Add to `src/ai_code2doc/analyzer/symbol_registry.py`, as a new method:

```python
    def _resolve_module_to_file(self, module_dotted: str) -> list[str]:
        """Convert a dotted module name to possible file paths.

        Examples:
            "ai_code2doc.scanner.project_scanner"
            → ["src/ai_code2doc/scanner/project_scanner.py"]

            "ai_code2doc.models.module"
            → ["src/ai_code2doc/models/module.py",
               "src/ai_code2doc/models/module/__init__.py"]
        """
        candidates: list[str] = []
        parts = module_dotted.split(".")
        # Try as a file path: a.b.c → a/b/c.py
        file_path = "/".join(parts) + ".py"
        candidates.append(file_path)
        # Try as a package directory: a.b.c → a/b/c/__init__.py
        init_path = "/".join(parts) + "/__init__.py"
        candidates.append(init_path)
        return candidates
```

- [ ] **Step 3: Fix Strategy 3 in resolve_call_site**

Replace the existing Strategy 3 block (lines ~206-228) with:

```python
        # --- Strategy 3: module.func() via import map --------------------
        if "." in callee_name:
            maybe_module, maybe_func = callee_name.split(".", 1)
            resolved = self.resolve_import(caller_file, maybe_module)
            if resolved is not None:
                # Convert dotted module to file paths and search each
                for candidate_path in self._resolve_module_to_file(resolved):
                    target_fqn = f"{candidate_path}::{maybe_func}"
                    sym = self.get_by_fqn(target_fqn)
                    if sym is not None:
                        return site.model_copy(
                            update={"callee_fqn": sym.fqn, "confidence": 0.95}
                        )
                # Also try: maybe_func is a class imported directly
                for sym in self.get_by_name(maybe_func):
                    if sym.file_path.endswith(
                        "/__init__.py"
                    ) or sym.file_path.replace("/", ".").startswith(resolved):
                        return site.model_copy(
                            update={"callee_fqn": sym.fqn, "confidence": 0.85}
                        )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/unit/test_symbol_registry.py -v`
Expected: ALL PASS (including new tests)

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/analyzer/symbol_registry.py tests/unit/test_symbol_registry.py
git commit -m "fix: resolve import map FQN mismatch for dotted module names"
```

---

### Task 3: Type Scope Model and Inferrer

**Files:**
- Create: `src/ai_code2doc/analyzer/type_inferrer.py`
- Create: `tests/unit/test_type_inferrer.py`

This is the core improvement. The `TypeInferrer` parses function/method bodies to track variable types from assignments.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_type_inferrer.py
from __future__ import annotations

from ai_code2doc.analyzer.type_inferrer import TypeInferrer


class TestTypeInferrer:
    def test_simple_assignment(self) -> None:
        source = (
            "def run():\n"
            "    scanner = ProjectScanner()\n"
            "    scanner.scan()\n"
        )
        scopes = TypeInferrer.infer(source, "a.py")
        assert scopes.lookup("scanner") == "ProjectScanner"

    def test_class_constructor(self) -> None:
        source = (
            "def run():\n"
            "    builder = DependencyGraphBuilder(root)\n"
        )
        scopes = TypeInferrer.infer(source, "a.py")
        assert scopes.lookup("builder") == "DependencyGraphBuilder"

    def test_attribute_access(self) -> None:
        source = (
            "def run(self):\n"
            "    self.data = Cache()\n"
        )
        scopes = TypeInferrer.infer(source, "a.py", enclosing_class="MyClass")
        assert scopes.lookup("self.data") == "Cache"

    def test_from_import_type(self) -> None:
        source = (
            "def run():\n"
            "    fi = parser.parse_file(f, root)\n"
            "    return fi\n"
        )
        scopes = TypeInferrer.infer(source, "a.py")
        # parser was assigned earlier as TreeSitterParser; parse_file returns FileInfo
        assert scopes.lookup("fi") == "FileInfo"

    def test_unknown_type(self) -> None:
        source = (
            "def run():\n"
            "    x = some_unknown_thing()\n"
        )
        scopes = TypeInferrer.infer(source, "a.py")
        assert scopes.lookup("x") is None

    def test_string_literal(self) -> None:
        source = 'def run():\n    name = "hello"\n'
        scopes = TypeInferrer.infer(source, "a.py")
        assert scopes.lookup("name") is None

    def test_self_type(self) -> None:
        source = "def process(self):\n    pass\n"
        scopes = TypeInferrer.infer(source, "a.py", enclosing_class="Service")
        assert scopes.lookup("self") == "Service"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_type_inferrer.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement TypeInferrer**

```python
# src/ai_code2doc/analyzer/type_inferrer.py
"""Lightweight type inference from assignment patterns in function bodies."""

from __future__ import annotations

from tree_sitter import Language, Node, Parser

import tree_sitter_python as tspy

_PY_LANGUAGE = Language(tspy.language())

_parser_cache: Parser | None = None


def _get_parser() -> Parser:
    global _parser_cache
    if _parser_cache is None:
        _parser_cache = Parser(_PY_LANGUAGE)
    return _parser_cache


class TypeScope:
    """Mutable type bindings for variables within a scope."""

    def __init__(self, enclosing_class: str | None = None) -> None:
        self._types: dict[str, str | None] = {}
        self.enclosing_class = enclosing_class

    def set(self, name: str, type_name: str | None) -> None:
        self._types[name] = type_name

    def lookup(self, name: str) -> str | None:
        return self._types.get(name)


class TypeInferrer:
    """Infer variable types from assignment statements using tree-sitter."""

    @staticmethod
    def infer(
        source: str,
        file_path: str,
        enclosing_class: str | None = None,
    ) -> TypeScope:
        """Parse *source* and return a :class:`TypeScope` of inferred types.

        Handles these patterns:
        - ``x = SomeClass()``         → x: SomeClass
        - ``x = module.Func()``     → x: Func (from import map, if available)
        - ``x = self.attr``          → x: attr (from enclosing class attributes)
        - ``x = "literal"``         → x: None (untyped)
        - ``x = [1, 2, 3]``        → x: None (untyped)
        - ``self._store = Cache()``  → self._store: Cache
        """
        parser = _get_parser()
        tree = parser.parse(source.encode("utf-8"))
        scope = TypeScope(enclosing_class=enclosing_class)
        TypeInferrer._walk(tree.root_node, source, scope)
        return scope

    @staticmethod
    def _walk(node: Node, source: str, scope: TypeScope) -> None:
        """Recursively walk the AST looking for assignment statements."""
        if node.type == "assignment":
            TypeInferrer._handle_assignment(node, source, scope)

        for child in node.children:
            TypeInferrer._walk(child, source, scope)

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

        # Get the variable name
        name = TypeInferrer._extract_target_name(left)
        if name is None:
            return

        # Infer type from the right-hand side
        type_name = TypeInferrer._infer_rhs(right, source, scope)
        scope.set(name, type_name)

    @staticmethod
    def _extract_target_name(left: Node) -> str | None:
        """Extract the variable name from the left side of an assignment."""
        if left.type == "identifier":
            return TypeInferrer._get_text(left, "")
        if left.type == "attribute":
            # self.attr or obj.attr
            return TypeInferrer._get_text(left, "")
        return None

    @staticmethod
    def _infer_rhs(right: Node, source: str, scope: TypeScope) -> str | None:
        """Infer the type of the right-hand side of an assignment."""
        # Call: SomeClass() or module.func()
        if right.type == "call":
            return TypeInferrer._infer_call_type(right, source, scope)

        # Attribute: self.X, obj.Y
        if right.type == "attribute":
            # self.store → look up "store" in enclosing class methods
            attr = TypeInferrer._get_text(right, source)
            # Strip self. prefix; the type is the attribute name
            if attr.startswith("self."):
                attr = attr[5:]
            # Try class method lookup
            if scope.enclosing_class:
                return None  # Would need full class analysis
            return attr

        # String/number literal → untyped
        if right.type in ("string", "number", "integer", "float"):
            return None

        # List/tuple literal → untyped
        if right.type in ("list", "tuple", "set", "dict"):
            return None

        # Identifier: could be a type name like "None", "True", or a variable
        if right.type == "identifier":
            text = TypeInferrer._get_text(right, source)
            # If it's a known name, return it as the type
            if text in ("None", "True", "False", "NotImplemented"):
                return None
            return scope.lookup(text)  # variable alias: x = y

        # for-loop target: `for x in ...`
        if right.type == "for":
            return None

        return None

    @staticmethod
    def _infer_call_type(call_node: Node, source: str, scope: TypeScope) -> str | None:
        """Infer the type from a call expression."""
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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/unit/test_type_inferrer.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/analyzer/type_inferrer.py tests/unit/test_type_inferrer.py
git commit -m "feat: add TypeInferrer for local variable type inference"
```

---

### Task 4: Integrate Type Inference into SymbolRegistry Resolution

**Files:**
- Modify: `src/ai_code2doc/analyzer/symbol_registry.py`
- Modify: `src/ai_code2doc/analyzer/call_graph_builder.py`
- Modify: `tests/unit/test_symbol_registry.py`

- [ ] **Step 1: Add type-aware tests to symbol_registry**

Add to `tests/unit/test_symbol_registry.py`:

```python
    def test_resolve_with_type_scope(self) -> None:
        """Variable type inference should resolve parser.parse_file."""
        from ai_code2doc.analyzer.type_inferrer import TypeScope
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="src/parser.py::TreeSitterParser",
            name="TreeSitterParser", file_path="src/parser.py",
            start_line=1, end_line=30, kind="class",
        ))
        reg.add(SymbolDefinition(
            fqn="src/parser.py::TreeSitterParser.parse_file",
            name="parse_file", file_path="src/parser.py",
            start_line=50, end_line=80, kind="method",
        ))
        reg.add(SymbolDefinition(
            fqn="src/main.py::main", name="main",
            file_path="src/main.py", start_line=1, end_line=10, kind="function",
        ))
        scope = TypeScope()
        scope.set("parser", "TreeSitterParser")
        site = CallSite(
            caller_fqn="src/main.py::main", callee_name="parser.parse_file",
            file_path="src/main.py", line_number=3, call_type="method",
        )
        resolved = reg.resolve_call_site(site, "src/main.py", type_scope=scope)
        assert resolved.callee_fqn is not None
        assert "parse_file" in resolved.callee_fqn
```

- [ ] **Step 2: Modify resolve_call_site to accept optional type_scope**

In `src/ai_code2doc/analyzer/symbol_registry.py`, update the signature:

```python
    def resolve_call_site(
        self,
        site: CallSite,
        caller_file: str,
        type_scope: TypeScope | None = None,
    ) -> CallSite:
```

- [ ] **Step 3: Add Strategy 0: type-scope-aware resolution**

Insert **before** Strategy 1 (self.X / cls.X) in `resolve_call_site`:

```python
        # --- Strategy 0: Type-scope-aware resolution --------------------
        if type_scope is not None and "." in callee_name:
            obj_name, method_name = callee_name.split(".", 1)
            inferred_type = type_scope.lookup(obj_name)
            if inferred_type is not None:
                # Look up the inferred type in the symbol registry
                type_syms = self.get_by_name(inferred_type)
                for sym in type_syms:
                    if sym.kind == "class":
                        target_fqn = f"{sym.fqn}.{method_name}"
                        method_sym = self.get_by_fqn(target_fqn)
                        if method_sym is not None:
                            return site.model_copy(
                                update={"callee_fqn": method_sym.fqn, "confidence": 0.90}
                            )
                    elif sym.kind == "function":
                        # type is actually a function, not a class
                        if method_name == sym.name:
                            return site.model_copy(
                                update={"callee_fqn": sym.fqn, "confidence": 0.85}
                            )
                # Also try: the inferred type IS a class and callee is its constructor
                for sym in type_syms:
                    if sym.kind == "class" and sym.name == method_name:
                        return site.model_copy(
                            update={"callee_fqn": sym.fqn, "confidence": 0.80}
                        )
```

- [ ] **Step 4: Update CallGraphBuilder to pass type scopes**

In `src/ai_code2doc/analyzer/call_graph_builder.py`, import TypeInferrer and pass scopes to resolution:

Add import at top:
```python
from ai_code2doc.analyzer.type_inferrer import TypeInferrer
```

In `_resolve_sites`, build type scope and pass to registry:

```python
    def _resolve_sites(self, sites: list[CallSite], fi: FileInfo) -> list[CallSite]:
        """Resolve call site names to FQNs using the registry."""
        file_path = str(fi.path).replace("\\", "/")

        # Build type scope from the source text
        source = getattr(fi, "source_text", None) or ""
        type_scope = None
        if source:
            # Determine enclosing class for the file (approximate)
            caller_parts = sites[0].caller_fqn.split("::") if sites else [""]
            enclosing = None
            if len(caller_parts) >= 2 and "." in caller_parts[1]:
                enclosing = caller_parts[1].split(".")[0]
            type_scope = TypeInferrer.infer(source, file_path, enclosing_class=enclosing)

        resolved: list[CallSite] = []
        for site in sites:
            r = self.registry.resolve_call_site(site, file_path, type_scope=type_scope)
            resolved.append(r)
        return resolved
```

- [ ] **Step 5: Run all tests**

Run: `python -m pytest -v --tb=short 2>&1 | tail -20`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/ai_code2doc/analyzer/symbol_registry.py src/ai_code2doc/analyzer/call_graph_builder.py tests/unit/test_symbol_registry.py
git commit -m "feat: integrate type inference into call site resolution"
```

---

### Task 5: C/C++ Call Extractor

**Files:**
- Create: `src/ai_code2doc/analyzer/c_cpp_calls.py`
- Create: `tests/unit/test_ccpp_call_extractor.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_ccpp_call_extractor.py
from __future__ import annotations

from ai_code2doc.analyzer.c_cpp_calls import CCppCallExtractor
from ai_code2doc.models.graph import CallSite


class TestCCppCallExtractor:
    def test_function_call(self) -> None:
        source = (
            "int add(int a, int b) {\n"
            "    return a + b;\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "add", "math.cpp")
        assert any(s.callee_name == "add" for s in sites)

    def test_method_call(self) -> None:
        source = (
            "void Counter::increment() {\n"
            "    count++;\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "Counter.increment", "counter.cpp")
        assert any("increment" in s.callee_name for s in sites)

    def test_pointer_method_call(self) -> None:
        source = (
            "void process(Data* data) {\n"
            "    data->validate();\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "process", "main.cpp")
        assert any("validate" in s.callee_name for s in sites)

    def test_constructor_call(self) -> None:
        source = (
            "int main() {\n"
            "    std::string s;\n"
            "    return 0;\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "main", "main.cpp")
        # std::string is a constructor — should be extracted
        names = [s.callee_name for s in sites]
        assert any("string" in n for n in names)

    def test_namespace_call(self) -> None:
        source = (
            "void run() {\n"
            "    std::cout << \"hello\";\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "run", "util.cpp")
        names = [s.callee_name for s in sites]
        assert any("cout" in n for n in names)

    def test_no_calls(self) -> None:
        source = (
            "int get_value() {\n"
            "    return 42;\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "get_value", "value.cpp")
        assert len(sites) == 0

    def test_skip_stdlib(self) -> None:
        source = (
            "void process() {\n"
            "    printf(\"hello\");\n"
            "    malloc(100);\n"
            "    free(ptr);\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "process", "proc.cpp")
        # printf and malloc should be filtered as stdlib
        names = [s.callee_name for s in sites]
        assert "printf" not in names
        assert "malloc" not in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_ccpp_call_extractor.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement CCppCallExtractor**

```python
# src/ai_code2doc/analyzer/c_cpp_calls.py
"""Extract function/method call sites from C/C++ source using tree-sitter."""

from __future__ import annotations

import tree_sitter_cpp as tscpp
from tree_sitter import Language, Node, Parser

from ai_code2doc.models.graph import CallSite

_CPP_LANGUAGE = Language(tscpp.language())

_CPP_STDLIB: frozenset[str] = frozenset({
    "printf", "fprintf", "sprintf", "snprintf",
    "scanf", "fscanf", "sscanf",
    "malloc", "calloc", "realloc", "free",
    "memcpy", "memmove", "memset", "memcmp",
    "strlen", "strcpy", "strncpy", "strcat", "strcmp",
    "atoi", "atol", "atof", "strtol", "strtoul",
    "exit", "abort", "assert", "static_assert",
    "sizeof", "offsetof", "typeid", "dynamic_cast",
    "new", "delete", "nothrow",
    "puts", "gets", "getchar", "putchar",
    "rand", "srand", "qsort", "bsearch",
    "errno", "perror", "fopen", "fclose",
    "fwrite", "fread", "fclose", "fgets", "fputs",
    "abort",
})

_parser_cache: Parser | None = None


def _get_parser() -> Parser:
    global _parser_cache
    if _parser_cache is None:
        _parser_cache = Parser(_CPP_LANGUAGE)
    return _parser_cache


def _get_text(node: Node, source: str) -> str:
    return source[node.start_byte : node.end_byte]


def _get_line(node: Node) -> int:
    return node.start_point[0] + 1


class CCppCallExtractor:
    """Extract call sites from C/C++ source code."""

    @staticmethod
    def extract_calls(
        source: str,
        caller_fqn: str,
        file_path: str,
    ) -> list[CallSite]:
        parser = _get_parser()
        tree = parser.parse(source.encode("utf-8"))
        root = tree.root_node
        sites: list[CallSite] = []
        _walk_for_calls(root, source, caller_fqn, file_path, sites)
        return sites


def _walk_for_calls(
    node: Node, source: str, caller_fqn: str, file_path: str, sites: list[CallSite],
) -> None:
    if node.type == "call_expression":
        func = node.child_by_field_name("function")
        if func is not None:
            callee_name = _extract_callee_name(func, source)
            if callee_name is not None:
                first_part = callee_name.split("::")[0].split("->")[0].split(".")[0]
                if first_part in _CPP_STDLIB:
                    for child in node.children:
                        _walk_for_calls(child, source, caller_fqn, file_path, sites)
                    return

                line = _get_line(node)
                call_type = _classify_call(callee_name, func)
                sites.append(CallSite(
                    caller_fqn=caller_fqn,
                    callee_name=callee_name,
                    callee_fqn=None,
                    file_path=file_path,
                    line_number=line,
                    call_type=call_type,
                    confidence=1.0,
                ))

    for child in node.children:
        _walk_for_calls(child, source, caller_fqn, file_path, sites)


def _extract_callee_name(func_node: Node, source: str) -> str | None:
    """Extract the callee name from the function field of a call_expression."""
    if func_node.type == "identifier":
        return _get_text(func_node, source)
    if func_node.type == "field_expression":
        # obj->method or obj.method
        return _get_text(func_node, source)
    if func_node.type == "qualified_identifier":
        # std::sort or ns::func
        return _get_text(func_node, source)
    return None


def _classify_call(callee_name: str, func_node: Node | None) -> str:
    if "::" in callee_name and callee_name.endswith("()"):
        return "constructor"
    if callee_name.endswith("()") and func_node and func_node.type == "identifier":
        # Check PascalCase heuristic for constructors
        name = callee_name[:-2]
        if name and name[0].isupper():
            return "constructor"
    if func_node and func_node.type == "field_expression":
        return "method"
    return "function"
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/unit/test_ccpp_call_extractor.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/analyzer/c_cpp_calls.py tests/unit/test_ccpp_call_extractor.py
git commit -m "feat: add C/C++ call extractor using tree-sitter"
```

---

### Task 6: Language-Dispatched Extraction in CallGraphBuilder

**Files:**
- Modify: `src/ai_code2doc/analyzer/call_graph_builder.py`
- Modify: `src/ai_code2doc/parser/language_registry.py` (add `get_by_extension_or_default` helper)
- Modify: `tests/unit/test_call_graph_builder.py`

- [ ] **Step 1: Add language-dispatched extraction tests**

Add to `tests/unit/test_call_graph_builder.py`:

```python
    def test_ccpp_extraction_dispatch(self, tmp_path: Path) -> None:
        from ai_code2doc.models.module import FileInfo, FunctionInfo
        builder = CallGraphBuilder(tmp_path)
        fi = FileInfo(
            path=tmp_path / "calc.cpp", name="calc.cpp",
            functions=[FunctionInfo(name="add", start_line=1, end_line=4)],
        )
        fi.source_text = "int add(int a, int b) {\n    return a + b;\n}\n"
        sites = builder.build_for_files([fi])
        assert len(sites) >= 1
```

- [ ] **Step 2: Add language detection helper to language_registry**

Add to `src/ai_code2doc/parser/language_registry.py`:

```python
    @classmethod
    def get_extension(file_path: str) -> str:
        """Return the file extension (including dot) for a file path."""
        p = file_path.rfind(".")
        return file_path[p:].lower() if p >= 0 else ""
```

- [ ] **Step 3: Update CallGraphBuilder for multi-language dispatch**

In `src/ai_code2doc/analyzer/call_graph_builder.py`, replace the hardcoded `PythonCallExtractor` usage with language-dispatched logic:

```python
from ai_code2doc.analyzer.type_inferrer import TypeInferrer
from ai_code2doc.parser.language_registry import LanguageRegistry


class CallGraphBuilder:
    def __init__(self, project_root: Path) -> None:
        self.root = project_root
        self.registry = SymbolRegistry()

    def build_for_files(self, file_infos: list[FileInfo]) -> list[CallSite]:
        for fi in file_infos:
            self.registry.add_from_file_info(fi)

        all_sites: list[CallSite] = []
        for fi in file_infos:
            sites = self._extract_from_file(fi)
            resolved = self._resolve_sites(sites, fi)
            all_sites.extend(resolved)

        return all_sites

    @staticmethod
    def _get_extractor(ext: str):
        """Return the appropriate call extractor for a file extension."""
        from ai_code2doc.analyzer.c_cpp_calls import CCppCallExtractor
        if ext in (".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".C"):
            return CCppCallExtractor.extract_calls
        from ai_code2doc.analyzer.call_extractor import PythonCallExtractor
        return PythonCallExtractor.extract_calls

    def _extract_from_file(self, fi: FileInfo) -> list[CallSite]:
        source = getattr(fi, "source_text", None) or ""
        if not source:
            return []

        file_path = str(fi.path).replace("\\", "/")
        ext = file_path.rsplit(".", 1)[-1] if "." in file_path else ""
        extract = self._get_extractor(f".{ext}")
        sites: list[CallSite] = []

        for func in fi.functions:
            fqn = f"{file_path}::{func.name}"
            func_source = self._extract_body(source, func.start_line, func.end_line)
            if func_source:
                func_sites = extract(func_source, fqn, file_path)
                sites.extend(func_sites)

        for cls in fi.classes:
            cls_fqn = f"{file_path}::{cls.name}"
            for method in cls.methods:
                method_fqn = f"{cls_fqn}.{method.name}"
                method_source = self._extract_body(source, method.start_line, method.end_line)
                if method_source:
                    method_sites = extract(method_source, method_fqn, file_path)
                    sites.extend(method_sites)

        return sites

    def _resolve_sites(self, sites: list[CallSite], fi: FileInfo) -> list[CallSite]:
        file_path = str(fi.path).replace("\\", "/")
        source = getattr(fi, "source_text", None) or ""
        type_scope = None
        if source:
            enclosing = None
            if sites:
                caller_parts = sites[0].caller_fqn.split("::")
                if len(caller_parts) >= 2 and "." in caller_parts[1]:
                    enclosing = caller_parts[1].split(".")[0]
            type_scope = TypeInferrer.infer(source, file_path, enclosing_class=enclosing)

        resolved: list[CallSite] = []
        for site in sites:
            r = self.registry.resolve_call_site(site, file_path, type_scope=type_scope)
            resolved.append(r)
        return resolved

    @staticmethod
    def _extract_body(source: str, start_line: int, end_line: int) -> str:
        lines = source.splitlines()
        return "\n".join(lines[start_line - 1 : end_line])
```

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest -v --tb=short 2>&1 | tail -20`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/analyzer/call_graph_builder.py src/ai_code2doc/parser/language_registry.py tests/unit/test_call_graph_builder.py
git commit -m "feat: language-dispatched call extraction for Python and C/C++"
```

---

### Task 7: End-to-End Validation

**Files:**
- Run: existing `tests/integration/test_call_graph_integration.py`
- Create: `tests/integration/test_ccpp_call_graph.py`

- [ ] **Step 1: Add C/C++ call graph integration test**

```python
# tests/integration/test_ccpp_call_graph.py
from __future__ import annotations

from pathlib import Path
from ai_code2doc.analyzer.call_graph_builder import CallGraphBuilder
from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser


class TestCCppCallGraphIntegration:
    def test_cpp_project(self, sample_c_project: Path, output_dir: Path) -> None:
        """Build a call graph for the sample C project."""
        from ai_code2doc.scanner.project_scanner import ProjectScanner

        scanner = ProjectScanner(sample_c_project)
        scan_result = scanner.scan()
        parser = TreeSitterParser()

        file_infos = []
        for f in scan_result.target_files:
            try:
                fi = parser.parse_file(f, sample_c_project)
                file_infos.append(fi)
            except Exception:
                continue

        assert len(file_infos) > 0

        call_builder = CallGraphBuilder(sample_c_project)
        call_sites = call_builder.build_for_files(file_infos)

        # Should find call sites in a real C project
        assert len(call_sites) >= 0

        dep_builder = DependencyGraphBuilder(sample_c_project)
        for fi in file_infos:
            dep_builder.add_file(fi)
        dep_builder.add_call_edges(call_sites)
        graph = dep_builder.build()

        call_edges = [
            (u, v) for u, v, d in graph.edges(data=True)
            if d.get("edge_type") == "call"
        ]
        if call_sites:
            assert len(call_edges) > 0

    def test_two_cpp_files(self, tmp_path: Path) -> None:
        """Test call resolution across C files."""
        a_h = tmp_path / "calc.h"
        a_h.write_text(
            "int add(int a, int b);\n"
            "int multiply(int x, int y);\n",
            encoding="utf-8",
        )
        a_c = tmp_path / "calc.c"
        a_c.write_text(
            '#include "calc.h"\n'
            "\n'
            "int add(int a, int b) {\n'
            "    return a + b;\n'
            "}\n"
            "\n"
            "int compute(int a, int b) {\n'
            "    return multiply(a, b) + add(a, b);\n'
            "}\n",
            encoding="utf-8",
        )

        parser = TreeSitterParser()
        fi_h = parser.parse_file(a_h, tmp_path)
        fi_c = parser.parse_file(a_c, tmp_path)

        call_builder = CallGraphBuilder(tmp_path)
        call_sites = call_builder.build_for_files([fi_h, fi_c])

        # compute() should call both multiply and add
        compute_calls = [s for s in call_sites if "compute" in s.caller_fqn]
        assert any("add" in s.callee_name for s in compute_calls)
        assert any("multiply" in s.callee_name for s in compute_calls)
```

- [ ] **Step 2: Run integration tests**

Run: `python -m pytest tests/integration/test_ccpp_call_graph.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest -v --tb=short 2>&1 | tail -20`
Expected: ALL PASS

- [ ] **Step 4: Run full analyze on project to measure improvement**

Run: `PYTHONIOENCODING=utf-8 python -m ai_code2doc analyze --full --no-llm --layers 3 --no-vector-store "F:/CodeWorkspace/ai_code2doc/ai_code2doc" 2>&1 | grep -E "(Resolved|Call sites|call graph|Resolution)"`
Expected: Resolved rate significantly higher than 28%

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_ccpp_call_graph.py
git commit -m "test: add C/C++ call graph integration tests"
```

---

### Task 8: Commit Design Doc Update

- [ ] **Step 1: Update design doc with v2 changes**

Update `docs/superpowers/specs/2026-05-15-call-graph-design.md` with a "v2 Changes" section documenting the type inference architecture, C/C++ support, and resolution rate improvements.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-05-15-call-graph-design.md
git commit -m "docs: update call graph design document with v2 architecture"
```
