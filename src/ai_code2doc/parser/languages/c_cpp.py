"""C / C++ language support for the ai_code2doc parser.

Provides a tree-sitter--based extractor, import resolver, tech-stack
detector, and entry-point detector for C and C++ source files.
"""

from __future__ import annotations

import re
from pathlib import Path

import tree_sitter_c as tsc
import tree_sitter_cpp as tscpp
from tree_sitter import Language, Node

from ai_code2doc.models.module import (
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    InterfaceInfo,
)
from ai_code2doc.models.project import TechStack
from ai_code2doc.parser.base_extractor import BaseStructureExtractor
from ai_code2doc.parser.base_resolver import BaseImportResolver
from ai_code2doc.parser.language_registry import LanguageAdapter, LanguageRegistry
from ai_code2doc.parser.languages._common import (
    get_text,
    get_line,
    get_end_line,
    child_by_field,
    strip_quotes,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_C_CPP_EXTENSIONS = {
    ".cpp",
    ".cc",
    ".cxx",
    ".hpp",
    ".hxx",
    ".c",
    ".h",
    ".C",
}

_CPP_ONLY_EXTENSIONS = {".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".C"}

_C_ONLY_EXTENSIONS = {".c"}

_INCLUDE_EXTENSIONS = [
    ".h",
    ".hpp",
    ".hxx",
    ".c",
    ".cpp",
    ".cc",
    ".cxx",
]


def _unwrap_pointer_declarator(node: Node) -> Node:
    """Peel away ``pointer_declarator`` wrappers to reach the inner node."""
    current = node
    while current.type == "pointer_declarator":
        child = child_by_field(current, "declarator")
        if child is None:
            break
        current = child
    return current


def _find_identifier_in_declarator(declarator_node: Node) -> str | None:
    """Walk a declarator chain and return the function/method name.

    Handles ``function_declarator``, ``pointer_declarator``,
    ``qualified_identifier``, ``identifier``, and ``field_identifier``.
    """
    current = declarator_node

    # Unwrap pointer_declarator layers
    current = _unwrap_pointer_declarator(current)

    # Direct identifier
    if current.type in ("identifier", "field_identifier"):
        return get_text(current, _source_holder[0])

    # Qualified identifier  (e.g.  MyClass::method)
    if current.type == "qualified_identifier":
        # The right-most name child is the actual method name
        name_node = child_by_field(current, "name")
        if name_node is not None:
            if name_node.type in ("identifier", "field_identifier"):
                return get_text(name_node, _source_holder[0])
            # nested qualified – recurse
            return _find_identifier_in_declarator(name_node)
        # Fallback: last child of type identifier/field_identifier
        for ch in reversed(current.children):
            if ch.type in ("identifier", "field_identifier"):
                return get_text(ch, _source_holder[0])

    # function_declarator — dig deeper
    if current.type == "function_declarator":
        inner = child_by_field(current, "declarator")
        if inner is not None:
            return _find_identifier_in_declarator(inner)

    return None


def _has_destructor_name(node: Node) -> bool:
    """Return True if *node* (or a descendant) contains a ``destructor_name``."""
    if node.type == "destructor_name":
        return True
    for child in node.children:
        if _has_destructor_name(child):
            return True
    return False


def _is_virtual(function_def: Node) -> bool:
    """Check whether a ``function_definition`` has a ``virtual`` specifier."""
    for child in function_def.children:
        if child.type == "storage_class_specifier":
            if get_text(child, _source_holder[0]) == "virtual":
                return True
        if child.type == "virtual_specifier":
            return True
    return False


def _is_pure_virtual(function_def: Node) -> bool:
    """Check whether a ``function_definition`` ends with ``= 0``."""
    for child in function_def.children:
        if child.type == "pure_virtual_clause":
            return True
    return False


# Module-level holder so helper functions can access source text without
# passing it through every call frame.  Set at the start of each public
# extraction method.
_source_holder: list[str] = [""]


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class CCppExtractor(BaseStructureExtractor):
    """Walk tree-sitter AST for C and C++ files."""

    # -- functions ----------------------------------------------------------

    def extract_functions(self, root: Node, source: str) -> list[FunctionInfo]:
        _source_holder[0] = source
        results: list[FunctionInfo] = []

        for node in self._walk(root, "function_definition"):
            func = self._parse_function(node, source)
            if func is not None:
                results.append(func)

        return results

    def _parse_function(self, node: Node, source: str) -> FunctionInfo | None:
        """Parse a single ``function_definition`` node into :class:`FunctionInfo`."""
        declarator = child_by_field(node, "declarator")
        if declarator is None:
            return None

        name = _find_identifier_in_declarator(declarator)
        if name is None:
            return None

        # Return type
        type_node = child_by_field(node, "type")
        return_type: str | None = None
        if type_node is not None:
            return_type = get_text(type_node, source)

        # Parameters
        params = self._extract_params(declarator, source)

        return FunctionInfo(
            name=name,
            start_line=get_line(node),
            end_line=get_end_line(node),
            params=params,
            return_type=return_type,
            is_async=False,
            decorators=[],
            is_exported=False,
        )

    @staticmethod
    def _extract_params(declarator: Node, source: str) -> list[str]:
        """Extract parameter text from a function declarator."""
        params: list[str] = []

        def _walk_for_params(n: Node) -> None:
            if n.type == "parameter_list":
                for child in n.children:
                    if child.type == "parameter_declaration":
                        params.append(get_text(child, source).strip())
                return
            for child in n.children:
                _walk_for_params(child)

        _walk_for_params(declarator)
        return params

    # -- classes ------------------------------------------------------------

    def extract_classes(self, root: Node, source: str) -> list[ClassInfo]:
        _source_holder[0] = source
        results: list[ClassInfo] = []

        for node in self._walk(root):
            if node.type in ("class_specifier", "struct_specifier"):
                cls = self._parse_class(node, source)
                if cls is not None:
                    results.append(cls)

        return results

    def _parse_class(self, node: Node, source: str) -> ClassInfo | None:
        """Parse a ``class_specifier`` or ``struct_specifier``."""
        name_node = child_by_field(node, "name")
        if name_node is None:
            # Anonymous struct / class or forward declaration without body
            return None

        name = get_text(name_node, source)

        body = child_by_field(node, "body")
        if body is None:
            # Forward declaration (e.g. ``class Foo;``)
            return None

        # Extends — C++ base class clause
        extends: str | None = None
        for child in node.children:
            if child.type == "base_class_clause":
                # Take the first base class as extends
                base_names = []
                for bc in child.children:
                    if bc.type == "type_identifier":
                        base_names.append(get_text(bc, source))
                if base_names:
                    extends = ", ".join(base_names)
                break

        # Methods & properties from field_declaration_list
        methods: list[FunctionInfo] = []
        properties: list[str] = []

        for child in body.children:
            if child.type == "function_definition":
                func = self._parse_function(child, source)
                if func is not None:
                    methods.append(func)
            elif child.type == "declaration":
                # Could be a member variable or a pure-virtual / regular
                # member function declaration (not a definition).
                decl = child
                declarator_node = child_by_field(decl, "declarator")
                if declarator_node is not None:
                    unwrapped = _unwrap_pointer_declarator(declarator_node)
                    if unwrapped.type in ("identifier", "field_identifier"):
                        properties.append(get_text(unwrapped, source))
                    elif unwrapped.type == "function_declarator":
                        # Member function *declaration* (no body, e.g.
                        # virtual / pure-virtual).
                        fname = _find_identifier_in_declarator(unwrapped)
                        if fname is not None:
                            func_info = FunctionInfo(
                                name=fname,
                                start_line=get_line(decl),
                                end_line=get_end_line(decl),
                                params=self._extract_params(unwrapped, source),
                                return_type=(
                                    get_text(t, source)
                                    if (t := child_by_field(decl, "type")) is not None
                                    else None
                                ),
                                is_async=False,
                                decorators=[],
                                is_exported=False,
                            )
                            methods.append(func_info)
            elif child.type == "field_declaration":
                # Field declarations (member variables with possible initialiser)
                fdecl = child
                fdeclarator = child_by_field(fdecl, "declarator")
                if fdeclarator is not None:
                    unwrapped = _unwrap_pointer_declarator(fdeclarator)
                    # Skip if it's actually a function declarator (method inline)
                    if unwrapped.type == "function_declarator":
                        func = self._parse_function(fdecl, source)
                        if func is not None:
                            methods.append(func)
                    elif unwrapped.type in ("identifier", "field_identifier"):
                        properties.append(get_text(unwrapped, source))
                    elif unwrapped.type == "array_declarator":
                        # e.g. int arr[10];
                        inner = child_by_field(unwrapped, "declarator")
                        if inner is not None:
                            inner = _unwrap_pointer_declarator(inner)
                            if inner.type in ("identifier", "field_identifier"):
                                properties.append(get_text(inner, source))

        return ClassInfo(
            name=name,
            start_line=get_line(node),
            end_line=get_end_line(node),
            methods=methods,
            properties=properties,
            extends=extends,
            implements=[],
            is_exported=False,
            decorators=[],
        )

    # -- interfaces ---------------------------------------------------------

    def extract_interfaces(self, root: Node, source: str) -> list[InterfaceInfo]:
        # C/C++ does not have a native interface concept.
        return []

    # -- imports ------------------------------------------------------------

    def extract_imports(self, root: Node, source: str) -> list[ImportInfo]:
        _source_holder[0] = source
        results: list[ImportInfo] = []

        for node in self._walk(root, "preproc_include"):
            path_node = child_by_field(node, "path")
            if path_node is None:
                continue

            raw = get_text(path_node, source)

            if raw.startswith("<") and raw.endswith(">"):
                # System include  — angle brackets
                include_path = raw[1:-1]
                is_type_only = True
            else:
                include_path = strip_quotes(raw)
                is_type_only = False

            results.append(
                ImportInfo(
                    source=include_path,
                    specifiers=[],
                    is_type_only=is_type_only,
                )
            )

        return results

    # -- exports ------------------------------------------------------------

    def extract_exports(self, root: Node, source: str) -> list[str]:
        # C/C++ has no module export concept.
        return []

    # -- extra metadata -----------------------------------------------------

    def extract_extra_metadata(self, root: Node, source: str) -> dict:
        """Extract C/C++-specific structural metadata.

        Returns a dict with keys:
        ``enums``, ``typedefs``, ``macros``, ``namespaces``, ``structs``.
        """
        _source_holder[0] = source
        enums: list[str] = []
        typedefs: list[str] = []
        macros: list[str] = []
        namespaces: list[str] = []
        structs: list[str] = []

        for node in self._walk(root):
            if node.type == "enum_specifier":
                name_node = child_by_field(node, "name")
                if name_node is not None:
                    enums.append(get_text(name_node, source))

            elif node.type == "type_definition":
                # typedef ...
                declarator = child_by_field(node, "declarator")
                if declarator is not None:
                    typedefs.append(get_text(declarator, source).strip())

            elif node.type in ("preproc_def", "preproc_function_def"):
                name_node = child_by_field(node, "name")
                if name_node is not None:
                    macros.append(get_text(name_node, source))

            elif node.type == "namespace_definition":
                name_node = child_by_field(node, "name")
                if name_node is not None:
                    namespaces.append(get_text(name_node, source))

        # Structs already captured in extract_classes; list names here too.
        for node in self._walk(root):
            if node.type == "struct_specifier":
                name_node = child_by_field(node, "name")
                if name_node is not None:
                    structs.append(get_text(name_node, source))

        return {
            "enums": enums,
            "typedefs": typedefs,
            "macros": macros,
            "namespaces": namespaces,
            "structs": structs,
        }

    # -- internal walk helper -----------------------------------------------

    @staticmethod
    def _walk(node: Node, target_type: str | None = None):
        """Depth-first traversal yielding nodes of *target_type* (or all)."""
        stack = list(node.children)
        while stack:
            current = stack.pop()
            if target_type is None or current.type == target_type:
                yield current
            stack.extend(current.children)


# ---------------------------------------------------------------------------
# Import resolver
# ---------------------------------------------------------------------------


class CCppImportResolver(BaseImportResolver):
    """Resolve C/C++ ``#include`` directives to file paths."""

    def resolve(
        self,
        import_source: str,
        from_file: Path,
        project_root: Path,
    ) -> Path | None:
        # Only resolve quoted (local) includes; system includes are external.
        # Angle-bracket includes are marked is_type_only and will not
        # typically be passed here, but guard against it.
        if not import_source:
            return None

        # Try relative to the importing file's directory first.
        candidate = from_file.parent / import_source
        if candidate.is_file():
            try:
                return candidate.relative_to(project_root)
            except ValueError:
                return candidate

        # Try with various extensions if the source has none or a wrong one.
        for ext in _INCLUDE_EXTENSIONS:
            candidate = from_file.parent / (import_source + ext)
            if not candidate.is_file():
                # Also try without adding duplicate extensions
                candidate = from_file.parent / import_source
            if candidate.is_file():
                try:
                    return candidate.relative_to(project_root)
                except ValueError:
                    return candidate

        # Try project_root / include /
        for dir_candidate in (
            project_root / "include",
            project_root / "src",
        ):
            if not dir_candidate.is_dir():
                continue
            candidate = dir_candidate / import_source
            if candidate.is_file():
                try:
                    return candidate.relative_to(project_root)
                except ValueError:
                    return candidate
            for ext in _INCLUDE_EXTENSIONS:
                candidate = dir_candidate / (import_source + ext)
                if candidate.is_file():
                    try:
                        return candidate.relative_to(project_root)
                    except ValueError:
                        return candidate

        return None


# ---------------------------------------------------------------------------
# Tech-stack detection
# ---------------------------------------------------------------------------


def _has_files_with_ext(project_root: Path, extensions: set[str]) -> bool:
    """Return True if the project tree contains any file with one of *extensions*."""
    for ext in extensions:
        for _ in project_root.rglob(f"*{ext}"):
            return True
    return False


def detect_ccpp_tech_stack(project_root: Path) -> TechStack:
    """Detect the C/C++ technology stack for *project_root*."""

    build_tool = ""
    package_manager = ""
    framework = ""
    language = ""

    # -- Build tool ---------------------------------------------------------
    if (project_root / "CMakeLists.txt").is_file():
        build_tool = "CMake"
    elif (project_root / "Makefile").is_file() or (project_root / "makefile").is_file():
        build_tool = "Make"
    elif (project_root / "meson.build").is_file():
        build_tool = "Meson"
    elif (project_root / "WORKSPACE").is_file() or (project_root / "BUILD").is_file():
        build_tool = "Bazel"
    else:
        for sln in project_root.rglob("*.sln"):
            build_tool = "MSBuild"
            break
        if not build_tool:
            for vcxproj in project_root.rglob("*.vcxproj"):
                build_tool = "MSBuild"
                break

    # -- Package manager ----------------------------------------------------
    if (project_root / "conanfile.py").is_file() or (
        project_root / "conanfile.txt"
    ).is_file():
        package_manager = "Conan"

    # -- Language detection -------------------------------------------------
    has_c = _has_files_with_ext(project_root, _C_ONLY_EXTENSIONS)
    has_cpp = _has_files_with_ext(project_root, _CPP_ONLY_EXTENSIONS)

    if has_c and has_cpp:
        language = "C/C++"
    elif has_cpp:
        language = "C++"
    elif has_c:
        language = "C"

    # -- Framework detection ------------------------------------------------
    if _detect_qt(project_root):
        framework = "Qt"
    elif _detect_boost(project_root):
        framework = "Boost"

    # CUDA
    for _ in project_root.rglob("*.cu"):
        if framework:
            framework += " + CUDA"
        else:
            framework = "CUDA"
        break

    return TechStack(
        language=language,
        build_tool=build_tool,
        framework=framework,
        package_manager=package_manager,
    )


def _detect_qt(project_root: Path) -> bool:
    """Heuristic for Qt usage."""
    # .pro files
    for _ in project_root.rglob("*.pro"):
        return True

    # Qt mentions in CMakeLists.txt
    cmake = project_root / "CMakeLists.txt"
    if cmake.is_file():
        try:
            text = cmake.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"\bQt[0-9]*::", text) or re.search(
                r"\bfind_package\s*\(\s*Qt", text
            ):
                return True
        except OSError:
            pass
    return False


def _detect_boost(project_root: Path) -> bool:
    """Heuristic for Boost usage."""
    for cmake_path in project_root.rglob("CMakeLists.txt"):
        try:
            text = cmake_path.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"\bfind_package\s*\(\s*boost", text, re.IGNORECASE):
                return True
            if re.search(r"\bBoost::", text):
                return True
        except OSError:
            pass
    return False


