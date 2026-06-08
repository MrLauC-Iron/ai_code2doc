"""Extended unit tests for DependencyStore edge cases and data consistency."""

from __future__ import annotations

from pathlib import Path

from code2doc_core.analyzer.dependency_store import DependencyStore


class TestDependentsEdgeCases:
    """Edge cases for dependents()."""

    def test_nonexistent_target(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        assert store.dependents("nonexistent_file.cpp") == []
        store.close()

    def test_empty_string_target(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        assert store.dependents("") == []
        store.close()

    def test_self_loop_included(self, tmp_path: Path) -> None:
        """dependents returns ALL source_ids including self-loops."""
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file")
        store.upsert_node("b.py", "b.py", "b.py", "file")
        store.upsert_edge("a.py", "a.py", "import")  # self-loop
        store.upsert_edge("a.py", "b.py", "import")
        store.commit()
        deps = store.dependents("a.py")
        # a.py has a self-loop edge pointing to a.py, so a.py is a dependent of itself
        assert "a.py" in deps
        store.close()

    def test_deduplicates_multiple_edges(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        for name in ("a.py", "b.py", "utils.py"):
            store.upsert_node(name, name, name, "file")
        # Two edges from a to utils (import + call) should return one entry
        store.upsert_edge("a.py", "utils.py", "import")
        store.upsert_edge("a.py", "utils.py", "call", confidence=0.9)
        store.commit()
        deps = store.dependents("utils.py")
        assert sorted(deps) == ["a.py"]
        store.close()

    def test_symbol_node_as_target(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file")
        store.upsert_node("a.py::foo", "a.py", "foo", "function")
        store.upsert_node("a.py::bar", "a.py", "bar", "function")
        store.upsert_edge("a.py::foo", "a.py::bar", "call", confidence=0.9)
        store.commit()
        deps = store.dependents("a.py::bar")
        assert deps == ["a.py::foo"]
        store.close()


class TestDependenciesEdgeCases:
    """Edge cases for dependencies()."""

    def test_nonexistent_target(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        assert store.dependencies("nonexistent_file.cpp") == []
        store.close()

    def test_empty_string_target(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        assert store.dependencies("") == []
        store.close()

    def test_self_loop_included(self, tmp_path: Path) -> None:
        """dependencies returns ALL target_ids including self-loops."""
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file")
        store.upsert_edge("a.py", "a.py", "import")  # self-loop
        store.commit()
        deps = store.dependencies("a.py")
        assert "a.py" in deps
        store.close()

    def test_returns_all_edge_types(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        for name in ("a.py", "b.py", "c.py", "d.py"):
            store.upsert_node(name, name, name, "file")
        store.upsert_edge("a.py", "b.py", "import")
        store.upsert_edge("a.py", "c.py", "call", confidence=0.9)
        store.upsert_edge("a.py", "d.py", "contains")
        store.commit()
        deps = store.dependencies("a.py")
        assert sorted(deps) == ["b.py", "c.py", "d.py"]
        store.close()


class TestCallersEdgeCases:
    """Edge cases for callers()."""

    def test_nonexistent_target(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        assert store.callers("nonexistent::func") == []
        store.close()

    def test_empty_string_target(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        assert store.callers("") == []
        store.close()

    def test_filters_by_confidence(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        for name in ("a.py", "b.py", "c.py"):
            store.upsert_node(name, name, name, "file")
        store.upsert_node("target", "t.py", "target", "function")
        store.upsert_edge("a.py", "target", "call", confidence=0.9)
        store.upsert_edge("b.py", "target", "call", confidence=0.8)
        store.upsert_edge("c.py", "target", "call", confidence=0.7)
        store.commit()

        all_callers = store.callers("target", min_confidence=0.0)
        assert len(all_callers) == 3

        high = store.callers("target", min_confidence=0.85)
        assert len(high) == 1
        assert high[0]["source_id"] == "a.py"

        mid = store.callers("target", min_confidence=0.75)
        assert len(mid) == 2
        store.close()

    def test_excludes_import_edges(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file")
        store.upsert_node("target", "t.py", "target", "function")
        store.upsert_edge("a.py", "target", "import")  # not a call
        store.commit()
        assert store.callers("target") == []
        store.close()

    def test_returns_full_edge_data(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file")
        store.upsert_node("target", "t.py", "target", "function")
        store.upsert_edge(
            "a.py", "target", "call", confidence=0.85,
            line_number=42, caller_name="main", callee_name="target",
        )
        store.commit()
        callers = store.callers("target")
        assert len(callers) == 1
        c = callers[0]
        assert c["source_id"] == "a.py"
        assert c["target_id"] == "target"
        assert c["confidence"] == 0.85
        assert c["line_number"] == 42
        assert c["caller_name"] == "main"
        assert c["callee_name"] == "target"
        store.close()


class TestCalleesEdgeCases:
    """Edge cases for callees()."""

    def test_nonexistent_source(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        assert store.callees("nonexistent::func") == []
        store.close()

    def test_empty_string_source(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        assert store.callees("") == []
        store.close()

    def test_filters_by_confidence(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("caller", "a.py", "caller", "function")
        for name in ("x", "y", "z"):
            store.upsert_node(name, name + ".py", name, "function")
        store.upsert_edge("caller", "x", "call", confidence=0.9)
        store.upsert_edge("caller", "y", "call", confidence=0.5)
        store.upsert_edge("caller", "z", "call", confidence=0.3)
        store.commit()

        assert len(store.callees("caller", min_confidence=0.0)) == 3
        assert len(store.callees("caller", min_confidence=0.6)) == 1
        assert len(store.callees("caller", min_confidence=0.95)) == 0
        store.close()


class TestHotspotsEdgeCases:
    """Edge cases for hotspots()."""

    def test_empty_database(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        assert store.hotspots(10) == []
        store.close()

    def test_confidence_monotonicity(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        for name in ("a.py", "b.py"):
            store.upsert_node(name, name, name, "file")
        store.upsert_node("func", "f.py", "func", "function")
        store.upsert_edge("a.py", "func", "call", confidence=0.9)
        store.upsert_edge("b.py", "func", "call", confidence=0.7)
        store.commit()

        h_high = store.hotspots(10, min_confidence=0.85)
        h_low = store.hotspots(10, min_confidence=0.5)
        assert h_high[0]["call_count"] == 1
        assert h_low[0]["call_count"] == 2
        store.close()

    def test_result_keys(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file")
        store.upsert_node("func", "f.py", "func", "function")
        store.upsert_edge("a.py", "func", "call", confidence=0.9)
        store.commit()

        hot = store.hotspots(1)
        assert len(hot) == 1
        assert "target_id" in hot[0]
        assert "call_count" in hot[0]
        assert hot[0]["target_id"] == "func"
        assert hot[0]["call_count"] == 1
        store.close()

    def test_respects_n_limit(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        # Create 3 targets each with different call counts
        for name in ("a.py", "b.py", "c.py"):
            store.upsert_node(name, name, name, "file")
        store.upsert_node("f1", "f1.py", "f1", "function")
        store.upsert_node("f2", "f2.py", "f2", "function")
        store.upsert_node("f3", "f3.py", "f3", "function")
        # f1 gets 3 calls, f2 gets 2, f3 gets 1
        for caller in ("a.py", "b.py", "c.py"):
            store.upsert_edge(caller, "f1", "call", confidence=0.9)
        for caller in ("a.py", "b.py"):
            store.upsert_edge(caller, "f2", "call", confidence=0.9)
        store.upsert_edge("a.py", "f3", "call", confidence=0.9)
        store.commit()

        hot1 = store.hotspots(1)
        assert len(hot1) == 1
        assert hot1[0]["target_id"] == "f1"
        hot2 = store.hotspots(2)
        assert len(hot2) == 2
        store.close()


class TestGetEdgesExtended:
    """Extended tests for get_edges()."""

    def test_target_id_only(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        for name in ("a.py", "b.py", "c.py"):
            store.upsert_node(name, name, name, "file")
        store.upsert_edge("a.py", "c.py", "import")
        store.upsert_edge("b.py", "c.py", "call", confidence=0.9)
        store.commit()

        # Reverse lookup: find all edges pointing to c.py
        edges = store.get_edges(target_id="c.py")
        assert len(edges) == 2
        store.close()

    def test_both_source_and_target(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        for name in ("a.py", "b.py"):
            store.upsert_node(name, name, name, "file")
        store.upsert_edge("a.py", "b.py", "import")
        store.commit()

        edges = store.get_edges(source_id="a.py", target_id="b.py")
        assert len(edges) == 1
        assert edges[0]["edge_type"] == "import"
        store.close()

    def test_both_nonexistent(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        assert store.get_edges(source_id="aaa", target_id="bbb") == []
        store.close()

    def test_all_filters_combined(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        for name in ("a.py", "b.py"):
            store.upsert_node(name, name, name, "file")
        store.upsert_edge("a.py", "b.py", "call", confidence=0.9)
        store.upsert_edge("a.py", "b.py", "import", confidence=0.5)
        store.commit()

        # Only the call edge should match
        edges = store.get_edges(
            source_id="a.py", target_id="b.py",
            edge_type="call", min_confidence=0.8,
        )
        assert len(edges) == 1
        assert edges[0]["edge_type"] == "call"
        store.close()


class TestDataConsistency:
    """Cross-query consistency checks."""

    def test_no_orphan_edge_sources(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file")
        store.upsert_node("b.py", "b.py", "b.py", "file")
        store.upsert_edge("a.py", "b.py", "import")
        store.commit()

        orphan = store._conn.execute(
            "SELECT COUNT(*) FROM edges WHERE source_id NOT IN (SELECT id FROM nodes)"
        ).fetchone()[0]
        assert orphan == 0
        store.close()

    def test_no_orphan_edge_targets(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file")
        store.upsert_node("b.py", "b.py", "b.py", "file")
        store.upsert_edge("a.py", "b.py", "import")
        store.commit()

        orphan = store._conn.execute(
            "SELECT COUNT(*) FROM edges WHERE target_id NOT IN (SELECT id FROM nodes)"
        ).fetchone()[0]
        assert orphan == 0
        store.close()

    def test_callers_count_matches_raw_sql(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file")
        store.upsert_node("b.py", "b.py", "b.py", "file")
        store.upsert_node("target", "t.py", "target", "function")
        store.upsert_edge("a.py", "target", "call", confidence=0.9)
        store.upsert_edge("b.py", "target", "call", confidence=0.8)
        store.commit()

        callers_list = store.callers("target", min_confidence=0.75)
        raw_count = store._conn.execute(
            "SELECT COUNT(*) FROM edges WHERE edge_type='call' AND target_id=? AND confidence >= 0.75",
            ("target",),
        ).fetchone()[0]
        assert len(callers_list) == raw_count
        store.close()

    def test_callees_count_matches_raw_sql(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("caller", "a.py", "caller", "function")
        for name in ("x", "y"):
            store.upsert_node(name, name + ".py", name, "function")
            store.upsert_edge("caller", name, "call", confidence=0.9)
        store.commit()

        callees_list = store.callees("caller", min_confidence=0.75)
        raw_count = store._conn.execute(
            "SELECT COUNT(*) FROM edges WHERE edge_type='call' AND source_id=? AND confidence >= 0.75",
            ("caller",),
        ).fetchone()[0]
        assert len(callees_list) == raw_count
        store.close()

    def test_hotspot_call_count_matches_raw_sql(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        for name in ("a.py", "b.py", "c.py"):
            store.upsert_node(name, name, name, "file")
        store.upsert_node("func", "f.py", "func", "function")
        for name in ("a.py", "b.py", "c.py"):
            store.upsert_edge(name, "func", "call", confidence=0.9)
        store.commit()

        hot = store.hotspots(1, min_confidence=0.75)
        assert len(hot) == 1
        actual = store._conn.execute(
            "SELECT COUNT(*) FROM edges WHERE edge_type='call' AND target_id=? AND confidence >= 0.75",
            (hot[0]["target_id"],),
        ).fetchone()[0]
        assert hot[0]["call_count"] == actual
        store.close()

    def test_contains_count_matches_symbol_nodes(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("src/engine.py", "src/engine.py", "engine.py", "file")
        store.upsert_node("src/engine.py::run", "src/engine.py", "run", "function")
        store.upsert_node("src/engine.py::stop", "src/engine.py", "stop", "function")
        store.upsert_node("src/engine.py::Engine", "src/engine.py", "Engine", "class")
        store.upsert_edge("src/engine.py", "src/engine.py::run", "contains")
        store.upsert_edge("src/engine.py", "src/engine.py::stop", "contains")
        store.upsert_edge("src/engine.py", "src/engine.py::Engine", "contains")
        store.commit()

        contains = store.get_edges(source_id="src/engine.py", edge_type="contains")
        symbol_count = store._conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE id LIKE ? AND kind IN ('file','class','function','method','symbol')",
            ("src/engine.py::%",),
        ).fetchone()[0]
        assert len(contains) == 3
        assert len(contains) == symbol_count
        store.close()


class TestPathSeparatorNormalization:
    """Verify forward-slash normalization for Windows compatibility."""

    def test_no_backslash_in_nodes(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        # Simulate what add_file() does: normalize to forward slashes
        store.upsert_node("src/core/engine.cpp", "src/core", "engine.cpp", "file")
        store.commit()

        bs = store._conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE id LIKE '%' || CHAR(92) || '%'"
        ).fetchone()[0]
        assert bs == 0
        store.close()

    def test_no_backslash_in_edges(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a/b/c.cpp", "a/b", "c.cpp", "file")
        store.upsert_node("a/b/d.hpp", "a/b", "d.hpp", "file")
        store.upsert_edge("a/b/c.cpp", "a/b/d.hpp", "import")
        store.commit()

        bs = store._conn.execute(
            "SELECT COUNT(*) FROM edges WHERE source_id LIKE '%' || CHAR(92) || '%' OR target_id LIKE '%' || CHAR(92) || '%'"
        ).fetchone()[0]
        assert bs == 0
        store.close()

    def test_dependents_works_with_normalized_paths(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("src/a.cpp", "src", "a.cpp", "file")
        store.upsert_node("src/b.cpp", "src", "b.cpp", "file")
        store.upsert_edge("src/a.cpp", "src/b.cpp", "import")
        store.commit()

        # Query with forward slash must find the edge
        deps = store.dependents("src/b.cpp")
        assert deps == ["src/a.cpp"]
        store.close()


class TestStatsAccuracy:
    """Verify get_stats accuracy."""

    def test_stats_with_mixed_edge_types(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file")
        store.upsert_node("b.py", "b.py", "b.py", "file")
        store.upsert_node("c.py", "c.py", "c.py", "file")
        store.upsert_edge("a.py", "b.py", "import")
        store.upsert_edge("a.py", "c.py", "call", confidence=0.9)
        store.upsert_edge("b.py", "c.py", "call", confidence=0.0)  # zero conf
        store.commit()

        stats = store.get_stats()
        assert stats["nodes"] == 3
        assert stats["edges"] == 3
        assert stats["resolved_calls"] == 1  # only one with confidence > 0
        store.close()
