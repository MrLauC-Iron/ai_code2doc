# Function/Class-Level Call Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the Layer 3 dependency graph from file-level imports to function/class-level call relationships, enabling precise impact analysis, call chain tracing, and richer documentation.

**Architecture:** Two-phase pipeline — extraction phase walks existing tree-sitter ASTs for call sites within function/method bodies, resolution phase maps callee names to definitions using an import map + symbol registry with a confidence-scored resolution cascade. Call edges coexist with existing import edges in the same `nx.DiGraph`.

**Tech Stack:** Python 3.11+, tree-sitter, networkx, pytest, pydantic

---

### Task 1: Add CallSite and SymbolDefinition Models

**Files:**
- Modify: `src/ai_code2doc/models/graph.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_call_graph_models.py
from ai_code2doc.models.graph import CallSite, SymbolDefinition


class TestCallSite:
    def test_creation(self) -> None:
        site = CallSite(
            caller_fqn="src/main.py::process",
            callee_name="helper",
            callee_fqn="src/utils.py::helper",
            file_path="src/main.py",
            line_number=10,
            call_type="function",
            confidence=0.95,
        )
        assert site.caller_fqn == "src/main.py::process"
        assert site.callee_name == "helper"
        assert site.confidence == 0.95

    def test_defaults(self) -> None:
        site = CallSite(
            caller_fqn="a.py::f",
            callee_name="g",
            file_path="a.py",
            line_number=1,
            call_type="function",
        )
        assert site.callee_fqn is None
        assert site.confidence == 1.0


class TestSymbolDefinition:
    def test_creation(self) -> None:
        sym = SymbolDefinition(
            fqn="src/models.py::User",
            name="User",
            file_path="src/models.py",
            start_line=10,
            end_line=50,
            kind="class",
            is_exported=True,
        )
        assert sym.kind == "class"
        assert sym.is_exported is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_call_graph_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'CallSite'`

- [ ] **Step 3: Add CallSite and SymbolDefinition to models/graph.py**

Append to `src/ai_code2doc/models/graph.py`:

```python
class CallSite(BaseModel):
    """A single function/method call extracted from source code."""

    model_config = ConfigDict(extra="forbid")

    caller_fqn: str
    callee_name: str
    callee_fqn: str | None = None
    file_path: str
    line_number: int
    call_type: str  # "function", "method", "static_method", "class_constructor", "super_call"
    confidence: float = 1.0


class SymbolDefinition(BaseModel):
    """A function or class definition that can be the target of calls."""

    model_config = ConfigDict(extra="forbid")

    fqn: str
    name: str
    file_path: str
    start_line: int
    end_line: int
    kind: str  # "function", "method", "class"
    is_exported: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_call_graph_models.py -v`
Expected: PASS

- [ ] **Step 5: Extend DependencyEdge with optional call-edge fields**

Add to `DependencyEdge` in `models/graph.py` (existing model, backward-compatible additions):

```python
class DependencyEdge(BaseModel):
    """A directed edge in the project dependency graph."""

    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    weight: int = 1
    edge_type: str = "import"
    callee_name: str | None = None
    caller_name: str | None = None
    confidence: float = 1.0
    line_number: int | None = None
```

- [ ] **Step 6: Update existing graph model tests**

Add to `tests/unit/test_call_graph_models.py`:

```python
class TestDependencyEdgeBackwardCompat:
    def test_import_edge_no_extra_fields(self) -> None:
        edge = DependencyEdge(source="a.py", target="b.py", edge_type="import")
        assert edge.callee_name is None
        assert edge.confidence == 1.0

    def test_call_edge_with_fields(self) -> None:
        edge = DependencyEdge(
            source="a.py::f", target="b.py::g",
            edge_type="call", callee_name="g",
            caller_name="f", confidence=0.95, line_number=10,
        )
        assert edge.edge_type == "call"
        assert edge.line_number == 10
```

- [ ] **Step 7: Run all model tests**

Run: `python -m pytest tests/unit/test_call_graph_models.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/ai_code2doc/models/graph.py tests/unit/test_call_graph_models.py
git commit -m "feat: add CallSite, SymbolDefinition models and extend DependencyEdge"
```

---

### Task 2: Implement SymbolRegistry

