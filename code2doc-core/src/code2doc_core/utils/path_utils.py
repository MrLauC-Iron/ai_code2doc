from __future__ import annotations

import re
from pathlib import Path

# Pattern matching characters that are unsafe in file names.
_UNSAFE_CHARS: re.Pattern[str] = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def relative_path(path: Path, base: Path) -> str:
    """Return *path* expressed relative to *base* using forward slashes.

    Parameters
    ----------
    path:
        The absolute or relative path to convert.
    base:
        The base directory.

    Returns
    -------
    str
        The relative path with ``/`` separators (POSIX-style).
    """
    try:
        rel = path.relative_to(base)
    except ValueError:
        # path is not under base; fall back to the original path.
        rel = Path(path)
    return rel.as_posix()


def module_name_from_path(path: Path, root: Path) -> str:
    """Derive a dotted module name from a file path.

    For example, given ``src/analyzer/parse.py`` with root ``src``, the result
    is ``analyzer.parse``.

    Parameters
    ----------
    path:
        The file path.
    root:
        The project root that serves as the package base.

    Returns
    -------
    str
        A dotted module name string.
    """
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = Path(path)

    parts = list(rel.parts)
    # Strip common file extensions that are not part of a module name.
    if parts:
        last = parts[-1]
        for ext in (
            ".py", ".pyi", ".pyw",
            ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx",
        ):
            if last.endswith(ext):
                parts[-1] = last[: -len(ext)]
                break
    # Remove __init__ or index leaves (they represent the package itself).
    if parts and parts[-1] in ("__init__", "index"):
        parts = parts[:-1]

    return ".".join(parts)


def ensure_dir(path: Path) -> Path:
    """Create *path* as a directory (with parents) if it does not exist.

    Parameters
    ----------
    path:
        The directory path to create.

    Returns
    -------
    Path
        The same *path*, for convenience in chained expressions.
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str) -> str:
    """Replace characters that are unsafe in file names with underscores.

    Parameters
    ----------
    name:
        The raw file name (without directory separators).

    Returns
    -------
    str
        A sanitised file name safe for all major operating systems.
    """
    cleaned = _UNSAFE_CHARS.sub("_", name)
    # Collapse consecutive underscores.
    cleaned = re.sub(r"_{2,}", "_", cleaned)
    # Strip leading/trailing underscores and dots.
    cleaned = cleaned.strip("_.")
    # Fall back if the name became empty.
    return cleaned or "unnamed"
