# Layer3 Refactor: code2doc-core Extraction & layer3_mcp Self-Containment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract shared parsing/scanning/analysis code into `code2doc-core` library, make `layer3_mcp` self-contained with in-process generation, and add `GitPoller` for periodic DB updates.

**Architecture:** Three-package monorepo: `code2doc-core` (shared infrastructure), `ai_code2doc` (layer1/layer2 application), `layer3_mcp` (standalone layer3 generation + query + poll). All share `code2doc-core`; no cross-dependency between `ai_code2doc` and `layer3_mcp`.

**Tech Stack:** Python 3.11+, hatchling build, FastMCP, typer, tree-sitter, networkx, asyncio

---

### Task 1: Create code2doc-core package skeleton

**Files:**
- Create: `code2doc-core/pyproject.toml`
- Create: `code2doc-core/src/code2doc_core/__init__.py`
- Create: `code2doc-core/src/code2doc_core/parser/__init__.py`
- Create: `code2doc-core/src/code2doc_core/scanner/__init__.py`
- Create: `code2doc-core/src/code2doc_core/analyzer/__init__.py`
- Create: `code2doc-core/src/code2doc_core/models/__init__.py`
- Create: `code2doc-core/src/code2doc_core/utils/__init__.py`

- [ ] **Step 1: Create `code2doc-core/pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "code2doc-core"
version = "0.1.0"
description = "Core library for code analysis: parsing, scanning, dependency graphs"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [{name = "ai-code2doc contributors"}]
dependencies = [
    "tree-sitter>=0.22",
    "tree-sitter-python>=0.23",
    "tree-sitter-c>=0.23",
    "tree-sitter-cpp>=0.23",
    "networkx>=3.2",
    "pydantic>=2.5",
    "pathspec>=0.12",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "ruff>=0.3",
    "mypy>=1.8",
]

[tool.hatch.build.targets.wheel]
packages = ["src/code2doc_core"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create `__init__.py` stubs for all subpackages**

Each `__init__.py` should be empty (content: `# code2doc_core.{subpackage}`). The re-exports will be added after files are copied in.

- [ ] **Step 3: Commit**

```bash
git add code2doc-core/
git commit -m "chore: create code2doc-core package skeleton"
```

---

### Task 2: Move models/ into code2doc-core

**Files:**
- Move: `src/ai_code2doc/models/analysis_state.py` -> `code2doc-core/src/code2doc_core/models/analysis_state.py`
- Move: `src/ai_code2doc/models/build.py` -> `code2doc-core/src/code2doc_core/models/build.py`
- Move: `src/ai_code2doc/models/graph.py` -> `code2doc-core/src/code2doc_core/models/graph.py`
- Move: `src/ai_code2doc/models/knowledge.py` -> `code2doc-core/src/code2doc_core/models/knowledge.py`
- Move: `src/ai_code2doc/models/module.py` -> `code2doc-core/src/code2doc_core/models/module.py`
- Move: `src/ai_code2doc/models/project.py` -> `code2doc-core/src/code2doc_core/models/project.py`
- Modify: `code2doc-core/src/code2doc_core/models/__init__.py` (add re-exports)

Models have NO internal imports from other `ai_code2doc` subpackages — they only use `pydantic` and stdlib. So they can move without any import changes.

- [ ] **Step 1: Copy all model files**

```bash
cp src/ai_code2doc/models/analysis_state.py code2doc-core/src/code2doc_core/models/
cp src/ai_code2doc/models/build.py code2doc-core/src/code2doc_core/models/
cp src/ai_code2doc/models/graph.py code2doc-core/src/code2doc_core/models/
cp src/ai_code2doc/models/knowledge.py code2doc-core/src/code2doc_core/models/
cp src/ai_code2doc/models/module.py code2doc-core/src/code2doc_core/models/
cp src/ai_code2doc/models/project.py code2doc-core/src/code2doc_core/models/
```

- [ ] **Step 2: Write `code2doc-core/src/code2doc_core/models/__init__.py`**

```python
"""Pydantic data models for code2doc-core."""

from code2doc_core.models.analysis_state import AnalysisState, FileState
from code2doc_core.models.graph import (
    CallChain,
    CallSite,
    CycleInfo,
    DependencyEdge,
    ImpactHint,
    SymbolDefinition,
)
from code2doc_core.models.knowledge import KnowledgeDocument
from code2doc_core.models.module import (
    ClassInfo,
    FileInfo,
    FunctionInfo,
    ImportInfo,
    InterfaceInfo,
    ModuleSummary,
)
from code2doc_core.models.project import ProjectMetadata, TechStack

__all__ = [
    "TechStack",
    "ProjectMetadata",
    "FunctionInfo",
    "ClassInfo",
    "InterfaceInfo",
    "ImportInfo",
    "FileInfo",
    "ModuleSummary",
    "DependencyEdge",
    "CallChain",
    "CallSite",
    "SymbolDefinition",
    "ImpactHint",
    "CycleInfo",
    "KnowledgeDocument",
    "FileState",
    "AnalysisState",
]
```

- [ ] **Step 3: Verify no import changes needed in model files**

Run: `grep -rn "from ai_code2doc" code2doc-core/src/code2doc_core/models/`
Expected: no matches

- [ ] **Step 4: Commit**

```bash
git add code2doc-core/
git commit -m "feat(core): add models package to code2doc-core"
```

---

### Task 3: Move utils/ (shared subset) into code2doc-core

**Files:**
- Move: `src/ai_code2doc/utils/hashing.py` -> `code2doc-core/src/code2doc_core/utils/hashing.py`
- Move: `src/ai_code2doc/utils/git.py` -> `code2doc-core/src/code2doc_core/utils/git.py`
- Move: `src/ai_code2doc/utils/path_utils.py` -> `code2doc-core/src/code2doc_core/utils/path_utils.py`
- Move: `src/ai_code2doc/utils/parse_cache.py` -> `code2doc-core/src/code2doc_core/utils/parse_cache.py`
- Create: `code2doc-core/src/code2doc_core/utils/__init__.py` (add re-exports)
- Modify: `code2doc-core/src/code2doc_core/utils/parse_cache.py` (fix imports)

