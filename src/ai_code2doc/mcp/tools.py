"""MCP tool definitions that wrap DependencyStore queries.

Defines ten tools for exploring dependency graphs via the Model Context
Protocol: dependents, dependencies, callers, callees, hotspots, subgraph,
impact, path, stats, and get_edges.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any, Callable

from ai_code2doc.analyzer.dependency_store import DependencyStore


# ======================================================================
# Helper
# ======================================================================

def _open_store(db_path: str | Path) -> DependencyStore:
    """Open a DependencyStore at *db_path*."""
    return DependencyStore(db_path)


# ======================================================================
# Handler functions
# ======================================================================

def _handle_dependents(db_path: str | Path, **kwargs: Any) -> str:
    """Return modules that depend on the given target.

    Parameters
    ----------
    db_path:
        Path to the SQLite dependency database.
    target:
        Target file or symbol path.
    """
    target: str = kwargs["target"]
    store = _open_store(db_path)
    try:
        result = store.dependents(target)
    finally:
        store.close()
    if not result:
        return f"No modules depend on '{target}'."
    lines = [f"Modules that depend on '{target}':"]
    for mod in result:
        lines.append(f"  - {mod}")
    return "\n".join(lines)


def _handle_dependencies(db_path: str | Path, **kwargs: Any) -> str:
    """Return modules that the given target depends on.

    Parameters
    ----------
    db_path:
        Path to the SQLite dependency database.
    target:
        Target file or symbol path.
    """
    target: str = kwargs["target"]
    store = _open_store(db_path)
    try:
        result = store.dependencies(target)
    finally:
        store.close()
    if not result:
        return f"'{target}' has no dependencies."
    lines = [f"Dependencies of '{target}':"]
    for mod in result:
        lines.append(f"  - {mod}")
    return "\n".join(lines)


def _handle_callers(db_path: str | Path, **kwargs: Any) -> str:
    """Return call edges where the target symbol is the callee.

    Parameters
    ----------
    db_path:
        Path to the SQLite dependency database.
    target:
        Target symbol fully-qualified name (FQN).
    confidence_threshold:
        Minimum confidence score (default 0.80).
    """
    target: str = kwargs["target"]
    threshold: float = kwargs.get("confidence_threshold", 0.80)
    store = _open_store(db_path)
    try:
        edges = store.callers(target, min_confidence=threshold)
    finally:
        store.close()
    if not edges:
        return f"No callers found for '{target}' with confidence >= {threshold:.2f}."
    lines = [f"Callers of '{target}' (confidence >= {threshold:.2f}):"]
    for e in edges:
        conf_pct = f"{e['confidence']:.0%}"
        line_info = f"line {e['line_number']}" if e.get("line_number") else "unknown line"
        lines.append(f"  - {e['source_id']} ({line_info}, confidence {conf_pct})")
    return "\n".join(lines)


def _handle_callees(db_path: str | Path, **kwargs: Any) -> str:
    """Return call edges where the source symbol is the caller.

    Parameters
    ----------
    db_path:
        Path to the SQLite dependency database.
    target:
        Caller symbol fully-qualified name (FQN).
    confidence_threshold:
        Minimum confidence score (default 0.80).
    """
    target: str = kwargs["target"]
    threshold: float = kwargs.get("confidence_threshold", 0.80)
    store = _open_store(db_path)
    try:
        edges = store.callees(target, min_confidence=threshold)
    finally:
        store.close()
    if not edges:
        return f"No callees found for '{target}' with confidence >= {threshold:.2f}."
    lines = [f"Callees of '{target}' (confidence >= {threshold:.2f}):"]
    for e in edges:
        conf_pct = f"{e['confidence']:.0%}"
        line_info = f"line {e['line_number']}" if e.get("line_number") else "unknown line"
        lines.append(f"  - {e['target_id']} ({line_info}, confidence {conf_pct})")
    return "\n".join(lines)


def _handle_hotspots(db_path: str | Path, **kwargs: Any) -> str:
    """Return the most-called symbols (hotspots).

    Parameters
    ----------
    db_path:
        Path to the SQLite dependency database.
    top_n:
        Number of results to return (default 20).
    confidence_threshold:
        Minimum confidence score (default 0.75).
    """
    top_n: int = kwargs.get("top_n", 20)
    threshold: float = kwargs.get("confidence_threshold", 0.75)
    store = _open_store(db_path)
    try:
        spots = store.hotspots(n=top_n, min_confidence=threshold)
    finally:
        store.close()
    if not spots:
        return f"No hotspots found with confidence >= {threshold:.2f}."
    lines = [f"Top {len(spots)} hotspots (confidence >= {threshold:.2f}):"]
    for i, s in enumerate(spots, 1):
        lines.append(f"  {i}. {s['target_id']} ({s['call_count']} calls)")
    return "\n".join(lines)


def _handle_subgraph(db_path: str | Path, **kwargs: Any) -> str:
    """Show the internal structure (edges) of one or more files.

    Parameters
    ----------
    db_path:
        Path to the SQLite dependency database.
    target:
        A single file path.
    files:
        Comma-separated list of file paths (optional; takes precedence over
        *target* when provided).
    """
    files_str: str | None = kwargs.get("files")
    target: str | None = kwargs.get("target")

    if files_str:
        file_list = [f.strip() for f in files_str.split(",") if f.strip()]
    elif target:
        file_list = [target]
    else:
        return "No target or files specified."

    store = _open_store(db_path)
    try:
        all_lines: list[str] = []
        for fpath in file_list:
            all_lines.append(f"=== {fpath} ===")
            # Get 'contains' edges (file -> symbol)
            contains = store.get_edges(source_id=fpath, edge_type="contains")
            # Get all edges touching this file
            all_edges = store.get_edges(source_id=fpath)
            if not contains and not all_edges:
                all_lines.append("  (no edges found)")
                continue
            for e in all_edges:
                src = e["source_id"]
                tgt = e["target_id"]
                etype = e["edge_type"]
                all_lines.append(f"  {src} --[{etype}]--> {tgt}")
    finally:
        store.close()
    return "\n".join(all_lines)


def _handle_impact(db_path: str | Path, **kwargs: Any) -> str:
    """Impact analysis: which modules are affected if *target* changes.

    Performs BFS through dependents up to the given depth and assesses risk.

    Parameters
    ----------
    db_path:
        Path to the SQLite dependency database.
    target:
        Module to analyse.
    depth:
        Maximum BFS depth (default 3).
    """
    target: str = kwargs["target"]
    depth: int = kwargs.get("depth", 3)
    store = _open_store(db_path)
    try:
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque()
        queue.append((target, 0))
        visited.add(target)

        while queue:
            current, d = queue.popleft()
            if d >= depth:
                continue
            for dep in store.dependents(current):
                if dep not in visited:
                    visited.add(dep)
                    queue.append((dep, d + 1))
    finally:
        store.close()

    # Exclude the target itself from affected count
    affected = sorted(visited - {target})
    count = len(affected)

    if count == 0:
        risk = "low"
    elif count <= 5:
        risk = "medium"
    else:
        risk = "high"

    lines = [
        f"Impact analysis for '{target}' (depth={depth}):",
        f"  Risk level: {risk}",
        f"  Affected modules ({count}):",
    ]
    for mod in affected:
        lines.append(f"    - {mod}")
    return "\n".join(lines)


def _handle_path(db_path: str | Path, **kwargs: Any) -> str:
    """Find the shortest dependency path between two modules.

    Uses bidirectional BFS via ``dependencies`` and ``dependents``.  The
    search is capped at 10 hops to avoid runaway traversal.

    Parameters
    ----------
    db_path:
        Path to the SQLite dependency database.
    target:
        Start node.
    end:
        End node.
    """
    start: str = kwargs["target"]
    end: str = kwargs["end"]

    if start == end:
        return f"Path: {start} (start and end are the same)."

    max_depth = 10

    store = _open_store(db_path)
    try:
        # Forward BFS from start using dependencies()
        fwd_visited: dict[str, str | None] = {start: None}
        fwd_queue: deque[str] = deque([start])

        # Backward BFS from end using dependents()
        bwd_visited: dict[str, str | None] = {end: None}
        bwd_queue: deque[str] = deque([end])

        meeting: str | None = None

        for _ in range(max_depth):
            if not fwd_queue and not bwd_queue:
                break

            # Expand forward one level
            next_fwd: deque[str] = deque()
            while fwd_queue:
                current = fwd_queue.popleft()
                for neighbour in store.dependencies(current):
                    if neighbour not in fwd_visited:
                        fwd_visited[neighbour] = current
                        if neighbour in bwd_visited:
                            meeting = neighbour
                            break
                        next_fwd.append(neighbour)
                if meeting:
                    break
            fwd_queue = next_fwd

            if meeting:
                break

            # Expand backward one level
            next_bwd: deque[str] = deque()
            while bwd_queue:
                current = bwd_queue.popleft()
                for neighbour in store.dependents(current):
                    if neighbour not in bwd_visited:
                        bwd_visited[neighbour] = current
                        if neighbour in fwd_visited:
                            meeting = neighbour
                            break
                        next_bwd.append(neighbour)
                if meeting:
                    break
            bwd_queue = next_bwd
    finally:
        store.close()

    if meeting is None:
        return "No path found."

    # Reconstruct path: start -> ... -> meeting -> ... -> end
    fwd_path: list[str] = []
    node: str | None = meeting
    while node is not None:
        fwd_path.append(node)
        node = fwd_visited[node]
    fwd_path.reverse()

    bwd_path: list[str] = []
    node = bwd_visited[meeting]
    while node is not None:
        bwd_path.append(node)
        node = bwd_visited[node]

    full_path = fwd_path + bwd_path
    return "Path: " + " -> ".join(full_path)


def _handle_stats(db_path: str | Path, **kwargs: Any) -> str:  # noqa: ARG001
    """Return summary statistics for the dependency graph.

    Parameters
    ----------
    db_path:
        Path to the SQLite dependency database.
    """
    store = _open_store(db_path)
    try:
        stats = store.get_stats()
        edges_by_type = {}
        for etype in ("import", "call", "contains"):
            edges_by_type[etype] = len(store.get_edges(edge_type=etype))
    finally:
        store.close()

    lines = [
        "Dependency Graph Statistics",
        "===========================",
        f"  Nodes:             {stats['nodes']}",
        f"  Total edges:       {stats['edges']}",
        f"  Resolved calls:    {stats['resolved_calls']}",
        "",
        "  Edges by type:",
    ]
    for etype, count in edges_by_type.items():
        lines.append(f"    {etype}:  {count}")
    return "\n".join(lines)


def _handle_get_edges(db_path: str | Path, **kwargs: Any) -> str:
    """Raw edge query with optional filters.

    Parameters
    ----------
    db_path:
        Path to the SQLite dependency database.
    source_id:
        Filter by source node ID (optional).
    target_id:
        Filter by target node ID (optional).
    edge_type:
        Filter by edge type, e.g. 'import', 'call', 'contains' (optional).
    min_confidence:
        Minimum confidence score (default 0.0).
    """
    source_id: str | None = kwargs.get("source_id")
    target_id: str | None = kwargs.get("target_id")
    edge_type: str | None = kwargs.get("edge_type")
    min_confidence: float = kwargs.get("min_confidence", 0.0)

    store = _open_store(db_path)
    try:
        edges = store.get_edges(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            min_confidence=min_confidence,
        )
    finally:
        store.close()

    if not edges:
        filters = []
        if source_id:
            filters.append(f"source_id={source_id}")
        if target_id:
            filters.append(f"target_id={target_id}")
        if edge_type:
            filters.append(f"edge_type={edge_type}")
        filters.append(f"min_confidence={min_confidence}")
        return f"No edges found ({', '.join(filters)})."

    lines = [f"Found {len(edges)} edges:"]
    for e in edges:
        conf = f"{e['confidence']:.2f}"
        weight = e.get("weight", 1)
        line_info = f", line {e['line_number']}" if e.get("line_number") else ""
        lines.append(
            f"  {e['source_id']} --[{e['edge_type']}]--> {e['target_id']} "
            f"(confidence={conf}, weight={weight}{line_info})"
        )
    return "\n".join(lines)


# ======================================================================
# Tool registration
# ======================================================================

def _make_handler(
    handler: Callable[..., str], db_path: str | Path
) -> Callable[..., str]:
    """Wrap a handler so it receives *db_path* automatically."""

    def wrapper(**kwargs: Any) -> str:
        return handler(db_path=db_path, **kwargs)

    return wrapper


def register_all_tools(
    server: Any, db_path: str | Path
) -> None:
    """Register all ten dependency-graph tools on an MCPServer instance.

    Parameters
    ----------
    server:
        An object with a ``register_tool(name, description, input_schema,
        handler)`` method.
    db_path:
        Path to the SQLite dependency database used by all tools.
    """
    tools: list[tuple[str, str, dict[str, Any], Callable[..., str]]] = [
        (
            "dependents",
            "Find modules that depend on a target file or symbol.",
            {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target file path or symbol path to query dependents for.",
                    }
                },
                "required": ["target"],
            },
            _make_handler(_handle_dependents, db_path),
        ),
        (
            "dependencies",
            "Find modules that a target file or symbol depends on.",
            {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target file path or symbol path to query dependencies for.",
                    }
                },
                "required": ["target"],
            },
            _make_handler(_handle_dependencies, db_path),
        ),
        (
            "callers",
            "Find functions that call a target symbol.",
            {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target symbol fully-qualified name (FQN) to find callers for.",
                    },
                    "confidence_threshold": {
                        "type": "number",
                        "description": "Minimum confidence score for call edges (default 0.80).",
                    },
                },
                "required": ["target"],
            },
            _make_handler(_handle_callers, db_path),
        ),
        (
            "callees",
            "Find functions called by a target symbol.",
            {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Caller symbol fully-qualified name (FQN) to find callees for.",
                    },
                    "confidence_threshold": {
                        "type": "number",
                        "description": "Minimum confidence score for call edges (default 0.80).",
                    },
                },
                "required": ["target"],
            },
            _make_handler(_handle_callees, db_path),
        ),
        (
            "hotspots",
            "List the most-called symbols (hotspots) in the codebase.",
            {
                "type": "object",
                "properties": {
                    "top_n": {
                        "type": "integer",
                        "description": "Number of top results to return (default 20).",
                    },
                    "confidence_threshold": {
                        "type": "number",
                        "description": "Minimum confidence score (default 0.75).",
                    },
                },
                "required": [],
            },
            _make_handler(_handle_hotspots, db_path),
        ),
        (
            "subgraph",
            "Show the internal structure (edges) of one or more files.",
            {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "A single file path to inspect.",
                    },
                    "files": {
                        "type": "string",
                        "description": "Comma-separated list of file paths to inspect (takes precedence over target).",
                    },
                },
                "required": [],
            },
            _make_handler(_handle_subgraph, db_path),
        ),
        (
            "impact",
            "Impact analysis: discover which modules are affected if a target changes.",
            {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Module to analyse for impact.",
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Maximum BFS depth for propagation (default 3).",
                    },
                },
                "required": ["target"],
            },
            _make_handler(_handle_impact, db_path),
        ),
        (
            "path",
            "Find the shortest dependency path between two modules.",
            {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Start node of the path.",
                    },
                    "end": {
                        "type": "string",
                        "description": "End node of the path.",
                    },
                },
                "required": ["target", "end"],
            },
            _make_handler(_handle_path, db_path),
        ),
        (
            "stats",
            "Return summary statistics for the dependency graph.",
            {
                "type": "object",
                "properties": {},
                "required": [],
            },
            _make_handler(_handle_stats, db_path),
        ),
        (
            "get_edges",
            "Raw edge query with optional filters for source, target, type, and confidence.",
            {
                "type": "object",
                "properties": {
                    "source_id": {
                        "type": "string",
                        "description": "Filter by source node ID.",
                    },
                    "target_id": {
                        "type": "string",
                        "description": "Filter by target node ID.",
                    },
                    "edge_type": {
                        "type": "string",
                        "description": "Filter by edge type ('import', 'call', or 'contains').",
                    },
                    "min_confidence": {
                        "type": "number",
                        "description": "Minimum confidence score (default 0.0).",
                    },
                },
                "required": [],
            },
            _make_handler(_handle_get_edges, db_path),
        ),
    ]

    for name, description, input_schema, handler in tools:
        server.register_tool(name, description, input_schema, handler)
