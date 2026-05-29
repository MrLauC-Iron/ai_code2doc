"""SQLite-backed storage layer for the dependency graph."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DependencyStore:
    """Persistent SQLite store for dependency graph nodes and edges."""

    def __init__(self, db_path: str | Path) -> None:
        """Open (or create) the database and initialise the schema."""
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id         TEXT PRIMARY KEY,
                path       TEXT,
                name       TEXT,
                kind       TEXT NOT NULL CHECK(kind IN ('file','class','function','method','symbol')),
                file_hash  TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS edges (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id   TEXT NOT NULL,
                target_id   TEXT NOT NULL,
                edge_type   TEXT NOT NULL CHECK(edge_type IN ('import','call','contains')),
                confidence  REAL NOT NULL DEFAULT 1.0,
                weight      INTEGER NOT NULL DEFAULT 1,
                line_number INTEGER,
                caller_name TEXT,
                callee_name TEXT,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES nodes(id),
                FOREIGN KEY (target_id) REFERENCES nodes(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        # Indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_type   ON edges(edge_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_kind   ON nodes(kind)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_path   ON nodes(path)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def upsert_node(
        self,
        node_id: str,
        path: str | Path,
        name: str,
        kind: str,
        file_hash: str | None = None,
    ) -> None:
        """Insert or update a node."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO nodes (id, path, name, kind, file_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                path      = excluded.path,
                name      = excluded.name,
                kind      = excluded.kind,
                file_hash = excluded.file_hash,
                updated_at = excluded.updated_at
            """,
            (node_id, str(path), name, kind, file_hash, now, now),
        )

    def upsert_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        confidence: float = 1.0,
        weight: int = 1,
        line_number: int | None = None,
        caller_name: str | None = None,
        callee_name: str | None = None,
    ) -> None:
        """Insert a new edge (no upsert -- duplicates are allowed)."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO edges (source_id, target_id, edge_type, confidence,
                               weight, line_number, caller_name, callee_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                target_id,
                edge_type,
                confidence,
                weight,
                line_number,
                caller_name,
                callee_name,
                now,
            ),
        )

    def delete_edges_for_file(self, file_path: str | Path) -> None:
        """Delete all edges where source or target starts with *file_path*."""
        prefix = str(file_path) + "%"
        self._conn.execute(
            "DELETE FROM edges WHERE source_id LIKE ? OR target_id LIKE ?",
            (prefix, prefix),
        )

    def delete_symbol_nodes_for_file(self, file_path: str | Path) -> None:
        """Delete non-file nodes whose id starts with ``file_path::``."""
        prefix = str(file_path) + "::%"
        self._conn.execute(
            "DELETE FROM nodes WHERE id LIKE ? AND kind != 'file'",
            (prefix,),
        )

    def commit(self) -> None:
        """Commit pending transactions."""
        self._conn.commit()

    def set_metadata(self, key: str, value: str) -> None:
        """Store a metadata key/value pair."""
        self._conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            (key, value),
        )

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Return a single node as a dict, or ``None``."""
        row = self._conn.execute(
            "SELECT * FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_edges(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        edge_type: str | None = None,
        min_confidence: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Return edges matching the given filters."""
        clauses: list[str] = []
        params: list[Any] = []

        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if target_id is not None:
            clauses.append("target_id = ?")
            params.append(target_id)
        if edge_type is not None:
            clauses.append("edge_type = ?")
            params.append(edge_type)
        clauses.append("confidence >= ?")
        params.append(min_confidence)

        where = " AND ".join(clauses)
        rows = self._conn.execute(
            f"SELECT * FROM edges WHERE {where}", params
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics for the stored graph."""
        nodes = self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        edges = self._conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        resolved = self._conn.execute(
            "SELECT COUNT(*) FROM edges WHERE edge_type = 'call' AND confidence > 0"
        ).fetchone()[0]
        return {"nodes": nodes, "edges": edges, "resolved_calls": resolved}

    def get_metadata(self, key: str) -> str | None:
        """Return a metadata value or ``None``."""
        row = self._conn.execute(
            "SELECT value FROM metadata WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def dependents(self, target_id: str) -> list[str]:
        """Return distinct source IDs that depend on *target_id*."""
        rows = self._conn.execute(
            "SELECT DISTINCT source_id FROM edges WHERE target_id = ?",
            (target_id,),
        ).fetchall()
        return [r["source_id"] for r in rows]

    def dependencies(self, source_id: str) -> list[str]:
        """Return distinct target IDs that *source_id* depends on."""
        rows = self._conn.execute(
            "SELECT DISTINCT target_id FROM edges WHERE source_id = ?",
            (source_id,),
        ).fetchall()
        return [r["target_id"] for r in rows]

    def callers(
        self, target_id: str, min_confidence: float = 0.0
    ) -> list[dict[str, Any]]:
        """Return call edges where *target_id* is the callee."""
        rows = self._conn.execute(
            "SELECT * FROM edges WHERE target_id = ? AND edge_type = 'call' AND confidence >= ?",
            (target_id, min_confidence),
        ).fetchall()
        return [dict(r) for r in rows]

    def callees(
        self, source_id: str, min_confidence: float = 0.0
    ) -> list[dict[str, Any]]:
        """Return call edges where *source_id* is the caller."""
        rows = self._conn.execute(
            "SELECT * FROM edges WHERE source_id = ? AND edge_type = 'call' AND confidence >= ?",
            (source_id, min_confidence),
        ).fetchall()
        return [dict(r) for r in rows]

    def hotspots(
        self, n: int = 20, min_confidence: float = 0.0
    ) -> list[dict[str, Any]]:
        """Return the *n* most-called targets ordered by call count."""
        rows = self._conn.execute(
            """
            SELECT target_id, COUNT(*) AS call_count
            FROM edges
            WHERE edge_type = 'call' AND confidence >= ?
            GROUP BY target_id
            ORDER BY call_count DESC
            LIMIT ?
            """,
            (min_confidence, n),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Incremental update
    # ------------------------------------------------------------------

    def get_changed_files(
        self, current_hashes: dict[str, str]
    ) -> tuple[list[str], list[str]]:
        """Compare *current_hashes* with stored file hashes.

        Returns ``(changed, deleted)`` where *changed* is a list of file
        paths whose hash differs from the stored value, and *deleted* is a
        list of file paths that exist in the store but not in
        *current_hashes*.
        """
        stored: dict[str, str] = {}
        all_file_ids: set[str] = set()
        for row in self._conn.execute(
            "SELECT id, file_hash FROM nodes WHERE kind = 'file'"
        ).fetchall():
            all_file_ids.add(row["id"])
            if row["file_hash"] is not None:
                stored[row["id"]] = row["file_hash"]

        changed: list[str] = []
        for fpath, fhash in current_hashes.items():
            if stored.get(fpath) != fhash:
                changed.append(fpath)

        deleted: list[str] = [
            fpath for fpath in all_file_ids if fpath not in current_hashes
        ]
        return changed, deleted

    # ------------------------------------------------------------------
    # JSON export / import
    # ------------------------------------------------------------------

    def export_json(self, path: str | Path) -> None:
        """Export the full store to a JSON file."""
        data: dict[str, Any] = {
            "version": "2.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stats": self.get_stats(),
            "nodes": [dict(r) for r in self._conn.execute("SELECT * FROM nodes").fetchall()],
            "edges": [dict(r) for r in self._conn.execute("SELECT * FROM edges").fetchall()],
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def import_json(self, path: str | Path) -> None:
        """Clear the store and re-import from a JSON file."""
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)

        # Clear existing data
        self._conn.execute("DELETE FROM edges")
        self._conn.execute("DELETE FROM nodes")
        self._conn.execute("DELETE FROM metadata")

        for node in data.get("nodes", []):
            self._conn.execute(
                """
                INSERT INTO nodes (id, path, name, kind, file_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node["id"],
                    node["path"],
                    node["name"],
                    node["kind"],
                    node.get("file_hash"),
                    node["created_at"],
                    node["updated_at"],
                ),
            )

        for edge in data.get("edges", []):
            self._conn.execute(
                """
                INSERT INTO edges (source_id, target_id, edge_type, confidence,
                                   weight, line_number, caller_name, callee_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge["source_id"],
                    edge["target_id"],
                    edge["edge_type"],
                    edge.get("confidence", 1.0),
                    edge.get("weight", 1),
                    edge.get("line_number"),
                    edge.get("caller_name"),
                    edge.get("callee_name"),
                    edge["created_at"],
                ),
            )

        self._conn.commit()

    # ------------------------------------------------------------------
    # Module summary generation
    # ------------------------------------------------------------------

    @staticmethod
    def generate_module_summaries(store: DependencyStore) -> list[dict[str, Any]]:
        """Generate a summary dict for each parent-directory module.

        Each summary contains keys ``id``, ``content``, and ``metadata``.
        """
        nodes_rows = store._conn.execute("SELECT * FROM nodes WHERE kind = 'file'").fetchall()
        edges_rows = store._conn.execute(
            "SELECT * FROM edges WHERE edge_type = 'import'"
        ).fetchall()
        call_rows = store._conn.execute(
            "SELECT * FROM edges WHERE edge_type = 'call'"
        ).fetchall()

        # Group files by parent directory (module)
        file_set: set[str] = {r["id"] for r in nodes_rows}
        modules: dict[str, list[str]] = defaultdict(list)
        for r in nodes_rows:
            parent = str(Path(r["id"]).parent).replace("\\", "/")
            modules[parent].append(r["id"])

        # Build import adjacency
        import_out: dict[str, list[str]] = defaultdict(list)
        import_in: dict[str, list[str]] = defaultdict(list)
        for r in edges_rows:
            src, tgt = r["source_id"], r["target_id"]
            if tgt in file_set:
                import_in[tgt].append(src)
            if src in file_set:
                import_out[src].append(tgt)

        # Build call adjacency
        call_out: dict[str, list[str]] = defaultdict(list)
        call_in: dict[str, list[str]] = defaultdict(list)
        for r in call_rows:
            src, tgt = r["source_id"], r["target_id"]
            call_out[src].append(tgt)
            call_in[tgt].append(src)

        summaries: list[dict[str, Any]] = []
        for module_path, files in modules.items():
            top_deps: list[str] = []
            top_dependents: list[str] = []
            call_edge_count = 0

            for f in files:
                top_deps.extend(import_out.get(f, []))
                top_dependents.extend(import_in.get(f, []))
                call_edge_count += len(call_out.get(f, []))

            # Deduplicate while preserving order
            seen_deps: set[str] = set()
            unique_deps: list[str] = []
            for d in top_deps:
                if d not in seen_deps:
                    seen_deps.add(d)
                    unique_deps.append(d)

            seen_in: set[str] = set()
            unique_in: list[str] = []
            for d in top_dependents:
                if d not in seen_in:
                    seen_in.add(d)
                    unique_in.append(d)

            summaries.append(
                {
                    "id": module_path,
                    "content": f"Module {module_path} with {len(files)} files",
                    "metadata": {
                        "file_count": len(files),
                        "files": files,
                        "top_dependencies": unique_deps[:10],
                        "top_dependents": unique_in[:10],
                        "call_edge_count": call_edge_count,
                    },
                }
            )

        return summaries