`parse_cache.py` imports from `ai_code2doc.models.module` and `ai_code2doc.parser.tree_sitter_parser`. These need to change to `code2doc_core.*`.

`hashing.py`, `git.py`, `path_utils.py` have NO internal imports — copy as-is.

- [ ] **Step 1: Copy utils files**

```bash
cp src/ai_code2doc/utils/hashing.py code2doc-core/src/code2doc_core/utils/
cp src/ai_code2doc/utils/git.py code2doc-core/src/code2doc_core/utils/
cp src/ai_code2doc/utils/path_utils.py code2doc-core/src/code2doc_core/utils/
cp src/ai_code2doc/utils/parse_cache.py code2doc-core/src/code2doc_core/utils/
```

- [ ] **Step 2: Fix `parse_cache.py` imports**

In `code2doc-core/src/code2doc_core/utils/parse_cache.py`, change:
```python
from ai_code2doc.models.module import FileInfo
from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser
```
to:
```python
from code2doc_core.models.module import FileInfo
from code2doc_core.parser.tree_sitter_parser import TreeSitterParser
```

- [ ] **Step 3: Write `code2doc-core/src/code2doc_core/utils/__init__.py`**

```python
from code2doc_core.utils.hashing import compute_content_hash, compute_file_hash
from code2doc_core.utils.path_utils import (
    ensure_dir,
    module_name_from_path,
    relative_path,
    safe_filename,
)

__all__ = [
    "compute_content_hash",
    "compute_file_hash",
    "ensure_dir",
    "module_name_from_path",
    "relative_path",
    "safe_filename",
]
```

- [ ] **Step 4: Commit**

```bash
git add code2doc-core/
git commit -m "feat(core): add shared utils to code2doc-core"
```

---

### Task 4: Move parser/ into code2doc-core

**Files:**
- Move: all files from `src/ai_code2doc/parser/` -> `code2doc-core/src/code2doc_core/parser/`
- Modify: all parser files (fix `ai_code2doc.*` -> `code2doc_core.*` imports)

Internal imports to fix in parser files:
- `ai_code2doc.models.module` -> `code2doc_core.models.module`
- `ai_code2doc.models.project` -> `code2doc_core.models.project`
- `ai_code2doc.parser.*` -> `code2doc_core.parser.*`
- `ai_code2doc.utils.hashing` -> `code2doc_core.utils.hashing`

- [ ] **Step 1: Copy entire parser directory**

```bash
cp -r src/ai_code2doc/parser/* code2doc-core/src/code2doc_core/parser/
```

- [ ] **Step 2: Fix all imports in parser files**

In ALL files under `code2doc-core/src/code2doc_core/parser/`, run:
```bash
sed -i 's/from ai_code2doc\.models\./from code2doc_core.models./g' code2doc-core/src/code2doc_core/parser/*.py code2doc-core/src/code2doc_core/parser/**/*.py
sed -i 's/from ai_code2doc\.parser\./from code2doc_core.parser./g' code2doc-core/src/code2doc_core/parser/*.py code2doc-core/src/code2doc_core/parser/**/*.py
sed -i 's/from ai_code2doc\.utils\./from code2doc_core.utils./g' code2doc-core/src/code2doc_core/parser/*.py code2doc-core/src/code2doc_core/parser/**/*.py
```

Verify: `grep -rn "ai_code2doc" code2doc-core/src/code2doc_core/parser/`
Expected: no matches

- [ ] **Step 3: Write `code2doc-core/src/code2doc_core/parser/__init__.py`**

```python
from code2doc_core.parser.base_extractor import BaseExtractor
from code2doc_core.parser.base_parser import BaseParser
from code2doc_core.parser.base_resolver import BaseResolver
from code2doc_core.parser.language_registry import LanguageRegistry
from code2doc_core.parser.tree_sitter_parser import TreeSitterParser

__all__ = [
    "BaseExtractor",
    "BaseParser",
    "BaseResolver",
    "LanguageRegistry",
    "TreeSitterParser",
]
```

- [ ] **Step 4: Commit**

```bash
git add code2doc-core/
git commit -m "feat(core): add parser package to code2doc-core"
```

---

### Task 5: Move scanner/ into code2doc-core

**Files:**
- Move: `src/ai_code2doc/scanner/*.py` -> `code2doc-core/src/code2doc_core/scanner/`
- Modify: scanner files (fix imports)
- Create: `code2doc-core/src/code2doc_core/constants.py` (extracted from `config.defaults`)

**Important:** `file_filter.py` imports `DEFAULT_IGNORE_PATTERNS` and `DEFAULT_IGNORE_EXTENSIONS` from `ai_code2doc.config.defaults`. These are pure constants with no config dependencies. Extract them to `code2doc-core/constants.py`.

- [ ] **Step 1: Create `code2doc-core/src/code2doc_core/constants.py`**

Copy the `DEFAULT_IGNORE_PATTERNS` and `DEFAULT_IGNORE_EXTENSIONS` lists from `src/ai_code2doc/config/defaults.py` into a new file:

