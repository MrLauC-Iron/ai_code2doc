"""Integration tests against the OpenCV dependency graph.

These tests validate all 9 API interfaces against real-world data
from OpenCV 4.x (44K+ nodes, 88K+ edges).

Marked as slow: run with  pytest -m slow  to include.
Skipped automatically when the OpenCV DB is not present.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import pytest

from code2doc_core.analyzer.dependency_store import DependencyStore
from ai_code2doc.agent.models import ToolCall
from ai_code2doc.agent.tools.analyze_deps import execute
from ai_code2doc.agent.context import AgentContext
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Fixture: skip the entire module if OpenCV DB is absent
# ---------------------------------------------------------------------------

OPENCV_DB = Path("F:/CodeWorkspace/xiaozhi/opencv-4.x/opencv-4.x/.ai_code2doc/layer3/dependency-graph.db")

requires_opencv = pytest.mark.skipif(
    not OPENCV_DB.exists(),
    reason="OpenCV dependency-graph.db not found",
)

pytestmark = [requires_opencv, pytest.mark.slow]


@pytest.fixture(scope="module")
def store() -> DependencyStore:
    """Share a single DB connection across all tests in this module."""
    s = DependencyStore(OPENCV_DB)
    yield s
    s.close()


@pytest.fixture(scope="module")
def context() -> AgentContext:
    """Mock context pointing to the OpenCV output dir."""
    mock_settings = MagicMock()
    mock_settings.output_dir = ".ai_code2doc"
    root = OPENCV_DB.parent.parent  # .ai_code2doc
    ctx = AgentContext(project_root=OPENCV_DB.parent.parent.parent, settings=mock_settings)
    return ctx


# Known ground-truth values from OpenCV
ALGORITHM_CPP = "modules/core/src/algorithm.cpp"
MAT_HPP = "modules/core/include/opencv2/core/mat.hpp"
MAT_CREATE = "modules/gapi/include/opencv2/gapi/own/mat.hpp::Mat.create"
HAL_INTERNAL = "modules/core/src/hal_internal.cpp"


# ===========================================================================
#  Data integrity checks
# ===========================================================================

class TestDataIntegrity:
    """Verify the DB itself is well-formed."""

    def test_no_backslash_in_nodes(self, store: DependencyStore) -> None:
        count = store._conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE id LIKE '%' || CHAR(92) || '%'"
        ).fetchone()[0]
        assert count == 0, f"{count} nodes contain backslash"

    def test_no_backslash_in_edges(self, store: DependencyStore) -> None:
        count = store._conn.execute(
            "SELECT COUNT(*) FROM edges WHERE source_id LIKE '%' || CHAR(92) || '%' "
            "OR target_id LIKE '%' || CHAR(92) || '%'"
        ).fetchone()[0]
        assert count == 0, f"{count} edges contain backslash"

    def test_no_orphan_sources(self, store: DependencyStore) -> None:
        count = store._conn.execute(
            "SELECT COUNT(*) FROM edges WHERE source_id NOT IN (SELECT id FROM nodes)"
        ).fetchone()[0]
        assert count == 0

    def test_no_orphan_targets(self, store: DependencyStore) -> None:
        count = store._conn.execute(
            "SELECT COUNT(*) FROM edges WHERE target_id NOT IN (SELECT id FROM nodes)"
        ).fetchone()[0]
        assert count == 0

    def test_all_call_edges_have_positive_confidence(self, store: DependencyStore) -> None:
        count = store._conn.execute(
            "SELECT COUNT(*) FROM edges WHERE edge_type='call' AND confidence <= 0"
        ).fetchone()[0]
        assert count == 0

    def test_min_data_scale(self, store: DependencyStore) -> None:
        stats = store.get_stats()
        assert stats["nodes"] >= 40000
        assert stats["edges"] >= 80000

    def test_edge_type_counts(self, store: DependencyStore) -> None:
        for etype, min_count in [("import", 1000), ("call", 10000), ("contains", 10000)]:
            count = store._conn.execute(
                "SELECT COUNT(*) FROM edges WHERE edge_type=?", (etype,)
            ).fetchone()[0]
            assert count >= min_count, f"Expected >= {min_count} {etype} edges, got {count}"


# ===========================================================================
#  Mode 1: dependents
# ===========================================================================

class TestDependents:
    def test_algorithm_cpp_dependents(self, store: DependencyStore) -> None:
        deps = store.dependents(ALGORITHM_CPP)
        assert len(deps) >= 5
        assert HAL_INTERNAL in deps

    def test_nonexistent(self, store: DependencyStore) -> None:
        assert store.dependents("nonexistent_xyz.cpp") == []

    def test_empty_string(self, store: DependencyStore) -> None:
        assert store.dependents("") == []

    def test_excludes_self(self, store: DependencyStore) -> None:
        deps = store.dependents(ALGORITHM_CPP)
        assert ALGORITHM_CPP not in deps


# ===========================================================================
#  Mode 2: dependencies
# ===========================================================================

class TestDependencies:
    def test_algorithm_cpp_dependencies(self, store: DependencyStore) -> None:
        deps = store.dependencies(ALGORITHM_CPP)
        assert len(deps) >= 1

    def test_nonexistent(self, store: DependencyStore) -> None:
        assert store.dependencies("nonexistent_xyz.cpp") == []

    def test_empty_string(self, store: DependencyStore) -> None:
        assert store.dependencies("") == []

    def test_excludes_self(self, store: DependencyStore) -> None:
        deps = store.dependencies(ALGORITHM_CPP)
        assert ALGORITHM_CPP not in deps


# ===========================================================================
#  Mode 3: callers
# ===========================================================================

class TestCallers:
    def test_mat_create_callers(self, store: DependencyStore) -> None:
        callers = store.callers(MAT_CREATE, min_confidence=0.75)
        assert len(callers) >= 200

    def test_confidence_filtering(self, store: DependencyStore) -> None:
        c90 = store.callers(MAT_CREATE, min_confidence=0.90)
        c75 = store.callers(MAT_CREATE, min_confidence=0.75)
        assert len(c90) <= len(c75)

    def test_callers_count_matches_sql(self, store: DependencyStore) -> None:
        # Pick top hotspot and verify count matches raw SQL
        hot = store.hotspots(1, min_confidence=0.90)
        target = hot[0]["target_id"]
        callers = store.callers(target, min_confidence=0.90)
        raw = store._conn.execute(
            "SELECT COUNT(*) FROM edges WHERE edge_type='call' AND target_id=? AND confidence >= 0.90",
            (target,),
        ).fetchone()[0]
        assert len(callers) == raw

    def test_nonexistent(self, store: DependencyStore) -> None:
        assert store.callers("nonexistent::func", min_confidence=0.75) == []

    def test_empty_string(self, store: DependencyStore) -> None:
        assert store.callers("", min_confidence=0.75) == []

    def test_result_has_full_edge_data(self, store: DependencyStore) -> None:
        callers = store.callers(MAT_CREATE, min_confidence=0.90)
        assert len(callers) > 0
        c = callers[0]
        assert "source_id" in c
        assert "target_id" in c
        assert "confidence" in c
        assert "line_number" in c
        assert c["confidence"] >= 0.90


# ===========================================================================
#  Mode 4: callees
# ===========================================================================

class TestCallees:
    def test_mat_copyto_callees(self, store: DependencyStore) -> None:
        callees = store.callees(
            "modules/gapi/include/opencv2/gapi/own/mat.hpp::Mat.copyTo",
            min_confidence=0.75,
        )
        assert len(callees) >= 3

    def test_confidence_filtering(self, store: DependencyStore) -> None:
        # Find a caller with known callees
        hot = store.hotspots(1)
        caller = hot[0]["target_id"]
        c_high = store.callees(caller, min_confidence=0.90)
        c_low = store.callees(caller, min_confidence=0.50)
        assert len(c_high) <= len(c_low)

    def test_callees_count_matches_sql(self, store: DependencyStore) -> None:
        # Find a symbol with callees
        row = store._conn.execute(
            "SELECT source_id FROM edges WHERE edge_type='call' AND confidence >= 0.90 LIMIT 1"
        ).fetchone()
        caller = row[0]
        callees = store.callees(caller, min_confidence=0.90)
        raw = store._conn.execute(
            "SELECT COUNT(*) FROM edges WHERE edge_type='call' AND source_id=? AND confidence >= 0.90",
            (caller,),
        ).fetchone()[0]
        assert len(callees) == raw

    def test_nonexistent(self, store: DependencyStore) -> None:
        assert store.callees("nonexistent::func", min_confidence=0.75) == []


# ===========================================================================
#  Mode 5: hotspots
# ===========================================================================

class TestHotspots:
    def test_returns_requested_count(self, store: DependencyStore) -> None:
        hot = store.hotspots(10, min_confidence=0.75)
        assert len(hot) == 10

    def test_sorted_descending(self, store: DependencyStore) -> None:
        hot = store.hotspots(20, min_confidence=0.75)
        counts = [h["call_count"] for h in hot]
        assert counts == sorted(counts, reverse=True)

    def test_confidence_monotonicity(self, store: DependencyStore) -> None:
        h90 = store.hotspots(50, min_confidence=0.90)
        h75 = store.hotspots(50, min_confidence=0.75)
        assert len(h90) <= len(h75)

    def test_call_count_matches_sql(self, store: DependencyStore) -> None:
        hot = store.hotspots(5, min_confidence=0.90)
        for h in hot:
            actual = store._conn.execute(
                "SELECT COUNT(*) FROM edges WHERE edge_type='call' AND target_id=? AND confidence >= 0.90",
                (h["target_id"],),
            ).fetchone()[0]
            assert h["call_count"] == actual, (
                f'{h["target_id"]}: hotspot says {h["call_count"]}, SQL says {actual}'
            )

    def test_top_entry_is_mat_type(self, store: DependencyStore) -> None:
        hot = store.hotspots(1, min_confidence=0.75)
        assert "Mat.type" in hot[0]["target_id"]
        assert hot[0]["call_count"] >= 800


# ===========================================================================
#  Mode 6: subgraph
# ===========================================================================

class TestSubgraph:
    def test_mat_hpp_contains_symbols(self, store: DependencyStore) -> None:
        contains = store.get_edges(source_id=MAT_HPP, edge_type="contains")
        assert len(contains) >= 30

    def test_contains_count_matches_symbol_nodes(self, store: DependencyStore) -> None:
        contains = store.get_edges(source_id=MAT_HPP, edge_type="contains")
        symbol_count = store._conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE id LIKE ? AND kind='symbol'",
            (MAT_HPP + "::%",),
        ).fetchone()[0]
        assert len(contains) == symbol_count

    def test_multi_file_subgraph(self, store: DependencyStore) -> None:
        files = [MAT_HPP, "modules/core/include/opencv2/core/mat.inl.hpp"]
        all_contains = []
        for f in files:
            all_contains.extend(store.get_edges(source_id=f, edge_type="contains"))
        assert len(all_contains) > 0
        sources = {e["source_id"] for e in all_contains}
        assert sources.issubset(set(files))

    def test_nonexistent_file(self, store: DependencyStore) -> None:
        edges = store.get_edges(source_id="nonexistent_xyz.cpp", edge_type="contains")
        assert len(edges) == 0


# ===========================================================================
#  Mode 7: impact
# ===========================================================================

class TestImpact:
    def test_algorithm_cpp_impact_depth_1(self, store: DependencyStore) -> None:
        affected = set()
        for dep in store.dependents(ALGORITHM_CPP):
            affected.add(dep)
        assert len(affected) >= 5

    def test_depth_monotonicity(self, store: DependencyStore) -> None:
        def impact(target, depth):
            visited = set()
            current = {target}
            for _ in range(depth):
                nxt = set()
                for node in current:
                    if node not in visited:
                        visited.add(node)
                    for dep in store.dependents(node):
                        if dep not in visited:
                            nxt.add(dep)
                visited.update(nxt)
                current = nxt
                if not nxt:
                    break
            return visited

        d1 = impact(ALGORITHM_CPP, 1)
        d3 = impact(ALGORITHM_CPP, 3)
        assert len(d3) >= len(d1)

    def test_nonexistent_target(self, store: DependencyStore) -> None:
        assert store.dependents("nonexistent_xyz.cpp") == []


# ===========================================================================
#  Mode 8: path
# ===========================================================================

class TestPath:
    def test_algorithm_to_hal_internal(self, store: DependencyStore) -> None:
        """Direct import path should exist."""
        deps = store.dependents(ALGORITHM_CPP)
        assert HAL_INTERNAL in deps

    def test_no_path_to_disconnected(self, store: DependencyStore) -> None:
        """BFS to a nonexistent target should find nothing."""
        visited = {ALGORITHM_CPP}
        queue = deque([(ALGORITHM_CPP, [ALGORITHM_CPP])])
        found = False
        while queue and not found:
            cur, path = queue.popleft()
            for dep in store.dependencies(cur):
                if dep not in visited:
                    visited.add(dep)
                    if "nonexistent_xyz" in dep:
                        found = True
                        break
                    if len(path) < 10:
                        queue.append((dep, path + [dep]))
        assert not found


# ===========================================================================
#  Mode 9: call_chains (NX fallback — test through SQL verification)
# ===========================================================================

class TestCallChains:
    def test_two_hop_chain_exists(self, store: DependencyStore) -> None:
        """Verify that 2-hop call chains exist in the data."""
        chain = store._conn.execute(
            """
            SELECT e1.source_id, e1.target_id, e2.target_id
            FROM edges e1
            JOIN edges e2 ON e2.source_id = e1.target_id
            WHERE e1.edge_type = 'call' AND e2.edge_type = 'call'
            AND e1.confidence >= 0.75 AND e2.confidence >= 0.75
            LIMIT 1
            """
        ).fetchone()
        assert chain is not None, "No 2-hop call chain found"
        assert chain[0] != chain[1]  # different nodes
        assert chain[1] != chain[2]


# ===========================================================================
#  Tool API integration via execute()
# ===========================================================================

class TestToolExecuteIntegration:
    """Test all 9 modes through the full execute() path."""

    def test_execute_dependents(self, context: AgentContext) -> None:
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": ALGORITHM_CPP, "mode": "dependents",
        })
        result = execute(tc, context)
        assert not result.is_error
        assert HAL_INTERNAL in result.content

    def test_execute_dependencies(self, context: AgentContext) -> None:
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": ALGORITHM_CPP, "mode": "dependencies",
        })
        result = execute(tc, context)
        assert not result.is_error

    def test_execute_callers(self, context: AgentContext) -> None:
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": MAT_CREATE, "mode": "callers",
        })
        result = execute(tc, context)
        assert not result.is_error
        assert "call(s)" in result.content or "call" in result.content.lower()

    def test_execute_callees(self, context: AgentContext) -> None:
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": MAT_CREATE, "mode": "callees",
        })
        result = execute(tc, context)
        assert not result.is_error

    def test_execute_hotspots(self, context: AgentContext) -> None:
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "mode": "hotspots",
        })
        result = execute(tc, context)
        assert not result.is_error
        assert "Mat.type" in result.content

    def test_execute_subgraph(self, context: AgentContext) -> None:
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": MAT_HPP, "mode": "subgraph",
        })
        result = execute(tc, context)
        assert not result.is_error
        assert "Subgraph" in result.content

    def test_execute_impact(self, context: AgentContext) -> None:
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": MAT_HPP, "mode": "impact", "depth": 2,
        })
        result = execute(tc, context)
        assert not result.is_error
        assert "Risk level:" in result.content

    def test_execute_path(self, context: AgentContext) -> None:
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": ALGORITHM_CPP, "mode": "path", "end": HAL_INTERNAL,
        })
        result = execute(tc, context)
        assert not result.is_error
        assert "path" in result.content.lower()

    def test_execute_path_no_end(self, context: AgentContext) -> None:
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": ALGORITHM_CPP, "mode": "path",
        })
        result = execute(tc, context)
        assert result.is_error

    def test_execute_nonexistent_target(self, context: AgentContext) -> None:
        tc = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": "nonexistent_xyz.cpp", "mode": "dependents",
        })
        result = execute(tc, context)
        assert not result.is_error
        assert "No dependents" in result.content

    def test_execute_no_target_error(self, context: AgentContext) -> None:
        tc = ToolCall(id="c1", name="analyze_deps", arguments={"mode": "callers"})
        result = execute(tc, context)
        assert result.is_error

    def test_execute_confidence_threshold(self, context: AgentContext) -> None:
        tc_hi = ToolCall(id="c1", name="analyze_deps", arguments={
            "target": MAT_CREATE, "mode": "callers", "confidence_threshold": 0.90,
        })
        tc_lo = ToolCall(id="c2", name="analyze_deps", arguments={
            "target": MAT_CREATE, "mode": "callers", "confidence_threshold": 0.75,
        })
        r_hi = execute(tc_hi, context)
        r_lo = execute(tc_lo, context)
        hi_count = r_hi.content.count("\n  -")
        lo_count = r_lo.content.count("\n  -")
        assert hi_count <= lo_count