# ---------------------------------------------------------------------------
# Entry-point detection
# ---------------------------------------------------------------------------

_MAIN_PATTERN = re.compile(r"\bint\s+main\s*\(|void\s+main\s*\(")
_ADD_EXEC_PATTERN = re.compile(r"add_executable\s*\(\s*(\w+)")


def detect_ccpp_entry_points(project_root: Path) -> list[str]:
    """Detect entry-point files for a C/C++ project."""

    entry_points: list[str] = []
    seen: set[str] = set()

    # 1. Grep for main() function definitions
    for ext in _C_CPP_EXTENSIONS:
        for path in project_root.rglob(f"*{ext}"):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if _MAIN_PATTERN.search(text):
                try:
                    rel = str(path.relative_to(project_root)).replace("\\", "/")
                except ValueError:
                    rel = str(path).replace("\\", "/")
                if rel not in seen:
                    entry_points.append(rel)
                    seen.add(rel)

    # 2. Parse CMakeLists.txt for add_executable targets
    for cmake_path in project_root.rglob("CMakeLists.txt"):
        _add_cmake_executables(cmake_path, project_root, entry_points, seen)

    # 3. Check common entry-file locations
    _check_common_entry_files(project_root, entry_points, seen)

    return entry_points


def _add_cmake_executables(
    cmake_path: Path,
    project_root: Path,
    entry_points: list[str],
    seen: set[str],
) -> None:
    """Look for ``add_executable`` in a CMakeLists.txt and resolve the source."""
    try:
        text = cmake_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return

    for m in _ADD_EXEC_PATTERN.finditer(text):
        target_name = m.group(1)
        # Try to find a matching source file near the CMakeLists.txt
        cmake_dir = cmake_path.parent
        for ext in _C_CPP_EXTENSIONS:
            candidate = cmake_dir / f"{target_name}{ext}"
            if candidate.is_file():
                try:
                    rel = str(candidate.relative_to(project_root)).replace("\\", "/")
                except ValueError:
                    rel = str(candidate).replace("\\", "/")
                if rel not in seen:
                    entry_points.append(rel)
                    seen.add(rel)
                return
        # Also try src/ subdirectory
        for ext in _C_CPP_EXTENSIONS:
            candidate = cmake_dir / "src" / f"{target_name}{ext}"
            if candidate.is_file():
                try:
                    rel = str(candidate.relative_to(project_root)).replace("\\", "/")
                except ValueError:
                    rel = str(candidate).replace("\\", "/")
                if rel not in seen:
                    entry_points.append(rel)
                    seen.add(rel)
                return


def _check_common_entry_files(
    project_root: Path,
    entry_points: list[str],
    seen: set[str],
) -> None:
    """Check for conventional entry-file locations."""
    common_paths = [
        project_root / "main.c",
        project_root / "main.cpp",
        project_root / "src" / "main.c",
        project_root / "src" / "main.cpp",
    ]
    for candidate in common_paths:
        if candidate.is_file():
            try:
                rel = str(candidate.relative_to(project_root)).replace("\\", "/")
            except ValueError:
                rel = str(candidate).replace("\\", "/")
            if rel not in seen:
                entry_points.append(rel)
                seen.add(rel)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_c_cpp() -> None:
    """Register the C / C++ language adapter with the global registry."""
    LanguageRegistry.register(
        LanguageAdapter(
            language_id="c_cpp",
            display_name="C / C++",
            extensions=(".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".C"),
            tree_sitter_language=Language(tscpp.language()),
            extractor=CCppExtractor(),
            resolver=CCppImportResolver(),
            detect_tech_stack=detect_ccpp_tech_stack,
            detect_entry_points=detect_ccpp_entry_points,
        )
    )