```python
"""Default constants used across code2doc packages."""

DEFAULT_IGNORE_PATTERNS: list[str] = [
    ".git", ".hg", ".svn",
    "node_modules", "vendor", "__pypackages__", ".venv", "venv", "env", ".env",
    "dist", "build", "out", "bin", "target", ".next", ".nuxt", ".output",
    "cmake-build-*", "CMakeFiles", "CMakeCache.txt",
    "__pycache__", ".cache", ".parcel-cache", ".turbo", ".temp", ".tmp",
    ".mypy_cache", ".ruff_cache",
    "coverage", ".nyc_output", ".pytest_cache", "htmlcov",
    ".idea", ".vscode", ".vs", "*.swp", "*.swo",
    "_site", ".docusaurus",
    ".DS_Store", "Thumbs.db",
    ".ai_code2doc",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Pipfile.lock", "uv.lock", "pdm.lock", "conan.lock", "CMakeLists.txt.lock",
]

DEFAULT_IGNORE_EXTENSIONS: list[str] = [
    ".min.js", ".min.css", ".map",
    ".spec.py", ".test.py",
    ".o", ".obj", ".so", ".dylib", ".a", ".lib", ".ko",
    ".snap", ".snapshot",
    ".pyc", ".pyo", ".pyd", ".class", ".exe", ".dll", ".wasm",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".webm",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".sqlite", ".db", ".pkl", ".pickle", ".npy", ".npz", ".h5", ".hdf5",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
]
```

- [ ] **Step 2: Copy scanner files**

```bash
cp src/ai_code2doc/scanner/project_scanner.py code2doc-core/src/code2doc_core/scanner/
cp src/ai_code2doc/scanner/change_detector.py code2doc-core/src/code2doc_core/scanner/
cp src/ai_code2doc/scanner/file_filter.py code2doc-core/src/code2doc_core/scanner/
```

- [ ] **Step 3: Fix scanner file imports**

In `code2doc-core/src/code2doc_core/scanner/change_detector.py`:
```python
# Change:
from ai_code2doc.models.analysis_state import AnalysisState, FileState
from ai_code2doc.utils.hashing import compute_file_hash
# To:
from code2doc_core.models.analysis_state import AnalysisState, FileState
from code2doc_core.utils.hashing import compute_file_hash
```

In `code2doc-core/src/code2doc_core/scanner/file_filter.py`:
```python
# Change:
from ai_code2doc.config.defaults import DEFAULT_IGNORE_PATTERNS, DEFAULT_IGNORE_EXTENSIONS
# To:
from code2doc_core.constants import DEFAULT_IGNORE_PATTERNS, DEFAULT_IGNORE_EXTENSIONS
```

Also in `file_filter.py`, fix the lazy import:
```python
# Change:
from ai_code2doc.parser.language_registry import LanguageRegistry
# To:
from code2doc_core.parser.language_registry import LanguageRegistry
```

In `code2doc-core/src/code2doc_core/scanner/project_scanner.py`:
```python
# Change:
from ai_code2doc.scanner.file_filter import FileFilter
# To:
from code2doc_core.scanner.file_filter import FileFilter
```

- [ ] **Step 4: Write `code2doc-core/src/code2doc_core/scanner/__init__.py`**

```python
from code2doc_core.scanner.change_detector import ChangeDetector
from code2doc_core.scanner.file_filter import FileFilter
from code2doc_core.scanner.project_scanner import ProjectScanner

__all__ = ["ChangeDetector", "FileFilter", "ProjectScanner"]
```

- [ ] **Step 5: Verify**

```bash
grep -rn "ai_code2doc" code2doc-core/src/code2doc_core/scanner/
```
Expected: no matches

- [ ] **Step 6: Commit**

```bash
git add code2doc-core/
git commit -m "feat(core): add scanner package and constants to code2doc-core"
```

---

### Task 6: Move analyzer/ into code2doc-core

**Files:**
- Move: all files from `src/ai_code2doc/analyzer/` -> `code2doc-core/src/code2doc_core/analyzer/`
- Modify: all analyzer files (fix `ai_code2doc.*` -> `code2doc_core.*` imports)

Internal imports to fix:
- `ai_code2doc.models.*` -> `code2doc_core.models.*`
- `ai_code2doc.parser.*` -> `code2doc_core.parser.*`

- [ ] **Step 1: Copy entire analyzer directory**

```bash
cp -r src/ai_code2doc/analyzer/* code2doc-core/src/code2doc_core/analyzer/
```

- [ ] **Step 2: Fix all imports in analyzer files**

```bash
sed -i 's/from ai_code2doc\.models\./from code2doc_core.models./g' code2doc-core/src/code2doc_core/analyzer/*.py
sed -i 's/from ai_code2doc\.parser\./from code2doc_core.parser./g' code2doc-core/src/code2doc_core/analyzer/*.py
```

Verify: `grep -rn "ai_code2doc" code2doc-core/src/code2doc_core/analyzer/`
Expected: no matches

- [ ] **Step 3: Write `code2doc-core/src/code2doc_core/analyzer/__init__.py`**

```python
from code2doc_core.analyzer.call_extractor import PythonCallExtractor
from code2doc_core.analyzer.call_graph_builder import CallGraphBuilder
from code2doc_core.analyzer.dependency_graph import DependencyGraphBuilder
from code2doc_core.analyzer.dependency_store import DependencyStore
from code2doc_core.analyzer.metrics import FileMetrics, MetricsCalculator, ProjectMetrics
from code2doc_core.analyzer.symbol_registry import SymbolRegistry
from code2doc_core.analyzer.tech_stack import TechStackDetector
from code2doc_core.analyzer.type_inferrer import CppTypeInferrer, TypeInferrer

__all__ = [
    "PythonCallExtractor",
    "CallGraphBuilder",
    "DependencyGraphBuilder",
    "DependencyStore",
    "FileMetrics",
    "MetricsCalculator",
    "ProjectMetrics",
    "SymbolRegistry",
    "TechStackDetector",
    "CppTypeInferrer",
    "TypeInferrer",
]
```

- [ ] **Step 4: Commit**

```bash
git add code2doc-core/
git commit -m "feat(core): add analyzer package to code2doc-core"
```

---

### Task 7: Write code2doc-core top-level __init__.py

**Files:**
- Modify: `code2doc-core/src/code2doc_core/__init__.py`

- [ ] **Step 1: Write top-level re-exports**

