"""update_doc tool: regenerate specific documentation layers or modules."""

from __future__ import annotations


from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolParameter, ToolResult


tool_definition = ToolDefinition(
    name="update_doc",
    description="Regenerate documentation for a specific layer or module.",
    parameters=[
        ToolParameter(name="layer", type="integer", description="Target layer (1=overview, 2=modules, 3=graph)"),
        ToolParameter(name="module", type="string", description="Module name for layer 2 updates", required=False),
        ToolParameter(name="instruction", type="string", description="What to update or change", required=False),
    ],
)


def execute(call: ToolCall, context) -> ToolResult:
    layer = call.arguments.get("layer")
    if layer is None:
        return ToolResult(tool_call_id=call.id, content="No layer specified.", is_error=True)
    layer = int(layer)

    try:
        if layer == 1:
            return ToolResult(tool_call_id=call.id, content="Layer 1 is user-maintained. Use layer3-mcp for dependency graph analysis.", is_error=True)

        if layer == 2:
            return ToolResult(tool_call_id=call.id, content="Layer 2 is handled by the standalone layer2-mcp package. Use `layer2-mcp serve <project>` for module documentation management.", is_error=True)

        elif layer == 3:
            return ToolResult(tool_call_id=call.id, content="Layer 3 is handled by the standalone layer3-mcp package. Use `layer3-mcp --repo <path>` for dependency graph analysis.", is_error=True)

        else:
            return ToolResult(tool_call_id=call.id, content=f"Unknown layer: {layer}", is_error=True)

    except Exception as exc:
        return ToolResult(tool_call_id=call.id, content=f"Document update failed: {exc}", is_error=True)