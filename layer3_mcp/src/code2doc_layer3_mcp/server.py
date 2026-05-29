"""FastMCP server with dependency graph query and branch management tools."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from code2doc_layer3_mcp.dependency_store import DependencyStore

# Module-level state set by create_server()
_default_db: Path | None = None
_branch_manager: Any | None = None  # BranchManager, imported lazily to avoid circular deps


async def _resolve_db(branch: str = "") -> Path:
    """Resolve the DB path based on server mode and branch parameter.

    - Local mode (no branch_manager): uses the default db_path, ignores branch.
    - Remote mode (branch_manager): resolves branch-specific DB, building if needed.
    """
    if _branch_manager is None:
        if _default_db is None:
            raise RuntimeError("No database configured.")
        return _default_db

    effective_branch = branch
    if not effective_branch:
        effective_branch = _branch_manager.get_current_branch()

    if not effective_branch:
        raise RuntimeError(
            "Cannot determine branch. Specify 'branch' parameter."
        )

    return await _branch_manager.ensure_branch(effective_branch)


def _query_dependents(db: Path, target: str) -> str:
    store = DependencyStore(db)
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


def _query_dependencies(db: Path, target: str) -> str:
    store = DependencyStore(db)
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


def _query_callers(db: Path, target: str, confidence_threshold: float) -> str:
    store = DependencyStore(db)
    try:
        edges = store.callers(target, min_confidence=confidence_threshold)
    finally:
        store.close()
    if not edges:
        return (
            f"No callers found for '{target}' "
            f"with confidence >= {confidence_threshold:.2f}."
        )
    lines = [f"Callers of '{target}' (confidence >= {confidence_threshold:.2f}):"]
    for e in edges:
        conf_pct = f"{e['confidence']:.0%}"
        line_info = (
            f"line {e['line_number']}" if e.get("line_number") else "unknown line"
        )
        lines.append(
            f"  - {e['source_id']} ({line_info}, confidence {conf_pct})"
        )
    return "\n".join(lines)


def _query_callees(db: Path, target: str, confidence_threshold: float) -> str:
    store = DependencyStore(db)
    try:
        edges = store.callees(target, min_confidence=confidence_threshold)
    finally:
        store.close()
    if not edges:
        return (
            f"No callees found for '{target}' "
            f"with confidence >= {confidence_threshold:.2f}."
        )
    lines = [f"Callees of '{target}' (confidence >= {confidence_threshold:.2f}):"]
    for e in edges:
        conf_pct = f"{e['confidence']:.0%}"
        line_info = (
            f"line {e['line_number']}" if e.get("line_number") else "unknown line"
        )
        lines.append(
            f"  - {e['target_id']} ({line_info}, confidence {conf_pct})"
        )
    return "\n".join(lines)


def _query_hotspots(db: Path, top_n: int, confidence_threshold: float) -> str:
    store = DependencyStore(db)
    try:
        spots = store.hotspots(n=top_n, min_confidence=confidence_threshold)
    finally:
        store.close()
    if not spots:
        return f"No hotspots found with confidence >= {confidence_threshold:.2f}."
    lines = [f"Top {len(spots)} hotspots (confidence >= {confidence_threshold:.2f}):"]
    for i, s in enumerate(spots, 1):
        lines.append(f"  {i}. {s['target_id']} ({s['call_count']} calls)")
    return "\n".join(lines)


def _query_subgraph(db: Path, target: str, files: str) -> str:
    if files:
        file_list = [f.strip() for f in files.split(",") if f.strip()]
    elif target:
        file_list = [target]
    else:
        return "No target or files specified."

    store = DependencyStore(db)
    try:
        all_lines: list[str] = []
        for fpath in file_list:
            all_lines.append(f"=== {fpath} ===")
            all_edges = store.get_edges(source_id=fpath)
            if not all_edges:
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


def _query_impact(db: Path, target: str, depth: int) -> str:
    store = DependencyStore(db)
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


def _query_path(db: Path, target: str, end: str) -> str:
    if target == end:
        return f"Path: {target} (start and end are the same)."

    max_depth = 10

    store = DependencyStore(db)
    try:
        fwd_visited: dict[str, str | None] = {target: None}
        fwd_queue: deque[str] = deque([target])

        bwd_visited: dict[str, str | None] = {end: None}
        bwd_queue: deque[str] = deque([end])

        meeting: str | None = None

        for _ in range(max_depth):
            if not fwd_queue and not bwd_queue:
                break

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


def _query_stats(db: Path) -> str:
    store = DependencyStore(db)
    try:
        graph_stats = store.get_stats()
        edges_by_type = {}
        for etype in ("import", "call", "contains"):
            edges_by_type[etype] = len(store.get_edges(edge_type=etype))
    finally:
        store.close()

    lines = [
        "Dependency Graph Statistics",
        "===========================",
        f"  Nodes:             {graph_stats['nodes']}",
        f"  Total edges:       {graph_stats['edges']}",
        f"  Resolved calls:    {graph_stats['resolved_calls']}",
        "",
        "  Edges by type:",
    ]
    for etype, count in edges_by_type.items():
        lines.append(f"    {etype}:  {count}")
    return "\n".join(lines)


def _query_get_edges(
    db: Path,
    source_id: str,
    target_id: str,
    edge_type: str,
    min_confidence: float,
) -> str:
    store = DependencyStore(db)
    try:
        edges = store.get_edges(
            source_id=source_id or None,
            target_id=target_id or None,
            edge_type=edge_type or None,
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
        line_info = (
            f", line {e['line_number']}" if e.get("line_number") else ""
        )
        lines.append(
            f"  {e['source_id']} --[{e['edge_type']}]--> {e['target_id']} "
            f"(confidence={conf}, weight={weight}{line_info})"
        )
    return "\n".join(lines)


def create_server(
    db_path: Path | None = None,
    repo_path: Path | None = None,
) -> FastMCP:
    """Create and configure a FastMCP instance.

    Args:
        db_path: Direct path to a dependency graph DB (local mode).
        repo_path: Path to a git repo for on-demand branch builds (remote mode).
    """
    global _default_db, _branch_manager
    _default_db = db_path
    _branch_manager = None

    if repo_path:
        from code2doc_layer3_mcp.branch_manager import BranchManager

        _branch_manager = BranchManager(repo_path)

    mcp = FastMCP(
        "code2doc-layer3-mcp",
        instructions="Query the dependency graph of a codebase. "
        "Use dependents/dependencies for import relations, "
        "callers/callees for call relations, "
        "hotspots for most-called symbols, "
        "impact for change propagation analysis, "
        "path for shortest dependency path, "
        "subgraph for file internals, "
        "stats for graph overview, "
        "get_edges for raw edge queries. "
        "Use 'branch' parameter to specify which git branch to query.",
    )

    # ------------------------------------------------------------------
    # Query tools (with optional branch param)
    # ------------------------------------------------------------------

    @mcp.tool()
    async def dependents(target: str, branch: str = "") -> str:
        """Find modules that depend on a target file or symbol."""
        db = await _resolve_db(branch)
        return _query_dependents(db, target)

    @mcp.tool()
    async def dependencies(target: str, branch: str = "") -> str:
        """Find modules that a target file or symbol depends on."""
        db = await _resolve_db(branch)
        return _query_dependencies(db, target)

    @mcp.tool()
    async def callers(
        target: str, confidence_threshold: float = 0.80, branch: str = ""
    ) -> str:
        """Find functions that call a target symbol."""
        db = await _resolve_db(branch)
        return _query_callers(db, target, confidence_threshold)

    @mcp.tool()
    async def callees(
        target: str, confidence_threshold: float = 0.80, branch: str = ""
    ) -> str:
        """Find functions called by a target symbol."""
        db = await _resolve_db(branch)
        return _query_callees(db, target, confidence_threshold)

    @mcp.tool()
    async def hotspots(
        top_n: int = 20, confidence_threshold: float = 0.75, branch: str = ""
    ) -> str:
        """List the most-called symbols (hotspots) in the codebase."""
        db = await _resolve_db(branch)
        return _query_hotspots(db, top_n, confidence_threshold)

    @mcp.tool()
    async def subgraph(
        target: str = "", files: str = "", branch: str = ""
    ) -> str:
        """Show the internal structure (edges) of one or more files."""
        db = await _resolve_db(branch)
        return _query_subgraph(db, target, files)

    @mcp.tool()
    async def impact(target: str, depth: int = 3, branch: str = "") -> str:
        """Impact analysis: discover which modules are affected if a target changes."""
        db = await _resolve_db(branch)
        return _query_impact(db, target, depth)

    @mcp.tool()
    async def path(target: str, end: str, branch: str = "") -> str:
        """Find the shortest dependency path between two modules."""
        db = await _resolve_db(branch)
        return _query_path(db, target, end)

    @mcp.tool()
    async def stats(branch: str = "") -> str:
        """Return summary statistics for the dependency graph."""
        db = await _resolve_db(branch)
        return _query_stats(db)

    @mcp.tool()
    async def get_edges(
        source_id: str = "",
        target_id: str = "",
        edge_type: str = "",
        min_confidence: float = 0.0,
        branch: str = "",
    ) -> str:
        """Raw edge query with optional filters for source, target, type, and confidence."""
        db = await _resolve_db(branch)
        return _query_get_edges(db, source_id, target_id, edge_type, min_confidence)

    # ------------------------------------------------------------------
    # Branch management tools
    # ------------------------------------------------------------------

    @mcp.tool()
    async def ensure_branch(branch: str) -> str:
        """Ensure a branch's dependency graph is built and ready.

        Triggers code fetch, checkout, and analysis if the branch DB
        does not exist yet. Returns once the DB is ready to query.
        """
        if _branch_manager is None:
            return "Error: branch management not configured (no --repo)."
        db_path = await _branch_manager.ensure_branch(branch)
        return f"Branch '{branch}' is ready. DB: {db_path}"

    @mcp.tool()
    def branch_status(branch: str = "") -> str:
        """Check build status for branches. Lists all built branches if no branch specified."""
        if _branch_manager is None:
            return "Error: branch management not configured (no --repo)."
        if branch:
            info = _branch_manager.get_branch_info(branch)
            if info["is_building"]:
                status = "building..."
            elif info["db_exists"]:
                status = "ready"
            else:
                status = "not built"
            lines = [
                f"Branch: {info['branch']}",
                f"Status: {status}",
                f"DB: {info['db_path']}",
            ]
            return "\n".join(lines)
        else:
            branches = _branch_manager.list_branches()
            if not branches:
                return "No branches built yet."
            lines = ["Built branches:"]
            for b in branches:
                lines.append(f"  - {b['branch']}")
            return "\n".join(lines)

    return mcp
