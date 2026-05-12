"""Full Python language support for the ai_code2doc parser.

Provides tree-sitter-based extraction of functions, classes, imports and
exports, plus import resolution and tech-stack / entry-point detection.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import tree_sitter_python as tspy
from tree_sitter import Language, Node

from ai_code2doc.models.module import ClassInfo, FunctionInfo, ImportInfo, InterfaceInfo
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
    find_parent_of_type,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PY_LANGUAGE = Language(tspy.language())


def _is_async_function(node: Node) -> bool:
    """Return True if *node* (a ``function_definition``) is async.

    Tree-sitter for Python marks async functions by having ``async`` as a
    leading unnamed child, or via a preceding sibling when wrapped in a
    ``decorated_definition``.
    """
    # Check first unnamed child — tree-sitter-python puts "async" before the
    # "def" keyword inside function_definition when the function is async.
    for child in node.children:
        if child.is_named:
            break
        if child.type == "async":
            return True

    # Also check the preceding sibling in the parent (covers cases where
    # tree-sitter represents async as a sibling modifier).
    parent = node.parent
    if parent is not None and parent.type == "decorated_definition":
        prev = node.prev_named_sibling
        if prev is not None and prev.type == "async":
            return True
        # Walk children to find "async" token before this function node.
        found_async = False
        for child in parent.children:
            if child == node:
                break
            if child.type == "async":
                found_async = True
        if found_async:
            return True

    return False


def _extract_decorators(node: Node, source: str) -> list[str]:
    """Extract decorator strings when *node* is inside a ``decorated_definition``."""
    parent = node.parent
    if parent is None or parent.type != "decorated_definition":
        return []

    decorators: list[str] = []
    for child in parent.children:
        if child.type == "decorator":
            decorators.append(get_text(child, source).strip())
    return decorators


def _extract_parameters(params_node: Node | None, source: str) -> list[str]:
    """Extract parameter text from a ``parameters`` node."""
    if params_node is None:
        return []

    params: list[str] = []
    for child in params_node.children:
        if child.type in (
            "identifier",
            "typed_parameter",
            "default_parameter",
            "typed_default_parameter",
            "list_splat_pattern",
            "dictionary_splat_pattern",
        ):
            params.append(get_text(child, source))
    return params


def _make_function_info(node: Node, source: str) -> FunctionInfo:
    """Build a :class:`FunctionInfo` from a ``function_definition`` node."""
    name_node = child_by_field(node, "name")
    name = get_text(name_node, source) if name_node else "<anonymous>"

    params_node = child_by_field(node, "parameters")
    params = _extract_parameters(params_node, source)

    return_type_node = child_by_field(node, "return_type")
    return_type = get_text(return_type_node, source) if return_type_node else None

    is_async = _is_async_function(node)
    decorators = _extract_decorators(node, source)

    return FunctionInfo(
        name=name,
        start_line=get_line(node),
        end_line=get_end_line(node),
        params=params,
        return_type=return_type,
        is_exported=False,
        is_async=is_async,
        decorators=decorators,
    )


# ---------------------------------------------------------------------------
# PythonExtractor
# ---------------------------------------------------------------------------

class PythonExtractor(BaseStructureExtractor):
    """Walk tree-sitter AST for Python files and extract structural info."""

    def extract_functions(self, root: Node, source: str) -> list[FunctionInfo]:
        """Extract top-level function definitions.

        Does NOT descend into class bodies — class methods are reported
        through :meth:`extract_classes`.
        """
        functions: list[FunctionInfo] = []
        for node in root.children:
            if node.type == "function_definition":
                functions.append(_make_function_info(node, source))
            elif node.type == "decorated_definition":
                # The decorated_definition wraps the actual function.
                for child in node.children:
                    if child.type == "function_definition":
                        functions.append(_make_function_info(child, source))
                        break
        return functions

    def extract_classes(self, root: Node, source: str) -> list[ClassInfo]:
        """Extract class definitions with their methods and properties."""
        classes: list[ClassInfo] = []
        for node in root.children:
            if node.type == "class_definition":
                classes.append(self._build_class_info(node, source))
            elif node.type == "decorated_definition":
                for child in node.children:
                    if child.type == "class_definition":
                        classes.append(self._build_class_info(child, source))
                        break
        return classes

    # -- class helper -------------------------------------------------------

    def _build_class_info(self, node: Node, source: str) -> ClassInfo:
        name_node = child_by_field(node, "name")
        name = get_text(name_node, source) if name_node else "<anonymous>"

        superclasses_node = child_by_field(node, "superclasses")
        extends: str | None = None
        if superclasses_node is not None:
            # The superclasses field is an argument_list; take the first named child.
            first_super = superclasses_node.child_by_field_name("first")
            if first_super is None and superclasses_node.named_child_count > 0:
                first_super = superclasses_node.named_children[0]
            if first_super is not None:
                extends = get_text(first_super, source)

        # Walk the class body for methods and properties.
        body_node = child_by_field(node, "body")
        methods: list[FunctionInfo] = []
        properties: list[str] = []

        if body_node is not None:
            # Use a cursor to walk direct children of the body — we need to
            # handle decorated_definition wrapping at this level too.
            for child in body_node.children:
                target = child
                if child.type == "decorated_definition":
                    for inner in child.children:
                        if inner.type in ("function_definition", "assignment"):
                            target = inner
                            break

                if target.type == "function_definition":
                    methods.append(_make_function_info(target, source))
                elif target.type == "assignment":
                    left = child_by_field(target, "left")
                    if left is not None and left.type == "identifier":
                        properties.append(get_text(left, source))

        decorators = _extract_decorators(node, source)

        return ClassInfo(
            name=name,
            start_line=get_line(node),
            end_line=get_end_line(node),
            methods=methods,
            properties=properties,
            extends=extends,
            implements=[],
            is_exported=False,
            decorators=decorators,
        )

    # -- imports ------------------------------------------------------------

    def extract_imports(self, root: Node, source: str) -> list[ImportInfo]:
        """Extract ``import`` and ``from ... import`` statements."""
        imports: list[ImportInfo] = []

        for node in root.children:
            if node.type == "import_statement":
                imports.append(self._parse_import_statement(node, source))
            elif node.type == "import_from_statement":
                imports.append(self._parse_import_from_statement(node, source))

        return imports

    def _parse_import_statement(self, node: Node, source: str) -> ImportInfo:
        """Parse ``import X`` / ``import X as Y`` / ``import X.Y``."""
        # Collect all named children (these are dotted_name / aliased_import nodes).
        parts: list[str] = []
        specifiers: list[str] = []

        for child in node.named_children:
            text = get_text(child, source)
            if child.type == "aliased_import":
                # e.g. "X as Y"
                specifiers.append(text)
                # The source for the import itself is the name before "as".
                parts.append(text)
            elif child.type == "dotted_name":
                parts.append(text)
                specifiers.append(text)
            else:
                parts.append(text)
                specifiers.append(text)

        # Join the top-level dotted_name parts for the source.  If there are
        # multiple comma-separated imports like ``import X, Y`` we treat the
        # whole thing as one ImportInfo with multiple specifiers.
        source_name = ", ".join(parts) if parts else ""
        return ImportInfo(
            source=source_name,
            specifiers=specifiers,
            is_type_only=False,
        )

    def _parse_import_from_statement(self, node: Node, source: str) -> ImportInfo:
        """Parse ``from X import Y`` / ``from .X import Y`` etc."""
        # First named child is the module source (dotted_name or relative_import).
        module_node = node.child_by_field_name("module_name")
        if module_node is None:
            # Fallback: first named child.
            module_node = node.named_children[0] if node.named_child_count > 0 else None

        module_name = get_text(module_node, source) if module_node else ""

        # Remaining named children after the module are the imported names.
        specifiers: list[str] = []
        started = False
        for child in node.named_children:
            if not started:
                if child == module_node:
                    started = True
                continue
            specifiers.append(get_text(child, source))

        # Handle wildcard: ``from X import *``
        # The star is an unnamed child but tree-sitter-python may expose it
        # as a child node with type "*".
        if not specifiers:
            for child in node.children:
                if get_text(child, source) == "*":
                    specifiers = ["*"]
                    break

        return ImportInfo(
            source=module_name,
            specifiers=specifiers,
            is_type_only=False,
        )

    # -- exports ------------------------------------------------------------

    def extract_exports(self, root: Node, source: str) -> list[str]:
        """Look for ``__all__ = [...]`` assignments and extract names."""
        exports: list[str] = []
        for node in root.children:
            # tree-sitter-python may wrap the assignment in expression_statement
            target = node
            if node.type == "expression_statement" and node.named_child_count > 0:
                target = node.named_children[0]
            if target.type != "assignment":
                continue
            left = child_by_field(target, "left")
            if left is None or get_text(left, source) != "__all__":
                continue

            right = child_by_field(target, "right")
            if right is None:
                continue

            # The right side should be a list / tuple literal.
            exports.extend(self._parse_string_list(right, source))
        return exports

    @staticmethod
    def _parse_string_list(node: Node, source: str) -> list[str]:
        """Extract string literal elements from a list/tuple literal node."""
        result: list[str] = []
        if node.type not in ("list", "list_comprehension", "tuple", "parenthesized_expression"):
            return result
        for child in node.named_children:
            if child.type == "string":
                text = strip_quotes(get_text(child, source))
                result.append(text)
        return result


# ---------------------------------------------------------------------------
# PythonImportResolver
# ---------------------------------------------------------------------------

class PythonImportResolver(BaseImportResolver):
    """Resolve Python imports to file paths within the project."""

    CANDIDATE_EXTENSIONS = (".py", ".pyi")
    INDEX_FILE = "__init__.py"

    def resolve(
        self,
        import_source: str,
        from_file: Path,
        project_root: Path,
    ) -> Path | None:
        """Resolve a Python import string to a file path relative to project root.

        Returns ``None`` for stdlib / third-party imports that do not map to a
        file inside *project_root*.
        """
        if not import_source:
            return None

        # Handle relative imports (leading dots).
        if import_source.startswith("."):
            return self._resolve_relative(import_source, from_file, project_root)

        return self._resolve_absolute(import_source, project_root)

    # -- absolute imports ---------------------------------------------------

    def _resolve_absolute(
        self, import_source: str, project_root: Path
    ) -> Path | None:
        """Resolve absolute dotted import like ``a.b.c``."""
        parts = import_source.split(".")
        rel_path = Path(*parts)

        # Try <path>.py / <path>.pyi
        for ext in self.CANDIDATE_EXTENSIONS:
            candidate = project_root / f"{rel_path}{ext}"
            if candidate.is_file():
                return candidate.relative_to(project_root)

        # Try <path>/__init__.py
        init_candidate = project_root / rel_path / self.INDEX_FILE
        if init_candidate.is_file():
            return init_candidate.relative_to(project_root)

        # Also try under a src/ directory (common in modern Python packaging).
        src_candidate_base = project_root / "src"
        if src_candidate_base.is_dir():
            for ext in self.CANDIDATE_EXTENSIONS:
                candidate = src_candidate_base / f"{rel_path}{ext}"
                if candidate.is_file():
                    return candidate.relative_to(project_root)
            init_candidate = src_candidate_base / rel_path / self.INDEX_FILE
            if init_candidate.is_file():
                return init_candidate.relative_to(project_root)

        return None

    # -- relative imports ---------------------------------------------------

    def _resolve_relative(
        self, import_source: str, from_file: Path, project_root: Path
    ) -> Path | None:
        """Resolve relative imports like ``.foo`` or ``..bar``."""
        # Count leading dots for the level.
        level = 0
        i = 0
        while i < len(import_source) and import_source[i] == ".":
            level += 1
            i += 1

        remainder = import_source[level:]

        # Start from the package directory of from_file.
        # Go up `level` directories (level=1 means current package).
        base = from_file.parent
        for _ in range(level - 1):
            base = base.parent

        if remainder:
            parts = remainder.split(".")
            rel_path = base / Path(*parts)
        else:
            rel_path = base

        # Try as module file.
        if not remainder:
            # ``from . import X`` — the target is the package itself.
            for ext in self.CANDIDATE_EXTENSIONS:
                candidate = rel_path / self.INDEX_FILE
                # Not applicable here since we don't know X yet; skip.
                # The import_source is just dots; we cannot resolve further.
                pass
            return None

        for ext in self.CANDIDATE_EXTENSIONS:
            candidate = rel_path.with_suffix(ext)
            if candidate.is_file():
                try:
                    return candidate.relative_to(project_root)
                except ValueError:
                    return None

        # Try as package.
        init_candidate = rel_path / self.INDEX_FILE
        if init_candidate.is_file():
            try:
                return init_candidate.relative_to(project_root)
            except ValueError:
                return None

        return None


# ---------------------------------------------------------------------------
# Tech-stack detection
# ---------------------------------------------------------------------------

# Known framework indicator packages.
_FRAMEWORK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Django", re.compile(r"\bdjango\b", re.IGNORECASE)),
    ("Flask", re.compile(r"\bflask\b", re.IGNORECASE)),
    ("FastAPI", re.compile(r"\bfastapi\b", re.IGNORECASE)),
    ("Starlette", re.compile(r"\bstarlette\b", re.IGNORECASE)),
    ("Pyramid", re.compile(r"\bpyramid\b", re.IGNORECASE)),
    ("PyTorch", re.compile(r"\btorch\b", re.IGNORECASE)),
    ("TensorFlow", re.compile(r"\btensorflow\b", re.IGNORECASE)),
    ("Scikit-learn", re.compile(r"\bscikit[-_]?learn\b", re.IGNORECASE)),
    ("Celery", re.compile(r"\bcelery\b", re.IGNORECASE)),
    ("SQLAlchemy", re.compile(r"\bsqlalchemy\b", re.IGNORECASE)),
    ("Pandas", re.compile(r"\bpandas\b", re.IGNORECASE)),
    ("NumPy", re.compile(r"\bnumpy\b", re.IGNORECASE)),
    ("Tornado", re.compile(r"\btornado\b", re.IGNORECASE)),
    ("Sanic", re.compile(r"\bsanic\b", re.IGNORECASE)),
    ("aiohttp", re.compile(r"\baiohttp\b", re.IGNORECASE)),
]

# Build tool detection from pyproject.toml build-system.
_BUILD_TOOL_MAP: dict[str, str] = {
    "poetry.core.masonry.api": "poetry",
    "flit_core.buildapi": "flit",
    "hatchling.build": "hatch",
    "pdm.backend": "pdm",
    "setuptools.build_meta": "setuptools",
}

# Package manager heuristics.
_PKG_MANAGER_FILES: dict[str, str] = {
    "poetry.lock": "poetry",
    "pdm.lock": "pdm",
    "uv.lock": "uv",
}


def _parse_toml_simple(text: str) -> dict:
    """Minimal TOML parser for the subset we care about.

    Handles flat tables, simple key = value pairs, and inline tables/arrays.
    This is deliberately lightweight to avoid a third-party dependency for
    projects not yet on Python 3.11+.
    """
    result: dict = {}
    current_table: list[str] = []
    current_dict: dict = result

    for line in text.splitlines():
        stripped = line.strip()

        # Skip blanks and comments.
        if not stripped or stripped.startswith("#"):
            continue

        # Table header.
        table_match = re.match(r"^\[([^\]]+)\]", stripped)
        if table_match:
            key_path = table_match.group(1).strip()
            parts = [p.strip().strip('"') for p in key_path.split(".")]
            current_table = parts
            current_dict = result
            for part in parts:
                if part not in current_dict:
                    current_dict[part] = {}
                current_dict = current_dict[part]
            continue

        # Key = value pair.
        kv_match = re.match(r"^([A-Za-z0-9_\-]+)\s*=\s*(.+)$", stripped)
        if kv_match:
            key = kv_match.group(1).strip()
            value_str = kv_match.group(2).strip()
            current_dict[key] = _parse_toml_value(value_str)

    return result


def _parse_toml_value(value_str: str):
    """Parse a single TOML value."""
    value_str = value_str.strip()

    if value_str.startswith('"') and value_str.endswith('"'):
        return value_str[1:-1]
    if value_str.startswith("'") and value_str.endswith("'"):
        return value_str[1:-1]
    if value_str.startswith("["):
        return _parse_toml_array(value_str)
    if value_str.startswith("{"):
        return _parse_toml_inline_table(value_str)
    if value_str.lower() == "true":
        return True
    if value_str.lower() == "false":
        return False
    try:
        return int(value_str)
    except ValueError:
        pass
    try:
        return float(value_str)
    except ValueError:
        pass
    return value_str


def _parse_toml_array(text: str) -> list:
    """Parse an inline TOML array string."""
    text = text.strip()
    if not text.startswith("[") or not text.endswith("]"):
        return []
    inner = text[1:-1].strip()
    if not inner:
        return []
    items: list[str] = []
    depth = 0
    current = []
    for ch in inner:
        if ch in ("[", "{"):
            depth += 1
            current.append(ch)
        elif ch in ("]", "}"):
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    last = "".join(current).strip()
    if last:
        items.append(last)
    return [_parse_toml_value(item) for item in items if item]


def _parse_toml_inline_table(text: str) -> dict:
    """Parse an inline TOML table like ``{key = "value"}``."""
    text = text.strip()
    if not text.startswith("{") or not text.endswith("}"):
        return {}
    inner = text[1:-1].strip()
    result: dict = {}
    if not inner:
        return result
    for pair in re.split(r",\s*", inner):
        kv = re.match(r"([A-Za-z0-9_\-]+)\s*=\s*(.+)", pair.strip())
        if kv:
            result[kv.group(1).strip()] = _parse_toml_value(kv.group(2).strip())
    return result


def _load_toml(path: Path) -> dict:
    """Load a TOML file, preferring ``tomllib`` when available."""
    try:
        import tomllib
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except ImportError:
        pass
    try:
        import tomli as _tomli
        with open(path, "rb") as fh:
            return _tomli.load(fh)
    except ImportError:
        pass
    # Fallback to minimal parser.
    return _parse_toml_simple(path.read_text(encoding="utf-8", errors="replace"))


def _merge_dependencies(
    deps: dict[str, str],
    all_deps: dict[str, str],
    framework: str,
    build_tool: str,
    pkg_manager: str,
    pyproject: dict | None,
) -> tuple[dict[str, str], str, str, str]:
    """Detect framework, build tool and package manager from dependency names."""

    # Framework detection.
    all_dep_names = {name.lower() for name in list(deps) + list(all_deps)}
    for fw_name, pattern in _FRAMEWORK_PATTERNS:
        for dep_name in all_dep_names:
            if pattern.search(dep_name):
                framework = fw_name
                break
        if framework:
            # Keep first match as the primary framework.
            break

    # Build tool from pyproject [build-system] build-backend.
    if pyproject:
        build_system = pyproject.get("build-system", {})
        backend = build_system.get("build-backend", "")
        if isinstance(backend, str) and backend in _BUILD_TOOL_MAP:
            build_tool = _BUILD_TOOL_MAP[backend]

    # Package manager.
    if pkg_manager == "":
        pkg_manager = "pip"

    return deps, framework, build_tool, pkg_manager


def detect_python_tech_stack(project_root: Path) -> TechStack:
    """Detect the Python tech stack by inspecting project metadata files."""
    deps: dict[str, str] = {}
    dev_deps: dict[str, str] = {}
    framework = ""
    build_tool = ""
    pkg_manager = ""
    pyproject_data: dict | None = None

    # --- pyproject.toml ----------------------------------------------------
    pyproject_path = project_root / "pyproject.toml"
    if pyproject_path.is_file():
        pyproject_data = _load_toml(pyproject_path)

        # [project] dependencies (PEP 621).
        project_section = pyproject_data.get("project", {})
        if isinstance(project_section, dict):
            raw_deps = project_section.get("dependencies", [])
            if isinstance(raw_deps, list):
                for dep in raw_deps:
                    name, version = _split_dep_string(dep)
                    deps[name] = version

            raw_dev_deps = project_section.get("optional-dependencies", {})
            if isinstance(raw_dev_deps, dict):
                for _group, group_deps in raw_dev_deps.items():
                    if isinstance(group_deps, list):
                        for dep in group_deps:
                            name, version = _split_dep_string(dep)
                            dev_deps[name] = version

        # [tool.poetry.dependencies]
        poetry_section = pyproject_data.get("tool", {}).get("poetry", {})
        if isinstance(poetry_section, dict):
            poetry_deps = poetry_section.get("dependencies", {})
            if isinstance(poetry_deps, dict):
                for name, ver in poetry_deps.items():
                    if name.lower() == "python":
                        continue
                    deps[name] = ver if isinstance(ver, str) else ""
            poetry_dev = poetry_section.get("dev-dependencies", {})
            if isinstance(poetry_dev, dict):
                for name, ver in poetry_dev.items():
                    dev_deps[name] = ver if isinstance(ver, str) else ""

    # --- setup.py ----------------------------------------------------------
    setup_py_path = project_root / "setup.py"
    if setup_py_path.is_file():
        setup_text = setup_py_path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(
            r"install_requires\s*=\s*\[(.*?)\]", setup_text, re.DOTALL
        ):
            for dep_m in re.finditer(r"[\"']([^\"']+)[\"']", m.group(1)):
                name, version = _split_dep_string(dep_m.group(1))
                if name and name not in deps:
                    deps[name] = version

    # --- requirements.txt --------------------------------------------------
    req_path = project_root / "requirements.txt"
    if req_path.is_file():
        for line in req_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            name, version = _split_dep_string(line)
            if name and name not in deps:
                deps[name] = version

    # --- requirements-dev.txt / requirements/dev.txt -----------------------
    for dev_name in ("requirements-dev.txt", "dev-requirements.txt",
                     "requirements/dev.txt"):
        dev_path = project_root / dev_name
        if dev_path.is_file():
            for line in dev_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                name, version = _split_dep_string(line)
                if name and name not in dev_deps:
                    dev_deps[name] = version

    # --- Detect framework / build tool / package manager -------------------
    all_dep_keys = set(deps) | set(dev_deps)
    for fw_name, pattern in _FRAMEWORK_PATTERNS:
        for dep_name in all_dep_keys:
            if pattern.search(dep_name):
                framework = fw_name
                break
        if framework:
            break

    if pyproject_data:
        build_system = pyproject_data.get("build-system", {})
        if isinstance(build_system, dict):
            backend = build_system.get("build-backend", "")
            if isinstance(backend, str) and backend in _BUILD_TOOL_MAP:
                build_tool = _BUILD_TOOL_MAP[backend]
            requires = build_system.get("requires", [])
            if isinstance(requires, list):
                for req in requires:
                    req_lower = req.lower()
                    if "poetry" in req_lower and not build_tool:
                        build_tool = "poetry"
                    elif "setuptools" in req_lower and not build_tool:
                        build_tool = "setuptools"
                    elif "hatchling" in req_lower and not build_tool:
                        build_tool = "hatch"
                    elif "flit" in req_lower and not build_tool:
                        build_tool = "flit"
                    elif "pdm" in req_lower and not build_tool:
                        build_tool = "pdm"

    # Package manager from lock files.
    for lock_name, manager in _PKG_MANAGER_FILES.items():
        if (project_root / lock_name).is_file():
            pkg_manager = manager
            break
    if not pkg_manager:
        if (project_root / "Pipfile").is_file():
            pkg_manager = "pipenv"
        elif (project_root / "setup.py").is_file() or (project_root / "requirements.txt").is_file():
            pkg_manager = "pip"
        elif pyproject_data:
            pkg_manager = "pip"

    return TechStack(
        framework=framework,
        build_tool=build_tool,
        language="Python",
        dependencies=deps,
        dev_dependencies=dev_deps,
        package_manager=pkg_manager,
    )


def _split_dep_string(dep: str) -> tuple[str, str]:
    """Split a PEP 508 dependency string into (name, version).

    Returns ``(name, version_spec)`` where *version_spec* may be empty.
    """
    dep = dep.strip()
    # Strip environment markers after ';'.
    dep = dep.split(";")[0].strip()
    # Match name up to a comparison operator or extras.
    m = re.match(r"^([A-Za-z0-9_][A-Za-z0-9._\-]*)", dep)
    if not m:
        return ("", "")
    name = m.group(1)
    rest = dep[m.end():].strip()
    # Extract version spec after operators like >=, ==, ~=, !=, etc.
    ver_match = re.match(r"^[<>=!~]+\s*([^\s,]+)", rest)
    version = ver_match.group(1) if ver_match else ""
    return (name, version)


# ---------------------------------------------------------------------------
# Entry-point detection
# ---------------------------------------------------------------------------

_ENTRY_POINT_CANDIDATES = [
    "__main__.py",
    "main.py",
    "app.py",
    "manage.py",
    "run.py",
    "server.py",
    "wsgi.py",
    "asgi.py",
]

_SRC_ENTRY_PREFIXES = ["src"]


def detect_python_entry_points(project_root: Path) -> list[str]:
    """Detect Python entry-point files for the project."""
    entry_points: list[str] = []

    # 1. Check pyproject.toml [project.scripts].
    pyproject_path = project_root / "pyproject.toml"
    if pyproject_path.is_file():
        pyproject_data = _load_toml(pyproject_path)
        scripts = pyproject_data.get("project", {}).get("scripts", {})
        if isinstance(scripts, dict):
            for _script_name, import_path in scripts.items():
                # import_path is like "mypackage.cli:main" -> resolve to file.
                module_part = import_path.split(":")[0]
                rel = module_part.replace(".", "/")
                for ext in (".py", "/__init__.py"):
                    candidate = project_root / f"{rel}{ext}"
                    if candidate.is_file():
                        try:
                            ep = str(candidate.relative_to(project_root)).replace("\\", "/")
                            if ep not in entry_points:
                                entry_points.append(ep)
                        except ValueError:
                            pass
                # Also try under src/.
                for prefix in _SRC_ENTRY_PREFIXES:
                    for ext in (".py", "/__init__.py"):
                        candidate = project_root / prefix / f"{rel}{ext}"
                        if candidate.is_file():
                            try:
                                ep = str(candidate.relative_to(project_root)).replace("\\", "/")
                                if ep not in entry_points:
                                    entry_points.append(ep)
                            except ValueError:
                                pass

    # 2. Check common file names.
    for candidate_name in _ENTRY_POINT_CANDIDATES:
        # Root level.
        candidate = project_root / candidate_name
        if candidate.is_file():
            ep = candidate_name
            if ep not in entry_points:
                entry_points.append(ep)
        # Under src/.
        for prefix in _SRC_ENTRY_PREFIXES:
            candidate = project_root / prefix / candidate_name
            if candidate.is_file():
                try:
                    ep = str(candidate.relative_to(project_root)).replace("\\", "/")
                    if ep not in entry_points:
                        entry_points.append(ep)
                except ValueError:
                    pass

    return entry_points


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_python() -> None:
    """Create a :class:`LanguageAdapter` for Python and register it."""
    adapter = LanguageAdapter(
        language_id="python",
        display_name="Python",
        extensions=(".py", ".pyi", ".pyw"),
        tree_sitter_language=_PY_LANGUAGE,
        extractor=PythonExtractor(),
        resolver=PythonImportResolver(),
        detect_tech_stack=detect_python_tech_stack,
        detect_entry_points=detect_python_entry_points,
    )
    LanguageRegistry.register(adapter)