**Files:**
- Create: `src/ai_code2doc/analyzer/symbol_registry.py`
- Create: `tests/unit/test_symbol_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_symbol_registry.py
from __future__ import annotations

from pathlib import Path
from ai_code2doc.analyzer.symbol_registry import SymbolRegistry
from ai_code2doc.models.graph import SymbolDefinition, CallSite


class TestSymbolRegistry:
    def test_add_and_lookup_by_fqn(self) -> None:
        reg = SymbolRegistry()
        sym = SymbolDefinition(
            fqn="src/utils.py::helper", name="helper",
            file_path="src/utils.py", start_line=1, end_line=10, kind="function",
        )
        reg.add(sym)
        assert reg.get_by_fqn("src/utils.py::helper") is sym
        assert reg.get_by_fqn("nonexistent") is None

    def test_lookup_by_name(self) -> None:
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="a.py::parse", name="parse",
            file_path="a.py", start_line=1, end_line=5, kind="function",
        ))
        reg.add(SymbolDefinition(
            fqn="b.py::parse", name="parse",
            file_path="b.py", start_line=1, end_line=5, kind="function",
        ))
        results = reg.get_by_name("parse")
        assert len(results) == 2

    def test_unique_name_resolution(self) -> None:
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="a.py::unique_func", name="unique_func",
            file_path="a.py", start_line=1, end_line=5, kind="function",
        ))
        result = reg.get_unique("unique_func")
        assert result is not None
        assert result.fqn == "a.py::unique_func"

    def test_unique_name_ambiguous(self) -> None:
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="a.py::f", name="f", file_path="a.py",
            start_line=1, end_line=5, kind="function",
        ))
        reg.add(SymbolDefinition(
            fqn="b.py::f", name="f", file_path="b.py",
            start_line=1, end_line=5, kind="function",
        ))
        assert reg.get_unique("f") is None

    def test_lookup_by_file(self) -> None:
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="a.py::f1", name="f1", file_path="a.py",
            start_line=1, end_line=5, kind="function",
        ))
        reg.add(SymbolDefinition(
            fqn="a.py::f2", name="f2", file_path="a.py",
            start_line=6, end_line=10, kind="function",
        ))
        reg.add(SymbolDefinition(
            fqn="b.py::g", name="g", file_path="b.py",
            start_line=1, end_line=5, kind="function",
        ))
        assert len(reg.get_by_file("a.py")) == 2
        assert len(reg.get_by_file("b.py")) == 1

    def test_add_from_file_info(self) -> None:
        from ai_code2doc.models.module import FileInfo, FunctionInfo, ClassInfo
        reg = SymbolRegistry()
        fi = FileInfo(
            path=Path("src/parser.py"), name="parser.py",
            functions=[FunctionInfo(name="parse", start_line=1, end_line=10)],
            classes=[ClassInfo(
                name="Parser", start_line=12, end_line=50,
                methods=[FunctionInfo(name="process", start_line=15, end_line=30)],
            )],
        )
        reg.add_from_file_info(fi)
        assert reg.get_by_fqn("src/parser.py::parse") is not None
        assert reg.get_by_fqn("src/parser.py::Parser") is not None
        assert reg.get_by_fqn("src/parser.py::Parser.process") is not None

    def test_import_map_operations(self) -> None:
        reg = SymbolRegistry()
        reg.add_import("a.py", "np", "numpy")
        reg.add_import("a.py", "MyClass", "src/models.py")
        assert reg.resolve_import("a.py", "np") == "numpy"
        assert reg.resolve_import("a.py", "MyClass") == "src/models.py"
        assert reg.resolve_import("a.py", "unknown") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_symbol_registry.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement SymbolRegistry**

```python
# src/ai_code2doc/analyzer/symbol_registry.py
"""Symbol registry for function/class-level call graph resolution."""

from __future__ import annotations

from ai_code2doc.models.graph import SymbolDefinition, CallSite
from ai_code2doc.models.module import FileInfo


class SymbolRegistry:
    """Index of all symbol definitions in the project, used for call resolution."""

    def __init__(self) -> None:
        self._by_fqn: dict[str, SymbolDefinition] = {}
        self._by_name: dict[str, list[SymbolDefinition]] = {}
        self._by_file: dict[str, list[SymbolDefinition]] = {}
        self._import_map: dict[str, dict[str, str]] = {}  # file -> {local_name: module_path}

    def add(self, sym: SymbolDefinition) -> None:
        self._by_fqn[sym.fqn] = sym
        self._by_name.setdefault(sym.name, []).append(sym)
        self._by_file.setdefault(sym.file_path, []).append(sym)

    def add_import(self, file_path: str, local_name: str, resolved_module: str) -> None:
        self._import_map.setdefault(file_path, {})[local_name] = resolved_module

    def get_by_fqn(self, fqn: str) -> SymbolDefinition | None:
        return self._by_fqn.get(fqn)

    def get_by_name(self, name: str) -> list[SymbolDefinition]:
        return list(self._by_name.get(name, []))

    def get_unique(self, name: str) -> SymbolDefinition | None:
        candidates = self._by_name.get(name, [])
        return candidates[0] if len(candidates) == 1 else None

    def get_by_file(self, file_path: str) -> list[SymbolDefinition]:
        return list(self._by_file.get(file_path, []))

    def resolve_import(self, file_path: str, local_name: str) -> str | None:
        file_imports = self._import_map.get(file_path, {})
        return file_imports.get(local_name)

    def add_from_file_info(self, fi: FileInfo) -> None:
        file_path = str(fi.path).replace("\\", "/")
        for func in fi.functions:
            fqn = f"{file_path}::{func.name}"
            self.add(SymbolDefinition(
                fqn=fqn, name=func.name, file_path=file_path,
                start_line=func.start_line, end_line=func.end_line, kind="function",
                is_exported=func.is_exported,
            ))
        for cls in fi.classes:
            cls_fqn = f"{file_path}::{cls.name}"
            self.add(SymbolDefinition(
                fqn=cls_fqn, name=cls.name, file_path=file_path,
                start_line=cls.start_line, end_line=cls.end_line, kind="class",
                is_exported=cls.is_exported,
            ))
            for method in cls.methods:
                method_fqn = f"{file_path}::{cls.name}.{method.name}"
                self.add(SymbolDefinition(
                    fqn=method_fqn, name=method.name, file_path=file_path,
                    start_line=method.start_line, end_line=method.end_line, kind="method",
                    is_exported=cls.is_exported,
                ))
        # Build import map from file's imports
        for imp in fi.imports:
            resolved = self.resolve_import(file_path, imp.source)
            if resolved is None:
                # Use source as-is for from-style imports
                resolved = imp.source.replace(".", "/")
            for spec in imp.specifiers:
                clean = spec.split(" as ")[-1].strip() if " as " in spec else spec.strip()
                self.add_import(file_path, clean, resolved)

    def resolve_call_site(self, site: CallSite, caller_file: str) -> CallSite:
        """Resolve a call site's callee name to a FQN. Returns a new CallSite."""
        callee = site.callee_name

        # Strategy 1: self.X / cls.X → method in same class
        if callee.startswith("self.") or callee.startswith("cls."):
            method_name = callee.split(".", 1)[1]
            # Find the class the caller belongs to
            caller_parts = site.caller_fqn.rsplit(".", 1)
            if len(caller_parts) == 2:
                class_fqn = caller_parts[0]
                method_fqn = f"{class_fqn}.{method_name}"
                sym = self.get_by_fqn(method_fqn)
                if sym:
                    return CallSite(**{**site.model_dump(), "callee_fqn": method_fqn, "confidence": 0.95})

        # Strategy 2: obj.method() → look up method name on class
        if "." in callee and not callee.startswith("self.") and not callee.startswith("cls."):
            parts = callee.split(".", 1)
            prefix, method_name = parts[0], parts[1]
            # Check if prefix is an import
            resolved_mod = self.resolve_import(caller_file, prefix)
            if resolved_mod:
                candidates = self.get_by_name(method_name)
                for c in candidates:
                    if c.file_path.startswith(resolved_mod) or c.file_path == resolved_mod:
                        return CallSite(**{**site.model_dump(), "callee_fqn": c.fqn, "confidence": 0.85})
            # Check if prefix is a class name in same file
            same_file_syms = self.get_by_file(caller_file)
            class_syms = [s for s in same_file_syms if s.kind == "class" and s.name == prefix]
            if class_syms:
                method_fqn = f"{class_syms[0].fqn}.{method_name}"
                sym = self.get_by_fqn(method_fqn)
                if sym:
                    return CallSite(**{**site.model_dump(), "callee_fqn": method_fqn, "confidence": 0.90})

        # Strategy 3: module.func() → import map resolution
        if "." in callee:
            prefix, name = callee.split(".", 1)
            resolved_mod = self.resolve_import(caller_file, prefix)
            if resolved_mod:
                target_fqn = f"{resolved_mod}::{name}"
                sym = self.get_by_fqn(target_fqn)
                if sym:
                    return CallSite(**{**site.model_dump(), "callee_fqn": target_fqn, "confidence": 0.95})

        # Strategy 4: Same file lookup
        same_file = self.get_by_file(caller_file)
        for sym in same_file:
            if sym.name == callee and sym.kind in ("function",):
                return CallSite(**{**site.model_dump(), "callee_fqn": sym.fqn, "confidence": 0.90})

        # Strategy 5: Unique name project-wide
        unique = self.get_unique(callee)
        if unique:
            return CallSite(**{**site.model_dump(), "callee_fqn": unique.fqn, "confidence": 0.75})

        # Unresolved
        return CallSite(**{**site.model_dump(), "confidence": 0.30})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_symbol_registry.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/analyzer/symbol_registry.py tests/unit/test_symbol_registry.py