```python
"""code2doc-core: shared code analysis infrastructure."""

__version__ = "0.1.0"
```

- [ ] **Step 2: Commit**

```bash
git add code2doc-core/
git commit -m "chore(core): finalize code2doc-core package init"
```

---

### Task 8: Update ai_code2doc to depend on code2doc-core

**Files:**
- Modify: `pyproject.toml` (add `code2doc-core` dependency)

- [ ] **Step 1: Install code2doc-core in development**

```bash
cd code2doc-core && pip install -e ".[dev]"
cd .. && pip install -e ".[dev]"
```

- [ ] **Step 2: Add dependency to `pyproject.toml`**

In `pyproject.toml`, add `"code2doc-core"` as the first item in `dependencies`:
```toml
dependencies = [
    "code2doc-core",
    "typer>=0.12",
    ...
]
```

- [ ] **Step 3: Verify import works**

```bash
python -c "from code2doc_core.models import FileInfo; from code2doc_core.parser import TreeSitterParser; print('OK')"
```
Expected: prints "OK"

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add code2doc-core dependency to ai_code2doc"
```

---

### Task 9: Update ai_code2doc source imports

**Files:** ALL files in `src/ai_code2doc/` that import from parser/scanner/analyzer/models/shared-utils

Import mapping to apply globally:
```
from ai_code2doc.models.X         -> from code2doc_core.models.X
from ai_code2doc.parser.X         -> from code2doc_core.parser.X
from ai_code2doc.scanner.X        -> from code2doc_core.scanner.X
from ai_code2doc.analyzer.X       -> from code2doc_core.analyzer.X
from ai_code2doc.utils.hashing    -> from code2doc_core.utils.hashing
from ai_code2doc.utils.git        -> from code2doc_core.utils.git
from ai_code2doc.utils.path_utils -> from code2doc_core.utils.path_utils
from ai_code2doc.utils.parse_cache -> from code2doc_core.utils.parse_cache
```

**Files that need changes (grouped by directory):**

In `src/ai_code2doc/config/`:
- `defaults.py`: Remove `DEFAULT_IGNORE_PATTERNS` and `DEFAULT_IGNORE_EXTENSIONS` (moved to code2doc-core). Keep prompt templates. Add import: `from code2doc_core.constants import DEFAULT_IGNORE_PATTERNS, DEFAULT_IGNORE_EXTENSIONS` for backward compat if needed by `generator/prompt_templates.py`.

In `src/ai_code2doc/generator/`:
- `base_generator.py`: `ai_code2doc.models.knowledge` -> `code2doc_core.models.knowledge`
- `layer1_overview.py`: `ai_code2doc.parser.*` -> `code2doc_core.parser.*`, `ai_code2doc.scanner.*` -> `code2doc_core.scanner.*`, `ai_code2doc.analyzer.*` -> `code2doc_core.analyzer.*`, `ai_code2doc.models.*` -> `code2doc_core.models.*`
- `layer2_modules.py`: same pattern as layer1_overview

In `src/ai_code2doc/agent/`:
- `context.py`: `ai_code2doc.models.knowledge` -> `code2doc_core.models.knowledge`
- `tools/analyze_deps.py`: `ai_code2doc.parser.*`, `ai_code2doc.scanner.*`, `ai_code2doc.analyzer.*`, `ai_code2doc.utils.*` -> `code2doc_core.*`
- `tools/rescan.py`: `ai_code2doc.scanner.*`, `ai_code2doc.utils.*`, `ai_code2doc.parser.*` -> `code2doc_core.*`

In `src/ai_code2doc/mcp/`:
- `tools.py`: `ai_code2doc.analyzer.dependency_store` -> `code2doc_core.analyzer.dependency_store`

In `src/ai_code2doc/web/`:
- `routes/overview.py`: `ai_code2doc.analyzer.*` -> `code2doc_core.analyzer.*`

In `src/ai_code2doc/cli/`:
- `analyze_cmd.py`: `ai_code2doc.scanner.*` -> `code2doc_core.scanner.*`
- `chat_cmd.py`: `ai_code2doc.scanner.change_detector` -> `code2doc_core.scanner.change_detector`
- `mcp_cmd.py`: `ai_code2doc.utils.git` -> `code2doc_core.utils.git`
- `status_cmd.py`: `ai_code2doc.models.analysis_state` -> `code2doc_core.models.analysis_state`

In `src/ai_code2doc/vector_store/`:
- `store.py`: `ai_code2doc.models.knowledge` -> `code2doc_core.models.knowledge`

In `src/ai_code2doc/utils/`:
- `__init__.py`: Update to re-export from `code2doc_core.utils` for the moved items

- [ ] **Step 1: Apply bulk sed replacements across src/**

```bash
cd src/ai_code2doc
# Models
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.models\./from code2doc_core.models./g' {} +
# Parser
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.parser\./from code2doc_core.parser./g' {} +
# Scanner
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.scanner\./from code2doc_core.scanner./g' {} +
# Analyzer
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.analyzer\./from code2doc_core.analyzer./g' {} +
# Shared utils
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.utils\.hashing/from code2doc_core.utils.hashing/g' {} +
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.utils\.git/from code2doc_core.utils.git/g' {} +
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.utils\.path_utils/from code2doc_core.utils.path_utils/g' {} +
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.utils\.parse_cache/from code2doc_core.utils.parse_cache/g' {} +
```

- [ ] **Step 2: Handle config/defaults.py**

Remove `DEFAULT_IGNORE_PATTERNS` and `DEFAULT_IGNORE_EXTENSIONS` from `src/ai_code2doc/config/defaults.py`. Keep prompt templates. Add backward-compat re-imports at the bottom:
```python
# Re-exported from code2doc-core for backward compatibility
from code2doc_core.constants import DEFAULT_IGNORE_PATTERNS, DEFAULT_IGNORE_EXTENSIONS  # noqa: F401
```

- [ ] **Step 3: Handle utils/__init__.py**

Update `src/ai_code2doc/utils/__init__.py` to re-export moved utils from `code2doc_core`:
```python
from code2doc_core.utils.hashing import compute_content_hash, compute_file_hash
from code2doc_core.utils.path_utils import (
    ensure_dir,
    module_name_from_path,
    relative_path,
    safe_filename,
)
from ai_code2doc.utils.logging import setup_logging
from ai_code2doc.utils.markdown_utils import (
    escape_markdown,
    format_code_block,
    format_table,
    format_toc,
)
```

- [ ] **Step 4: Verify zero stale imports**

```bash
grep -rn "from ai_code2doc\.models\.\|from ai_code2doc\.parser\.\|from ai_code2doc\.scanner\.\|from ai_code2doc\.analyzer\." src/ai_code2doc/ --include="*.py"
```
Expected: only the backward-compat line in `config/defaults.py`

- [ ] **Step 5: Commit**

```bash
git add src/ pyproject.toml
git commit -m "refactor: update ai_code2doc to import from code2doc-core"
```

---

### Task 10: Update ai_code2doc tests

**Files:** ALL test files in `tests/` that import from parser/scanner/analyzer/models/shared-utils

- [ ] **Step 1: Apply same sed replacements to tests/**

```bash
cd tests
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.models\./from code2doc_core.models./g' {} +
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.parser\./from code2doc_core.parser./g' {} +
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.scanner\./from code2doc_core.scanner./g' {} +
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.analyzer\./from code2doc_core.analyzer./g' {} +
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.utils\.hashing/from code2doc_core.utils.hashing/g' {} +
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.utils\.git/from code2doc_core.utils.git/g' {} +
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.utils\.path_utils/from code2doc_core.utils.path_utils/g' {} +
find . -name "*.py" -exec sed -i 's/from ai_code2doc\.utils\.parse_cache/from code2doc_core.utils.parse_cache/g' {} +
```

- [ ] **Step 2: Update `tests/conftest.py` and `tests/integration/conftest.py` if needed**

Check if they import from moved modules.

- [ ] **Step 3: Run main test suite**

```bash
pytest tests/ -x -v 2>&1 | head -100
```
Expected: All existing tests pass (import paths updated correctly)

Fix any remaining import errors iteratively.

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "refactor: update test imports to use code2doc-core"
```

