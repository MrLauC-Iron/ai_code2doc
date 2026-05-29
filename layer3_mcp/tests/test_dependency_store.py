"""Tests for DependencyStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from code2doc_layer3_mcp.dependency_store import DependencyStore


class TestUpsertAndGet:
    def test_upsert_and_get_node(self, store: DependencyStore) -> None:
        node = store.get_node("a.py")
        assert node is not None
        assert node["id"] == "a.py"
        assert node["kind"] == "file"
        assert node["file_hash"] == "hash_a.py"

    def test_get_nonexistent_node(self, store: DependencyStore) -> None:
        assert store.get_node("nonexistent.py") is None

    def test_upsert_symbol_node(self, store: DependencyStore) -> None:
        node = store.get_node("a.py::func_a")
        assert node is not None
        assert node["kind"] == "symbol"
        assert node["name"] == "func_a"


class TestGetEdges:
    def test_filter_by_source(self, store: DependencyStore) -> None:
        edges = store.get_edges(source_id="a.py")
        # 2 import + 1 contains = 3 (call edges have source_id="a.py::func_a")
        assert len(edges) == 3

    def test_filter_by_target(self, store: DependencyStore) -> None:
        edges = store.get_edges(target_id="d.py")
        assert len(edges) == 2  # import from b.py, c.py

    def test_filter_by_edge_type(self, store: DependencyStore) -> None:
        import_edges = store.get_edges(edge_type="import")
        call_edges = store.get_edges(edge_type="call")
        assert len(import_edges) == 4
        assert len(call_edges) == 5

    def test_filter_by_confidence(self, store: DependencyStore) -> None:
        edges = store.get_edges(edge_type="call", min_confidence=0.85)
        assert len(edges) == 3  # 0.95, 0.85, 0.90

    def test_combined_filters(self, store: DependencyStore) -> None:
        edges = store.get_edges(
            source_id="a.py::func_a",
            edge_type="call",
            min_confidence=0.80,
        )
        assert len(edges) == 2  # func_b (0.95), func_c (0.85)

    def test_empty_result(self, store: DependencyStore) -> None:
        edges = store.get_edges(source_id="nonexistent")
        assert edges == []


class TestDependentsDependencies:
    def test_dependents(self, store: DependencyStore) -> None:
        deps = store.dependents("b.py")
        assert "a.py" in deps

    def test_dependents_nonexistent(self, store: DependencyStore) -> None:
        deps = store.dependents("nonexistent.py")
        assert deps == []

    def test_dependencies(self, store: DependencyStore) -> None:
        deps = store.dependencies("a.py")
        assert "b.py" in deps
        assert "c.py" in deps

    def test_dependencies_nonexistent(self, store: DependencyStore) -> None:
        deps = store.dependencies("nonexistent.py")
        assert deps == []


class TestCallersCallees:
    def test_callers(self, store: DependencyStore) -> None:
        edges = store.callers("b.py::func_b")
        assert len(edges) == 1
        assert edges[0]["source_id"] == "a.py::func_a"
        assert edges[0]["confidence"] == 0.95

    def test_callers_with_confidence(self, store: DependencyStore) -> None:
        edges = store.callers("d.py::func_d", min_confidence=0.80)
        assert len(edges) == 1  # only func_c (0.90)

    def test_callees(self, store: DependencyStore) -> None:
        edges = store.callees("a.py::func_a")
        assert len(edges) == 2  # func_b and func_c

    def test_callees_with_confidence(self, store: DependencyStore) -> None:
        edges = store.callees("a.py::func_a", min_confidence=0.90)
        assert len(edges) == 1  # only func_b (0.95)

    def test_callers_nonexistent(self, store: DependencyStore) -> None:
        edges = store.callers("nonexistent")
        assert edges == []

    def test_callees_nonexistent(self, store: DependencyStore) -> None:
        edges = store.callees("nonexistent")
        assert edges == []


class TestHotspots:
    def test_hotspots(self, store: DependencyStore) -> None:
        spots = store.hotspots(n=5, min_confidence=0.0)
        assert len(spots) == 4  # func_d (2 calls), func_b, func_c, func_a (1 each)
        assert spots[0]["target_id"] == "d.py::func_d"
        assert spots[0]["call_count"] == 2  # COUNT(*) = 2 rows

    def test_hotspots_with_confidence(self, store: DependencyStore) -> None:
        spots = store.hotspots(n=10, min_confidence=0.80)
        targets = [s["target_id"] for s in spots]
        assert "d.py::func_d" in targets
        # func_d is called with 0.70 and 0.90 — only 0.90 qualifies
        # func_b is called with 0.95 — qualifies
        # func_c is called with 0.85 — qualifies
        # func_a is called with 0.60 — doesn't qualify

    def test_hotspots_empty(self, store: DependencyStore) -> None:
        spots = store.hotspots(n=10, min_confidence=1.0)
        # No edges with confidence >= 1.0 (import edges are 1.0 but edge_type=call)
        assert spots == []


class TestStats:
    def test_stats(self, store: DependencyStore) -> None:
        stats = store.get_stats()
        assert stats["nodes"] == 8  # 4 files + 4 symbols
        assert stats["edges"] == 13  # 4 import + 5 call + 4 contains
        assert stats["resolved_calls"] == 5  # all call edges


class TestMetadata:
    def test_set_and_get_metadata(self, store: DependencyStore) -> None:
        store.set_metadata("key1", "value1")
        assert store.get_metadata("key1") == "value1"
        assert store.get_metadata("nonexistent") is None
