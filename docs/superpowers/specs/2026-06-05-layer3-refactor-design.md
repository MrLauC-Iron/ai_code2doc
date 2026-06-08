# Layer3 Refactor: code2doc-core Extraction & layer3_mcp Self-Containment

**Date:** 2026-06-05
**Status:** Approved

## Problem

Layer 3 knowledge generation and query are split across two packages with no clean boundary:

- **Generation** lives in the monolithic `ai_code2doc` package (analyzer, parser, scanner, generator)
- **Query** lives in the standalone `layer3_mcp` package (MCP server, DependencyStore)
- `layer3_mcp` shells out to `ai-code2doc analyze` via subprocess to rebuild DBs
- Adding periodic updates to `layer3_mcp` would deepen this coupling further

Additionally, `layer3_mcp` duplicates core code (DependencyStore, git utilities) that already exists in the main package.

## Goal

1. Extract shared infrastructure into a `code2doc-core` library
2. Make `layer3_mcp` fully self-contained: generation + query + periodic updates
3. Remove subprocess coupling between packages
4. Keep `ai_code2doc` working for layer1/layer2 via `code2doc-core` dependency

## Architecture

```
code2doc-core/              # Shared core library (pure computation, no CLI/UI)
  pyproject.toml            # name = "code2doc-core"
  src/code2doc_core/
    parser/                  # tree-sitter parsing, language adapters
    scanner/                 # project scanning, change detection
    analyzer/                # dependency graph, call graph, metrics
    models/                  # FileInfo, KnowledgeDocument, Graph types
    utils/                   # hashing, git, path_utils, parse_cache

ai_code2doc/                 # Main application (layer1/layer2 + agent/web/cli)
  pyproject.toml            # depends on code2doc-core
  src/ai_code2doc/
    generator/               # layer1_overview, layer2_modules only
    agent/
    web/
    cli/
    mcp/
    config/
    llm/
    vector_store/
    utils/                   # main-package-only utils (markdown, logging)

layer3_mcp/                  # Layer3 standalone package (generate + query + poll)
  pyproject.toml            # depends on code2doc-core, mcp, typer
  src/code2doc_layer3_mcp/
    generator/               # layer3_graph (migrated from main package)
    server/                  # MCP query service (existing)
    branch_manager/          # git branch management (existing, refactored)
    git_poller/             # NEW: periodic git pull + rebuild
    cli.py                   # CLI entry point
```

Dependency graph:
- `ai_code2doc` -> `code2doc-core`
- `layer3_mcp` -> `code2doc-core`
- No direct dependency between `ai_code2doc` and `layer3_mcp`

## code2doc-core Package Contents

### parser/ (from src/ai_code2doc/parser/)
- `base_parser.py`
- `base_extractor.py`
- `base_resolver.py`
- `tree_sitter_parser.py`
- `import_resolver.py`
- `language_registry.py`
- `ast_queries.py`
- `structure_extractor.py`
- `languages/python.py`
- `languages/c_cpp.py`
- `languages/_common.py`
- `build/cmake_parser.py`

### scanner/ (from src/ai_code2doc/scanner/)
- `project_scanner.py`
- `change_detector.py`
- `file_filter.py`

### analyzer/ (from src/ai_code2doc/analyzer/)
- `dependency_graph.py`
- `dependency_store.py`
- `call_graph_builder.py`
- `call_extractor.py`
- `symbol_registry.py`
- `type_inferrer.py`
- `c_cpp_calls.py`
- `metrics.py`
- `tech_stack.py`
- `external_libs.py`

### models/ (from src/ai_code2doc/models/)
- `knowledge.py` (KnowledgeDocument)
- `module.py` (FileInfo, ModuleSummary)
- `graph.py` (DependencyEdge, CallSite, CycleInfo, etc.)
- `build.py` (CMakeProjectInfo)
- `analysis_state.py` (AnalysisState, FileState)

### utils/ (selected from src/ai_code2doc/utils/)
- `hashing.py`
- `git.py`
- `path_utils.py`
- `parse_cache.py`

### NOT included (stays in ai_code2doc)
- `config/settings.py`, `config/defaults.py`
- `llm/` (entire directory)
- `vector_store/` (entire directory)
- `generator/layer1_overview.py`, `generator/layer2_modules.py`, `generator/base_generator.py`, `generator/markdown_writer.py`, `generator/prompt_templates.py`
- `utils/logging.py`, `utils/markdown_utils.py`
- `agent/`, `web/`, `cli/`, `mcp/`

## layer3_mcp Changes

### Migrated from main package
- `generator/layer3_graph.py` -> `layer3_mcp/src/code2doc_layer3_mcp/generator/layer3_graph.py`
  - All imports updated from `ai_code2doc.*` to `code2doc_core.*`