---

### Task 11: Remove migrated source files from ai_code2doc

**Files to delete from `src/ai_code2doc/`:**
- Delete: `src/ai_code2doc/models/` (entire directory — 6 .py files)
- Delete: `src/ai_code2doc/parser/` (entire directory — 13 .py files)
- Delete: `src/ai_code2doc/scanner/` (entire directory — 4 .py files)
- Delete: `src/ai_code2doc/analyzer/` (entire directory — 11 .py files)
- Delete: `src/ai_code2doc/utils/hashing.py`
- Delete: `src/ai_code2doc/utils/git.py`
- Delete: `src/ai_code2doc/utils/path_utils.py`
- Delete: `src/ai_code2doc/utils/parse_cache.py`

**Keep in `src/ai_code2doc/`:**
- `src/ai_code2doc/utils/__init__.py` (updated with re-exports)
- `src/ai_code2doc/utils/logging.py`
- `src/ai_code2doc/utils/markdown_utils.py`
- `src/ai_code2doc/generator/layer3_graph.py` (remove in Task 14, not yet)

- [ ] **Step 1: Delete migrated directories and files**

```bash
rm -rf src/ai_code2doc/models/
rm -rf src/ai_code2doc/parser/
rm -rf src/ai_code2doc/scanner/
rm -rf src/ai_code2doc/analyzer/
rm src/ai_code2doc/utils/hashing.py
rm src/ai_code2doc/utils/git.py
rm src/ai_code2doc/utils/path_utils.py
rm src/ai_code2doc/utils/parse_cache.py
```

- [ ] **Step 2: Run tests to verify nothing broke**

```bash
pytest tests/ -x -v 2>&1 | head -100
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: remove migrated code from ai_code2doc (now in code2doc-core)"
```

---

### Task 12: Remove layer3 generation from ai_code2doc CLI

**Files:**
- Modify: `src/ai_code2doc/cli/analyze_cmd.py`
- Delete: `src/ai_code2doc/generator/layer3_graph.py`

- [ ] **Step 1: Remove layer3 from `analyze_cmd.py`**

In `src/ai_code2doc/cli/analyze_cmd.py`, remove the entire `if 3 in selected_layers:` block (lines ~201-229). Add a warning when layer 3 is requested:

```python
if 3 in selected_layers:
    console.print(
        "  [yellow]Layer 3 is now handled by the standalone layer3-mcp package.[/yellow]"
    )
    console.print(
        "  Run [bold]layer3-mcp --repo <path>[/bold] for Layer 3 analysis."
    )
    selected_layers = [l for l in selected_layers if l != 3]
```

- [ ] **Step 2: Delete `src/ai_code2doc/generator/layer3_graph.py`**

```bash
rm src/ai_code2doc/generator/layer3_graph.py
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/ -x -v 2>&1 | head -80
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: remove layer3 generation from ai_code2doc CLI"
```

---

### Task 13: Update layer3_mcp to depend on code2doc-core

**Files:**
- Modify: `layer3_mcp/pyproject.toml`
- Delete: `layer3_mcp/src/code2doc_layer3_mcp/dependency_store.py` (duplicate)
- Delete: `layer3_mcp/src/code2doc_layer3_mcp/git.py` (duplicate)
- Modify: `layer3_mcp/src/code2doc_layer3_mcp/server.py` (update imports)
- Modify: `layer3_mcp/src/code2doc_layer3_mcp/branch_manager.py` (update imports)
- Modify: `layer3_mcp/src/code2doc_layer3_mcp/cli.py` (update imports)

