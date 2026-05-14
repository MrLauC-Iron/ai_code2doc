"""CMake build-file parser for ai_code2doc.

Extracts structured build metadata from ``CMakeLists.txt`` files using
lightweight regex-based parsing (no full CMake evaluator required).
"""

from __future__ import annotations

import re
from pathlib import Path

from ai_code2doc.models.build import CMakeProjectInfo, CMakeTarget

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Matches top-level CMake commands we care about.
_CMAKE_CMD_RE = re.compile(
    r"^\s*"
    r"(cmake_minimum_required|project|add_subdirectory|find_package|"
    r"add_executable|add_library|"
    r"target_include_directories|target_link_libraries|target_sources)"
    r"\s*\(",
    re.MULTILINE,
)

# cmake_minimum_required(VERSION 3.20 ...)
_CMAKE_VERSION_RE = re.compile(
    r"cmake_minimum_required\s*\(\s*VERSION\s*([\d.]+)", re.IGNORECASE
)

# project(MyProject [LANGUAGES C CXX])
_PROJECT_NAME_RE = re.compile(r"^\s*(\w+)")
_PROJECT_LANG_RE = re.compile(
    r"project\s*\([^)]*LANGUAGES\s+([\w\s]+?)(?:\)|$)", re.IGNORECASE
)

# find_package(Qt6 REQUIRED COMPONENTS Widgets)
_FIND_PKG_RE = re.compile(r"find_package\s*\(\s*(\w+)")

# Visibility keywords used inside target_* commands.
_VISIBILITY_RE = re.compile(r"\b(PUBLIC|PRIVATE|INTERFACE)\b")

# add_library type keywords (STATIC, SHARED, MODULE, OBJECT, INTERFACE).
_LIB_TYPE_MAP = {
    "STATIC": "static_library",
    "SHARED": "shared_library",
    "MODULE": "module_library",
    "OBJECT": "object_library",
    "INTERFACE": "interface_library",
    "": "static_library",  # default
}

