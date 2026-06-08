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