- [ ] **Step 1: Update `layer3_mcp/pyproject.toml`**

Add dependencies:
```toml
dependencies = [
    "code2doc-core",
    "mcp>=1.0",
    "typer>=0.12",
    "uvicorn[standard]>=0.27",
]
```

- [ ] **Step 2: Delete duplicate files**

```bash
rm layer3_mcp/src/code2doc_layer3_mcp/dependency_store.py
rm layer3_mcp/src/code2doc_layer3_mcp/git.py
```

- [ ] **Step 3: Update `server.py` imports**

Change:
```python
from code2doc_layer3_mcp.dependency_store import DependencyStore
```
to:
```python
from code2doc_core.analyzer.dependency_store import DependencyStore
```

- [ ] **Step 4: Update `branch_manager.py` imports**

Change:
```python
from code2doc_layer3_mcp.git import sanitize_branch_name
```
to:
```python
from code2doc_core.utils.git import sanitize_branch_name
```

- [ ] **Step 5: Update `cli.py` imports**

Change:
```python
from code2doc_layer3_mcp.git import get_layer3_db_path
```
to:
```python
from code2doc_core.utils.git import get_layer3_db_path
```

- [ ] **Step 6: Run layer3_mcp tests**

```bash
cd layer3_mcp && pytest tests/ -x -v 2>&1 | head -80
```

- [ ] **Step 7: Commit**

```bash
git add layer3_mcp/
git commit -m "refactor: layer3_mcp depends on code2doc-core, remove duplicate code"
```

---

### Task 14: Migrate layer3_graph.py into layer3_mcp

**Files:**
- Create: `layer3_mcp/src/code2doc_layer3_mcp/generator/__init__.py`
- Create: `layer3_mcp/src/code2doc_layer3_mcp/generator/layer3_graph.py` (migrated + import-fixed)

- [ ] **Step 1: Create generator directory and __init__.py**

```bash
mkdir -p layer3_mcp/src/code2doc_layer3_mcp/generator
```

`layer3_mcp/src/code2doc_layer3_mcp/generator/__init__.py`:
```python
# code2doc_layer3_mcp.generator
```

- [ ] **Step 2: Copy and fix `layer3_graph.py`**

Copy the file from the current main package (before Task 12 deletion, use git):
```bash
git show HEAD~1:src/ai_code2doc/generator/layer3_graph.py > layer3_mcp/src/code2doc_layer3_mcp/generator/layer3_graph.py
```

If that doesn't work (commit history), recreate from `code2doc-core` backup or the original file content.

Fix all imports in the copied file:
```python
# All ai_code2doc.* -> code2doc_core.*
from code2doc_core.analyzer.dependency_graph import DependencyGraphBuilder
from code2doc_core.analyzer.metrics import MetricsCalculator
from code2doc_core.analyzer.call_graph_builder import CallGraphBuilder
from code2doc_core.analyzer.dependency_store import DependencyStore
from code2doc_core.models.knowledge import KnowledgeDocument
from code2doc_core.models.graph import CallSite
from code2doc_core.parser.tree_sitter_parser import TreeSitterParser
from code2doc_core.scanner.project_scanner import ProjectScanner
from code2doc_core.utils.hashing import compute_file_hash
from code2doc_core.utils.git import get_current_branch, sanitize_branch_name
from code2doc_core.utils.parse_cache import ParseCache
```

