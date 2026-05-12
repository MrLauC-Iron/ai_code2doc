"""Layer 2 generator: module-level summary documents.

Produces one ``KnowledgeDocument`` per logical module (directory) found in
the project.  Each document describes the module's purpose, public API,
internal design, dependencies and consumers.  When *use_llm* is ``True``
the analysis is enriched via the LLM; otherwise a structural static summary
is produced.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
from ai_code2doc.config.settings import Settings
from ai_code2doc.generator.base_generator import BaseGenerator
from ai_code2doc.generator.markdown_writer import MarkdownWriter
from ai_code2doc.generator.prompt_templates import format_layer2_prompt
from ai_code2doc.llm.client import LLMClient
from ai_code2doc.models.knowledge import KnowledgeDocument
from ai_code2doc.models.module import FileInfo
from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser
from ai_code2doc.scanner.project_scanner import ProjectScanner

logger = logging.getLogger(__name__)


class Layer2ModuleGenerator(BaseGenerator):
    """Generate Layer-2 module summary knowledge documents."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._writer = MarkdownWriter()
        self._parser = TreeSitterParser()

    # ------------------------------------------------------------------
    # BaseGenerator interface
    # ------------------------------------------------------------------

    @property
    def layer_number(self) -> int:
        return 2

    @property
    def layer_name(self) -> str:
        return "module_summaries"

    async def generate(
        self,
        project_root: Path,
        output_dir: Path,
        use_llm: bool = True,
        changed_files: list[Path] | None = None,
    ) -> list[KnowledgeDocument]:
        """Parse every target file, group by module, and produce summaries.

        Returns
        -------
        list[KnowledgeDocument]
            One document per module that contains at least one source file.
        """
        project_root = project_root.resolve()

        # 0. Skip entirely when nothing changed
        if changed_files is not None and len(changed_files) == 0:
            return []

        # 1. Scan the project
        scanner = ProjectScanner(project_root)
        scan_result = scanner.scan()

        # 2. Parse target files (incremental via cache)
        from ai_code2doc.utils.parse_cache import ParseCache

        cache = ParseCache(output_dir)
        changed_set = set(changed_files) if changed_files else None
        file_infos = cache.resolve_file_infos(
            scan_result.target_files, changed_set, self._parser, project_root,
        )

        # 3. Build the dependency graph
        graph_builder = DependencyGraphBuilder(project_root)
        for fi in file_infos:
            graph_builder.add_file(fi)
        _graph = graph_builder.build()

        # 4. Group files by module (parent directory relative to root)
        module_files: dict[str, list[FileInfo]] = defaultdict(list)
        for fi in file_infos:
            module_path = str(fi.path.parent)
            if module_path == ".":
                module_path = "(root)"
            module_files[module_path].append(fi)

        # 5. Determine which modules contain changed files
        changed_dirs: set[str] | None = None
        if changed_files is not None:
            changed_dirs = set()
            for f in changed_files:
                try:
                    changed_dirs.add(str(f.relative_to(project_root).parent))
                except ValueError:
                    changed_dirs.add(str(f.parent))

        # 6. Generate a document per module
        documents: list[KnowledgeDocument] = []
        for module_path, files in module_files.items():
            # Skip modules that have no changed files
            if changed_dirs is not None and module_path not in changed_dirs:
                continue
            # Compute dependencies and dependents for the module
            # Use the first file's path as the representative for the module
            representative = str(files[0].path) if files else module_path
            deps, dependents = graph_builder.get_module_dependencies(representative)

            # Build static content
            static_content = self._build_static_module_content(
                module_path=module_path,
                files=files,
                deps=deps,
                dependents=dependents,
            )

            # Optionally enhance with LLM
            if use_llm:
                content = await self._generate_llm_content(
                    module_name=self._module_display_name(module_path),
                    module_path=module_path,
                    files=files,
                    deps=deps,
                    dependents=dependents,
                    static_content=static_content,
                )
            else:
                content = static_content

            doc = KnowledgeDocument(
                id=f"layer2-{module_path.replace('/', '-').replace(' ', '-')}",
                layer=2,
                source_path=module_path,
                title=f"Module: {self._module_display_name(module_path)}",
                content=content,
                summary=f"Module summary for {module_path} ({len(files)} files)",
                tags=["layer2", "module", self._module_display_name(module_path).lower()],
                created_at=datetime.now(),
                updated_at=datetime.now(),
                metadata={
                    "module_path": module_path,
                    "file_count": len(files),
                    "total_lines": sum(f.line_count for f in files),
                    "dependencies": deps[:20],
                    "dependents": dependents[:20],
                },
            )

            # Write to disk
            safe_name = module_path.replace("/", "_").replace("\\", "_").replace(" ", "_")
            if safe_name == "(root)":
                safe_name = "_root"
            output_path = output_dir / "layer2" / f"{safe_name}.md"
            self._writer.write_doc(output_path, doc)

            documents.append(doc)

        return documents

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _module_display_name(module_path: str) -> str:
        """Return a human-friendly name for the module."""
        if module_path == "(root)":
            return "Root"
        return module_path.replace("\\", "/").split("/")[-1] or module_path

    def _build_static_module_content(
        self,
        module_path: str,
        files: list[FileInfo],
        deps: list[str],
        dependents: list[str],
    ) -> str:
        """Build a purely static module summary in Markdown."""
        sections: list[str] = []
        display_name = self._module_display_name(module_path)

        # Purpose
        sections.append(
            f"## Module: {display_name}\n\n"
            f"Path: `{module_path}`\n\n"
            f"This module contains **{len(files)}** source file(s) with a combined "
            f"**{sum(f.line_count for f in files)}** lines of code.\n"
        )

        # Files
        file_table_rows: list[str] = ["| File | Lines | Functions | Classes | Interfaces |"]
        file_table_rows.append("|------|-------|-----------|---------|------------|")
        for fi in files:
            file_table_rows.append(
                f"| `{fi.name}` | {fi.line_count} | {len(fi.functions)} "
                f"| {len(fi.classes)} | {len(fi.interfaces)} |"
            )
        sections.append("### Files\n\n" + "\n".join(file_table_rows))

        # Public API: exported functions and classes
        api_items: list[str] = []
        for fi in files:
            for func in fi.functions:
                if func.is_exported:
                    params_str = ", ".join(func.params)
                    ret = f": {func.return_type}" if func.return_type else ""
                    async_marker = "async " if func.is_async else ""
                    api_items.append(
                        f"- `{async_marker}{func.name}({params_str}){ret}` "
                        f"({fi.name}:{func.start_line})"
                    )
            for cls in fi.classes:
                if cls.is_exported:
                    extends_str = f" extends {cls.extends}" if cls.extends else ""
                    impl_str = ""
                    if cls.implements:
                        impl_str = f" implements {', '.join(cls.implements)}"
                    api_items.append(
                        f"- `class {cls.name}{extends_str}{impl_str}` ({fi.name}:{cls.start_line})"
                    )
            for iface in fi.interfaces:
                if iface.is_exported:
                    extends_str = ""
                    if iface.extends:
                        extends_str = f" extends {', '.join(iface.extends)}"
                    api_items.append(
                        f"- `interface {iface.name}{extends_str}` ({fi.name}:{iface.start_line})"
                    )

        if api_items:
            sections.append("### Public API\n\n" + "\n".join(api_items))
        else:
            sections.append("### Public API\n\n*No explicitly exported members detected.*")

        # Internal functions (non-exported)
        internal_items: list[str] = []
        for fi in files:
            for func in fi.functions:
                if not func.is_exported:
                    params_str = ", ".join(func.params)
                    async_marker = "async " if func.is_async else ""
                    internal_items.append(
                        f"- `{async_marker}{func.name}({params_str})` ({fi.name}:{func.start_line})"
                    )
        if internal_items:
            sections.append(
                "### Internal Functions\n\n" + "\n".join(internal_items[:30])
            )

        # Internal classes (non-exported)
        internal_classes: list[str] = []
        for fi in files:
            for cls in fi.classes:
                if not cls.is_exported:
                    internal_classes.append(
                        f"- `class {cls.name}` ({fi.name}:{cls.start_line})"
                    )
        if internal_classes:
            sections.append("### Internal Classes\n\n" + "\n".join(internal_classes[:20]))

        # Dependencies
        if deps:
            dep_lines = [f"- `{d}`" for d in deps[:20]]
            sections.append("### Dependencies\n\n" + "\n".join(dep_lines))
        else:
            sections.append("### Dependencies\n\n*No internal dependencies detected.*")

        # Dependents
        if dependents:
            dep_lines = [f"- `{d}`" for d in dependents[:20]]
            sections.append("### Dependents\n\n" + "\n".join(dep_lines))
        else:
            sections.append("### Dependents\n\n*No internal dependents detected.*")

        # Imports summary
        all_imports: list[str] = []
        for fi in files:
            for imp in fi.imports:
                specifiers = ", ".join(imp.specifiers) if imp.specifiers else "*"
                all_imports.append(f"- `{specifiers}` from `{imp.source}` ({fi.name})")
        if all_imports:
            sections.append("### Imports\n\n" + "\n".join(all_imports[:30]))

        return "\n\n".join(sections)

    def _build_file_summaries_text(self, files: list[FileInfo]) -> str:
        """Build a text summary of all files for use in LLM prompts."""
        parts: list[str] = []
        for fi in files:
            lines: list[str] = [f"#### {fi.name} ({fi.line_count} lines)"]

            if fi.functions:
                fn_names = [f.name for f in fi.functions]
                lines.append(f"Functions: {', '.join(fn_names)}")
            if fi.classes:
                cls_names = [f.name for f in fi.classes]
                lines.append(f"Classes: {', '.join(cls_names)}")
            if fi.interfaces:
                iface_names = [f.name for f in fi.interfaces]
                lines.append(f"Interfaces: {', '.join(iface_names)}")
            if fi.exports:
                lines.append(f"Exports: {', '.join(fi.exports)}")
            if fi.imports:
                imp_sources = [f.source for f in fi.imports]
                lines.append(f"Imports from: {', '.join(imp_sources)}")

            parts.append("\n".join(lines))

        return "\n\n".join(parts)

    async def _generate_llm_content(
        self,
        module_name: str,
        module_path: str,
        files: list[FileInfo],
        deps: list[str],
        dependents: list[str],
        static_content: str,
    ) -> str:
        """Call the LLM to produce a module summary, falling back to static."""
        file_summaries = self._build_file_summaries_text(files)
        deps_str = ", ".join(deps) if deps else "None"
        dependents_str = ", ".join(dependents) if dependents else "None"

        prompt = format_layer2_prompt(
            module_name=module_name,
            module_path=module_path,
            file_summaries=file_summaries,
            dependencies=deps_str,
            dependents=dependents_str,
        )

        try:
            client = LLMClient(settings=self._settings)
            response = await client.agenerate(prompt=prompt)
            return response.content
        except Exception as exc:
            logger.warning("LLM generation failed for module %s: %s", module_path, exc)
            return (
                f"<!-- LLM generation failed: {exc} -->\n\n"
                f"{static_content}"
            )
