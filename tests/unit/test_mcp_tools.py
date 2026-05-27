"""Handler tests for MCP tool functions against a real DependencyStore."""

from __future__ import annotations

from pathlib import Path

from ai_code2doc.analyzer.dependency_store import DependencyStore
from ai_code2doc.mcp.tools import (
    _handle_dependents,
    _handle_dependencies,
    _handle_callers,
    _handle_callees,
    _handle_hotspots,
    _handle_subgraph,
    _handle_impact,
    _handle_path,
    _handle_stats,
    _handle_get_edges,
)


def _make_store(tmp_path: Path, db_name: str = "test.db") -> DependencyStore:
    store = DependencyStore(tmp_path / db_name)
    for name in ("src/engine.py", "src/parser.py", "src/utils.py", "lib/helper.py"):
        store.upsert_node(name, name, Path(name).name, "file")
    store.upsert_node("src/engine.py::run", "src/engine.py", "run", "function")
    store.upsert_node("src/engine.py::stop", "src/engine.py", "stop", "function")
    store.upsert_node("src/parser.py::parse", "src/parser.py", "parse", "function")
    store.upsert_node("src/utils.py::log", "src/utils.py", "log", "function")
    store.upsert_node("lib/helper.py::helper", "lib/helper.py", "helper", "function")
    store.upsert_edge("src/engine.py", "src/parser.py", "import")
    store.upsert_edge("src/engine.py", "src/utils.py", "import")
    store.upsert_edge("src/parser.py", "src/utils.py", "import")
    store.upsert_edge("src/engine.py", "lib/helper.py", "import")
    store.upsert_edge("src/engine.py::run", "src/parser.py::parse", "call", confidence=0.9, line_number=10)
    store.upsert_edge("src/engine.py::run", "src/utils.py::log", "call", confidence=0.85, line_number=15)
    store.upsert_edge("src/engine.py::stop", "src/utils.py::log", "call", confidence=0.9, line_number=20)
    store.upsert_edge("src/engine.py::run", "lib/helper.py::helper", "call", confidence=0.7, line_number=5)
    store.upsert_edge("src/engine.py", "src/engine.py::run", "contains")
    store.upsert_edge("src/engine.py", "src/engine.py::stop", "contains")
    store.upsert_edge("src/parser.py", "src/parser.py::parse", "contains")
    store.upsert_edge("src/utils.py", "src/utils.py::log", "contains")
    store.upsert_edge("lib/helper.py", "lib/helper.py::helper", "contains")
    store.commit()
    return store


class TestDependents:
    def test_basic(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_dependents(db_path=db_path, target="src/parser.py")
        assert "engine.py" in result

    def test_empty(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_dependents(db_path=db_path, target="nonexistent")
        assert "No modules depend" in result


class TestDependencies:
    def test_basic(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_dependencies(db_path=db_path, target="src/engine.py")
        assert "parser.py" in result
        assert "utils.py" in result

    def test_empty(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_dependencies(db_path=db_path, target="nonexistent")
        assert "has no dependencies" in result


class TestCallers:
    def test_basic(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_callers(db_path=db_path, target="src/utils.py::log")
        assert "engine.py::run" in result
        assert "engine.py::stop" in result

    def test_confidence_filter(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_callers(db_path=db_path, target="src/utils.py::log", confidence_threshold=0.90)
        assert "engine.py::stop" in result
        assert "engine.py::run" not in result


class TestCallees:
    def test_basic(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_callees(db_path=db_path, target="src/engine.py::run")
        assert "parse" in result
        assert "log" in result

    def test_confidence_filter(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_callees(
            db_path=db_path, target="src/engine.py::run", confidence_threshold=0.80
        )
        assert "parse" in result
        assert "log" in result
        assert "helper" not in result


class TestHotspots:
    def test_basic(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_hotspots(db_path=db_path)
        assert "log" in result

    def test_top_n(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_hotspots(db_path=db_path, top_n=1)
        # There should be only one numbered result line (e.g. "  1. ...")
        lines = [l for l in result.split("\n") if l.strip() and l.strip()[0].isdigit()]
        assert len(lines) == 1


class TestSubgraph:
    def test_single_file(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_subgraph(db_path=db_path, target="src/engine.py")
        assert "run" in result
        assert "stop" in result

    def test_multi_file(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_subgraph(db_path=db_path, files="src/engine.py,src/parser.py")
        assert "engine.py" in result
        assert "parser.py" in result


class TestImpact:
    def test_basic(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_impact(db_path=db_path, target="src/utils.py")
        assert "engine.py" in result
        assert "parser.py" in result

    def test_depth(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_impact(db_path=db_path, target="src/utils.py", depth=0)
        assert "low" in result


class TestPath:
    def test_existing_path(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_path(db_path=db_path, target="src/engine.py", end="src/parser.py")
        assert "Path:" in result

    def test_no_path(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_path(db_path=db_path, target="src/engine.py", end="nonexistent")
        assert "No path" in result


class TestStats:
    def test_basic(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_stats(db_path=db_path)
        assert "Nodes:" in result
        assert "Total edges:" in result
        # Parse out the node count to verify >= 4
        for line in result.split("\n"):
            if "Nodes:" in line:
                count = int(line.split("Nodes:")[-1].strip())
                assert count >= 4


class TestGetEdges:
    def test_by_type(self, tmp_path: Path) -> None:
        _make_store(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = _handle_get_edges(db_path=db_path, edge_type="import")
        for line in result.split("\n"):
            if "--[import]-->" in line:
                assert True
                return
        assert False, "Expected at least one import edge"
