"""Comprehensive tests for DependencyStore."""

from __future__ import annotations

import json
from pathlib import Path

from ai_code2doc.analyzer.dependency_store import DependencyStore


class TestDependencyStoreInit:
    def test_init_creates_tables(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        store = DependencyStore(db)
        # Query sqlite_master to confirm tables exist
        tables = {
            row[0]
            for row in store._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "nodes" in tables
        assert "edges" in tables
        assert "metadata" in tables
        store.close()

        # Verify indexes exist
        store = DependencyStore(db)
        indexes = {
            row[0]
            for row in store._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            ).fetchall()
        }
        assert "idx_edges_source" in indexes
        assert "idx_edges_target" in indexes
        assert "idx_edges_type" in indexes
        assert "idx_nodes_kind" in indexes
        assert "idx_nodes_path" in indexes
        store.close()


class TestUpsertNode:
    def test_upsert_node(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("src/main.py", "src/main.py", "main.py", "file", "abc123")
        store.commit()
        node = store.get_node("src/main.py")
        assert node is not None
        assert node["name"] == "main.py"
        assert node["kind"] == "file"
        assert node["file_hash"] == "abc123"
        store.close()

    def test_upsert_node_update(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("src/main.py", "src/main.py", "main.py", "file", "hash1")
        store.commit()

        # Update with new data
        store.upsert_node("src/main.py", "src/main.py", "main.py", "file", "hash2")
        store.commit()
        node = store.get_node("src/main.py")
        assert node is not None
        assert node["file_hash"] == "hash2"
        store.close()


class TestUpsertEdge:
    def test_upsert_edge(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        # Create source and target nodes first (FK constraint)
        store.upsert_node("a.py", "a.py", "a.py", "file")
        store.upsert_node("b.py", "b.py", "b.py", "file")
        store.upsert_edge("a.py", "b.py", "import", confidence=0.9, weight=1)
        store.commit()
        edges = store.get_edges()
        assert len(edges) == 1
        assert edges[0]["source_id"] == "a.py"
        assert edges[0]["target_id"] == "b.py"
        assert edges[0]["edge_type"] == "import"
        assert edges[0]["confidence"] == 0.9
        store.close()


class TestGetEdgesWithFilters:
    def test_get_edges_with_filters(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        for name in ("a.py", "b.py", "c.py"):
            store.upsert_node(name, name, name, "file")
        store.upsert_edge("a.py", "b.py", "import", confidence=0.5)
        store.upsert_edge("a.py", "c.py", "call", confidence=0.8, caller_name="run", callee_name="do_stuff")
        store.upsert_edge("b.py", "c.py", "import", confidence=0.3)
        store.commit()

        # Filter by source
        assert len(store.get_edges(source_id="a.py")) == 2

        # Filter by target
        assert len(store.get_edges(target_id="c.py")) == 2

        # Filter by edge_type
        assert len(store.get_edges(edge_type="import")) == 2

        # Filter by min_confidence
        assert len(store.get_edges(min_confidence=0.6)) == 1

        # Combined filters
        assert len(store.get_edges(source_id="a.py", edge_type="call")) == 1
        store.close()


class TestDeleteEdgesForFile:
    def test_delete_edges_for_file(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        for name in ("src/a.py", "src/a.py::func1", "other/b.py"):
            store.upsert_node(name, name, name, "file" if "::" not in name else "function")
        store.upsert_edge("src/a.py", "other/b.py", "import")
        store.upsert_edge("src/a.py::func1", "other/b.py", "call")
        store.upsert_edge("other/b.py", "src/a.py", "import")
        store.commit()

        assert len(store.get_edges()) == 3
        store.delete_edges_for_file("src/a.py")
        store.commit()
        assert len(store.get_edges()) == 0
        store.close()


class TestDeleteSymbolNodesForFile:
    def test_delete_symbol_nodes_for_file(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("src/a.py", "src/a.py", "a.py", "file")
        store.upsert_node("src/a.py:: MyClass", "src/a.py", "MyClass", "class")
        store.upsert_node("src/a.py:: run", "src/a.py", "run", "function")
        store.commit()

        assert store.get_node("src/a.py") is not None
        assert store.get_node("src/a.py:: MyClass") is not None
        assert store.get_node("src/a.py:: run") is not None

        store.delete_symbol_nodes_for_file("src/a.py")
        store.commit()

        # File node must remain
        assert store.get_node("src/a.py") is not None
        # Symbol nodes must be gone
        assert store.get_node("src/a.py:: MyClass") is None
        assert store.get_node("src/a.py:: run") is None
        store.close()


class TestDependents:
    def test_dependents(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        for name in ("a.py", "b.py", "c.py", "utils.py"):
            store.upsert_node(name, name, name, "file")
        store.upsert_edge("a.py", "utils.py", "import")
        store.upsert_edge("b.py", "utils.py", "import")
        store.upsert_edge("c.py", "utils.py", "call")
        store.commit()

        deps = store.dependents("utils.py")
        assert sorted(deps) == ["a.py", "b.py", "c.py"]
        store.close()


class TestDependencies:
    def test_dependencies(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        for name in ("app.py", "db.py", "config.py", "log.py"):
            store.upsert_node(name, name, name, "file")
        store.upsert_edge("app.py", "db.py", "import")
        store.upsert_edge("app.py", "config.py", "import")
        store.upsert_edge("app.py", "log.py", "call")
        store.commit()

        deps = store.dependencies("app.py")
        assert sorted(deps) == ["config.py", "db.py", "log.py"]
        store.close()


class TestCallers:
    def test_callers(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file")
        store.upsert_node("b.py", "b.py", "b.py", "file")
        store.upsert_node("c.py", "c.py", "c.py", "file")
        store.upsert_node("helper", "utils.py", "helper", "function")
        store.upsert_edge("a.py", "helper", "call", confidence=0.7)
        store.upsert_edge("b.py", "helper", "call", confidence=0.4)
        store.upsert_edge("c.py", "helper", "import")  # import, not call
        store.commit()

        all_callers = store.callers("helper")
        assert len(all_callers) == 2

        filtered = store.callers("helper", min_confidence=0.6)
        assert len(filtered) == 1
        assert filtered[0]["source_id"] == "a.py"
        store.close()


class TestCallees:
    def test_callees(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("app.py", "app.py", "app.py", "file")
        store.upsert_node("db.py", "db.py", "db.py", "file")
        store.upsert_node("log.py", "log.py", "log.py", "file")
        store.upsert_edge("app.py", "db.py", "call", confidence=0.9)
        store.upsert_edge("app.py", "log.py", "call", confidence=0.3)
        store.commit()

        all_callees = store.callees("app.py")
        assert len(all_callees) == 2

        filtered = store.callees("app.py", min_confidence=0.5)
        assert len(filtered) == 1
        assert filtered[0]["target_id"] == "db.py"
        store.close()


class TestHotspots:
    def test_hotspots(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file")
        store.upsert_node("b.py", "b.py", "b.py", "file")
        store.upsert_node("c.py", "c.py", "c.py", "file")
        store.upsert_node("common:: util", "common.py", "util", "function")
        store.upsert_node("common:: log", "common.py", "log", "function")

        # util is called 4 times, log 2 times
        store.upsert_edge("a.py", "common:: util", "call")
        store.upsert_edge("b.py", "common:: util", "call")
        store.upsert_edge("c.py", "common:: util", "call")
        store.upsert_edge("a.py", "common:: log", "call")
        store.upsert_edge("b.py", "common:: log", "call")
        store.upsert_edge("c.py", "common:: log", "call", confidence=0.1)
        store.commit()

        spots = store.hotspots(n=10)
        # With min_confidence=0.0, util and log each have 3 calls
        assert len(spots) == 2
        assert spots[0]["target_id"] == "common:: util"  # tie -- either order
        assert spots[0]["call_count"] == 3

        # Filter by confidence
        spots_high = store.hotspots(n=10, min_confidence=0.5)
        assert len(spots_high) == 2
        util_spot = [s for s in spots_high if s["target_id"] == "common:: util"][0]
        log_spot = [s for s in spots_high if s["target_id"] == "common:: log"][0]
        assert util_spot["call_count"] == 3
        assert log_spot["call_count"] == 2
        store.close()


class TestGetStats:
    def test_get_stats(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file")
        store.upsert_node("b.py", "b.py", "b.py", "file")
        store.upsert_edge("a.py", "b.py", "import")
        store.upsert_edge("a.py", "b.py", "call", confidence=0.8)
        store.commit()

        stats = store.get_stats()
        assert stats["nodes"] == 2
        assert stats["edges"] == 2
        assert stats["resolved_calls"] == 1
        store.close()


class TestSetGetMetadata:
    def test_set_get_metadata(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        assert store.get_metadata("project_root") is None
        store.set_metadata("project_root", "/home/user/project")
        store.commit()
        assert store.get_metadata("project_root") == "/home/user/project"

        # Update existing key
        store.set_metadata("project_root", "/new/path")
        store.commit()
        assert store.get_metadata("project_root") == "/new/path"
        store.close()


class TestGetChangedFiles:
    def test_get_changed_files(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file", "hash1")
        store.upsert_node("b.py", "b.py", "b.py", "file", "hash2")
        store.upsert_node("c.py", "c.py", "c.py", "file")
        store.commit()

        current = {"a.py": "hash1", "b.py": "hash2_updated", "d.py": "hash_new"}
        changed, deleted = store.get_changed_files(current)

        # b.py changed, d.py is new (treated as changed)
        assert "b.py" in changed
        assert "d.py" in changed
        assert "a.py" not in changed

        # c.py was deleted (exists in store, not in current)
        assert "c.py" in deleted
        store.close()


class TestExportJson:
    def test_export_json(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        store.upsert_node("a.py", "a.py", "a.py", "file", "h1")
        store.upsert_node("b.py", "b.py", "b.py", "file", "h2")
        store.upsert_edge("a.py", "b.py", "import", confidence=0.5)
        store.commit()

        out = tmp_path / "export.json"
        store.export_json(out)
        store.close()

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["version"] == "2.0"
        assert "generated_at" in data
        assert data["stats"]["nodes"] == 2
        assert data["stats"]["edges"] == 1
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1


class TestImportJsonRoundtrip:
    def test_import_json_roundtrip(self, tmp_path: Path) -> None:
        db1 = tmp_path / "db1.sqlite"
        db2 = tmp_path / "db2.sqlite"
        export_file = tmp_path / "export.json"

        # Populate first store
        store1 = DependencyStore(db1)
        store1.upsert_node("x.py", "x.py", "x.py", "file", "hx")
        store1.upsert_node("y.py", "y.py", "y.py", "file", "hy")
        store1.upsert_node("x.py:: foo", "x.py", "foo", "function")
        store1.upsert_edge("x.py", "y.py", "import", confidence=0.7)
        store1.upsert_edge("x.py:: foo", "y.py", "call", confidence=0.9, caller_name="foo", callee_name="bar", line_number=10)
        store1.set_metadata("key1", "val1")
        store1.commit()
        store1.export_json(export_file)
        stats1 = store1.get_stats()
        store1.close()

        # Import into second store
        store2 = DependencyStore(db2)
        store2.import_json(export_file)

        # Verify data matches
        assert store2.get_node("x.py") is not None
        assert store2.get_node("x.py")["file_hash"] == "hx"
        assert store2.get_node("y.py") is not None
        assert store2.get_node("x.py:: foo") is not None

        edges = store2.get_edges()
        assert len(edges) == 2
        call_edges = store2.get_edges(edge_type="call")
        assert len(call_edges) == 1
        assert call_edges[0]["caller_name"] == "foo"
        assert call_edges[0]["callee_name"] == "bar"
        assert call_edges[0]["line_number"] == 10

        stats2 = store2.get_stats()
        assert stats2 == stats1
        store2.close()


class TestGenerateModuleSummaries:
    def test_generate_module_summaries(self, tmp_path: Path) -> None:
        store = DependencyStore(tmp_path / "test.db")
        # Create files in two modules: src/core/ and src/utils/
        files = [
            "src/core/engine.py",
            "src/core/parser.py",
            "src/utils/helpers.py",
        ]
        for f in files:
            store.upsert_node(f, f, Path(f).name, "file")

        # engine.py imports helpers.py
        store.upsert_edge("src/core/engine.py", "src/utils/helpers.py", "import")
        # parser.py imports helpers.py
        store.upsert_edge("src/core/parser.py", "src/utils/helpers.py", "import")
        # engine.py calls a function in parser.py
        store.upsert_node("src/core/parser.py:: parse", "src/core/parser.py", "parse", "function")
        store.upsert_edge("src/core/engine.py", "src/core/parser.py:: parse", "call")
        store.commit()

        summaries = DependencyStore.generate_module_summaries(store)

        # Should have 2 module summaries: src/core and src/utils
        module_ids = {s["id"] for s in summaries}
        assert "src/core" in module_ids
        assert "src/utils" in module_ids

        core_summary = next(s for s in summaries if s["id"] == "src/core")
        utils_summary = next(s for s in summaries if s["id"] == "src/utils")

        assert core_summary["metadata"]["file_count"] == 2
        assert utils_summary["metadata"]["file_count"] == 1
        assert core_summary["metadata"]["call_edge_count"] == 1

        store.close()
