from __future__ import annotations

# ---------------------------------------------------------------------------
# Ignore patterns (directory and file names)
# ---------------------------------------------------------------------------
DEFAULT_IGNORE_PATTERNS: list[str] = [
    # Version control
    ".git",
    ".hg",
    ".svn",
    # Dependencies
    "node_modules",
    "vendor",
    "__pypackages__",
    ".venv",
    "venv",
    "env",
    ".env",
    # Build output
    "dist",
    "build",
    "out",
    "bin",
    "target",
    ".next",
    ".nuxt",
    ".output",
    "cmake-build-*",
    "CMakeFiles",
    "CMakeCache.txt",
    # Cache / temp
    "__pycache__",
    ".cache",
    ".parcel-cache",
    ".turbo",
    ".temp",
    ".tmp",
    ".mypy_cache",
    ".ruff_cache",
    # Coverage / test output
    "coverage",
    ".nyc_output",
    ".pytest_cache",
    "htmlcov",
    # IDE / editor
    ".idea",
    ".vscode",
    ".vs",
    "*.swp",
    "*.swo",
    # Documentation site output
    "_site",
    ".docusaurus",
    # OS files
    ".DS_Store",
    "Thumbs.db",
    # AI / tooling
    ".ai_code2doc",
    # Package manager lockfiles (usually not useful for docs)
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "uv.lock",
    "pdm.lock",
    "conan.lock",
    "CMakeLists.txt.lock",
]

# ---------------------------------------------------------------------------
# Ignore extensions (exact suffix match)
# ---------------------------------------------------------------------------
DEFAULT_IGNORE_EXTENSIONS: list[str] = [
    # Minified / generated
    ".min.js",
    ".min.css",
    # Source maps
    ".map",
    # Test / spec files
    ".spec.py",
    ".test.py",
    # C/C++ compiled objects
    ".o",
    ".obj",
    ".so",
    ".dylib",
    ".a",
    ".lib",
    ".ko",
    # Snapshot / fixture
    ".snap",
    ".snapshot",
    # Compiled / binary
    ".pyc",
    ".pyo",
    ".pyd",
    ".class",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".o",
    ".obj",
    ".wasm",
    # Images / media
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".webp",
    ".mp3",
    ".mp4",
    ".wav",
    ".avi",
    ".mov",
    ".webm",
    # Fonts
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    # Archives
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".7z",
    ".rar",
    # Data / serialization
    ".sqlite",
    ".db",
    ".pkl",
    ".pickle",
    ".npy",
    ".npz",
    ".h5",
    ".hdf5",
    # PDF / Office
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
]

# Extensions to keep even if a broader pattern above would exclude them.
KEEP_EXTENSIONS: list[str] = [
    "__init__.py",
]

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

PROMPT_LAYER1: str = """\
You are a senior software architect analysing a codebase to produce a \
high-level overview document.

## Task
Examine the following project structure and produce a concise project overview \
that covers:

1. **Purpose** - What does this project do? What problem does it solve?
2. **Technology Stack** - Key languages, frameworks, and libraries used.
3. **Architecture** - High-level architectural pattern (monolith, microservices, \
modular library, etc.) and major subsystems.
4. **Directory Layout** - Brief description of the top-level directories and \
their roles.
5. **Entry Points** - Main entry files and how the application is started or \
consumed.

## Project Structure
```
{tree}
```

## Key Files (extracts)
{key_files}

Respond in well-structured Markdown. Be factual - only describe what you can \
infer from the provided information. If something is uncertain, say so.
"""

PROMPT_LAYER2: str = """\
You are a senior software engineer writing module-level documentation.

## Task
For the module at **{module_path}**, produce a summary that covers:

1. **Responsibility** - What does this module do? What problem does it solve \
within the larger project?
2. **Public API** - Key classes, functions, and constants exported by this \
module. For each, give a one-line description including parameter types and \
return types where obvious.
3. **Internal Design** - How is the module organised internally? Mention any \
notable design patterns or abstractions used.
4. **Dependencies** - Other modules or external packages this module depends on.
5. **Consumers** - Which other modules are likely to import or use this module?

## Module Source
```{language}
{source}
```

Respond in well-structured Markdown. Use fenced code blocks for identifiers. \
Be concise but precise.
"""

PROMPT_LAYER3: str = """\
You are a software architect documenting the dependency graph of a codebase.

## Task
Given the following module dependency information, produce a textual \
description of the dependency graph that covers:

1. **Core Modules** - Which modules sit at the centre of the dependency graph \
and are depended upon by many others?
2. **Layer Boundaries** - Identify logical layers (e.g. UI, business logic, \
data access, infrastructure) and the direction of dependencies between them.
3. **Coupling Hotspots** - Modules with an unusually large number of direct \
dependencies that may benefit from refactoring.
4. **Circular Dependencies** - Any cycles detected in the import graph.
5. **Orphan Modules** - Modules with no incoming or outgoing dependencies.

## Dependency Data
```
{dependencies}
```

Respond in well-structured Markdown. Use relative module paths as identifiers. \
Where relevant, suggest improvements to the dependency structure.
"""
