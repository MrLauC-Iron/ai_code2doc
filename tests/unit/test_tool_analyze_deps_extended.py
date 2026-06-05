"""Extended tests for analyze_deps tool - all 9 modes via execute()."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_code2doc.agent.context import AgentContext
from ai_code2doc.agent.models import ToolCall
from ai_code2doc.agent.tools.analyze_deps import execute, _query_sqlite, tool_definition
from code2doc_core.analyzer.dependency_store import DependencyStore


def _make_store(tmp_path: Path, db_name: str = "test.db") -> DependencyStore:
    """Create a pre-populated DependencyStore for testing."""
    store = DependencyStore(tmp_path / db_name)

    # File nodes
    for name in ("src/engine.py", "src/parser.py", "src/utils.py", "lib/helper.py"):
        store.upsert_node(name, name, Path(name).name, "file")

    # Symbol nodes
    store.upsert_node("src/engine.py::run", "src/engine.py", "run", "function")
    store.upsert_node("src/engine.py::stop", "src/engine.py", "stop", "function")
    store.upsert_node("src/parser.py::parse", "src/parser.py", "parse", "function")
    store.upsert_node("src/utils.py::log", "src/utils.py", "log", "function")
    store.upsert_node("lib/helper.py::helper", "lib/helper.py", "helper", "function")

    # Import edges
    store.upsert_edge("src/engine.py", "src/parser.py", "import")
    store.upsert_edge("src/engine.py", "src/utils.py", "import")
    store.upsert_edge("src/parser.py", "src/utils.py", "import")
    store.upsert_edge("src/engine.py", "lib/helper.py", "import")

    # Call edges
    store.upsert_edge("src/engine.py::run", "src/parser.py::parse", "call", confidence=0.9, line_number=10)
    store.upsert_edge("src/engine.py::run", "src/utils.py::log", "call", confidence=0.85, line_number=15)
    store.upsert_edge("src/engine.py::stop", "src/utils.py::log", "call", confidence=0.9, line_number=20)
    store.upsert_edge("src/engine.py::run", "lib/helper.py::helper", "call", confidence=0.7, line_number=5)

    # Contains edges
    store.upsert_edge("src/engine.py", "src/engine.py::run", "contains")
    store.upsert_edge("src/engine.py", "src/engine.py::stop", "contains")
    store.upsert_edge("src/parser.py", "src/parser.py::parse", "contains")
    store.upsert_edge("src/utils.py", "src/utils.py::log", "contains")
    store.upsert_edge("lib/helper.py", "lib/helper.py::helper", "contains")

    store.commit()
    return store


def _make_context(tmp_path: Path, store: DependencyStore) -> AgentContext:
    """Create a mock context that points to a store.

    _get_store() looks for: context.output_dir / "layer3" / "dependency-graph.db"
    where context.output_dir = project_root / settings.output_dir.
    We place the DB at tmp_path / ".ai_code2doc" / "layer3" / "dependency-graph.db"
    and set output_dir accordingly.
    """
    store.close()

    import shutil
    layer3_dir = tmp_path / ".ai_code2doc" / "layer3"
    layer3_dir.mkdir(parents=True, exist_ok=True)
    dst_db = layer3_dir / "dependency-graph.db"
    shutil.copy2(tmp_path / "test.db", dst_db)

    mock_settings = MagicMock()
    mock_settings.output_dir = ".ai_code2doc"
    ctx = AgentContext(project_root=tmp_path, settings=mock_settings)
    return ctx


class TestToolDefinition:
    """Verify tool metadata."""

    def test_all_9_modes_declared(self) -> None:
        params = {p.name for p in tool_definition.parameters}
        assert "target" in params
        assert "mode" in params
        assert "depth" in params
        assert "files" in params
        assert "confidence_threshold" in params
        assert "end" in params
        mode_param = next(p for p in tool_definition.parameters if p.name == "mode")
        assert set(mode_param.enum) == {
            "call_chains", "impact", "dependents", "dependencies",
            "callers", "callees", "hotspots", "subgraph", "path",
        }


class TestExecuteDependents:
    """execute() with mode=dependents via SQLite."""

    def test_basic(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "src/parser.py", "mode": "dependents",
        })
        result = execute(tc, ctx)
        assert not result.is_error
        assert "engine.py" in result.content

    def test_nonexistent_returns_message(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "nonexistent.cpp", "mode": "dependents",
        })
        result = execute(tc, ctx)
        assert not result.is_error
        assert "No dependents" in result.content


class TestExecuteDependencies:
    """execute() with mode=dependencies via SQLite."""

    def test_basic(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "src/engine.py", "mode": "dependencies",
        })
        result = execute(tc, ctx)
        assert not result.is_error
        assert "parser.py" in result.content
        assert "utils.py" in result.content

    def test_nonexistent(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "nonexistent.cpp", "mode": "dependencies",
        })
        result = execute(tc, ctx)
        assert "No dependencies" in result.content


class TestExecuteCallers:
    """execute() with mode=callers via SQLite."""

    def test_basic(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "src/utils.py::log", "mode": "callers",
        })
        result = execute(tc, ctx)
        assert not result.is_error
        assert "engine.py::run" in result.content
        assert "engine.py::stop" in result.content

    def test_confidence_threshold(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        # At 0.90, only run->log(0.85) and stop->log(0.90) — but 0.85 < 0.90
        # So only stop->log (0.90) matches
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "src/utils.py::log", "mode": "callers",
            "confidence_threshold": 0.90,
        })
        result = execute(tc, ctx)
        assert not result.is_error
        count = result.content.count("\n  -")
        assert count == 1  # only stop->log (confidence=0.90)

    def test_nonexistent(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "nonexistent::func", "mode": "callers",
        })
        result = execute(tc, ctx)
        assert "No callers" in result.content


class TestExecuteCallees:
    """execute() with mode=callees via SQLite."""

    def test_basic(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "src/engine.py::run", "mode": "callees",
        })
        result = execute(tc, ctx)
        assert not result.is_error
        # Default confidence_threshold is 0.80
        # run->parse(0.90) and run->log(0.85) pass, run->helper(0.70) does not
        assert "parse" in result.content
        assert "log" in result.content
        assert "helper" not in result.content  # confidence 0.70 < default 0.80

    def test_confidence_filter(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        # helper has confidence 0.70, others 0.85/0.90
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "src/engine.py::run", "mode": "callees",
            "confidence_threshold": 0.80,
        })
        result = execute(tc, ctx)
        assert "helper" not in result.content  # 0.70 < 0.80
        assert "parse" in result.content  # 0.90 >= 0.80


class TestExecuteHotspots:
    """execute() with mode=hotspots via SQLite."""

    def test_basic(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={"mode": "hotspots"})
        result = execute(tc, ctx)
        assert not result.is_error
        assert "log" in result.content  # most-called (2 times at >=0.75)

    def test_returns_sorted(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={"mode": "hotspots"})
        result = execute(tc, ctx)
        # First result should have the highest call count
        lines = [l for l in result.content.split("\n") if "call(s)" in l]
        assert len(lines) >= 2
        # Parse counts and verify descending order
        counts = []
        for line in lines:
            count_str = line.split(":")[-1].strip().split(" ")[0]
            counts.append(int(count_str))
        assert counts == sorted(counts, reverse=True)


class TestExecuteSubgraph:
    """execute() with mode=subgraph via SQLite."""

    def test_single_file(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "src/engine.py", "mode": "subgraph",
        })
        result = execute(tc, ctx)
        assert not result.is_error
        assert "contains" in result.content
        assert "run" in result.content
        assert "stop" in result.content

    def test_multiple_files(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "src/engine.py", "mode": "subgraph",
            "files": "src/engine.py,src/parser.py",
        })
        result = execute(tc, ctx)
        assert not result.is_error
        assert "Subgraph for 2 file(s)" in result.content

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "nonexistent.cpp", "mode": "subgraph",
        })
        result = execute(tc, ctx)
        assert "No edges found" in result.content


class TestExecuteImpact:
    """execute() with mode=impact via SQLite."""

    def test_depth_1(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "src/utils.py", "mode": "impact", "depth": 1,
        })
        result = execute(tc, ctx)
        assert not result.is_error
        assert "Risk level:" in result.content
        assert "Affected modules" in result.content
        assert "engine.py" in result.content
        assert "parser.py" in result.content

    def test_depth_0_no_affected(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "src/utils.py", "mode": "impact", "depth": 0,
        })
        result = execute(tc, ctx)
        assert "no other modules" in result.content

    def test_risk_levels(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)

        # depth=1: engine + parser depend on utils.py -> 2 affected -> "low" (<=2)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "src/utils.py", "mode": "impact", "depth": 1,
        })
        result = execute(tc, ctx)
        assert "Risk level: low" in result.content

        # depth=2: engine depends on parser too, parser depends on utils
        tc2 = ToolCall(id="c2", name="analyze_deps", arguments={
            "target": "src/parser.py", "mode": "impact", "depth": 2,
        })
        result2 = execute(tc2, ctx)
        assert "Risk level:" in result2.content


class TestExecutePath:
    """execute() with mode=path via SQLite."""

    def test_existing_path(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "src/engine.py", "mode": "path",
            "end": "src/utils.py",
        })
        result = execute(tc, ctx)
        assert not result.is_error
        assert "Shortest path" in result.content
        assert "engine.py" in result.content
        assert "utils.py" in result.content

    def test_no_end_parameter(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "src/engine.py", "mode": "path",
        })
        result = execute(tc, ctx)
        assert result.is_error

    def test_nonexistent_target(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "src/engine.py", "mode": "path",
            "end": "nonexistent.cpp",
        })
        result = execute(tc, ctx)
        assert "No path" in result.content


class TestExecuteErrorCases:
    """execute() error handling."""

    def test_no_target_for_dependents(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={"mode": "dependents"})
        result = execute(tc, ctx)
        assert result.is_error

    def test_no_target_for_dependencies(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={"mode": "dependencies"})
        result = execute(tc, ctx)
        assert result.is_error

    def test_no_target_for_callers(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={"mode": "callers"})
        result = execute(tc, ctx)
        assert result.is_error

    def test_no_target_for_callees(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={"mode": "callees"})
        result = execute(tc, ctx)
        assert result.is_error

    def test_unknown_mode(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        ctx = _make_context(tmp_path, store)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "foo", "mode": "nonexistent_mode",
        })
        result = execute(tc, ctx)
        assert result.is_error


class TestExecuteFallback:
    """execute() falls back to NetworkX when SQLite is unavailable.

    subgraph and path modes are SQLite-only, so they fall through to
    the NX fallback and hit 'Unknown mode' — that's expected behavior.
    """

    def test_dependents_fallback(self, tmp_path: Path) -> None:
        import networkx as nx
        g = nx.DiGraph()
        g.add_node("a.py")
        g.add_node("b.py")
        g.add_edge("a.py", "b.py", weight=1, edge_type="import")
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        with patch("ai_code2doc.agent.tools.analyze_deps._get_store", return_value=None):
            with patch("ai_code2doc.agent.tools.analyze_deps._build_graph", return_value=g):
                tc = ToolCall(id="c1", name="analyze_deps", arguments={
                    "target": "b.py", "mode": "dependents",
                })
                result = execute(tc, ctx)
                assert not result.is_error
                assert "a.py" in result.content

    def test_dependencies_fallback(self, tmp_path: Path) -> None:
        import networkx as nx
        g = nx.DiGraph()
        g.add_node("a.py")
        g.add_node("b.py")
        g.add_edge("a.py", "b.py", weight=1, edge_type="import")
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        with patch("ai_code2doc.agent.tools.analyze_deps._get_store", return_value=None):
            with patch("ai_code2doc.agent.tools.analyze_deps._build_graph", return_value=g):
                tc = ToolCall(id="c1", name="analyze_deps", arguments={
                    "target": "a.py", "mode": "dependencies",
                })
                result = execute(tc, ctx)
                assert not result.is_error
                assert "b.py" in result.content

    def test_impact_fallback(self, tmp_path: Path) -> None:
        import networkx as nx
        g = nx.DiGraph()
        g.add_node("target.py")
        for i in range(6):
            g.add_node(f"file_{i}.py")
            g.add_edge(f"file_{i}.py", "target.py", weight=1, edge_type="import")
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        with patch("ai_code2doc.agent.tools.analyze_deps._get_store", return_value=None):
            with patch("ai_code2doc.agent.tools.analyze_deps._build_graph", return_value=g):
                tc = ToolCall(id="c1", name="analyze_deps", arguments={
                    "target": "target.py", "mode": "impact",
                })
                result = execute(tc, ctx)
                assert "high" in result.content

    def test_subgraph_fallback_is_error(self, tmp_path: Path) -> None:
        """subgraph has no NX fallback — should return error."""
        import networkx as nx
        g = nx.DiGraph()
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        with patch("ai_code2doc.agent.tools.analyze_deps._get_store", return_value=None):
            with patch("ai_code2doc.agent.tools.analyze_deps._build_graph", return_value=g):
                tc = ToolCall(id="c1", name="analyze_deps", arguments={
                    "target": "a.py", "mode": "subgraph",
                })
                result = execute(tc, ctx)
                assert result.is_error

    def test_path_fallback_is_error(self, tmp_path: Path) -> None:
        """path has no NX fallback — should return error."""
        import networkx as nx
        g = nx.DiGraph()
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        with patch("ai_code2doc.agent.tools.analyze_deps._get_store", return_value=None):
            with patch("ai_code2doc.agent.tools.analyze_deps._build_graph", return_value=g):
                tc = ToolCall(id="c1", name="analyze_deps", arguments={
                    "target": "a.py", "mode": "path", "end": "b.py",
                })
                result = execute(tc, ctx)
                assert result.is_error

    def test_failed_build_returns_error(self, tmp_path: Path) -> None:
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        with patch("ai_code2doc.agent.tools.analyze_deps._get_store", return_value=None):
            with patch("ai_code2doc.agent.tools.analyze_deps._build_graph", return_value=None):
                tc = ToolCall(id="c1", name="analyze_deps", arguments={
                    "target": "a.py", "mode": "dependents",
                })
                result = execute(tc, ctx)
                assert result.is_error


class TestQuerySqliteDirect:
    """Direct tests for _query_sqlite helper."""

    def test_returns_none_for_unhandled_mode(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "a", "mode": "call_chains", "end": "b",
        })
        result = _query_sqlite(store, tc)
        assert result is None
        store.close()

    def test_hotspots_no_target_required(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "", "mode": "hotspots",
        })
        result = _query_sqlite(store, tc)
        assert result is not None
        assert not getattr(result, "is_error", False)
        store.close()