Also update the MarkdownWriter reference. The `layer3_graph.py` uses `self._writer = MarkdownWriter()` and imports from `ai_code2doc.generator.markdown_writer`. Since MarkdownWriter stays in the main package, we need to handle this. Options:
- Copy MarkdownWriter into layer3_mcp (it's small)
- Or inline the write logic

Simplest: Copy `markdown_writer.py` to `layer3_mcp/src/code2doc_layer3_mcp/generator/markdown_writer.py` and update its imports.

- [ ] **Step 3: Copy markdown_writer.py**

```bash
cp src/ai_code2doc/generator/markdown_writer.py layer3_mcp/src/code2doc_layer3_mcp/generator/markdown_writer.py
```

Fix imports in copied file — it imports `ai_code2doc.models.knowledge`:
```python
from code2doc_core.models.knowledge import KnowledgeDocument
```

- [ ] **Step 4: Fix layer3_graph.py imports to use local markdown_writer**

```python
from code2doc_layer3_mcp.generator.markdown_writer import MarkdownWriter
```

Remove the base_generator import (layer3_graph doesn't extend BaseGenerator — it has its own `generate` method). If it does import `BaseGenerator`, copy that too or inline.

Check: Does `layer3_graph.py` import `BaseGenerator`? Yes — `from ai_code2doc.generator.base_generator import BaseGenerator`. The class extends it for `layer_number` and `layer_name` properties. Simplest approach: just keep these properties inline in the layer3_graph class without the base class.

- [ ] **Step 5: Run tests**

```bash
cd layer3_mcp && pytest tests/ -x -v 2>&1 | head -80
```

- [ ] **Step 6: Commit**

```bash
git add layer3_mcp/
git commit -m "feat: migrate layer3_graph generator into layer3_mcp"
```

---

### Task 15: Refactor BranchManager to use in-process generation

**Files:**
- Modify: `layer3_mcp/src/code2doc_layer3_mcp/branch_manager.py`

- [ ] **Step 1: Refactor `_run_analyze` method**

Replace the subprocess call with in-process generation:

```python
def _run_analyze(self) -> None:
    """Run Layer 3 analysis in-process (no subprocess)."""
    import asyncio
    from pathlib import Path
    from code2doc_layer3_mcp.generator.layer3_graph import Layer3GraphGenerator

    project_root = self.repo_path
    output_dir = project_root / ".ai_code2doc"

    generator = Layer3GraphGenerator()
    # Run the async generator synchronously
    asyncio.run(generator.generate(
        project_root=project_root,
        output_dir=output_dir,
        use_llm=False,
        changed_files=None,  # Full rebuild
    ))
```

Also update `_build_branch` to call this directly instead of via `run_in_executor`:

```python
async def _build_branch(self, branch: str) -> None:
    """Fetch, checkout, and analyze a branch."""
    loop = asyncio.get_event_loop()

    # 1. git fetch
    logger.info("Fetching branch '%s'...", branch)
    result = await loop.run_in_executor(
        None, self._run_git, "fetch", "origin", branch
    )
    if result.returncode != 0:
        logger.warning("git fetch failed: %s", result.stderr.strip())

    # 2. git checkout
    logger.info("Checking out branch '%s'...", branch)
    result = await loop.run_in_executor(
        None, self._run_git, "checkout", branch
    )
    if result.returncode != 0:
        raise RuntimeError(f"git checkout failed: {result.stderr.strip()}")

    # 3. Run Layer 3 analysis in-process
    logger.info("Running Layer 3 analysis for branch '%s'...", branch)
    self._run_analyze()

    logger.info("Branch '%s' Layer 3 build complete.", branch)
```

- [ ] **Step 2: Run layer3_mcp tests**

```bash
cd layer3_mcp && pytest tests/ -x -v 2>&1 | head -80
```

- [ ] **Step 3: Commit**

```bash
git add layer3_mcp/
git commit -m "refactor: BranchManager uses in-process generation instead of subprocess"
```

---

### Task 16: Add GitPoller to layer3_mcp

**Files:**
- Create: `layer3_mcp/src/code2doc_layer3_mcp/git_poller.py`
- Create: `layer3_mcp/tests/test_git_poller.py`
- Modify: `layer3_mcp/src/code2doc_layer3_mcp/server.py` (register poll MCP tools)
- Modify: `layer3_mcp/src/code2doc_layer3_mcp/cli.py` (add `--poll-interval` flag)
- Modify: `layer3_mcp/src/code2doc_layer3_mcp/branch_manager.py` (add `fetch_remote_heads` method)

- [ ] **Step 1: Write failing test for GitPoller**

Create `layer3_mcp/tests/test_git_poller.py`:

```python
"""Tests for GitPoller."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from code2doc_layer3_mcp.git_poller import GitPoller


class FakeBranchManager:
    def __init__(self) -> None:
        self.builds: list[str] = []

    async def ensure_branch(self, branch: str) -> Path:
        self.builds.append(branch)
        return Path(f"/fake/{branch}/dependency-graph.db")

    async def fetch_remote_heads(self, branches: list[str]) -> dict[str, bool]:
        # Simulate first branch having changes
        return {branches[0]: True, branches[-1]: False}


@pytest.mark.asyncio
async def test_poller_rebuilds_changed_branches():
    bm = FakeBranchManager()
    poller = GitPoller(
        repo_path=Path("/fake/repo"),
        branch_manager=bm,
        poll_interval=1,
        branches=["main", "dev"],
    )
    try:
        await poller.start()
        await asyncio.sleep(1.5)
        await poller.stop()
    finally:
        pass
    # "main" should have been rebuilt (simulated as changed)
    assert "main" in bm.builds
    # "dev" should NOT have been rebuilt (simulated as unchanged)
    assert "dev" not in bm.builds


@pytest.mark.asyncio
async def test_poller_status():
    bm = FakeBranchManager()
    poller = GitPoller(
        repo_path=Path("/fake/repo"),
        branch_manager=bm,
        poll_interval=60,
    )
    status = poller.get_status()
    assert status["running"] is False
    assert status["poll_interval"] == 60
    assert status["last_poll"] is None
    assert status["last_rebuild"] is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd layer3_mcp && pytest tests/test_git_poller.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'code2doc_layer3_mcp.git_poller'`

- [ ] **Step 3: Implement GitPoller**

Create `layer3_mcp/src/code2doc_layer3_mcp/git_poller.py`:

```python
"""Periodic git poller for automatic Layer 3 DB updates."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from code2doc_layer3_mcp.branch_manager import BranchManager

logger = logging.getLogger(__name__)


class GitPoller:
    """Periodically checks git remotes for changes and triggers rebuilds."""

    def __init__(
        self,
        repo_path: Path,
        branch_manager: BranchManager,
        poll_interval: int = 300,
        branches: list[str] | None = None,
    ) -> None:
        self.repo_path = repo_path
        self.branch_manager = branch_manager
        self.poll_interval = poll_interval
        self.branches = branches
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_poll: datetime | None = None
        self._last_rebuild: datetime | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            "GitPoller started (interval=%ds, repo=%s)",
            self.poll_interval,
            self.repo_path,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("GitPoller stopped")

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._poll_once()
            except Exception:
                logger.exception("Poll cycle failed")
            await asyncio.sleep(self.poll_interval)

    async def _poll_once(self) -> None:
        branches = self.branches or self._get_tracked_branches()
        if not branches:
            logger.debug("No branches to poll")
            return

        logger.info("Polling %d branches...", len(branches))
        self._last_poll = datetime.now(timezone.utc)

        changed = await self.branch_manager.fetch_remote_heads(branches)
        for branch, has_changes in changed.items():
            if has_changes:
                logger.info("Changes detected on '%s', rebuilding...", branch)
                try:
                    await self.branch_manager.ensure_branch(branch)
                    self._last_rebuild = datetime.now(timezone.utc)
                    logger.info("Rebuild complete for '%s'", branch)
                except Exception:
                    logger.exception("Rebuild failed for '%s'", branch)
            else:
                logger.debug("No changes on '%s'", branch)

    def _get_tracked_branches(self) -> list[str]:
        result = subprocess.run(
            ["git", "branch", "--list"],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        return [b.strip().lstrip("* ") for b in result.stdout.strip().splitlines() if b.strip()]

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "poll_interval": self.poll_interval,
            "branches": self.branches or "auto",
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
            "last_rebuild": self._last_rebuild.isoformat() if self._last_rebuild else None,
        }
```

- [ ] **Step 4: Add `fetch_remote_heads` to BranchManager**

In `layer3_mcp/src/code2doc_layer3_mcp/branch_manager.py`, add method:

```python
async def fetch_remote_heads(self, branches: list[str]) -> dict[str, bool]:
    """Fetch remote refs and check if each branch has changes.

    Returns dict mapping branch name -> True if remote has new commits.
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, self._run_git, "fetch", "--dry-run", "origin"
    )
    if result.returncode != 0:
        logger.warning("git fetch --dry-run failed: %s", result.stderr.strip())
        return {b: False for b in branches}

    changed: dict[str, bool] = {}
    for branch in branches:
        # Compare local HEAD with remote HEAD
        local = await loop.run_in_executor(
            None, self._run_git, "rev-parse", branch
        )
        remote = await loop.run_in_executor(
            None, self._run_git, "rev-parse", f"origin/{branch}"
        )
        if local.returncode == 0 and remote.returncode == 0:
            changed[branch] = local.stdout.strip() != remote.stdout.strip()
        else:
            changed[branch] = False

    return changed
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd layer3_mcp && pytest tests/test_git_poller.py -v
```
Expected: PASS

- [ ] **Step 6: Register poll MCP tools in server.py**

In `layer3_mcp/src/code2doc_layer3_mcp/server.py`, add a module-level poller reference and register tools:

At module level, add:
```python
_git_poller: GitPoller | None = None
```

In `create_server()`, add poller initialization:
```python
global _git_poller
if repo_path:
    from code2doc_layer3_mcp.git_poller import GitPoller
    _git_poller = GitPoller(repo_path, _branch_manager)
```

Add MCP tools:
```python
@mcp.tool()
async def poll_start(interval: int = 0) -> str:
    """Start the background git poller. Optionally override poll interval (seconds)."""
    if _git_poller is None:
        return "Error: poller not configured (no --repo)."
    if interval > 0:
        _git_poller.poll_interval = interval
    await _git_poller.start()
    status = _git_poller.get_status()
    return f"Poller started (interval={status['poll_interval']}s)"

@mcp.tool()
async def poll_stop() -> str:
    """Stop the background git poller."""
    if _git_poller is None:
        return "Error: poller not configured (no --repo)."
    await _git_poller.stop()
    return "Poller stopped."

@mcp.tool()
def poll_status() -> str:
    """Get current poller status (running, last poll, last rebuild)."""
    if _git_poller is None:
        return "Error: poller not configured (no --repo)."
    import json
    return json.dumps(_git_poller.get_status(), indent=2)
```

- [ ] **Step 7: Add CLI flags**

In `layer3_mcp/src/code2doc_layer3_mcp/cli.py`, add `poll_interval` parameter to the `main` callback:

```python
poll_interval: int = typer.Option(
    0,
    "--poll-interval",
    help="Enable periodic git polling (seconds). 0 = disabled.",
),
```

After server creation, start poller if interval > 0:
```python
if poll_interval > 0 and repo:
    from code2doc_layer3_mcp.git_poller import GitPoller
    poller = GitPoller(resolved_repo, manager, poll_interval=poll_interval)
    # Store reference for MCP tools
    import code2doc_layer3_mcp.server as _srv
    _srv._git_poller = poller
    asyncio.get_event_loop().create_task(poller.start())
    import sys
    print(f"Git poller enabled (interval={poll_interval}s)", file=sys.stderr)
```

- [ ] **Step 8: Commit**

```bash
git add layer3_mcp/
git commit -m "feat: add GitPoller for periodic Layer 3 DB updates"
```

---

### Task 17: Update layer3_mcp tests

**Files:**
- Modify: `layer3_mcp/tests/conftest.py`
- Modify: `layer3_mcp/tests/test_server.py`
- Modify: `layer3_mcp/tests/test_tools.py`
- Modify: `layer3_mcp/tests/test_branch_manager.py`
- Modify: `layer3_mcp/tests/test_dependency_store.py`

- [ ] **Step 1: Fix all test imports**

In layer3_mcp tests, replace:
```python
from code2doc_layer3_mcp.dependency_store import DependencyStore
from code2doc_layer3_mcp.git import sanitize_branch_name
```
with:
```python
from code2doc_core.analyzer.dependency_store import DependencyStore
from code2doc_core.utils.git import sanitize_branch_name
```

- [ ] **Step 2: Run full layer3_mcp test suite**

```bash
cd layer3_mcp && pytest tests/ -v 2>&1 | tail -20
```

Fix any remaining import errors.

- [ ] **Step 3: Commit**

```bash
git add layer3_mcp/
git commit -m "refactor: update layer3_mcp test imports to use code2doc-core"
```

---

### Task 18: Full integration verification

- [ ] **Step 1: Install all packages in development mode**

```bash
pip install -e code2doc-core/[dev]
pip install -e .[dev]
pip install -e layer3_mcp/[dev]
```

- [ ] **Step 2: Run main test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -40
```

- [ ] **Step 3: Run layer3_mcp test suite**

```bash
cd layer3_mcp && pytest tests/ -v --tb=short 2>&1 | tail -40
```

- [ ] **Step 4: Verify CLI commands work**

```bash
ai-code2doc analyze --help
layer3-mcp --help
```

- [ ] **Step 5: Verify import chain is clean**

```bash
# No ai_code2doc references in code2doc-core
grep -rn "ai_code2doc" code2doc-core/src/ --include="*.py"
# No code2doc_layer3_mcp references in ai_code2doc
grep -rn "code2doc_layer3_mcp" src/ --include="*.py"
# No ai_code2doc references in layer3_mcp
grep -rn "ai_code2doc" layer3_mcp/src/ --include="*.py"
```

Expected: All three return zero matches.

- [ ] **Step 6: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: integration verification cleanup"
```
