from __future__ import annotations

from pathlib import Path

from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
from ai_code2doc.models.graph import CallSite


class TestDependencyGraphCallEdges:
    def test_add_call_edges(self, tmp_path: Path) -> None:
        builder = DependencyGraphBuilder(tmp_path)
        builder.build()  # initialize graph

        sites = [
            CallSite(
                caller_fqn="a.py::main",
                callee_name="helper",
                callee_fqn="b.py::helper",
                file_path="a.py",
                line_number=5,
                call_type="function",
                confidence=0.90,
            ),
        ]
        builder.add_call_edges(sites)

        graph = builder.build()
        assert "a.py" in graph.nodes
        assert "b.py" in graph.nodes
        assert "a.py::main" in graph.nodes
        assert "b.py::helper" in graph.nodes
        assert graph.has_edge("a.py::main", "b.py::helper")
        data = graph.get_edge_data("a.py::main", "b.py::helper")
        assert data["edge_type"] == "call"

    def test_contains_edges(self, tmp_path: Path) -> None:
        builder = DependencyGraphBuilder(tmp_path)
        builder.build()

        sites = [
            CallSite(
                caller_fqn="a.py::main",
                callee_name="helper",
                callee_fqn="a.py::helper",
                file_path="a.py",
                line_number=5,
                call_type="function",
                confidence=0.90,
            ),
        ]
        builder.add_call_edges(sites)
        graph = builder.build()
        assert graph.has_edge("a.py", "a.py::main")
        assert graph.has_edge("a.py", "a.py::helper")
        assert graph.get_edge_data("a.py", "a.py::main")["edge_type"] == "contains"

    def test_existing_import_edges_unchanged(self, tmp_path: Path) -> None:
        from ai_code2doc.models.module import FileInfo, ImportInfo

        # Create the target file so the Python resolver can resolve the import.
        (tmp_path / "b.py").write_text("", encoding="utf-8")

        builder = DependencyGraphBuilder(tmp_path)
        fi = FileInfo(
            path=tmp_path / "a.py",
            name="a.py",
            imports=[ImportInfo(source="b", specifiers=["b"])],
        )
        builder.add_file(fi)
        builder.add_call_edges([])
        graph = builder.build()
        assert any(
            d.get("edge_type") == "import" for _, _, d in graph.edges(data=True)
        )

    def test_unresolved_calls_no_edge(self, tmp_path: Path) -> None:
        builder = DependencyGraphBuilder(tmp_path)
        builder.build()
        sites = [
            CallSite(
                caller_fqn="a.py::main",
                callee_name="unknown",
                callee_fqn=None,
                file_path="a.py",
                line_number=5,
                call_type="function",
                confidence=0.30,
            ),
        ]
        builder.add_call_edges(sites)
        graph = builder.build()
        # Caller symbol node should exist
        assert "a.py::main" in graph.nodes
        # No call edge should exist (unresolved)
        assert not graph.has_edge("a.py::main", "unknown")
