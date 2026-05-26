"""Dependency graph builder and analyser for ai_code2doc."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from ai_code2doc.models.module import FileInfo, ModuleSummary
from ai_code2doc.models.graph import CallSite, DependencyEdge, CallChain, ImpactHint, CycleInfo
from ai_code2doc.parser.language_registry import LanguageRegistry


class DependencyGraphBuilder:
    """Builds and analyses a directed dependency graph for a project."""

    def __init__(self, project_root: Path) -> None:
        self.root = project_root
        self.graph: nx.DiGraph = nx.DiGraph()
        self._module_map: dict[str, str] = {}  # file_path -> module_name

    def add_file(self, file_info: FileInfo) -> None:
        """Add a file and its imports to the graph."""
        source = str(file_info.path).replace("\\", "/")
        self.graph.add_node(source)

        # Determine the file extension to pick the right resolver.
        ext = Path(source).suffix.lower()
        adapter = LanguageRegistry.get_by_extension(ext)
        if adapter is None:
            return

        for imp in file_info.imports:
            resolved = adapter.resolver.resolve(
                imp.source,
                self.root / source,
                self.root,
            )
            if resolved is not None:
                target = str(resolved).replace("\\", "/")
                self.graph.add_node(target)
                self.graph.add_edge(source, target, weight=1, edge_type="import")

    def add_call_edges(self, call_sites: list[CallSite]) -> None:
        """Add call edges to the graph for each resolved call site."""
        for site in call_sites:
            caller_fqn = site.caller_fqn
            caller_file = site.file_path

            # Add caller symbol node and "contains" edge from file to caller.
            self.graph.add_node(caller_fqn, kind="symbol")
            self.graph.add_node(caller_file)
            self.graph.add_edge(caller_file, caller_fqn, edge_type="contains")

            if site.callee_fqn is not None:
                callee_fqn = site.callee_fqn
                callee_file = callee_fqn.split("::")[0]

                # Add callee symbol node and "contains" edge.
                self.graph.add_node(callee_fqn, kind="symbol")
                self.graph.add_node(callee_file)
                self.graph.add_edge(callee_file, callee_fqn, edge_type="contains")

                # Add call edge from caller to callee.
                self.graph.add_edge(
                    caller_fqn,
                    callee_fqn,
                    edge_type="call",
                    confidence=site.confidence,
                    line_number=site.line_number,
                )

    def build(self) -> nx.DiGraph:
        """Return the fully constructed dependency graph."""
        return self.graph

    def get_edges(self) -> list[DependencyEdge]:
        """Return all edges in the graph as DependencyEdge models."""
        edges: list[DependencyEdge] = []
        for u, v, data in self.graph.edges(data=True):
            edges.append(
                DependencyEdge(
                    source=u,
                    target=v,
                    weight=data.get("weight", 1),
                    edge_type=data.get("edge_type", "import"),
                )
            )
        return edges

    def detect_cycles(self) -> list[CycleInfo]:
        """Detect circular dependencies in the graph."""
        cycles: list[CycleInfo] = []
        try:
            for cycle in nx.simple_cycles(self.graph):
                if len(cycle) > 1:
                    cycles.append(
                        CycleInfo(
                            nodes=cycle,
                            description=" -> ".join(cycle) + " -> " + cycle[0],
                        )
                    )
        except nx.NetworkXError:
            pass
        return cycles

    def compute_impact(self, target: str) -> ImpactHint:
        """Compute what modules are affected if *target* changes."""
        # Reverse BFS to find all dependents
        affected: list[str] = []
        visited: set[str] = set()
        queue: list[str] = [target]
        while queue:
            node = queue.pop(0)
            for pred in self.graph.predecessors(node):
                if pred not in visited:
                    visited.add(pred)
                    affected.append(pred)
                    queue.append(pred)

        # Risk level based on count
        if len(affected) <= 2:
            risk = "low"
        elif len(affected) <= 5:
            risk = "medium"
        else:
            risk = "high"

        return ImpactHint(
            change_target=target,
            affected_modules=affected,
            risk_level=risk,
        )

    def find_call_chains(
        self,
        start: str,
        end: str,
        max_depth: int = 10,
    ) -> list[CallChain]:
        """Find all paths from *start* to *end* module."""
        chains: list[CallChain] = []
        try:
            for path in nx.all_simple_paths(self.graph, start, end, cutoff=max_depth):
                chains.append(
                    CallChain(
                        start=start,
                        end=end,
                        path=path,
                        description=" -> ".join(path),
                    )
                )
        except nx.NetworkXError:
            pass
        return chains

    def topological_sort(self) -> list[str]:
        """Return files in dependency order."""
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXUnfeasible:
            # Has cycles -- fall back to approximate sort
            return list(nx.approximate_treewidth_min_fill_in(self.graph))

    def get_module_dependencies(
        self, module_path: str
    ) -> tuple[list[str], list[str]]:
        """Get dependencies and dependents for a module."""
        deps = (
            list(self.graph.successors(module_path))
            if module_path in self.graph
            else []
        )
        dependents = (
            list(self.graph.predecessors(module_path))
            if module_path in self.graph
            else []
        )
        return deps, dependents

    def to_mermaid(self) -> str:
        """Generate a Mermaid graph representation."""
        lines: list[str] = ["graph TD"]
        seen: set[tuple[str, str]] = set()
        for u, v in self.graph.edges():
            # Use short names for readability
            u_name = Path(u).stem
            v_name = Path(v).stem
            # Avoid duplicate edges in rendering
            key = (u_name, v_name)
            if key not in seen and u_name != v_name:
                seen.add(key)
                lines.append(f"    {u_name} --> {v_name}")
        return "\n".join(lines)