### Refactored existing code
- `BranchManager._run_analyze()`: no longer calls `ai-code2doc analyze` via subprocess
  - Now calls `Layer3GraphGenerator.generate()` directly in-process
  - Removes dependency on `ai_code2doc` CLI being installed

- Duplicate code removed:
  - `layer3_mcp/dependency_store.py` (duplicate) -> use `code2doc_core.analyzer.dependency_store`
  - `layer3_mcp/git.py` (partial duplicate) -> use `code2doc_core.utils.git`

### New: GitPoller

Located at `layer3_mcp/src/code2doc_layer3_mcp/git_poller.py`

```python
class GitPoller:
    def __init__(self, repo_path: Path, branch_manager: BranchManager,
                 poll_interval: int = 300, branches: list[str] | None = None)
    async def start(self) -> None          # Start background polling loop
    async def stop(self) -> None           # Stop polling loop
    def is_running(self) -> bool
    def get_status(self) -> dict           # Last poll time, last rebuild time, etc.
```

Behavior:
- Periodically runs `git fetch origin` for configured branches (default: all tracked branches)
- Compares remote HEAD with local HEAD to detect changes
- If changes detected, calls `BranchManager.ensure_branch()` to rebuild DB
- Runs as an asyncio background task within the MCP server process
- Logs poll results and rebuild status

### New MCP tools exposed by GitPoller
- `poll_start`: Start the background poller (with optional interval override)
- `poll_stop`: Stop the background poller
- `poll_status`: Get current poller status (running, last poll, last rebuild)

### CLI extension
```
layer3-mcp --repo /path/to/repo --poll-interval 300    # poll every 5 minutes
layer3-mcp --repo /path/to/repo --poll-branches main,dev  # specific branches
```

## ai_code2doc Main Package Changes

### Import path updates
All imports from parser/scanner/analyzer/models change:
- `from ai_code2doc.parser.*` -> `from code2doc_core.parser.*`
- `from ai_code2doc.scanner.*` -> `from code2doc_core.scanner.*`
- `from ai_code2doc.analyzer.*` -> `from code2doc_core.analyzer.*`
- `from ai_code2doc.models.*` -> `from code2doc_core.models.*`
- `from ai_code2doc.utils.hashing` -> `from code2doc_core.utils.hashing`
- `from ai_code2doc.utils.git` -> `from code2doc_core.utils.git`
- `from ai_code2doc.utils.parse_cache` -> `from code2doc_core.utils.parse_cache`

### pyproject.toml
```toml
dependencies = [
    "code2doc-core",  # new
    "typer>=0.12",
    "rich>=13",
    ...existing...
]
```

### cli/analyze_cmd.py
- Remove the `if 3 in selected_layers` branch (layer3 generation)
- If user requests layer3, print a message: "Use `layer3-mcp --repo <path>` for Layer 3 analysis"

### cli/mcp_cmd.py and mcp/tools.py
- Update DependencyStore import to `from code2doc_core.analyzer.dependency_store`

### agent/tools/analyze_deps.py
- Update imports to use `code2doc_core`

## Migration Strategy

Single migration commit with these steps in order:

1. Create `code2doc-core/` package with pyproject.toml and source layout
2. Copy shared modules into `code2doc-core/src/code2doc_core/`, adjust internal imports
3. Update `ai_code2doc/pyproject.toml` to depend on `code2doc-core`
4. Update all imports in `ai_code2doc/src/` to use `code2doc_core.*`
5. Update tests in `tests/` to use new import paths
6. Remove migrated source files from `ai_code2doc/src/ai_code2doc/`
7. Update `layer3_mcp/pyproject.toml` to depend on `code2doc-core`
8. Migrate `layer3_graph.py` into `layer3_mcp`, remove duplicate code
9. Refactor `BranchManager` to call generator in-process
10. Add `GitPoller` to `layer3_mcp`
11. Update `layer3_mcp/tests/` imports
12. Run full test suite for both packages

## Risk Mitigation

- **Import path breakage**: After step 4, grep for all `from ai_code2doc.{parser,scanner,analyzer,models,utils.hashing,utils.git,utils.parse_cache}` to confirm zero remaining references
- **Circular dependencies**: `code2doc-core` has no dependency on `ai_code2doc` or `layer3_mcp`, so cycles are structurally impossible
- **Test coverage**: Run `pytest` for both `ai_code2doc` and `layer3_mcp` after each major step
- **Not affected**: `fuxian/` and `fuxian_modules_info_mcp_sever/` are independent, no changes needed

## Out of Scope

- `fuxian_modules_info_mcp_sever` refactor
- `web-ui/` changes
- `ai_code2doc mcp` subcommand deprecation (can be done later)
- Layer1/layer2 generator changes beyond import fixes
