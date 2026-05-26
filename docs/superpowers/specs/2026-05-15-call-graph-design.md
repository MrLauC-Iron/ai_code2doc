# Function/Class-Level Call Graph Design

**Goal:** Enhance the Layer 3 dependency graph from file-level import relationships to function/class-level call relationships, enabling precise impact analysis, call chain tracing, and richer documentation.

**Date:** 2026-05-15

---

## 1. Problem Statement

The current `DependencyGraphBuilder` produces a graph where:
- **Nodes** = source files (paths)
- **Edges** = import statements between files

This is insufficient for:
- "Which functions does `UserService.authenticate()` call?"
- "If I change `parse_config()`, which functions are affected?"
- "Show me the call chain from `main()` to `DB.query()`"
- "What are the public APIs of this module and who calls them?"

Layer 2 already extracts `FunctionInfo` and `ClassInfo` with names, signatures, and line ranges via tree-sitter. Layer 3 only uses the file-level import edges. The gap: **no function-to-function call relationships are extracted or tracked**.

## 2. Approach

Adopt a two-phase pipeline inspired by [graph-sitter](https://github.com/codegen-sh/graph-sitter) and [Codebase-Memory](https://github.com/DeusData/codebase-memory-mcp):

1. **Extraction Phase**: Walk tree-sitter ASTs to extract raw call sites (function calls, method calls, class instantiations) within each function/method body.
2. **Resolution Phase**: Resolve call-site names to specific function/method definitions using an import map + symbol registry with a confidence-scored resolution cascade.

This is a **backward-compatible enhancement** — the existing file-level graph is preserved. Call relationships are stored as a second layer of edges on the same graph, distinguished by `edge_type`.

## 3. Data Model Changes

### 3.1 New Models (in `models/graph.py`)

```python
class CallSite(BaseModel):
    """A single function/method call extracted from source code."""
    caller_fqn: str            # Fully qualified name of the calling function (e.g. "module.py::MyClass.process")
    callee_name: str           # Name as written in source (e.g. "self.parse", "helper()")
    callee_fqn: str | None     # Resolved fully qualified name (None if unresolved)
    file_path: str             # Source file path
    line_number: int
    call_type: str              # "function", "method", "static_method", "class_constructor", "super_call"
    confidence: float = 1.0     # Resolution confidence (0.0-1.0)

class SymbolDefinition(BaseModel):
    """A function or class definition that can be the target of calls."""
    fqn: str                    # Fully qualified name (e.g. "src/module.py::MyClass.__init__")
    name: str                   # Short name (e.g. "__init__")
    file_path: str
    start_line: int
    end_line: int
    kind: str                   # "function", "method", "class"
    is_exported: bool = False
```

### 3.2 Existing Model Changes

No breaking changes. `DependencyEdge` gains a `callee_name` optional field for call edges:

```python
class DependencyEdge(BaseModel):
    source: str
    target: str
    weight: int = 1
    edge_type: str = "import"   # Existing values: "import", "cmake_link"
                                  # New values: "call", "inherit"
    callee_name: str | None = None  # For call edges: the callee short name
    caller_name: str | None = None  # For call edges: the caller short name
    confidence: float = 1.0        # Resolution confidence for call edges
    line_number: int | None = None  # Source line of the call site
```

### 3.3 Graph Node Convention

Graph nodes will use two naming conventions coexisting in the same `nx.DiGraph`:
- **File nodes**: `src/path/to/file.py` (existing, unchanged)
- **Symbol nodes**: `src/path/to/file.py::ClassName.method_name` or `src/path/to/file.py::function_name` (new)

Edges:
- File → File with `edge_type="import"` (existing)
- Symbol → Symbol with `edge_type="call"` (new)
- File → Symbol with `edge_type="contains"` (new, for bookkeeping)
- Symbol → Symbol with `edge_type="inherit"` (new, for class inheritance)

## 4. Architecture

### 4.1 New Components

```
analyzer/
  call_graph_builder.py    # Orchestrates extraction + resolution
  call_extractor.py        # Tree-sitter based call site extraction
  symbol_registry.py       # Symbol index for resolution

parser/
  extractors/
    call_extractor_base.py # Abstract base for call extraction
    python_calls.py        # Python-specific call extraction
    c_cpp_calls.py         # C/C++ specific call extraction
```

### 4.2 Call Extraction Pipeline

```
For each FileInfo:
  1. Build import map: local_name -> resolved_module
     e.g. "np" -> "numpy", "MyClass" -> "src/models.py::MyClass"

  2. Extract call sites from function/method bodies:
     - Walk each function's AST body
     - Find call nodes (tree-sitter: "call", "call_expression", "method_invocation")
     - Record: caller function, callee name, line, call_type

  3. Resolve callee names:
     Strategy cascade (Codebase-Memory inspired):
     a) Import map: "np.array" -> resolve "np" in imports -> numpy -> find "numpy.array"
     b) Same file: "helper()" -> look up in file's own symbol table
     c) Same class: "self.method()" -> look up in class methods
     d) Unique name: "parse_config()" -> if only one project-wide match
     e) Unresolved: mark confidence=0.3

  4. Add edges to graph:
     - caller_symbol -> callee_symbol (edge_type="call")
     - file -> symbol (edge_type="contains")
```

### 4.3 Python Call Extraction Details

Tree-sitter node types for Python:

| Call Type | AST Pattern | Example |
|-----------|-------------|---------|
| Function call | `call` where function is `identifier` | `helper()` |
| Method call | `call` where function is `attribute` | `self.run()` |
| Chained call | `call` where function is nested `attribute` | `self.db.query().fetch()` |
| Class constructor | `call` where function is `identifier` matching known class | `MyService()` |
| Super call | `call` where function is `attribute` with object `super()` | `super().__init__()` |

Resolution rules for Python:
- `self.method()` → resolve to a method in the same class
- `cls.method()` → resolve to a class method in the same class
- `module.function()` → look up `module` in imports, resolve to target file's function
- `function()` → look up in same file first, then project-wide unique match
- `ClassName()` → look up class definition, resolve to `__init__`

### 4.4 C/C++ Call Extraction Details

Tree-sitter node types for C/C++:

| Call Type | AST Pattern | Example |
|-----------|-------------|---------|
| Function call | `call_expression` where function is `identifier` | `printf()` |
| Method call | `call_expression` where function is `field_expression` | `obj.process()` |
| Member call | `call_expression` where function is `member_expression` | `ptr->next()` |
| Constructor | `call_expression` in `declaration` with type name | `MyClass obj()` |
| Namespace call | `call_expression` where function is `qualified_identifier` | `std::sort()` |

Resolution rules for C/C++:
- `obj.method()` → look up struct/class definition for `obj`'s type, find method
- `ns::function()` → look up namespace in includes, resolve to header
- `function()` → look up in same file, then included headers
- Constructor calls → look up class/struct definition

## 5. Integration Points

### 5.1 DependencyGraphBuilder Enhancement

`add_file()` will be extended to also accept call sites:

```python
def add_file(self, file_info: FileInfo, call_sites: list[CallSite] | None = None) -> None:
    # Existing: file-level import edges
    ...

    # New: symbol nodes and call edges
    if call_sites:
        self._add_symbol_edges(file_info, call_sites)
```

### 5.2 CallGraphBuilder (New Orchestrator)

```python
class CallGraphBuilder:
    """Builds function/class-level call relationships."""

    def __init__(self, project_root: Path):
        self.root = project_root
        self.registry = SymbolRegistry()
        self.call_extractor = CallExtractorFactory.create()

    def build(self, file_infos: list[FileInfo]) -> list[CallSite]:
        """Extract and resolve call sites across all files."""
        # Phase 1: Build symbol registry
        for fi in file_infos:
            self.registry.add_definitions(fi)

        # Phase 2: Extract and resolve call sites
        all_sites: list[CallSite] = []
        for fi in file_infos:
            sites = self.call_extractor.extract_calls(fi)
            resolved = self.registry.resolve_sites(sites, fi)
            all_sites.extend(resolved)

        return all_sites
```

### 5.3 Layer 3 Generator Enhancement

The Layer 3 generator will:
1. Run `CallGraphBuilder` alongside `DependencyGraphBuilder`
2. Add call edges to the graph
3. Generate enhanced documentation including:
   - Per-module call graph summaries
   - Most-called functions (hotspot analysis)
   - Cross-module call interface tables
   - Enhanced call chain analysis (function-level paths)
   - Enhanced Mermaid diagrams (subgraph per module showing internal calls)

### 5.4 Agent Tool Enhancement

The `analyze_deps` agent tool will gain new modes:
- `call_chains`: "Show the call chain from function A to function B"
- `callers`: "Who calls function X?"
- `callees`: "What does function X call?"
- `hotspots`: "Most-called functions in the project"

## 6. FQN (Fully Qualified Name) Convention

Format: `{file_path}::{symbol_name}`

Examples:
- `src/parser/python.py::PythonExtractor.extract_functions` (method)
- `src/parser/python.py::register_python` (function)
- `src/models/module.py::FunctionInfo` (class)
- `src/models/module.py::FunctionInfo.__init__` (method)

For class methods, the FQN includes the class name. Top-level functions use the file path directly.

## 7. Confidence Scoring

Based on Codebase-Memory's approach:

| Resolution Strategy | Confidence | Notes |
|--------------------|-----------|-------|
| Import map + exact match | 0.95 | `module.func()` where module resolves via import |
| Self/cls method in same class | 0.95 | `self.method()` resolved to class body |
| Same file definition | 0.90 | Direct function call within the same file |
| Unique name project-wide | 0.75 | Only one function with this name exists |
| Suffix match | 0.55 | Partial match among multiple candidates |
| Unresolved | 0.30 | Could not determine target |

## 8. Scope and Phases

### Phase 1: Core Infrastructure (this implementation)
- New data models (`CallSite`, `SymbolDefinition`)
- `SymbolRegistry` for indexing definitions
- `CallGraphBuilder` orchestrator
- Python call extractor (most critical language for this project)
- Integration with `DependencyGraphBuilder` (add call edges alongside import edges)
- Enhanced Layer 3 documentation generation
- Enhanced `analyze_deps` agent tool

### Phase 2 (future): Additional Languages
- C/C++ call extractor
- TypeScript/JavaScript call extractor
- Java call extractor

### Phase 3 (future): Advanced Features
- Intra-class call tracking (method-to-method within a class)
- Call frequency counting (how many times X calls Y)
- Community detection (Louvain algorithm) for architecture clusters
- Incremental call graph updates on file change

## 9. Constraints

- **Performance**: Call extraction must not significantly slow down analysis. Tree-sitter ASTs are already parsed — call extraction is an additional walk over existing trees. Target: <2x current analysis time.
- **Accuracy**: Static analysis is inherently approximate for dynamic languages. Confidence scores must be honest about uncertainty. Unresolved calls should be reported, not silently dropped.
- **Backward Compatibility**: Existing file-level graph, Mermaid diagrams, and API must continue to work unchanged. Call edges are additive.
- **Memory**: Large codebases (10K+ files) must not blow up memory. The symbol registry is a simple dict-based index — should be fine for projects up to ~50K files.

---

## 10. v2 Changes (2026-05-26)

The v2 iteration addresses resolution accuracy, language coverage, and noise reduction. All changes are backward-compatible additions.

### 10.1 External Library Filtering (`external_libs.py`)

**Problem:** The Python call extractor produced many `CallSite` entries for stdlib functions (`print`, `len`, `range`), test mocks (`MagicMock`, `patch`), and common third-party libraries (`numpy`, `flask`). These can never resolve to project-internal definitions and inflate the unresolved call count.

**Solution:** A dedicated filter module (`analyzer/external_libs.py`) with three curated sets:

| Set | Examples | Purpose |
|-----|----------|---------|
| `_PYTHON_STDLIB` | `print`, `len`, `isinstance`, `Path` | Built-in and stdlib functions/types |
| `_TEST_MOCKS` | `MagicMock`, `AsyncMock`, `patch`, `pytest` | Test/mock framework calls |
| `_THIRD_PARTY` | `numpy`, `requests`, `flask`, `typer` | Common third-party libraries |

The `is_external_call(callee_name, file_path)` function checks only bare names (no dots), since `obj.method()` calls may resolve project-internally. It is integrated into `PythonCallExtractor._walk_for_calls()` as an early-return filter that still recurses into children for nested calls.

### 10.2 Import Map FQN Fix (`_resolve_module_to_file`)

**Problem:** Strategy 3 (import-map resolution) stored dotted module names (e.g. `ai_code2doc.scanner.project_scanner`) in the import map but tried to match them directly against file-path-based FQNs (e.g. `ai_code2doc/scanner/project_scanner.py::scan`). The dot-vs-slash mismatch caused most import-map lookups to fail.

**Solution:** Added `SymbolRegistry._resolve_module_to_file()` which converts a dotted module name to a list of candidate file paths:

```
"ai_code2doc.scanner.project_scanner"
  -> ["ai_code2doc.scanner.project_scanner",       # original (passthrough)
      "ai_code2doc/scanner/project_scanner.py",     # module-as-file
      "ai_code2doc/scanner/project_scanner/__init__.py",  # package
      "src/ai_code2doc/scanner/project_scanner.py", # with src/ prefix
      "src/ai_code2doc/scanner/project_scanner/__init__.py"]
```

Strategy 3 now iterates over these candidates when constructing the target FQN, and also attempts direct import-map lookup for the full `callee_name` as a fallback.

### 10.3 Type Inference Architecture (`type_inferrer.py`)

**Problem:** Calls like `store.get()` or `cache.invalidate()` could not be resolved because the resolution cascade had no knowledge of what `store` or `cache` were. Only `self.X` calls were resolved within the same class.

**Solution:** A lightweight assignment-based type inferrer that parses function bodies and extracts type bindings.

#### TypeScope

A mutable scope object mapping variable names to inferred type names:

```python
class TypeScope:
    def __init__(self, enclosing_class: str | None = None): ...
    def set(self, name: str, type_name: str | None) -> None: ...
    def lookup(self, name: str) -> str | None: ...
```

When inside a method, `self` is automatically bound to the enclosing class name.

#### TypeInferrer

Walks the tree-sitter AST for a function body looking for assignment statements. Supported patterns:

| Pattern | Inferred Type | Example |
|---------|---------------|---------|
| `x = SomeClass()` | `SomeClass` | Constructor call |
| `x = module.Func()` | `module.Func` | Dotted call |
| `self._store = Cache()` | `self._store -> Cache` | Attribute assignment |
| `x = other_var` | `other_var`'s type | Variable alias |
| `x = "literal"` | `None` (untyped) | Literal values |

### 10.4 Strategy 0: Type-Scope-Aware Resolution

**Problem:** The original 5-strategy cascade (Section 7) had no mechanism to use inferred variable types for resolving `obj.method()` calls where `obj` is a local variable.

**Solution:** A new Strategy 0 inserted at the top of the resolution cascade in `SymbolRegistry.resolve_call_site()`:

```
Resolution strategies (updated, in priority order):

  0. Type-scope-aware  -- use inferred variable types (confidence 0.80-0.90)  [NEW]
  1. self.X / cls.X    -- method on the same class (confidence 0.95)
  2. obj.method()      -- look up method on a known class (confidence 0.85-0.90)
  3. module.func()     -- import-map resolution (confidence 0.95)
  4. Same-file lookup  (confidence 0.90)
  5. Unique name project-wide (confidence 0.75)
  Fallback: unresolved (confidence 0.30)
```

Strategy 0 works by:
1. If the `type_scope` parameter is provided and the callee name contains a dot, split it into `obj_name` and `method_name`.
2. Look up `obj_name` in the type scope to get the inferred type.
3. Find the inferred type's `SymbolDefinition` in the registry.
4. If it is a class, try `class_fqn.method_name`; if it is a function, check for a name match.
5. Also try the case where the inferred type IS the target class (constructor pattern).

Confidence is 0.90 when the method is found on the inferred class, 0.85 for function matches, and 0.80 for constructor resolution.

The `CallGraphBuilder._resolve_sites()` method now creates a `TypeScope` via `TypeInferrer.infer()` for each file and passes it to `resolve_call_site()`.

### 10.5 C/C++ Call Extractor (`c_cpp_calls.py`)

**Problem:** The original design (Section 4.4) described C/C++ extraction but it was deferred to Phase 2. The project needed C/C++ support for mixed-language codebases with CMake integration.

**Solution:** `CCppCallExtractor` in `analyzer/c_cpp_calls.py` using `tree_sitter_cpp`.

#### Call patterns supported

| Pattern | AST Node | Example |
|---------|----------|---------|
| Function call | `call_expression` with `identifier` | `printf()` |
| Method call | `call_expression` with `field_expression` | `obj.process()` |
| Member (pointer) call | `call_expression` with `field_expression` (->) | `ptr->next()` |
| Constructor | `new_expression` with `type_identifier` | `new MyClass()` |
| Qualified call | `call_expression` with `qualified_identifier` | `std::sort()` |

#### C/C++ stdlib filtering

A built-in `_CPP_STDLIB` set filters common C/C++ standard library calls (`printf`, `malloc`, `memcpy`, `strlen`, etc.) analogous to the Python `external_libs.py` filter.

#### API design

Same interface as `PythonCallExtractor`:

```python
class CCppCallExtractor:
    @staticmethod
    def extract_calls(source: str, caller_fqn: str, file_path: str) -> list[CallSite]: ...
```

### 10.6 Language Dispatch in CallGraphBuilder

**Problem:** `CallGraphBuilder` was hardcoded to use `PythonCallExtractor` for all files.

**Solution:** A dispatch mechanism based on file extension:

```python
_CPP_EXTENSIONS: frozenset[str] = frozenset({
    ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx",
})

@staticmethod
def _get_extractor(ext: str) -> Callable[[str, str, str], list[CallSite]]:
    if ext in CallGraphBuilder._CPP_EXTENSIONS:
        return CCppCallExtractor.extract_calls
    return PythonCallExtractor.extract_calls
```

The `_extract_from_file()` method now determines the file extension and selects the appropriate extractor. Type inference (`TypeInferrer`) is currently Python-only; C/C++ files skip type scope creation.

### 10.7 Resolution Rate Impact

The v2 changes improve resolution rates through two mechanisms:

1. **Import map fix** (Section 10.2): Resolves dotted module imports that previously failed the dot-vs-slash mismatch. This is the single largest improvement, enabling Strategy 3 for most cross-module calls.
2. **Strategy 0** (Section 10.4): Resolves `obj.method()` calls on locally-instantiated objects, which previously fell through to the same-file or unique-name strategies (or went unresolved).

External library filtering (Section 10.1) does not directly improve resolution rate but reduces noise: the denominator of "total calls" shrinks, making the resolved percentage more meaningful and reducing false unresolved entries.
