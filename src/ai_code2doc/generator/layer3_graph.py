"""Layer 3 generator: dependency graph analysis document.

Produces a single ``KnowledgeDocument`` that describes the full dependency
graph of the project, including a Mermaid diagram, detected cycles, impact
analysis for critical modules, and coupling metrics.  When *use_llm* is
``True`` the raw graph data is sent to the LLM for a richer narrative.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
from ai_code2doc.analyzer.metrics import MetricsCalculator
from ai_code2doc.config.settings import Settings
from ai_code2doc.generator.base_generator import BaseGenerator
from ai_code2doc.generator.markdown_writer import MarkdownWriter
from ai_code2doc.generator.prompt_templates import format_layer3_prompt
from ai_code2doc.llm.client import LLMClient
from ai_code2doc.models.knowledge import KnowledgeDocument
from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser
from ai_code2doc.scanner.project_scanner import ProjectScanner

logger = logging.getLogger(__name__)


class Layer3GraphGenerator(BaseGenerator):
    """Generate the Layer-3 dependency graph knowledge document."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._writer = MarkdownWriter()
        self._parser = TreeSitterParser()

    # ------------------------------------------------------------------
    # BaseGenerator interface
    # ------------------------------------------------------------------

    @property
    def layer_number(self) -> int:
        return 3

    @property
    def layer_name(self) -> str:
        return "dependency_graph"

    async def generate(
        self,
        project_root: Path,
        output_dir: Path,
        use_llm: bool = True,
        changed_files: list[Path] | None = None,
    ) -> list[KnowledgeDocument]:
        """Build the full dependency graph and produce the analysis document.

        Returns
        -------
        list[KnowledgeDocument]
            A single-element list containing the dependency graph document.
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
        graph = graph_builder.build()

        # 4. Compute structural metrics
        calculator = MetricsCalculator()
        file_metrics_list = []
        for fi in file_infos:
            file_metrics_list.append(calculator.compute_file_metrics_from_info(fi))
        project_metrics = calculator.compute_project_metrics(file_metrics_list)

        # 5. Graph-level metrics
        node_count = graph.number_of_nodes()
        edge_count = graph.number_of_edges()

        # Degree distribution for coupling analysis
        in_degrees = dict(graph.in_degree())
        out_degrees = dict(graph.out_degree())

        # Top coupled modules by in-degree (most depended upon)
        most_depended = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)[:10]
        # Top coupling modules by out-degree (most dependencies)
        most_coupled = sorted(out_degrees.items(), key=lambda x: x[1], reverse=True)[:10]

        # 6. Detect cycles
        cycles = graph_builder.detect_cycles()

        # 7. Impact analysis for the most-depended-upon modules
        impacts = []
        for node, _ in most_depended[:5]:
            impact = graph_builder.compute_impact(node)
            impacts.append(impact)

        # 8. Generate Mermaid diagram
        mermaid_graph = graph_builder.to_mermaid()

        # 9. Compute graph-level metrics text
        metrics_text = self._format_metrics(
            node_count=node_count,
            edge_count=edge_count,
            most_depended=most_depended,
            most_coupled=most_coupled,
            cycles=cycles,
            impacts=impacts,
            project_metrics=project_metrics,
        )

        # 10. Format cycles text
        cycles_text = self._format_cycles(cycles)

        # 11. Build content (LLM or static)
        if use_llm:
            content = await self._generate_llm_content(
                mermaid_graph=mermaid_graph,
                cycles_text=cycles_text,
                metrics_text=metrics_text,
            )
        else:
            content = self._build_static_content(
                mermaid_graph=mermaid_graph,
                cycles=cycles,
                cycles_text=cycles_text,
                most_depended=most_depended,
                most_coupled=most_coupled,
                impacts=impacts,
                node_count=node_count,
                edge_count=edge_count,
                metrics_text=metrics_text,
            )

        # 12. Assemble the knowledge document
        doc = KnowledgeDocument(
            id="layer3-dependency-graph",
            layer=3,
            source_path=str(project_root),
            title="Dependency Graph Analysis",
            content=content,
            summary=(
                f"Dependency graph with {node_count} nodes, {edge_count} edges, "
                f"{len(cycles)} cycle(s) detected."
            ),
            tags=["layer3", "dependency-graph", "architecture"],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={
                "node_count": node_count,
                "edge_count": edge_count,
                "cycle_count": len(cycles),
                "most_depended": [(n, d) for n, d in most_depended[:5]],
                "most_coupled": [(n, d) for n, d in most_coupled[:5]],
            },
        )

        # 13. Write to disk
        output_path = output_dir / "layer3" / "dependency-graph.md"
        self._writer.write_doc(output_path, doc)

        # Also write the raw Mermaid diagram as a separate file
        mermaid_path = output_dir / "layer3" / "dependency-graph.mmd"
        self._writer.write_raw(mermaid_path, mermaid_graph)

        return [doc]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_cycles(cycles: list) -> str:
        """Format cycle information as readable text."""
        if not cycles:
            return "No circular dependencies detected."
        parts: list[str] = []
        for i, cycle in enumerate(cycles, 1):
            parts.append(f"{i}. {' -> '.join(cycle.nodes)} -> {cycle.nodes[0]}")
        return "\n".join(parts)

    @staticmethod
    def _format_metrics(
        node_count: int,
        edge_count: int,
        most_depended: list[tuple[str, int]],
        most_coupled: list[tuple[str, int]],
        cycles: list,
        impacts: list,
        project_metrics: object,
    ) -> str:
        """Format graph metrics as readable text for LLM prompts."""
        parts: list[str] = [
            f"Nodes (files): {node_count}",
            f"Edges (imports): {edge_count}",
            f"Cycles: {len(cycles)}",
            "",
            "Most depended-upon modules:",
        ]
        for node, degree in most_depended:
            parts.append(f"  - {node} (in-degree: {degree})")

        parts.append("")
        parts.append("Most coupled modules (most dependencies):")
        for node, degree in most_coupled:
            parts.append(f"  - {node} (out-degree: {degree})")

        if impacts:
            parts.append("")
            parts.append("Impact analysis (top modules):")
            for impact in impacts:
                parts.append(
                    f"  - Changing {impact.change_target} affects "
                    f"{len(impact.affected_modules)} module(s), "
                    f"risk: {impact.risk_level}"
                )

        parts.append("")
        parts.append(
            f"Total project files: {project_metrics.total_files}, "
            f"total lines: {project_metrics.total_lines}"
        )

        return "\n".join(parts)

    def _build_static_content(
        self,
        mermaid_graph: str,
        cycles: list,
        cycles_text: str,
        most_depended: list[tuple[str, int]],
        most_coupled: list[tuple[str, int]],
        impacts: list,
        node_count: int,
        edge_count: int,
        metrics_text: str,
    ) -> str:
        """Build a purely static dependency graph analysis document."""
        sections: list[str] = []

        # Overview
        sections.append(
            "## Dependency Graph Overview\n\n"
            f"The project's dependency graph contains **{node_count}** nodes "
            f"(source files) and **{edge_count}** edges (import relationships).\n"
        )

        # Mermaid diagram
        if mermaid_graph.strip():
            sections.append(
                "## Dependency Diagram\n\n"
                "```mermaid\n"
                f"{mermaid_graph}\n"
                "```\n"
            )

        # Coupling analysis
        if most_depended:
            rows = ["| Module | In-Degree |", "|--------|-----------|"]
            for node, degree in most_depended:
                rows.append(f"| `{node}` | {degree} |")
            sections.append(
                "### Most Depended-Upon Modules\n\n"
                "These modules are imported by the most other files:\n\n"
                + "\n".join(rows)
            )

        if most_coupled:
            rows = ["| Module | Out-Degree |", "|--------|------------|"]
            for node, degree in most_coupled:
                rows.append(f"| `{node}` | {degree} |")
            sections.append(
                "### Most Coupled Modules\n\n"
                "These modules have the most import dependencies:\n\n"
                + "\n".join(rows)
            )

        # Cycles
        if cycles:
            cycle_lines: list[str] = []
            for i, cycle in enumerate(cycles, 1):
                cycle_lines.append(f"{i}. `{' -> '.join(cycle.nodes)} -> {cycle.nodes[0]}`")
            sections.append(
                "### Circular Dependencies\n\n"
                f"**{len(cycles)}** circular dependency chain(s) detected:\n\n"
                + "\n".join(cycle_lines)
            )
        else:
            sections.append(
                "### Circular Dependencies\n\n"
                "No circular dependencies detected. The import graph is acyclic."
            )

        # Impact analysis
        if impacts:
            impact_lines: list[str] = []
            for impact in impacts:
                risk_emoji = {"low": "low", "medium": "medium", "high": "high"}
                risk_label = risk_emoji.get(impact.risk_level, impact.risk_level)
                affected_str = ", ".join(
                    f"`{a}`" for a in impact.affected_modules[:5]
                )
                if len(impact.affected_modules) > 5:
                    affected_str += f", ... (+{len(impact.affected_modules) - 5} more)"
                impact_lines.append(
                    f"- **`{impact.change_target}`** - risk: *{risk_label}* - "
                    f"affects: {affected_str or 'none'}"
                )
            sections.append(
                "### Impact Analysis\n\n"
                "Risk assessment for changes to the most-depended-upon modules:\n\n"
                + "\n".join(impact_lines)
            )

        # Metrics summary
        sections.append("### Metrics Summary\n\n```\n" + metrics_text + "\n```")

        return "\n\n".join(sections)

    async def _generate_llm_content(
        self,
        mermaid_graph: str,
        cycles_text: str,
        metrics_text: str,
    ) -> str:
        """Call the LLM to produce a dependency analysis narrative."""
        prompt = format_layer3_prompt(
            mermaid_graph=mermaid_graph,
            cycles=cycles_text,
            metrics=metrics_text,
        )
        try:
            client = LLMClient(settings=self._settings)
            response = await client.agenerate(prompt=prompt)
            return response.content
        except Exception as exc:
            logger.warning("LLM generation failed for layer 3: %s", exc)
            return (
                f"<!-- LLM generation failed: {exc} -->\n\n"
                "## Dependency Graph Analysis (static fallback)\n\n"
                "```\n"
                f"{metrics_text}\n"
                "```\n"
            )
