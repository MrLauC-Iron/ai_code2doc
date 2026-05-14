"""Layer 1 generator: project-level overview document.

Produces a single ``KnowledgeDocument`` that summarises the entire project
from a high-level architectural perspective.  When *use_llm* is ``True`` the
static analysis data is sent to the configured LLM for a richer narrative;
otherwise a purely structural markdown document is generated.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ai_code2doc.analyzer.tech_stack import TechStackDetector
from ai_code2doc.analyzer.metrics import MetricsCalculator
from ai_code2doc.config.settings import Settings
from ai_code2doc.generator.base_generator import BaseGenerator
from ai_code2doc.generator.markdown_writer import MarkdownWriter
from ai_code2doc.generator.prompt_templates import format_layer1_prompt
from ai_code2doc.llm.client import LLMClient
from ai_code2doc.models.knowledge import KnowledgeDocument
from ai_code2doc.scanner.project_scanner import ProjectScanner

if TYPE_CHECKING:
    from ai_code2doc.models.build import CMakeProjectInfo


class Layer1OverviewGenerator(BaseGenerator):
    """Generate the Layer-1 project overview knowledge document."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._writer = MarkdownWriter()

    # ------------------------------------------------------------------
    # BaseGenerator interface
    # ------------------------------------------------------------------

    @property
    def layer_number(self) -> int:
        return 1

    @property
    def layer_name(self) -> str:
        return "project_overview"

    async def generate(
        self,
        project_root: Path,
        output_dir: Path,
        use_llm: bool = True,
        changed_files: list[Path] | None = None,
    ) -> list[KnowledgeDocument]:
        """Analyse the project and produce the overview document.

        Returns
        -------
        list[KnowledgeDocument]
            A single-element list containing the project overview document.
        """
        project_root = project_root.resolve()

        # 0. Skip entirely when nothing changed
        if changed_files is not None and len(changed_files) == 0:
            return []

        # 1. Scan the project files
        scanner = ProjectScanner(project_root)
        scan_result = scanner.scan()

        # 2. Parse CMake build info if available
        cmake_info: CMakeProjectInfo | None = None
        if (project_root / "CMakeLists.txt").is_file():
            from ai_code2doc.parser.build.cmake_parser import CMakeParser
            cmake_info = CMakeParser().parse(project_root)

        # 3. Detect the technology stack
        detector = TechStackDetector(project_root, cmake_info=cmake_info)
        tech_stack = detector.detect()
        entry_points = detector.detect_entry_points()

        # 3. Compute basic metrics
        calculator = MetricsCalculator()
        file_metrics_list = []
        for fp in scan_result.target_files:
            try:
                fm = calculator.compute_file_metrics(fp)
                file_metrics_list.append(fm)
            except Exception:
                continue
        project_metrics = calculator.compute_project_metrics(file_metrics_list)

        # 4. Build the directory tree string
        directory_tree = self._build_directory_tree(scan_result)

        # 5. Gather key file summaries (top-level + entry points)
        key_files = self._summarize_key_files(scan_result, entry_points, project_root)

        # 6. Format the tech stack as a human-readable string
        tech_stack_str = self._format_tech_stack(tech_stack, cmake_info)

        # 7. Build the prompt / static content
        if use_llm:
            content = await self._generate_llm_content(
                project_root=project_root,
                project_name=project_root.name,
                tech_stack=tech_stack_str,
                directory_tree=directory_tree,
                entry_points=", ".join(entry_points) if entry_points else "N/A",
                key_files=key_files,
            )
        else:
            content = self._build_static_content(
                project_name=project_root.name,
                tech_stack=tech_stack,
                tech_stack_str=tech_stack_str,
                directory_tree=directory_tree,
                entry_points=entry_points,
                key_files=key_files,
                project_metrics=project_metrics,
                cmake_info=cmake_info,
            )

        # 8. Assemble the knowledge document
        doc = KnowledgeDocument(
            id=f"layer1-{project_root.name}-overview",
            layer=1,
            source_path=str(project_root),
            title=f"Project Overview: {project_root.name}",
            content=content,
            summary=f"High-level overview of {project_root.name} ({tech_stack.framework}/{tech_stack.language})",
            tags=["layer1", "overview", tech_stack.framework.lower(), tech_stack.language.lower()],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={
                "total_files": project_metrics.total_files,
                "total_lines": project_metrics.total_lines,
                "framework": tech_stack.framework,
                "language": tech_stack.language,
                "build_tool": tech_stack.build_tool,
                "entry_points": entry_points,
            },
        )

        # 9. Write to disk
        output_path = output_dir / "layer1" / "README.md"
        self._writer.write_doc(output_path, doc)

        return [doc]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_directory_tree(self, scan_result: Any, max_depth: int = 4) -> str:
        """Build a textual directory tree from the scan result.

        Parameters
        ----------
        scan_result:
            A :class:`ScanResult` from :class:`ProjectScanner`.
        max_depth:
            Maximum directory depth to render.
        """
        root = scan_result.root
        lines: list[str] = [root.name + "/"]

        # Collect directories and files sorted by path
        dir_set: set[Path] = set()
        for d in scan_result.directories:
            try:
                rel = d.relative_to(root)
                dir_set.add(rel)
            except ValueError:
                continue

        file_dirs: set[Path] = set()
        for f in scan_result.target_files:
            try:
                rel = f.relative_to(root)
                file_dirs.add(rel)
            except ValueError:
                continue

        # Build a simple tree representation
        all_paths = sorted(dir_set | file_dirs)
        for rel_path in all_paths:
            parts = rel_path.parts
            if len(parts) > max_depth:
                continue
            indent = "    " * (len(parts) - 1)
            name = parts[-1]
            if rel_path in dir_set:
                lines.append(f"{indent}{name}/")
            else:
                lines.append(f"{indent}{name}")

        return "\n".join(lines[:200])  # cap to avoid huge prompts

    def _summarize_key_files(
        self,
        scan_result: Any,
        entry_points: list[str],
        project_root: Path,
        max_files: int = 10,
    ) -> str:
        """Return a short text summary of the most important files.

        Prioritises entry points and then top-level source files.
        """
        summaries: list[str] = []
        seen: set[str] = set()

        # Entry points first
        for ep in entry_points[:5]:
            ep_path = project_root / ep
            if ep_path.exists() and ep not in seen:
                seen.add(ep)
                try:
                    content = ep_path.read_text(encoding="utf-8", errors="replace")
                    first_lines = "\n".join(content.split("\n")[:15])
                    summaries.append(f"### {ep}\n```\n{first_lines}\n```")
                except Exception:
                    summaries.append(f"### {ep}\n*(could not read file)*")

        # Top-level source files
        for fp in scan_result.target_files:
            if len(summaries) >= max_files:
                break
            try:
                rel = str(fp.relative_to(project_root))
            except ValueError:
                continue
            if rel in seen:
                continue
            depth = rel.count("/")
            if depth <= 1:
                seen.add(rel)
                try:
                    content = fp.read_text(encoding="utf-8", errors="replace")
                    first_lines = "\n".join(content.split("\n")[:10])
                    summaries.append(f"### {rel}\n```\n{first_lines}\n```")
                except Exception:
                    summaries.append(f"### {rel}\n*(could not read file)*")

        return "\n\n".join(summaries) if summaries else "No key files identified."

    @staticmethod
    def _format_tech_stack(
        tech_stack: Any,
        cmake_info: CMakeProjectInfo | None = None,
    ) -> str:
        """Return a human-readable description of the tech stack."""
        parts = [
            f"Language: {tech_stack.language}",
            f"Framework: {tech_stack.framework}",
            f"Build Tool: {tech_stack.build_tool}",
            f"Package Manager: {tech_stack.package_manager}",
        ]
        if cmake_info and cmake_info.cmake_version:
            parts.append(f"CMake Version: {cmake_info.cmake_version}")
        if tech_stack.dependencies:
            dep_names = list(tech_stack.dependencies.keys())[:20]
            parts.append(f"Key Dependencies: {', '.join(dep_names)}")
        return "\n".join(parts)

    async def _generate_llm_content(
        self,
        project_root: Path,
        project_name: str,
        tech_stack: str,
        directory_tree: str,
        entry_points: str,
        key_files: str,
    ) -> str:
        """Call the LLM to produce a narrative project overview."""
        prompt = format_layer1_prompt(
            project_name=project_name,
            tech_stack=tech_stack,
            directory_tree=directory_tree,
            entry_points=entry_points,
            key_files=key_files,
        )
        try:
            client = LLMClient(settings=self._settings)
            response = await client.agenerate(prompt=prompt)
            return response.content
        except Exception as exc:
            # Fall back to static content if LLM fails
            return (
                f"<!-- LLM generation failed: {exc} -->\n\n"
                "## Project Overview (static fallback)\n\n"
                f"- **Project**: {project_name}\n"
                f"- **Tech Stack**: {tech_stack}\n"
                f"- **Entry Points**: {entry_points}\n"
            )

    def _build_static_content(
        self,
        project_name: str,
        tech_stack: Any,
        tech_stack_str: str,
        directory_tree: str,
        entry_points: list[str],
        key_files: str,
        project_metrics: Any,
        cmake_info: CMakeProjectInfo | None = None,
    ) -> str:
        """Build a purely static overview document without LLM assistance."""
        sections: list[str] = []

        # Purpose
        sections.append(
            "## Purpose\n\n"
            f"**{project_name}** is a software project built with "
            f"{tech_stack.language} using the {tech_stack.framework} framework.\n"
        )

        # Technology Stack
        tech_rows = [
            f"| Language | {tech_stack.language} |",
            f"| Framework | {tech_stack.framework} |",
            f"| Build Tool | {tech_stack.build_tool} |",
            f"| Package Manager | {tech_stack.package_manager} |",
        ]
        if cmake_info and cmake_info.cmake_version:
            tech_rows.append(f"| CMake Version | {cmake_info.cmake_version} |")

        sections.append(
            "## Technology Stack\n\n"
            "| Attribute | Value |\n"
            "|---|---|\n"
            + "\n".join(tech_rows)
        )

        # CMake Build Targets
        if cmake_info and cmake_info.targets:
            target_rows = [
                "| Target | Type | Sources |",
                "|--------|------|---------|",
            ]
            for name, target in cmake_info.targets.items():
                srcs = ", ".join(Path(s).name for s in target.sources[:5])
                if len(target.sources) > 5:
                    srcs += f" (+{len(target.sources) - 5} more)"
                target_rows.append(f"| `{name}` | {target.target_type} | {srcs} |")
            sections.append(
                "## Build Targets\n\n"
                + "\n".join(target_rows)
            )

        if tech_stack.dependencies:
            dep_lines = []
            for name, version in list(tech_stack.dependencies.items())[:20]:
                dep_lines.append(f"| {name} | {version} |")
            sections.append(
                "### Dependencies\n\n"
                "| Package | Version |\n|---|---|\n"
                + "\n".join(dep_lines)
            )

        # Project Metrics
        sections.append(
            "## Project Metrics\n\n"
            f"| Metric | Value |\n"
            f"|---|---|\n"
            f"| Total Files | {project_metrics.total_files} |\n"
            f"| Total Lines | {project_metrics.total_lines} |\n"
            f"| Code Lines | {project_metrics.total_code_lines} |\n"
            f"| Comment Lines | {project_metrics.total_comment_lines} |\n"
            f"| Blank Lines | {project_metrics.total_blank_lines} |\n"
        )

        # Entry Points
        ep_str = "\n".join(f"- `{ep}`" for ep in entry_points) if entry_points else "- N/A"
        sections.append(f"## Entry Points\n\n{ep_str}")

        # Directory Structure
        sections.append(
            "## Directory Structure\n\n"
            "```\n"
            f"{directory_tree}\n"
            "```\n"
        )

        # Key Files
        sections.append(f"## Key Files\n\n{key_files}")

        return "\n\n".join(sections)
