"""Layer 3 generator: dependency graph analysis document.

Produces a single ``KnowledgeDocument`` that describes the full dependency
graph of the project, including a Mermaid diagram, detected cycles, impact
analysis for critical modules, and coupling metrics.  When *use_llm* is
``True`` the raw graph data is sent to the LLM for a richer narrative.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from ai_code2doc.models.build import CMakeProjectInfo
    from ai_code2doc.models.graph import CallSite

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

        # 3b. Build call graph
        from ai_code2doc.analyzer.call_graph_builder import CallGraphBuilder

        call_builder = CallGraphBuilder(project_root)
        call_sites = call_builder.build_for_files(file_infos)
        graph_builder.add_call_edges(call_sites)
        graph = graph_builder.build()

        # 3c. Parse CMake build info if available
        cmake_info: CMakeProjectInfo | None = None
        if (project_root / "CMakeLists.txt").is_file():
            from ai_code2doc.parser.build.cmake_parser import CMakeParser
            cmake_info = CMakeParser().parse(project_root)

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

        # 5b. Call graph metrics
        call_edges = [(u, v) for u, v, d in graph.edges(data=True) if d.get("edge_type") == "call"]
        call_node_count = sum(1 for n in graph.nodes if graph.nodes[n].get("kind") == "symbol")
        resolved_calls = sum(1 for s in call_sites if s.callee_fqn is not None)

        # Hotspot analysis: most-called symbols
        caller_counts: dict[str, int] = {}
        for u, v, d in graph.edges(data=True):
            if d.get("edge_type") == "call":
                caller_counts[v] = caller_counts.get(v, 0) + 1
        hotspots = sorted(caller_counts.items(), key=lambda x: x[1], reverse=True)[:10]

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
            call_node_count=call_node_count,
            call_sites=call_sites,
            resolved_calls=resolved_calls,
            hotspots=hotspots,
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
                cmake_info=cmake_info,
                call_sites=call_sites,
                hotspots=hotspots,
                resolved_calls=resolved_calls,
                call_node_count=call_node_count,
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
                f"{len(cycles)} cycle(s) detected. "
                f"Call graph: {call_node_count} symbol nodes, "
                f"{len(call_sites)} call sites, {resolved_calls} resolved."
            ),
            tags=["layer3", "dependency-graph", "architecture", "call-graph"],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={
                "node_count": node_count,
                "edge_count": edge_count,
                "cycle_count": len(cycles),
                "most_depended": [(n, d) for n, d in most_depended[:5]],
                "most_coupled": [(n, d) for n, d in most_coupled[:5]],
                "call_node_count": call_node_count,
                "call_site_count": len(call_sites),
                "resolved_call_count": resolved_calls,
                "hotspots": hotspots[:5],
            },
        )

        # 13. Write to disk
        output_path = output_dir / "layer3" / "dependency-graph.md"
        self._writer.write_doc(output_path, doc)

        # Also write the raw Mermaid diagram as a separate file
        mermaid_path = output_dir / "layer3" / "dependency-graph.mmd"
        self._writer.write_raw(mermaid_path, mermaid_graph)

        # 14. Export to SQLite + JSON + module embeddings
        try:
            from ai_code2doc.analyzer.dependency_store import DependencyStore
            from ai_code2doc.utils.hashing import compute_file_hash

            from ai_code2doc.utils.git import get_current_branch, sanitize_branch_name

            branch = get_current_branch(project_root)
            if branch:
                db_path = (
                    output_dir
                    / "layer3"
                    / "branches"
                    / sanitize_branch_name(branch)
                    / "dependency-graph.db"
                )
            else:
                db_path = output_dir / "layer3" / "dependency-graph.db"
            store = DependencyStore(db_path)

            # Compute file hashes for incremental tracking
            current_hashes: dict[str, str] = {}
            for fi in file_infos:
                fp = str(fi.path).replace("\\", "/")
                try:
                    h = compute_file_hash(fi.path)
                    current_hashes[fp] = h
                except Exception:
                    current_hashes[fp] = ""

            # Full rebuild on first run, incremental after
            if not store.get_metadata("version"):
                store._conn.execute("DELETE FROM edges")
                store._conn.execute("DELETE FROM nodes")

            # Write file nodes
            for fi in file_infos:
                fp = str(fi.path).replace("\\", "/")
                store.upsert_node(
                    node_id=fp, path=fp, name=fi.name,
                    kind="file", file_hash=current_hashes.get(fp),
                )

            # Write import edges and call edges from NetworkX graph
            for u, v, d in graph.edges(data=True):
                edge_type = d.get("edge_type", "import")
                conf = d.get("confidence", 1.0)
                line_num = d.get("line_number")
                weight = d.get("weight", 1)

                # Ensure source node exists
                if store.get_node(u) is None:
                    u_name = u.rsplit("/", 1)[-1].split("::")[-1] if "::" in u else u.rsplit("/", 1)[-1]
                    u_kind = "symbol" if "::" in u else "file"
                    u_path = u.split("::")[0] if "::" in u else u
                    store.upsert_node(node_id=u, path=u_path, name=u_name, kind=u_kind)

                # Ensure target node exists
                if store.get_node(v) is None:
                    v_name = v.rsplit("/", 1)[-1].split("::")[-1] if "::" in v else v.rsplit("/", 1)[-1]
                    v_kind = "symbol" if "::" in v else "file"
                    v_path = v.split("::")[0] if "::" in v else v
                    store.upsert_node(node_id=v, path=v_path, name=v_name, kind=v_kind)

                store.upsert_edge(
                    source_id=u, target_id=v, edge_type=edge_type,
                    confidence=conf, weight=weight, line_number=line_num,
                )

            store.commit()
            store.set_metadata("version", "2.0")
            store.set_metadata("generated_at", datetime.now(timezone.utc).isoformat())

            # 15. Export JSON
            json_path = output_dir / "layer3" / "dependency-graph.json"
            store.export_json(json_path)

            # 16. Generate and store module-level embeddings
            try:
                from ai_code2doc.vector_store.store import VectorStore
                vs = VectorStore(self._settings)
                summaries = DependencyStore.generate_module_summaries(store)
                vs.add_module_summaries(summaries)
            except Exception as emb_exc:
                logger.warning("Module embedding generation failed: %s", emb_exc)

            store.close()
            logger.info(
                "Layer 3 exported: SQLite (%s), JSON (%s)",
                db_path, json_path,
            )
        except Exception as exc:
            logger.warning("Layer 3 structured export failed: %s", exc)

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
        call_node_count: int = 0,
        call_sites: list[CallSite] | None = None,
        resolved_calls: int = 0,
        hotspots: list[tuple[str, int]] | None = None,
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

        # Call graph metrics
        if call_sites is not None:
            parts.append("")
            parts.append(f"Call graph nodes (symbols): {call_node_count}")
            parts.append(f"Call sites: {len(call_sites)}")
            parts.append(f"Resolved calls: {resolved_calls}")
            if hotspots:
                parts.append("")
                parts.append("Most-called symbols (hotspots):")
                for sym, count in hotspots[:10]:
                    parts.append(f"  - {sym} (called {count} times)")

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
        cmake_info: CMakeProjectInfo | None = None,
        call_sites: list[CallSite] | None = None,
        hotspots: list[tuple[str, int]] | None = None,
        resolved_calls: int = 0,
        call_node_count: int = 0,
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

        # CMake Build Target Dependencies
        if cmake_info and cmake_info.targets:
            cmake_sections: list[str] = [
                "## Build Target Dependencies\n\n"
                "Dependencies between CMake build targets (from ``target_link_libraries``):\n\n",
            ]

            # Build target mermaid diagram
            has_links = any(t.link_libraries for t in cmake_info.targets.values())
            if has_links:
                lines: list[str] = ["```mermaid", "graph LR"]
                seen_pairs: set[tuple[str, str]] = set()
                for target in cmake_info.targets.values():
                    for lib in target.link_libraries:
                        pair = (target.name, lib)
                        if pair not in seen_pairs and target.name != lib:
                            seen_pairs.add(pair)
                            lines.append(f"    {target.name} --> {lib}")
                lines.append("```")
                cmake_sections.append("\n".join(lines))

            # Target details table
            target_rows = [
                "| Target | Type | Links | Sources |",
                "|--------|------|-------|---------|",
            ]
            for name, target in cmake_info.targets.items():
                links = ", ".join(target.link_libraries) if target.link_libraries else "-"
                srcs = ", ".join(Path(s).name for s in target.sources[:5])
                if len(target.sources) > 5:
                    srcs += f" (+{len(target.sources) - 5})"
                target_rows.append(
                    f"| `{name}` | {target.target_type} | {links} | {srcs} |"
                )
            cmake_sections.append("\n".join(target_rows))

            # find_package list
            if cmake_info.find_packages:
                pkg_str = ", ".join(f"`{p}`" for p in cmake_info.find_packages)
                cmake_sections.append(
                    f"\n### External Dependencies (find_package)\n\n{pkg_str}"
                )

            sections.append("\n\n".join(cmake_sections))

        # Call graph section
        if call_sites:
            call_sections = ["## Call Graph Analysis\n\n"]
            call_sections.append(
                f"The call graph contains **{call_node_count}** symbol nodes and "
                f"**{len(call_sites)}** call sites, **{resolved_calls}** of which "
                f"were resolved to specific definitions.\n"
            )

            if hotspots:
                rows = ["| Symbol | Call Count |", "|--------|------------|"]
                for sym, count in hotspots:
                    rows.append(f"| `{sym}` | {count} |")
                call_sections.append(
                    "### Most-Called Symbols (Hotspots)\n\n"
                    "These functions/methods are called most frequently:\n\n"
                    + "\n".join(rows)
                )

            # Cross-module call interface table
            cross_module_calls = [
                s for s in call_sites
                if s.callee_fqn and "::" in s.callee_fqn
                and s.caller_fqn.split("::")[0] != s.callee_fqn.split("::")[0]
            ]
            if cross_module_calls:
                rows = ["| Caller | Callee | Confidence | Line |",
                         "|--------|--------|------------|------|"]
                for s in cross_module_calls[:20]:
                    rows.append(
                        f"| `{s.caller_fqn}` | `{s.callee_fqn}` | "
                        f"{s.confidence:.0%} | {s.line_number} |"
                    )
                call_sections.append(
                    "### Cross-Module Calls\n\n"
                    "Calls that cross file boundaries:\n\n"
                    + "\n".join(rows)
                )

            sections.append("\n\n".join(call_sections))

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
