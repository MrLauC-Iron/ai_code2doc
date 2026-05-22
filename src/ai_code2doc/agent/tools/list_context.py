"""list_context tool: show current analysis state."""

from __future__ import annotations

from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolResult

tool_definition = ToolDefinition(
    name="list_context",
    description="Show the current analysis context: project info, files analyzed, "
    "available layers, and vector store status.",
    parameters=[],
)


def execute(call: ToolCall, context) -> ToolResult:
    parts = [f"Project: {context.project_root}"]
    if context.analysis_result:
        ar = context.analysis_result
        parts.append(f"Files analyzed: {ar.total_files}")
        parts.append(f"Total lines: {ar.total_lines}")
        if ar.target_files:
            names = [f.name for f in ar.target_files[:15]]
            parts.append(f"Files: {', '.join(names)}")
            if len(ar.target_files) > 15:
                parts.append(f"  ... and {len(ar.target_files) - 15} more")
    else:
        parts.append("No analysis results loaded.")
    parts.append(f"Output dir: {context.output_dir}")
    parts.append(f"Vector store: {'available' if context.has_vector_store() else 'not available'}")
    return ToolResult(tool_call_id=call.id, content="\n".join(parts))