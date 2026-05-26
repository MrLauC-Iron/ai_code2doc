"""Symbol registry that indexes all function/class definitions for call resolution."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from ai_code2doc.models.graph import CallSite, SymbolDefinition
from ai_code2doc.models.module import FileInfo

if TYPE_CHECKING:
    from ai_code2doc.analyzer.type_inferrer import TypeScope


class SymbolRegistry:
    """Central index of symbol definitions with lookup and call-site resolution.

    Maintains multiple indexes (by FQN, by name, by file) and an import map so
    that :class:`CallSite` objects extracted by call extractors can be resolved
    to concrete :class:`SymbolDefinition` targets.
    """

    def __init__(self) -> None:
        self._by_fqn: dict[str, SymbolDefinition] = {}
        self._by_name: dict[str, list[SymbolDefinition]] = defaultdict(list)
        self._by_file: dict[str, list[SymbolDefinition]] = defaultdict(list)
        # import_map: file_path -> { local_name: resolved_module }
        self._import_map: dict[str, dict[str, str]] = defaultdict(dict)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def add(self, sym: SymbolDefinition) -> None:
        """Add a symbol definition to all internal indexes."""
        self._by_fqn[sym.fqn] = sym
        self._by_name[sym.name].append(sym)
        self._by_file[sym.file_path].append(sym)

    def add_import(self, file_path: str, local_name: str, resolved_module: str) -> None:
        """Record that *local_name* in *file_path* resolves to *resolved_module*."""
        self._import_map[file_path][local_name] = resolved_module

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def get_by_fqn(self, fqn: str) -> SymbolDefinition | None:
        """Return the symbol with the given fully-qualified name, or ``None``."""
        return self._by_fqn.get(fqn)

    def get_by_name(self, name: str) -> list[SymbolDefinition]:
        """Return all symbols that match *name* (may be ambiguous)."""
        return list(self._by_name.get(name, []))

    def get_unique(self, name: str) -> SymbolDefinition | None:
        """Return the symbol for *name* only if there is exactly one match."""
        matches = self._by_name.get(name, [])
        if len(matches) == 1:
            return matches[0]
        return None

    def get_by_file(self, file_path: str) -> list[SymbolDefinition]:
        """Return all symbols defined in *file_path*."""
        return list(self._by_file.get(file_path, []))

    def resolve_import(self, file_path: str, local_name: str) -> str | None:
        """Look up an imported name in the import map for *file_path*."""
        return self._import_map.get(file_path, {}).get(local_name)

    # ------------------------------------------------------------------
    # Bulk loading from FileInfo
    # ------------------------------------------------------------------

    def add_from_file_info(self, fi: FileInfo) -> None:
        """Extract definitions and imports from a :class:`FileInfo` and index them.

        For each function the FQN is ``{file_path}::{func.name}``.
        For each class the FQN is ``{file_path}::{cls.name}`` and each method
        gets ``{file_path}::{cls.name}.{method.name}``.
        """
        file_path_str = str(fi.path).replace("\\", "/")

        for func in fi.functions:
            self.add(
                SymbolDefinition(
                    fqn=f"{file_path_str}::{func.name}",
                    name=func.name,
                    file_path=file_path_str,
                    start_line=func.start_line,
                    end_line=func.end_line,
                    kind="function",
                    is_exported=func.is_exported,
                )
            )

        for cls in fi.classes:
            self.add(
                SymbolDefinition(
                    fqn=f"{file_path_str}::{cls.name}",
                    name=cls.name,
                    file_path=file_path_str,
                    start_line=cls.start_line,
                    end_line=cls.end_line,
                    kind="class",
                    is_exported=cls.is_exported,
                )
            )
            for method in cls.methods:
                self.add(
                    SymbolDefinition(
                        fqn=f"{file_path_str}::{cls.name}.{method.name}",
                        name=method.name,
                        file_path=file_path_str,
                        start_line=method.start_line,
                        end_line=method.end_line,
                        kind="method",
                        is_exported=method.is_exported,
                    )
                )

        # Build import map from FileInfo's imports list.
        for imp in fi.imports:
            if imp.specifiers:
                # ``from X import a, b`` — map each specifier.
                for spec in imp.specifiers:
                    # Handle aliased imports: ``from X import a as b``
                    local = spec
                    resolved = imp.source
                    if " as " in spec:
                        parts = spec.split(" as ", 1)
                        local = parts[1].strip()
                    self.add_import(file_path_str, local, resolved)
            else:
                # ``import X`` — map the module name to its source.
                self.add_import(file_path_str, imp.source, imp.source)

    # ------------------------------------------------------------------
    # Module-path conversion
    # ------------------------------------------------------------------

    def _resolve_module_to_file(self, module_dotted: str) -> list[str]:
        """Convert a dotted module name to possible file paths.

        Examples:
            "ai_code2doc.scanner.project_scanner"
            -> ["ai_code2doc/scanner/project_scanner.py",
                "ai_code2doc/scanner/project_scanner/__init__.py",
                "src/ai_code2doc/scanner/project_scanner.py",
                "src/ai_code2doc/scanner/project_scanner/__init__.py"]

            "src/helpers.py"
            -> ["src/helpers.py", "src/helpers.py/__init__.py"]

        Always includes the original value as the first candidate so that
        import maps that already store file paths continue to work.
        """
        candidates: list[str] = []
        # Include the original value as-is (handles file-path imports).
        candidates.append(module_dotted)
        parts = module_dotted.split(".")
        if len(parts) > 1:
            # Try as a file path: a.b.c -> a/b/c.py
            file_path = "/".join(parts) + ".py"
            if file_path not in candidates:
                candidates.append(file_path)
            # Try as a package directory: a.b.c -> a/b/c/__init__.py
            init_path = "/".join(parts) + "/__init__.py"
            candidates.append(init_path)
            # Also try with "src/" prefix for project modules.
            src_file = "src/" + file_path
            if src_file not in candidates:
                candidates.append(src_file)
            src_init = "src/" + init_path
            candidates.append(src_init)
        return candidates

    # ------------------------------------------------------------------
    # Call-site resolution (5-strategy cascade)
    # ------------------------------------------------------------------

    def resolve_call_site(
        self,
        site: CallSite,
        caller_file: str,
        type_scope: TypeScope | None = None,
    ) -> CallSite:
        """Resolve a :class:`CallSite` using a 6-strategy cascade.

        Resolution strategies (in priority order):

        0. **Type-scope-aware** -- use inferred variable types (confidence 0.80-0.90)
        1. **self.X / cls.X** -- method on the same class (confidence 0.95)
        2. **obj.method()** -- look up method on a known class (confidence 0.85-0.90)
        3. **module.func()** -- import-map resolution (confidence 0.95)
        4. **Same-file lookup** (confidence 0.90)
        5. **Unique name project-wide** (confidence 0.75)

        If no strategy matches the fallback is unresolved (confidence 0.30).
        """
        callee_name = site.callee_name

        # --- Strategy 0: Type-scope-aware resolution --------------------
        if type_scope is not None and "." in callee_name:
            obj_name, method_name = callee_name.split(".", 1)
            inferred_type = type_scope.lookup(obj_name)
            if inferred_type is not None:
                # Look up the inferred type in the symbol registry
                type_syms = self.get_by_name(inferred_type)
                for sym in type_syms:
                    if sym.kind == "class":
                        target_fqn = f"{sym.fqn}.{method_name}"
                        method_sym = self.get_by_fqn(target_fqn)
                        if method_sym is not None:
                            return site.model_copy(
                                update={"callee_fqn": method_sym.fqn, "confidence": 0.90}
                            )
                    elif sym.kind == "function":
                        # type is actually a function, not a class
                        if method_name == sym.name:
                            return site.model_copy(
                                update={"callee_fqn": sym.fqn, "confidence": 0.85}
                            )
                # Also try: the inferred type IS a class and callee is its constructor
                for sym in type_syms:
                    if sym.kind == "class" and sym.name == method_name:
                        return site.model_copy(
                            update={"callee_fqn": sym.fqn, "confidence": 0.80}
                        )

        # --- Strategy 1: self.X / cls.X --------------------------------
        if callee_name.startswith("self.") or callee_name.startswith("cls."):
            prefix = "self." if callee_name.startswith("self.") else "cls."
            method_name = callee_name[len(prefix):]
            # Derive the class FQN from the caller's FQN.
            caller_fqn = site.caller_fqn
            # The caller_fqn is like "a.py::MyClass.process"; extract class part.
            # Handle both method and class-level callers.
            if "::" in caller_fqn:
                parts = caller_fqn.split("::", 1)
                file_part = parts[0]
                member_part = parts[1]
                # If caller is a method, get the class prefix.
                if "." in member_part:
                    class_name = member_part.rsplit(".", 1)[0]
                else:
                    class_name = member_part  # caller is the class itself
                target_fqn = f"{file_part}::{class_name}.{method_name}"
                sym = self.get_by_fqn(target_fqn)
                if sym is not None:
                    return site.model_copy(
                        update={"callee_fqn": sym.fqn, "confidence": 0.95}
                    )

        # --- Strategy 2: obj.method() -----------------------------------
        if "." in callee_name and not callee_name.startswith("self.") and not callee_name.startswith("cls."):
            obj_name, method_name = callee_name.split(".", 1)
            # Check if obj_name is a known class name in the same file.
            file_syms = self.get_by_file(caller_file)
            for sym in file_syms:
                if sym.kind == "class" and sym.name == obj_name:
                    target_fqn = f"{sym.fqn}.{method_name}"
                    method_sym = self.get_by_fqn(target_fqn)
                    if method_sym is not None:
                        return site.model_copy(
                            update={"callee_fqn": method_sym.fqn, "confidence": 0.85}
                        )
            # Try lookup by name across the project.
            class_matches = self.get_by_name(obj_name)
            if len(class_matches) == 1:
                sym = class_matches[0]
                target_fqn = f"{sym.fqn}.{method_name}"
                method_sym = self.get_by_fqn(target_fqn)
                if method_sym is not None:
                    return site.model_copy(
                        update={"callee_fqn": method_sym.fqn, "confidence": 0.90}
                    )

        # --- Strategy 3: module.func() via import map --------------------
        if "." in callee_name:
            maybe_module, maybe_func = callee_name.split(".", 1)
            resolved = self.resolve_import(caller_file, maybe_module)
            if resolved is not None:
                # Convert dotted module to file paths and search each
                for candidate_path in self._resolve_module_to_file(resolved):
                    target_fqn = f"{candidate_path}::{maybe_func}"
                    sym = self.get_by_fqn(target_fqn)
                    if sym is not None:
                        return site.model_copy(
                            update={"callee_fqn": sym.fqn, "confidence": 0.95}
                        )
                # Also try: maybe_func is a class imported directly
                for sym in self.get_by_name(maybe_func):
                    if sym.file_path.endswith(
                        "/__init__.py"
                    ) or sym.file_path.replace("/", ".").startswith(resolved):
                        return site.model_copy(
                            update={"callee_fqn": sym.fqn, "confidence": 0.85}
                        )
        # Try direct import map lookup for the full callee_name.
        resolved_module = self.resolve_import(caller_file, callee_name)
        if resolved_module is not None:
            # The import resolves to a module; look for the function inside it.
            # If callee_name was the local alias, the resolved module is the target.
            # Try to find a symbol whose FQN starts with the resolved module.
            for sym in self.get_by_name(callee_name):
                if sym.file_path.startswith(resolved_module) or resolved_module in sym.fqn:
                    return site.model_copy(
                        update={"callee_fqn": sym.fqn, "confidence": 0.95}
                    )

        # --- Strategy 4: Same-file lookup --------------------------------
        file_syms = self.get_by_file(caller_file)
        for sym in file_syms:
            if sym.name == callee_name:
                return site.model_copy(
                    update={"callee_fqn": sym.fqn, "confidence": 0.90}
                )

        # --- Strategy 5: Unique name project-wide ------------------------
        unique = self.get_unique(callee_name)
        if unique is not None:
            return site.model_copy(
                update={"callee_fqn": unique.fqn, "confidence": 0.75}
            )

        # --- Fallback: unresolved ----------------------------------------
        return site.model_copy(
            update={"callee_fqn": None, "confidence": 0.30}
        )
