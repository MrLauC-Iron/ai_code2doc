"""Shared test fixtures for code2doc-layer3-mcp."""

from __future__ import annotations

from pathlib import Path

import pytest

from code2doc_layer3_mcp.dependency_store import DependencyStore


def _make_store(tmp_path: Path) -> DependencyStore:
    """Create a DependencyStore populated with synthetic test data."""
    db_path = tmp_path / "test.db"
    store = DependencyStore(db_path)

    # File nodes
    for fpath in ["a.py", "b.py", "c.py", "d.py"]:
        store.upsert_node(fpath, fpath, fpath, "file", file_hash="hash_" + fpath)

    # Symbol nodes
    store.upsert_node("a.py::func_a", "a.py", "func_a", "symbol")
    store.upsert_node("b.py::func_b", "b.py", "func_b", "symbol")
    store.upsert_node("c.py::func_c", "c.py", "func_c", "symbol")
    store.upsert_node("d.py::func_d", "d.py", "func_d", "symbol")

    # Import edges
    store.upsert_edge("a.py", "b.py", "import", confidence=1.0)
    store.upsert_edge("a.py", "c.py", "import", confidence=1.0)
    store.upsert_edge("b.py", "d.py", "import", confidence=1.0)
    store.upsert_edge("c.py", "d.py", "import", confidence=1.0)

    # Call edges (varying confidence)
    store.upsert_edge(
        "a.py::func_a", "b.py::func_b", "call",
        confidence=0.95, weight=3, line_number=10,
        caller_name="func_a", callee_name="func_b",
    )
    store.upsert_edge(
        "a.py::func_a", "c.py::func_c", "call",
        confidence=0.85, weight=2, line_number=20,
        caller_name="func_a", callee_name="func_c",
    )
    store.upsert_edge(
        "b.py::func_b", "d.py::func_d", "call",
        confidence=0.70, weight=1, line_number=15,
        caller_name="func_b", callee_name="func_d",
    )
    store.upsert_edge(
        "c.py::func_c", "d.py::func_d", "call",
        confidence=0.90, weight=5, line_number=25,
        caller_name="func_c", callee_name="func_d",
    )
    store.upsert_edge(
        "d.py::func_d", "a.py::func_a", "call",
        confidence=0.60, weight=1, line_number=30,
        caller_name="func_d", callee_name="func_a",
    )

    # Contains edges
    store.upsert_edge("a.py", "a.py::func_a", "contains")
    store.upsert_edge("b.py", "b.py::func_b", "contains")
    store.upsert_edge("c.py", "c.py::func_c", "contains")
    store.upsert_edge("d.py", "d.py::func_d", "contains")

    store.commit()
    return store


@pytest.fixture
def store(tmp_path: Path) -> DependencyStore:
    """Provide a store with synthetic data. Caller must close it."""
    return _make_store(tmp_path)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Provide a db_path with synthetic data already written and closed."""
    s = _make_store(tmp_path)
    path = tmp_path / "test.db"
    s.close()
    return path