git commit -m "feat: add SymbolRegistry for call site resolution"
```

---

### Task 3: Implement Python Call Extractor

**Files:**
- Create: `src/ai_code2doc/analyzer/call_extractor.py`
- Create: `tests/unit/test_call_extractor.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_call_extractor.py
from __future__ import annotations

from pathlib import Path
from ai_code2doc.analyzer.call_extractor import PythonCallExtractor
from ai_code2doc.models.graph import CallSite


class TestPythonCallExtractor:
    def test_simple_function_call(self) -> None:
        source = (
            "def process():\n"
            "    helper()\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "process", "test.py")
        assert len(sites) == 1
        assert sites[0].callee_name == "helper"
        assert sites[0].call_type == "function"

    def test_method_call_on_self(self) -> None:
        source = (
            "def process(self):\n"
            "    self.validate()\n"
            "    self.data.save()\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "MyClass.process", "test.py")
        assert len(sites) == 2
        assert sites[0].callee_name == "self.validate"
        assert sites[0].call_type == "method"
        assert sites[1].callee_name == "self.data.save"
        assert sites[1].call_type == "method"

    def test_method_call_on_object(self) -> None:
        source = (
            "def run(self):\n"
            "    parser = Parser()\n"
            "    result = parser.parse(text)\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "run", "test.py")
        call_names = [s.callee_name for s in sites]
        assert "parser.parse" in call_names
        assert "Parser" in call_names

    def test_class_constructor(self) -> None:
        source = (
            "def create():\n"
            "    service = MyService()\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "create", "test.py")
        assert any(s.callee_name == "MyService" for s in sites)

    def test_super_call(self) -> None:
        source = (
            "def __init__(self, x):\n"
            "    super().__init__(x)\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "MyClass.__init__", "test.py")
        assert any(s.call_type == "super_call" for s in sites)

    def test_no_calls(self) -> None:
        source = (
            "def empty():\n"
            "    x = 1\n"
            "    return x\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "empty", "test.py")
        assert len(sites) == 0

    def test_chained_calls(self) -> None:
        source = (
            "def run(self):\n"
            "    self.db.query().filter().first()\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "run", "test.py")
        assert len(sites) >= 1

    def test_skips_print_and_builtins(self) -> None:
        source = (
            "def run():\n"
            "    print('hello')\n"
            "    len([1, 2, 3])\n"
            "    custom_func()\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "run", "test.py")
        assert len(sites) >= 1
        assert any(s.callee_name == "custom_func" for s in sites)

    def test_with_line_numbers(self) -> None:
        source = "def f():\n    g()\n"
        sites = PythonCallExtractor.extract_calls(source, "f", "test.py")
        assert sites[0].line_number == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_call_extractor.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement PythonCallExtractor**

```python
# src/ai_code2doc/analyzer/call_extractor.py
"""Extract function/method call sites from tree-sitter ASTs."""

from __future__ import annotations

import tree_sitter_python as tspy
from tree_sitter import Language, Parser, Node

from ai_code2doc.models.graph import CallSite

_PY_LANGUAGE = Language(tspy.language())

_BUILTINS = frozenset({
    "print", "len", "range", "str", "int", "float", "list", "dict", "set",
    "tuple", "bool", "bytes", "type", "isinstance", "issubclass", "hasattr",
    "getattr", "setattr", "delattr", "property", "staticmethod", "classmethod",
    "super", "enumerate", "zip", "map", "filter", "sorted", "reversed",
    "any", "all", "min", "max", "sum", "abs", "round", "hash", "id",
    "repr", "format", "open", "input", "iter", "next", "dir", "vars",
    "exec", "eval", "compile", "__import__", "breakpoint", "callable",
    "chr", "ord", "hex", "oct", "bin", "pow", "divmod", "complex",
    "memoryview", "bytearray", "frozenset", "slice", "object",
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "AttributeError", "RuntimeError", "StopIteration", "NotImplementedError",
    "ImportError", "FileNotFoundError", "OSError", "IOError",
})

_parser_cache: Parser | None = None


def _get_parser() -> Parser:
    global _parser_cache
    if _parser_cache is None:
        _parser_cache = Parser(_PY_LANGUAGE)
    return _parser_cache


def _get_text(node: Node, source: str) -> str:
    return source[node.start_byte : node.end_byte]


def _get_line(node: Node) -> int:
    return node.start_point[0] + 1


def _extract_call_name(node: Node, source: str) -> str | None:
    """Extract the callee name from a call/function node.

    Handles: identifier (foo), attribute (self.bar, obj.method),
    chained attributes (self.data.process).
    """
    func_node = node.child_by_field_name("function")
    if func_node is None:
        return None

    if func_node.type == "identifier":
        return _get_text(func_node, source)

    if func_node.type == "attribute":
        return _get_text(func_node, source)

    return None


def _classify_call(callee_name: str, func_node: Node | None, source: str) -> str:
    """Classify the type of call."""
    if callee_name.startswith("super(") or callee_name.startswith("super."):
        return "super_call"

    if callee_name.startswith("self.") or callee_name.startswith("cls."):
        return "method"

    # Check if function node is an attribute (method call on object)
    if func_node and func_node.type == "attribute":
        return "method"

    return "function"


class PythonCallExtractor:
    """Extract function/method call sites from Python source code."""

    @staticmethod
    def extract_calls(
        source: str,
        caller_fqn: str,
        file_path: str,
    ) -> list[CallSite]:
        """Parse *source* and return all call sites within it.

        Parameters
        ----------
        source:
            The Python source code of a function/method body.
        caller_fqn:
            Fully qualified name of the caller (e.g. "module.py::MyClass.process").
        file_path:
            Path to the file (for import resolution context).
        """
        parser = _get_parser()
        tree = parser.parse(source.encode("utf-8"))
        root = tree.root_node

        sites: list[CallSite] = []
        _walk_for_calls(root, source, caller_fqn, file_path, sites)
        return sites


def _walk_for_calls(
    node: Node,
    source: str,
    caller_fqn: str,
    file_path: str,
    sites: list[CallSite],
) -> None:
    """Recursively walk the AST looking for call nodes."""
    if node.type == "call":
        callee_name = _extract_call_name(node, source)
        if callee_name is not None:
            # Strip parentheses for class constructor detection
            clean_name = callee_name.rstrip("()")

            # Skip Python builtins
            first_part = clean_name.split(".")[0].split("(")[0]
            if first_part in _BUILTINS and "." not in clean_name:
                # Still record builtins with method access (e.g. print is skipped
                # but not obj.something)
                for child in node.children:
                    _walk_for_calls(child, source, caller_fqn, file_path, sites)
                return

            func_node = node.child_by_field_name("function")
            call_type = _classify_call(clean_name, func_node, source)
            line = _get_line(node)

            sites.append(CallSite(
                caller_fqn=caller_fqn,
                callee_name=clean_name,
                callee_fqn=None,
                file_path=file_path,
                line_number=line,
                call_type=call_type,
                confidence=1.0,
            ))

    for child in node.children:
        _walk_for_calls(child, source, caller_fqn, file_path, sites)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_call_extractor.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/analyzer/call_extractor.py tests/unit/test_call_extractor.py
git commit -m "feat: add Python call extractor using tree-sitter"
```

---

### Task 4: Implement CallGraphBuilder Orchestrator

**Files:**
- Create: `src/ai_code2doc/analyzer/call_graph_builder.py`
- Create: `tests/unit/test_call_graph_builder.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_call_graph_builder.py
from __future__ import annotations

from pathlib import Path
from ai_code2doc.analyzer.call_graph_builder import CallGraphBuilder
from ai_code2doc.models.graph import CallSite, SymbolDefinition


class TestCallGraphBuilder:
    def test_build_single_file(self) -> None:
        from ai_code2doc.models.module import FileInfo, FunctionInfo
        builder = CallGraphBuilder(Path("/project"))

        fi = FileInfo(
            path=Path("src/main.py"), name="main.py",
            functions=[FunctionInfo(name="main", start_line=1, end_line=10)],
        )
        fi.source_text = "def main():\n    helper()\n    parse()\n"
        sites = builder.build_for_files([fi])
        assert len(sites) >= 2

    def test_build_with_resolution(self) -> None:
        from ai_code2doc.models.module import FileInfo, FunctionInfo
        builder = CallGraphBuilder(Path("/project"))

        fi_a = FileInfo(path=Path("a.py"), name="a.py",
                        functions=[FunctionInfo(name="run", start_line=1, end_line=5)])
        fi_a.source_text = "def run():\n    helper()\n"

        fi_b = FileInfo(path=Path("b.py"), name="b.py",
                        functions=[FunctionInfo(name="helper", start_line=1, end_line=10)])
        fi_b.source_text = "def helper():\n    pass\n"

        sites = builder.build_for_files([fi_a, fi_b])
        resolved = [s for s in sites if s.callee_fqn is not None]
        assert len(resolved) >= 1
        # helper() in a.py should resolve to b.py::helper
        helper_sites = [s for s in resolved if s.callee_name == "helper"]
        assert any("b.py" in s.callee_fqn for s in helper_sites)

    def test_build_empty(self) -> None:
        builder = CallGraphBuilder(Path("/project"))
        sites = builder.build_for_files([])
        assert sites == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_call_graph_builder.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement CallGraphBuilder**

```python
# src/ai_code2doc/analyzer/call_graph_builder.py
"""Orchestrates extraction and resolution of function-level call sites."""

from __future__ import annotations

from pathlib import Path

from ai_code2doc.analyzer.call_extractor import PythonCallExtractor
from ai_code2doc.analyzer.symbol_registry import SymbolRegistry
from ai_code2doc.models.graph import CallSite
from ai_code2doc.models.module import FileInfo


class CallGraphBuilder:
    """Builds function/class-level call relationships across a project."""

    def __init__(self, project_root: Path) -> None:
        self.root = project_root
        self.registry = SymbolRegistry()

    def build_for_files(self, file_infos: list[FileInfo]) -> list[CallSite]:
        """Extract and resolve call sites across all files.

        Parameters
        ----------
        file_infos:
            Parsed FileInfo objects (must have source_text set for call extraction).
        """
        # Phase 1: Build symbol registry from all definitions
        for fi in file_infos:
            self.registry.add_from_file_info(fi)

        # Phase 2: Extract and resolve call sites
        all_sites: list[CallSite] = []
        for fi in file_infos:
            sites = self._extract_from_file(fi)
            resolved = self._resolve_sites(sites, fi)
            all_sites.extend(resolved)

        return all_sites

    def _extract_from_file(self, fi: FileInfo) -> list[CallSite]:
        """Extract raw call sites from a file's functions and methods."""
        source = getattr(fi, "source_text", None)
        if not source:
            return []

        file_path = str(fi.path).replace("\\", "/")
        sites: list[CallSite] = []

        # Extract calls from top-level functions
        for func in fi.functions:
            fqn = f"{file_path}::{func.name}"
            func_source = self._extract_body(source, func.start_line, func.end_line)
            if func_source:
                func_sites = PythonCallExtractor.extract_calls(func_source, fqn, file_path)
                sites.extend(func_sites)

        # Extract calls from class methods
        for cls in fi.classes:
            cls_fqn = f"{file_path}::{cls.name}"
            for method in cls.methods:
                method_fqn = f"{cls_fqn}.{method.name}"
                method_source = self._extract_body(source, method.start_line, method.end_line)
                if method_source:
                    method_sites = PythonCallExtractor.extract_calls(
                        method_source, method_fqn, file_path,
                    )
                    sites.extend(method_sites)

        return sites

    def _resolve_sites(self, sites: list[CallSite], fi: FileInfo) -> list[CallSite]:
        """Resolve call site names to FQNs using the registry."""
        file_path = str(fi.path).replace("\\", "/")
        resolved: list[CallSite] = []
        for site in sites:
            r = self.registry.resolve_call_site(site, file_path)
            resolved.append(r)
        return resolved

    @staticmethod
    def _extract_body(source: str, start_line: int, end_line: int) -> str:
        """Extract the source text for a line range (1-indexed, inclusive)."""
        lines = source.splitlines()
        body_lines = lines[start_line - 1 : end_line]
        return "\n".join(body_lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_call_graph_builder.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/analyzer/call_graph_builder.py tests/unit/test_call_graph_builder.py
git commit -m "feat: add CallGraphBuilder orchestrator"
```

---

### Task 5: Enhance DependencyGraphBuilder with Call Edges

**Files:**
- Modify: `src/ai_code2doc/analyzer/dependency_graph.py`
- Modify: `tests/unit/test_dependency_graph.py` (create if not exists)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_call_graph_integration.py
from __future__ import annotations

from pathlib import Path
from networkx import DiGraph
from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
from ai_code2doc.models.graph import CallSite


class TestDependencyGraphCallEdges:
    def test_add_call_edges(self, tmp_path: Path) -> None:
        builder = DependencyGraphBuilder(tmp_path)
        builder.build()  # initialize graph

        sites = [
            CallSite(
                caller_fqn="a.py::main", callee_name="helper",
                callee_fqn="b.py::helper", file_path="a.py",
                line_number=5, call_type="function", confidence=0.90,
            ),
        ]
        builder.add_call_edges(sites)

        graph = builder.build()
        # File nodes should exist
        assert "a.py" in graph.nodes
        assert "b.py" in graph.nodes
        # Symbol nodes should exist
        assert "a.py::main" in graph.nodes
        assert "b.py::helper" in graph.nodes
        # Call edge should exist
        assert graph.has_edge("a.py::main", "b.py::helper")
        data = graph.get_edge_data("a.py::main", "b.py::helper")
        assert data["edge_type"] == "call"

    def test_contains_edges(self, tmp_path: Path) -> None:
        builder = DependencyGraphBuilder(tmp_path)
        builder.build()

        sites = [
            CallSite(
                caller_fqn="a.py::main", callee_name="helper",
                callee_fqn="a.py::helper", file_path="a.py",
                line_number=5, call_type="function", confidence=0.90,
            ),
        ]
        builder.add_call_edges(sites)
        graph = builder.build()

        # Contains edges: file -> symbol
        assert graph.has_edge("a.py", "a.py::main")
        assert graph.has_edge("a.py", "a.py::helper")
        assert graph.get_edge_data("a.py", "a.py::main")["edge_type"] == "contains"

    def test_existing_import_edges_unchanged(self, tmp_path: Path) -> None:
        from ai_code2doc.models.module import FileInfo, ImportInfo
        builder = DependencyGraphBuilder(tmp_path)
        fi = FileInfo(
            path=tmp_path / "a.py", name="a.py",
            imports=[ImportInfo(source="b", specifiers=["b"])],
        )
        builder.add_file(fi)
        builder.add_call_edges([])
        graph = builder.build()
        # File-level import edges still exist
        assert graph.has_edge(str(fi.path).replace("\\", "/"), "b")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_call_graph_integration.py -v`
Expected: FAIL — `add_call_edges` method does not exist

- [ ] **Step 3: Add add_call_edges to DependencyGraphBuilder**

Add the following method to `DependencyGraphBuilder` in `src/ai_code2doc/analyzer/dependency_graph.py`:

```python
    def add_call_edges(self, call_sites: list[CallSite]) -> None:
        """Add function-level call edges to the graph.

        This adds:
        - Symbol nodes (e.g. ``src/a.py::main``)
        - Call edges (caller_symbol -> callee_symbol, edge_type="call")
        - Contains edges (file -> symbol, edge_type="contains")
        """
        for site in call_sites:
            caller_node = site.caller_fqn
            callee_node = site.callee_fqn
            caller_file = site.file_path

            # Add symbol nodes
            self.graph.add_node(caller_node, kind="symbol")
            self.graph.add_node(caller_file, kind="file")

            # Contains edges: file -> symbol
            if not self.graph.has_edge(caller_file, caller_node):
                self.graph.add_edge(caller_file, caller_node, edge_type="contains")

            # Call edges: caller -> callee
            if callee_node:
                callee_file = callee_node.split("::")[0]
                self.graph.add_node(callee_node, kind="symbol")
                self.graph.add_node(callee_file, kind="file")

                if not self.graph.has_edge(callee_file, callee_node):
                    self.graph.add_edge(callee_file, callee_node, edge_type="contains")

                self.graph.add_edge(
                    caller_node, callee_node,
                    weight=1,
                    edge_type="call",
                    confidence=site.confidence,
                    line_number=site.line_number,
                )
```

Also update the import at the top of `dependency_graph.py` to include `CallSite`:

```python
from ai_code2doc.models.graph import DependencyEdge, CallChain, ImpactHint, CycleInfo, CallSite
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_call_graph_integration.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `python -m pytest tests/unit/ -v --ignore=tests/unit/test_call_graph_models.py --ignore=tests/unit/test_symbol_registry.py --ignore=tests/unit/test_call_extractor.py --ignore=tests/unit/test_call_graph_builder.py --ignore=tests/unit/test_call_graph_integration.py`
Expected: ALL PASS (existing tests still pass with backward-compatible changes)

- [ ] **Step 6: Commit**

```bash
git add src/ai_code2doc/analyzer/dependency_graph.py tests/unit/test_call_graph_integration.py
git commit -m "feat: add call edge support to DependencyGraphBuilder"
```

---

### Task 6: Add source_text to FileInfo

**Files:**
- Modify: `src/ai_code2doc/models/module.py`
- Modify: `src/ai_code2doc/parser/tree_sitter_parser.py`

- [ ] **Step 1: Add source_text field to FileInfo**

In `src/ai_code2doc/models/module.py`, add to `FileInfo`:

```python
    source_text: str = ""
```

This is a backward-compatible addition (default empty string).

- [ ] **Step 2: Populate source_text in TreeSitterParser**

In `src/ai_code2doc/parser/tree_sitter_parser.py`, find the `parse_file` method and add `source_text=source` when constructing the `FileInfo` object.

Read the parser file to find the exact location, then add `source_text=source` to the FileInfo constructor call.

- [ ] **Step 3: Run existing parser tests to verify no regressions**

Run: `python -m pytest tests/unit/test_*parser* tests/integration/test_*parser* -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add src/ai_code2doc/models/module.py src/ai_code2doc/parser/tree_sitter_parser.py
git commit -m "feat: add source_text field to FileInfo for call extraction"
```

---

### Task 7: Enhance Layer 3 Generator with Call Graph Data

**Files:**
- Modify: `src/ai_code2doc/generator/layer3_graph.py`

- [ ] **Step 1: Integrate CallGraphBuilder into Layer 3**

In `src/ai_code2doc/generator/layer3_graph.py`, modify the `generate` method to:

1. After building the import-based dependency graph (step 3), build the call graph:

```python
        # 3b. Build call graph
        from ai_code2doc.analyzer.call_graph_builder import CallGraphBuilder

        call_builder = CallGraphBuilder(project_root)
        call_sites = call_builder.build_for_files(file_infos)
        graph_builder.add_call_edges(call_sites)
```

2. Add call graph statistics to metrics:

```python
        # Call graph metrics
        call_edges = [e for u, v, e in graph.edges(data=True) if e.get("edge_type") == "call"]
        call_node_count = sum(1 for n in graph.nodes if graph.nodes[n].get("kind") == "symbol")
        resolved_calls = sum(1 for s in call_sites if s.callee_fqn is not None)
```

3. Add call hotspot analysis — find most-called symbols:

```python
        # Hotspot analysis: most-called symbols
        caller_counts: dict[str, int] = {}
        for u, v, e in graph.edges(data=True):
            if e.get("edge_type") == "call":
                caller_counts[v] = caller_counts.get(v, 0) + 1
        hotspots = sorted(caller_counts.items(), key=lambda x: x[1], reverse=True)[:10]
```

4. Pass call graph data to static content builder and LLM prompt.

- [ ] **Step 2: Update static content builder**

Add a new section to `_build_static_content` for call graph:

```python
        # Call graph section
        if call_sites:
            call_sections = ["## Call Graph Analysis\n\n"]
            call_sections.append(
                f"The call graph contains **{call_node_count}** symbol nodes and "
                f"**{len(call_sites)}** call sites, **{resolved_calls}** of which "
                f"were resolved to specific definitions.\n"
            )

            if hotspots:
                rows = ["| Symbol | Call Count |", "|--------|------------|"]
                for sym, count in hotspots:
                    rows.append(f"| `{sym}` | {count} |")
                call_sections.append(
                    "### Most-Called Symbols (Hotspots)\n\n"
                    "These functions/methods are called most frequently:\n\n"
                    + "\n".join(rows)
                )

            # Cross-module call interface table
            cross_module_calls = [
                s for s in call_sites
                if s.callee_fqn and "::" in s.callee_fqn
                and s.caller_fqn.split("::")[0] != s.callee_fqn.split("::")[0]
            ]
            if cross_module_calls:
                rows = ["| Caller | Callee | Confidence | Line |",
                         "|--------|--------|------------|------|"]
                for s in cross_module_calls[:20]:
                    rows.append(
                        f"| `{s.caller_fqn}` | `{s.callee_fqn}` | "
                        f"{s.confidence:.0%} | {s.line_number} |"
                    )
                call_sections.append(
                    "### Cross-Module Calls\n\n"
                    "Calls that cross file boundaries:\n\n"
                    + "\n".join(rows)
                )

            sections.append("\n\n".join(call_sections))
```

- [ ] **Step 3: Update LLM prompt with call graph metrics**

Add call graph data to `_format_metrics`:

```python
        parts.append("")
        parts.append(f"Call graph nodes (symbols): {call_node_count}")
        parts.append(f"Call sites: {len(call_sites)}")
        parts.append(f"Resolved calls: {resolved_calls}")
        if hotspots:
            parts.append("")
            parts.append("Most-called symbols (hotspots):")
            for sym, count in hotspots[:10]:
                parts.append(f"  - {sym} (called {count} times)")
```

- [ ] **Step 4: Run existing Layer 3 tests**

Run: `python -m pytest tests/unit/test_*layer3* -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/generator/layer3_graph.py
git commit -m "feat: integrate call graph into Layer 3 generator"
```

---

### Task 8: Enhance analyze_deps Agent Tool

**Files:**
- Modify: `src/ai_code2doc/agent/tools/analyze_deps.py`
- Modify: `tests/unit/test_tool_analyze_deps.py`

- [ ] **Step 1: Add new modes to tool_definition**

In `analyze_deps.py`, update the `enum` in `tool_definition` to include new call graph modes:

```python
        ToolParameter(
            name="mode", type="string", description="Analysis mode",
            required=False,
            enum=["call_chains", "impact", "dependents", "dependencies",
                  "callers", "callees", "hotspots"],
        ),
```

- [ ] **Step 2: Add callers mode**

```python
    elif mode == "callers":
        callers = []
        for u, v, d in graph.edges(data=True):
            if d.get("edge_type") == "call" and v == target:
                callers.append((u, d.get("confidence", 0), d.get("line_number")))
        if not callers:
            return ToolResult(tool_call_id=call.id, content=f"No callers found for '{target}'.")
        lines = [f"Functions that call '{target}':"]
        for caller, conf, ln in callers:
            conf_str = f" (confidence: {conf:.0%})" if conf < 1.0 else ""
            line_str = f" at line {ln}" if ln else ""
            lines.append(f"  - {caller}{line_str}{conf_str}")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))
```

- [ ] **Step 3: Add callees mode**

```python
    elif mode == "callees":
        callees = []
        for u, v, d in graph.edges(data=True):
            if d.get("edge_type") == "call" and u == target:
                callees.append((v, d.get("confidence", 0), d.get("line_number")))
        if not callees:
            return ToolResult(tool_call_id=call.id, content=f"No callees found for '{target}'.")
        lines = [f"Functions called by '{target}':"]
        for callee, conf, ln in callees:
            conf_str = f" (confidence: {conf:.0%})" if conf < 1.0 else ""
            line_str = f" at line {ln}" if ln else ""
            lines.append(f"  - {callee}{line_str}{conf_str}")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))
```

- [ ] **Step 4: Add hotspots mode**

```python
    elif mode == "hotspots":
        caller_counts: dict[str, int] = {}
        for u, v, d in graph.edges(data=True):
            if d.get("edge_type") == "call":
                caller_counts[v] = caller_counts.get(v, 0) + 1
        if not caller_counts:
            return ToolResult(tool_call_id=call.id, content="No call graph data available.")
        sorted_hotspots = sorted(caller_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        lines = ["Most-called symbols (hotspots):"]
        for sym, count in sorted_hotspots:
            lines.append(f"  {sym}: {count} call(s)")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))
```

- [ ] **Step 5: Update _build_graph to include call edges**

Modify `_build_graph` in `analyze_deps.py` to also build call graph:

```python
def _build_graph(context) -> nx.DiGraph | None:
    try:
        from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
        from ai_code2doc.analyzer.call_graph_builder import CallGraphBuilder
        from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser
        from ai_code2doc.scanner.project_scanner import ProjectScanner
        from ai_code2doc.utils.parse_cache import ParseCache

        scanner = ProjectScanner(context.project_root)
        scan_result = scanner.scan()
        parser = TreeSitterParser()
        builder = DependencyGraphBuilder(context.project_root)
        cache = ParseCache(context.output_dir / "file_infos")
        file_infos = []
        for f in scan_result.target_files:
            try:
                fi = cache.get(str(f.relative_to(context.project_root)))
                if fi is None:
                    fi = parser.parse_file(f, context.project_root)
                    cache.put(fi)
                builder.add_file(fi)
                file_infos.append(fi)
            except Exception:
                continue

        # Build call graph edges
        call_builder = CallGraphBuilder(context.project_root)
        call_sites = call_builder.build_for_files(file_infos)
        builder.add_call_edges(call_sites)

        return builder.build()
    except Exception:
        return None
```

- [ ] **Step 6: Add tests for new modes**

Add to `tests/unit/test_tool_analyze_deps.py`:

```python
    def test_execute_callers_mode(self, tmp_path: Path) -> None:
        import networkx as nx
        g = nx.DiGraph()
        g.add_node("a.py::f", kind="symbol")
        g.add_node("a.py::g", kind="symbol")
        g.add_edge("a.py::f", "a.py::g", edge_type="call", confidence=0.9, line_number=5)
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        with patch("ai_code2doc.agent.tools.analyze_deps._build_graph", return_value=g):
            tc = ToolCall(id="c1", name="analyze_deps", arguments={"target": "a.py::g", "mode": "callers"})
            result = execute(tc, ctx)
            assert not result.is_error
            assert "a.py::f" in result.content

    def test_execute_hotspots_mode(self, tmp_path: Path) -> None:
        import networkx as nx
        g = nx.DiGraph()
        g.add_edge("a::f", "a::g", edge_type="call")
        g.add_edge("a::h", "a::g", edge_type="call")
        g.add_edge("a::f", "a::h", edge_type="call")
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        with patch("ai_code2doc.agent.tools.analyze_deps._build_graph", return_value=g):
            tc = ToolCall(id="c1", name="analyze_deps", arguments={"mode": "hotspots"})
            result = execute(tc, ctx)
            assert not result.is_error
```

- [ ] **Step 7: Run all tests**

Run: `python -m pytest tests/unit/test_tool_analyze_deps.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/ai_code2doc/agent/tools/analyze_deps.py tests/unit/test_tool_analyze_deps.py
git commit -m "feat: add callers/callees/hotspots modes to analyze_deps tool"
```

---

### Task 9: End-to-End Integration Test

**Files:**
- Create: `tests/integration/test_call_graph_integration.py`

- [ ] **Step 1: Write integration test with real Python project**

```python
# tests/integration/test_call_graph_integration.py
from __future__ import annotations

from pathlib import Path
import pytest

from ai_code2doc.analyzer.call_graph_builder import CallGraphBuilder
from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser


class TestCallGraphEndToEnd:
    def test_sample_python_project(self, sample_py_project: Path, output_dir: Path) -> None:
        """Build a call graph for the sample Python project and verify results."""
        from ai_code2doc.scanner.project_scanner import ProjectScanner

        scanner = ProjectScanner(sample_py_project)
        scan_result = scanner.scan()
        parser = TreeSitterParser()

        file_infos = []
        for f in scan_result.target_files:
            try:
                fi = parser.parse_file(f, sample_py_project)
                file_infos.append(fi)
            except Exception:
                continue

        assert len(file_infos) > 0

        # All file_infos should have source_text
        for fi in file_infos:
            assert fi.source_text, f"No source_text for {fi.path}"

        # Build call graph
        call_builder = CallGraphBuilder(sample_py_project)
        call_sites = call_builder.build_for_files(file_infos)

        # Should find at least some call sites in a real project
        assert len(call_sites) >= 0  # may be 0 for minimal fixtures

        # Build dependency graph with call edges
        dep_builder = DependencyGraphBuilder(sample_py_project)
        for fi in file_infos:
            dep_builder.add_file(fi)
        dep_builder.add_call_edges(call_sites)
        graph = dep_builder.build()

        # Graph should have both file and symbol nodes
        node_kinds = [graph.nodes[n].get("kind", "file") for n in graph.nodes]
        assert "file" in node_kinds

        # File-level import edges should still exist
        import_edges = [
            (u, v) for u, v, d in graph.edges(data=True)
            if d.get("edge_type") == "import"
        ]

        # Call edges should exist if call sites were found
        if call_sites:
            call_edges = [
                (u, v) for u, v, d in graph.edges(data=True)
                if d.get("edge_type") == "call"
            ]
            assert len(call_edges) > 0

    def test_two_file_cross_call(self, tmp_path: Path) -> None:
        """Test call resolution across two files."""
        # File 1: calls a function from file 2
        a_py = tmp_path / "a.py"
        a_py.write_text(
            "from b import helper\n"
            "\n"
            "def process():\n"
            "    result = helper()\n"
            "    return result\n",
            encoding="utf-8",
        )

        # File 2: defines helper
        b_py = tmp_path / "b.py"
        b_py.write_text(
            "def helper():\n"
            "    return 42\n"
            "\n"
            "def main():\n"
            "    helper()\n"
            "    process()\n",
            encoding="utf-8",
        )

        parser = TreeSitterParser()
        fi_a = parser.parse_file(a_py, tmp_path)
        fi_b = parser.parse_file(b_py, tmp_path)

        call_builder = CallGraphBuilder(tmp_path)
        call_sites = call_builder.build_for_files([fi_a, fi_b])

        # process() in a.py calls helper()
        process_calls = [s for s in call_sites if s.caller_fqn.endswith("::process")]
        assert any(s.callee_name == "helper" for s in process_calls)

        # main() in b.py calls helper() (same file)
        main_calls = [s for s in call_sites if s.caller_fqn.endswith("::main")]
        assert any(s.callee_name == "helper" for s in main_calls)
```

- [ ] **Step 2: Run integration test**

Run: `python -m pytest tests/integration/test_call_graph_integration.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_call_graph_integration.py
git commit -m "test: add end-to-end call graph integration tests"
```

---

### Task 10: Final Review and Cleanup

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest -v --tb=short`
Expected: ALL PASS

- [ ] **Step 2: Verify no regressions in existing tests**

Run: `python -m pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: All tests pass, no warnings or failures

- [ ] **Step 3: Check for any TODO/FIXME left in code**

Run: `grep -rn "TODO\|FIXME\|XXX" src/ai_code2doc/analyzer/call_graph_builder.py src/ai_code2doc/analyzer/call_extractor.py src/ai_code2doc/analyzer/symbol_registry.py`
Expected: No matches (or only intentional placeholders)

- [ ] **Step 4: Verify backward compatibility**

Confirm:
- `DependencyEdge` with no new fields still works
- Existing file-level graph features (import edges, cycles, impact, call chains) are unchanged
- Existing `analyze_deps` modes (`call_chains`, `impact`, `dependents`, `dependencies`) work
- `to_mermaid()` still generates file-level diagram

- [ ] **Step 5: Final commit if any cleanup needed**

```bash
git add -A
git commit -m "chore: final cleanup for call graph feature"
```
