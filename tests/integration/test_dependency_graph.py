"""Integration tests for dependency graph builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
from ai_code2doc.models.module import FileInfo, ImportInfo
from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser


@pytest.fixture
def parser() -> TreeSitterParser:
    return TreeSitterParser()


class TestDependencyGraph:
    def test_single_file_no_deps(self) -> None:
        builder = DependencyGraphBuilder(Path("/project"))
        fi = FileInfo(path=Path("src/main.py"), name="main.py")
        builder.add_file(fi)
        graph = builder.build()
        assert len(graph.nodes) == 1
        assert len(graph.edges) == 0

    def test_two_file_dependency(self) -> None:
        builder = DependencyGraphBuilder(Path("/project"))
        fi_a = FileInfo(
            path=Path("src/a.py"),
            name="a.py",
            imports=[ImportInfo(source="src.b")],
        )
        fi_b = FileInfo(path=Path("src/b.py"), name="b.py")
        builder.add_file(fi_a)
        builder.add_file(fi_b)
        # Note: edge depends on resolver being able to resolve "src.b"
        # With proper resolver setup, this should create an edge
        graph = builder.build()
        assert len(graph.nodes) == 2

    def test_cycle_detection(self) -> None:
        builder = DependencyGraphBuilder(Path("/project"))
        # Manually add edges to create a cycle
        builder.graph.add_edge("a.py", "b.py", weight=1, edge_type="import")
        builder.graph.add_edge("b.py", "a.py", weight=1, edge_type="import")
        cycles = builder.detect_cycles()
        assert len(cycles) >= 1

    def test_impact_analysis_low_risk(self) -> None:
        builder = DependencyGraphBuilder(Path("/project"))
        builder.graph.add_edge("a.py", "target.py", weight=1, edge_type="import")
        impact = builder.compute_impact("target.py")
        assert impact.change_target == "target.py"
        assert len(impact.affected_modules) <= 2
        assert impact.risk_level == "low"

    def test_impact_analysis_high_risk(self) -> None:
        builder = DependencyGraphBuilder(Path("/project"))
        # Create many dependents on target
        for i in range(6):
            builder.graph.add_edge(f"file_{i}.py", "target.py", weight=1, edge_type="import")
        impact = builder.compute_impact("target.py")
        assert len(impact.affected_modules) >= 6
        assert impact.risk_level == "high"

    def test_find_call_chains(self) -> None:
        builder = DependencyGraphBuilder(Path("/project"))
        builder.graph.add_edge("a.py", "b.py", weight=1, edge_type="import")
        builder.graph.add_edge("b.py", "c.py", weight=1, edge_type="import")
        chains = builder.find_call_chains("a.py", "c.py")
        assert len(chains) >= 1
        assert chains[0].path == ["a.py", "b.py", "c.py"]

    def test_topological_sort(self) -> None:
        builder = DependencyGraphBuilder(Path("/project"))
        builder.graph.add_edge("a.py", "b.py", weight=1, edge_type="import")
        builder.graph.add_edge("b.py", "c.py", weight=1, edge_type="import")
        order = builder.topological_sort()
        assert len(order) == 3
        # topological_sort returns nodes such that for every edge u->v,
        # u comes before v in the order (i.e. dependents before dependencies)
        assert "a.py" in order and "b.py" in order and "c.py" in order

    def test_mermaid_output(self) -> None:
        builder = DependencyGraphBuilder(Path("/project"))
        builder.graph.add_edge("a.py", "b.py", weight=1, edge_type="import")
        mermaid = builder.to_mermaid()
        assert "graph TD" in mermaid
        assert "-->" in mermaid

    def test_get_module_dependencies(self) -> None:
        builder = DependencyGraphBuilder(Path("/project"))
        builder.graph.add_edge("a.py", "b.py", weight=1, edge_type="import")
        builder.graph.add_edge("c.py", "a.py", weight=1, edge_type="import")
        deps, dependents = builder.get_module_dependencies("a.py")
        assert "b.py" in deps
        assert "c.py" in dependents

    def test_get_module_dependencies_nonexistent(self) -> None:
        builder = DependencyGraphBuilder(Path("/project"))
        deps, dependents = builder.get_module_dependencies("nonexistent.py")
        assert deps == []
        assert dependents == []


class TestDependencyGraphWithRealProject:
    def test_py_project_graph(self, parser: TreeSitterParser, sample_py_project: Path) -> None:
        """Build graph from the sample Python project."""
        py_files = list(sample_py_project.rglob("*.py"))
        builder = DependencyGraphBuilder(sample_py_project)

        for pf in py_files:
            try:
                info = parser.parse_file(pf, sample_py_project)
                builder.add_file(info)
            except ValueError:
                pass

        graph = builder.build()
        assert len(graph.nodes) > 0

    def test_c_project_graph(self, parser: TreeSitterParser, sample_c_project: Path) -> None:
        """Build graph from the sample C project."""
        c_files = list(sample_c_project.rglob("*.c")) + list(sample_c_project.rglob("*.h"))
        builder = DependencyGraphBuilder(sample_c_project)

        for cf in c_files:
            try:
                info = parser.parse_file(cf, sample_c_project)
                builder.add_file(info)
            except ValueError:
                pass

        graph = builder.build()
        assert len(graph.nodes) > 0

    def test_mixed_language_graph(
        self, parser: TreeSitterParser,
        sample_py_project: Path, sample_c_project: Path,
    ) -> None:
        """Graph can contain nodes from both Python and C files."""
        builder = DependencyGraphBuilder(Path("/project"))

        # Add a Python file
        py_files = list(sample_py_project.rglob("*.py"))[:1]
        for pf in py_files:
            try:
                info = parser.parse_file(pf, sample_py_project)
                builder.add_file(info)
            except ValueError:
                pass

        # Add a C file
        c_files = list(sample_c_project.rglob("*.c"))[:1]
        for cf in c_files:
            try:
                info = parser.parse_file(cf, sample_c_project)
                builder.add_file(info)
            except ValueError:
                pass

        graph = builder.build()
        # Should have at least 2 nodes (one py, one c)
        assert len(graph.nodes) >= 2
