"""analyze_deps tool: dependency and impact analysis."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolParameter, ToolResult


tool_definition = ToolDefinition(
    name="analyze_deps",
    description="Analyze dependencies, call chains, impact, and function-level calls. "
                "Queries SQLite cache when available (fast), falls back to graph rebuild.",
    parameters=[
        ToolParameter(name="target", type="string", description="Target file or module path"),
        ToolParameter(
            name="mode", type="string", description="Analysis mode",
            required=False,
            enum=["call_chains", "impact", "dependents", "dependencies",
                  "callers", "callees", "hotspots", "subgraph", "path"],
        ),
        ToolParameter(name="end", type="string", description="End node for call_chains/path mode", required=False),
        ToolParameter(name="depth", type="integer", description="BFS depth for subgraph/impact mode (default: 3)", required=False),
        ToolParameter(name="files", type="string", description="Comma-separated file list for subgraph mode", required=False),
        ToolParameter(name="confidence_threshold", type="number", description="Min confidence for call edges (default: 0.80)", required=False),
    ],
)


def _build_graph(context) -> nx.DiGraph | None:
    try:
        from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
        from ai_code2doc.analyzer.call_graph_builder import CallGraphBuilder
        from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser
        from ai_code2doc.scanner.project_scanner import ProjectScanner
        from ai_code2doc.utils.parse_cache import ParseCache

        scanner = ProjectScanner(context.project_root)
        scan_result = scanner.scan()
        parser = TreeSitterParser()
        builder = DependencyGraphBuilder(context.project_root)
        cache = ParseCache(context.output_dir / "file_infos")
        file_infos = []
        for f in scan_result.target_files:
            try:
                fi = cache.get(str(f.relative_to(context.project_root)))
                if fi is None:
                    fi = parser.parse_file(f, context.project_root)
                    cache.put(fi)
                builder.add_file(fi)
                file_infos.append(fi)
            except Exception:
                continue

        # Build call graph edges
        call_builder = CallGraphBuilder(context.project_root)
        call_sites = call_builder.build_for_files(file_infos)
        builder.add_call_edges(call_sites)

        return builder.build()
    except Exception:
        return None


def _get_store(context) -> "DependencyStore | None":
    """Try to open the SQLite store, return None if not available."""
    try:
        from ai_code2doc.analyzer.dependency_store import DependencyStore
        from ai_code2doc.utils.git import get_layer3_db_path

        db_path = get_layer3_db_path(
            context.project_root,
            str(context.output_dir.relative_to(context.project_root)),
        )
        if db_path.exists():
            return DependencyStore(db_path)
    except Exception:
        pass
    return None


def _query_sqlite(store, call: ToolCall) -> ToolResult | None:
    """Try to answer the query from SQLite. Returns None if mode not supported."""
    target = call.arguments.get("target", "")
    mode = call.arguments.get("mode", "dependents")
    threshold = float(call.arguments.get("confidence_threshold", 0.80))

    if mode == "dependents":
        deps = store.dependents(target)
        if not deps:
            return ToolResult(tool_call_id=call.id, content=f"No dependents found for '{target}'.")
        lines = [f"Modules that depend on '{target}':"]
        for d in deps:
            lines.append(f"  - {d}")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "dependencies":
        deps = store.dependencies(target)
        if not deps:
            return ToolResult(tool_call_id=call.id, content=f"No dependencies found for '{target}'.")
        lines = [f"Modules that '{target}' depends on:"]
        for d in deps:
            lines.append(f"  - {d}")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "callers":
        callers = store.callers(target, min_confidence=threshold)
        if not callers:
            return ToolResult(tool_call_id=call.id, content=f"No callers found for '{target}' (threshold: {threshold}).")
        lines = [f"Functions that call '{target}' (confidence >= {threshold}):"]
        for c in callers:
            conf_str = f" (confidence: {c['confidence']:.0%})" if c['confidence'] < 1.0 else ""
            line_str = f" at line {c['line_number']}" if c['line_number'] else ""
            lines.append(f"  - {c['source_id']}{line_str}{conf_str}")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "callees":
        callees = store.callees(target, min_confidence=threshold)
        if not callees:
            return ToolResult(tool_call_id=call.id, content=f"No callees found for '{target}' (threshold: {threshold}).")
        lines = [f"Functions called by '{target}' (confidence >= {threshold}):"]
        for c in callees:
            conf_str = f" (confidence: {c['confidence']:.0%})" if c['confidence'] < 1.0 else ""
            line_str = f" at line {c['line_number']}" if c['line_number'] else ""
            lines.append(f"  - {c['target_id']}{line_str}{conf_str}")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "hotspots":
        hot = store.hotspots(n=20, min_confidence=threshold)
        if not hot:
            return ToolResult(tool_call_id=call.id, content="No call graph data available.")
        lines = [f"Most-called symbols (confidence >= {threshold}):"]
        for h in hot:
            lines.append(f"  {h['target_id']}: {h['call_count']} call(s)")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "subgraph":
        files_str = call.arguments.get("files", "")
        if not files_str:
            files_str = target
        file_list = [f.strip() for f in files_str.split(",") if f.strip()]
        contains = []
        edges = []
        for fid in file_list:
            contains.extend(store.get_edges(source_id=fid, edge_type="contains"))
            edges.extend(store.get_edges(source_id=fid))
            edges.extend(store.get_edges(target_id=fid))
        # Deduplicate edges (avoid repeating contains)
        contains_ids = {(e["source_id"], e["target_id"]) for e in contains}
        edges = [e for e in edges if (e["source_id"], e["target_id"]) not in contains_ids]
        if not contains and not edges:
            return ToolResult(tool_call_id=call.id, content=f"No edges found for files: {files_str}")
        lines = [f"Subgraph for {len(file_list)} file(s):"]
        for e in contains[:50]:
            lines.append(f"  {e['source_id']} --[{e['edge_type']}]--> {e['target_id']}")
        for e in edges[:50]:
            conf = f" (conf: {e['confidence']:.0%})" if e['confidence'] < 1.0 else ""
            lines.append(f"  {e['source_id']} --[{e['edge_type']}]--> {e['target_id']}{conf}")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "impact":
        depth = int(call.arguments.get("depth", 3))
        affected = set()
        current_level = {target}
        for _ in range(depth):
            next_level = set()
            for node in current_level:
                for dep in store.dependents(node):
                    if dep not in affected:
                        next_level.add(dep)
            affected.update(next_level)
            current_level = next_level
            if not next_level:
                break
        if not affected:
            return ToolResult(tool_call_id=call.id, content=f"Changing '{target}' affects no other modules (depth={depth}).")
        if len(affected) <= 2:
            risk = "low"
        elif len(affected) <= 5:
            risk = "medium"
        else:
            risk = "high"
        lines = [f"Impact analysis for '{target}' (depth={depth}):",
                 f"  Risk level: {risk}",
                 f"  Affected modules ({len(affected)}):"]
        for a in sorted(affected)[:30]:
            lines.append(f"    - {a}")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "path":
        end = call.arguments.get("end", "")
        if not end:
            return ToolResult(tool_call_id=call.id, content="'end' required for path mode.", is_error=True)
        import collections
        visited = {target}
        queue = collections.deque([(target, [target])])
        found = None
        while queue and found is None:
            current, path = queue.popleft()
            for dep in store.dependencies(current):
                if dep not in visited:
                    visited.add(dep)
                    new_path = path + [dep]
                    if dep == end or end in dep:
                        found = new_path
                        break
                    if len(new_path) <= 10:
                        queue.append((dep, new_path))
        if found:
            return ToolResult(tool_call_id=call.id, content=f"Shortest path from '{target}' to '{end}':\n  {' -> '.join(found)}")
        return ToolResult(tool_call_id=call.id, content=f"No path found from '{target}' to '{end}'.")

    return None  # Not handled by SQLite, use fallback


def execute(call: ToolCall, context) -> ToolResult:
    target = call.arguments.get("target", "")
    mode = call.arguments.get("mode", "dependents")

    if not target and mode not in ("hotspots", "subgraph"):
        return ToolResult(tool_call_id=call.id, content="No target specified.", is_error=True)

    # Try SQLite first (fast path)
    store = _get_store(context)
    if store is not None:
        try:
            result = _query_sqlite(store, call)
            if result is not None:
                store.close()
                return result
        except Exception:
            pass
        store.close()

    # Fallback: rebuild graph (slow path)
    graph = _build_graph(context)
    if graph is None:
        return ToolResult(tool_call_id=call.id, content="Failed to build dependency graph.", is_error=True)

    if mode == "call_chains":
        end = call.arguments.get("end", "")
        if not end:
            return ToolResult(tool_call_id=call.id, content="'end' required for call_chains mode.", is_error=True)
        from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
        builder = DependencyGraphBuilder(context.project_root)
        builder.graph = graph
        chains = builder.find_call_chains(target, end)
        if not chains:
            return ToolResult(tool_call_id=call.id, content=f"No call chains found from '{target}' to '{end}'.")
        lines = [f"Call chains from '{target}' to '{end}':"]
        for c in chains:
            lines.append(f"  {' -> '.join(c.path)}: {c.description}")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "impact":
        from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
        builder = DependencyGraphBuilder(context.project_root)
        builder.graph = graph
        impact = builder.compute_impact(target)
        lines = [f"Impact analysis for '{target}':", f"  Risk level: {impact.risk_level}",
                 f"  Affected modules: {', '.join(impact.affected_modules) if impact.affected_modules else 'none'}"]
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "dependents":
        try:
            dependents = list(graph.predecessors(target))
        except nx.NetworkXError:
            return ToolResult(tool_call_id=call.id, content=f"Target '{target}' not found in graph.", is_error=True)
        lines = [f"Modules that depend on '{target}':"]
        for d in dependents:
            lines.append(f"  - {d}")
        if not dependents:
            lines.append("  (none)")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "dependencies":
        try:
            deps = list(graph.successors(target))
        except nx.NetworkXError:
            return ToolResult(tool_call_id=call.id, content=f"Target '{target}' not found in graph.", is_error=True)
        lines = [f"Modules that '{target}' depends on:"]
        for d in deps:
            lines.append(f"  - {d}")
        if not deps:
            lines.append("  (none)")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "callers":
        callers = []
        for u, v, d in graph.edges(data=True):
            if d.get("edge_type") == "call" and v == target:
                conf = d.get("confidence", 0)
                ln = d.get("line_number")
                conf_str = f" (confidence: {conf:.0%})" if conf < 1.0 else ""
                line_str = f" at line {ln}" if ln else ""
                callers.append(f"  - {u}{line_str}{conf_str}")
        if not callers:
            return ToolResult(tool_call_id=call.id, content=f"No callers found for '{target}'.")
        lines = [f"Functions that call '{target}':"] + callers
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "callees":
        callees = []
        for u, v, d in graph.edges(data=True):
            if d.get("edge_type") == "call" and u == target:
                conf = d.get("confidence", 0)
                ln = d.get("line_number")
                conf_str = f" (confidence: {conf:.0%})" if conf < 1.0 else ""
                line_str = f" at line {ln}" if ln else ""
                callees.append(f"  - {v}{line_str}{conf_str}")
        if not callees:
            return ToolResult(tool_call_id=call.id, content=f"No callees found for '{target}'.")
        lines = [f"Functions called by '{target}':"] + callees
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "hotspots":
        caller_counts: dict[str, int] = {}
        for u, v, d in graph.edges(data=True):
            if d.get("edge_type") == "call":
                caller_counts[v] = caller_counts.get(v, 0) + 1
        if not caller_counts:
            return ToolResult(tool_call_id=call.id, content="No call graph data available.")
        sorted_hotspots = sorted(caller_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        lines = ["Most-called symbols (hotspots):"]
        for sym, count in sorted_hotspots:
            lines.append(f"  {sym}: {count} call(s)")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    return ToolResult(tool_call_id=call.id, content=f"Unknown mode: {mode}", is_error=True)