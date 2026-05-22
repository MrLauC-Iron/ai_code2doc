"""analyze_deps tool: dependency and impact analysis."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolParameter, ToolResult


tool_definition = ToolDefinition(
    name="analyze_deps",
    description="Analyze dependencies, call chains, and impact for a module or file.",
    parameters=[
        ToolParameter(name="target", type="string", description="Target file or module path"),
        ToolParameter(name="mode", type="string", description="Analysis mode", required=False, enum=["call_chains", "impact", "dependents", "dependencies"]),
        ToolParameter(name="end", type="string", description="End node for call_chain mode", required=False),
    ],
)


def _build_graph(context) -> nx.DiGraph | None:
    try:
        from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
        from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser
        from ai_code2doc.scanner.project_scanner import ProjectScanner
        from ai_code2doc.utils.parse_cache import ParseCache

        scanner = ProjectScanner(context.project_root)
        scan_result = scanner.scan()
        parser = TreeSitterParser()
        builder = DependencyGraphBuilder(context.project_root)
        cache = ParseCache(context.output_dir / "file_infos")
        for f in scan_result.target_files:
            try:
                fi = cache.get(str(f.relative_to(context.project_root)))
                if fi is None:
                    fi = parser.parse_file(f, context.project_root)
                    cache.put(fi)
                builder.add_file(fi)
            except Exception:
                continue
        return builder.build()
    except Exception:
        return None


def execute(call: ToolCall, context) -> ToolResult:
    target = call.arguments.get("target", "")
    if not target:
        return ToolResult(tool_call_id=call.id, content="No target specified.", is_error=True)

    mode = call.arguments.get("mode", "dependents")
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

    return ToolResult(tool_call_id=call.id, content=f"Unknown mode: {mode}", is_error=True)