# CMake keywords that are NOT source file paths.
_CMAKE_KEYWORDS = frozenset({
    "STATIC", "SHARED", "MODULE", "OBJECT", "INTERFACE",
    "PUBLIC", "PRIVATE", "INTERFACE",
    "REQUIRED", "COMPONENTS", "OPTIONAL", "QUIET", "CONFIG", "NO_MODULE",
    "GLOBAL", "IMPORTED", "ALIAS", "EXCLUDE_FROM_ALL",
    "VERSION", "LANGUAGES",
    "WIN32", "MACOSX_BUNDLE", "EXCLUDE_FROM_ALL",
    "AUTOGEN", "AUTOMOC", "AUTOUIC", "AUTORCC",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_comments(line: str) -> str:
    """Remove ``#`` comments from a single CMake line."""
    # Handle string literals: don't strip inside quotes.
    in_quote: str | None = None
    for i, ch in enumerate(line):
        if ch in ('"', "'") and (i == 0 or line[i - 1] != "\\"):
            if in_quote is None:
                in_quote = ch
            elif in_quote == ch:
                in_quote = None
        elif ch == "#" and in_quote is None:
            return line[:i]
    return line


def _extract_balanced_args(text: str, start: int) -> tuple[str, int]:
    """Extract the content inside parentheses starting at *start*.

    *start* should point at the opening ``(``.  Returns the content
    (without outer parens) and the index of the closing paren, or
    ``("", -1)`` on failure.
    """
    if start >= len(text) or text[start] != "(":
        return "", -1
    depth = 0
    i = start
    content_start = start + 1
    in_quote: str | None = None
    while i < len(text):
        ch = text[i]
        if ch in ('"', "'") and (i == 0 or text[i - 1] != "\\"):
            if in_quote is None:
                in_quote = ch
            elif in_quote == ch:
                in_quote = None
        elif in_quote is None:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return text[content_start:i], i
        i += 1
    return "", -1


def _tokenize_args(args_text: str) -> list[str]:
    """Split CMake argument text into tokens, respecting quotes.

    Also strips comments and converts to uppercase for keyword detection.
    """
    tokens: list[str] = []
    current: list[str] = []
    in_quote: str | None = None

    for line in args_text.splitlines():
        stripped = _strip_comments(line)
        for ch in stripped:
            if ch in ('"', "'"):
                if in_quote is None:
                    in_quote = ch
                elif in_quote == ch:
                    in_quote = None
                # Don't add quote characters to token
            elif in_quote is None and ch in (" ", "\t", "\n", "\r"):
                if current:
                    tokens.append("".join(current))
                    current = []
            else:
                current.append(ch)

    if current:
        tokens.append("".join(current))

    return tokens


def _split_by_visibility(tokens: list[str]) -> dict[str, list[str]]:
    """Split a token list by PUBLIC/PRIVATE/INTERFACE keywords.

    Tokens before the first visibility keyword are treated as PUBLIC.
    Returns ``{"PUBLIC": [...], "PRIVATE": [...], "INTERFACE": [...]}``.
    """
    sections: dict[str, list[str]] = {"PUBLIC": [], "PRIVATE": [], "INTERFACE": []}
    current_vis = "PUBLIC"
    for token in tokens:
        upper = token.upper()
        if upper in ("PUBLIC", "PRIVATE", "INTERFACE"):
            current_vis = upper
        else:
            sections[current_vis].append(token)
    return sections


def _normalize_source_path(source: str, cmake_dir: Path, project_root: Path) -> str:
    """Convert a source path relative to *cmake_dir* to be relative to *project_root*."""
    p = (cmake_dir / source).resolve()
    try:
        return str(p.relative_to(project_root)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _normalize_dir_path(dir_path: str, cmake_dir: Path, project_root: Path) -> str:
    """Normalize a directory path to be relative to *project_root*."""
    p = (cmake_dir / dir_path).resolve()
    try:
        return str(p.relative_to(project_root)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class CMakeParser:
    """Parse ``CMakeLists.txt`` files to extract build metadata.

    Usage::

        parser = CMakeParser()
        info = parser.parse(project_root)
        print(info.targets, info.find_packages)
    """

    def parse(self, project_root: Path) -> CMakeProjectInfo:
        """Walk *project_root* for all ``CMakeLists.txt`` and extract metadata."""
        project_root = project_root.resolve()
        info = CMakeProjectInfo()

        # Collect all CMakeLists.txt files, sorted by depth then path.
        cmake_files = sorted(
            project_root.rglob("CMakeLists.txt"),
            key=lambda p: (str(p).count("/"), str(p)),
        )

        for cmake_path in cmake_files:
            try:
                text = cmake_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            rel_cmake = self._rel(cmake_path, project_root)
            cmake_dir = cmake_path.parent

            self._parse_file(text, rel_cmake, cmake_dir, project_root, info)

        return info

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _rel(path: Path, root: Path) -> str:
        try:
            return str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")

    def _parse_file(
        self,
        text: str,
        rel_cmake: str,
        cmake_dir: Path,
        project_root: Path,
        info: CMakeProjectInfo,
    ) -> None:
        """Parse a single CMakeLists.txt content and update *info*."""
        for m in _CMAKE_CMD_RE.finditer(text):
            cmd = m.group(1)
            # Extract balanced parentheses content.
            args_text, end = _extract_balanced_args(text, m.end() - 1)
            if end == -1:
                continue

            tokens = _tokenize_args(args_text)
            if not tokens:
                continue

            if cmd == "cmake_minimum_required":
                ver_m = _CMAKE_VERSION_RE.search(text[m.start(): m.end() + 100])
                if ver_m and not info.cmake_version:
                    info.cmake_version = ver_m.group(1)

            elif cmd == "project":
                if not info.project_name:
                    name_m = _PROJECT_NAME_RE.search(args_text)
                    if name_m:
                        info.project_name = name_m.group(1)
                if not info.project_languages:
                    lang_m = _PROJECT_LANG_RE.search(args_text)
                    if lang_m:
                        info.project_languages = lang_m.group(1).split()
                    else:
                        # Default: check for C/CXX files inferred from tokens
                        for t in tokens:
                            upper = t.upper()
                            if upper in ("C", "CXX", "CUDA", "OBJC", "OBJCXX"):
                                info.project_languages.append(upper)

            elif cmd == "add_subdirectory":
                if tokens:
                    info.subdirectories.append(
                        _normalize_dir_path(tokens[0], cmake_dir, project_root)
                    )

            elif cmd == "find_package":
                if tokens:
                    pkg_name = tokens[0]
                    if pkg_name.upper() not in _CMAKE_KEYWORDS:
                        if pkg_name not in info.find_packages:
                            info.find_packages.append(pkg_name)

            elif cmd == "add_executable":
                target = self._parse_add_executable(tokens, rel_cmake, cmake_dir, project_root)
                if target:
                    info.targets[target.name] = target

            elif cmd == "add_library":
                target = self._parse_add_library(tokens, rel_cmake, cmake_dir, project_root)
                if target:
                    info.targets[target.name] = target

            elif cmd == "target_include_directories":
                self._parse_target_include_directories(tokens, info, cmake_dir, project_root)

            elif cmd == "target_link_libraries":
                self._parse_target_link_libraries(tokens, info)

            elif cmd == "target_sources":
                self._parse_target_sources(tokens, rel_cmake, cmake_dir, project_root, info)

    # ------------------------------------------------------------------
    # Target parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_add_executable(
        tokens: list[str],
        rel_cmake: str,
        cmake_dir: Path,
        project_root: Path,
    ) -> CMakeTarget | None:
        """Parse ``add_executable(target_name source1 source2 ...)``."""
        if not tokens:
            return None
        name = tokens[0]
        # Skip keywords after name (WIN32, MACOSX_BUNDLE, EXCLUDE_FROM_ALL).
        sources = [
            _normalize_source_path(t, cmake_dir, project_root)
            for t in tokens[1:]
            if t.upper() not in _CMAKE_KEYWORDS and not t.startswith("$<")
        ]
        return CMakeTarget(
            name=name,
            target_type="executable",
            sources=sources,
            cmake_file=rel_cmake,
        )

    @staticmethod
    def _parse_add_library(
        tokens: list[str],
        rel_cmake: str,
        cmake_dir: Path,
        project_root: Path,
    ) -> CMakeTarget | None:
        """Parse ``add_library(name [STATIC|SHARED|...] source1 source2 ...)``."""
        if not tokens:
            return None
        name = tokens[0]
        lib_type = "static_library"  # default
        source_start = 1

        if len(tokens) > 1:
            second_upper = tokens[1].upper()
            if second_upper in _LIB_TYPE_MAP:
                lib_type = _LIB_TYPE_MAP[second_upper]
                source_start = 2
            elif second_upper == "INTERFACE":
                lib_type = "interface_library"
                source_start = 2

        sources = [
            _normalize_source_path(t, cmake_dir, project_root)
            for t in tokens[source_start:]
            if t.upper() not in _CMAKE_KEYWORDS and not t.startswith("$<")
        ]
        return CMakeTarget(
            name=name,
            target_type=lib_type,
            sources=sources,
            cmake_file=rel_cmake,
        )

    @staticmethod
    def _parse_target_include_directories(
        tokens: list[str],
        info: CMakeProjectInfo,
        cmake_dir: Path,
        project_root: Path,
    ) -> None:
        """Parse ``target_include_directories(target [PUBLIC|PRIVATE|INTERFACE] dir1 ...)``."""
        if len(tokens) < 2:
            return
        target_name = tokens[0]
        target = info.targets.get(target_name)
        if target is None:
            return

        sections = _split_by_visibility(tokens[1:])
        for vis, dirs in sections.items():
            for d in dirs:
                if d.upper() in _CMAKE_KEYWORDS or d.startswith("$<") or d.startswith("${"):
                    continue
                normalized = _normalize_dir_path(d, cmake_dir, project_root)
                if normalized not in target.include_dirs:
                    target.include_dirs.append(normalized)

    @staticmethod
    def _parse_target_link_libraries(
        tokens: list[str],
        info: CMakeProjectInfo,
    ) -> None:
        """Parse ``target_link_libraries(target [PUBLIC|PRIVATE|INTERFACE] lib1 ...)``."""
        if len(tokens) < 2:
            return
        target_name = tokens[0]
        target = info.targets.get(target_name)
        if target is None:
            return

        sections = _split_by_visibility(tokens[1:])
        for vis, libs in sections.items():
            for lib in libs:
                if lib.upper() in _CMAKE_KEYWORDS or lib.startswith("$<") or lib.startswith("${"):
                    continue
                # Strip common CMake qualifiers from lib name
                clean = lib.split("::")[-1] if "::" in lib else lib
                if clean and clean not in target.link_libraries:
                    target.link_libraries.append(clean)

    @staticmethod
    def _parse_target_sources(
        tokens: list[str],
        rel_cmake: str,
        cmake_dir: Path,
        project_root: Path,
        info: CMakeProjectInfo,
    ) -> None:
        """Parse ``target_sources(target [PUBLIC|PRIVATE|INTERFACE] file1 ...)``."""
        if len(tokens) < 2:
            return
        target_name = tokens[0]
        target = info.targets.get(target_name)
        if target is None:
            return

        sections = _split_by_visibility(tokens[1:])
        for vis, srcs in sections.items():
            for src in srcs:
                if src.upper() in _CMAKE_KEYWORDS or src.startswith("$<") or src.startswith("${"):
                    continue
                normalized = _normalize_source_path(src, cmake_dir, project_root)
                if normalized not in target.sources:
                    target.sources.append(normalized)
