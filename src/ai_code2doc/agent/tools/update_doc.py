"""update_doc tool: regenerate specific documentation layers or modules."""

from __future__ import annotations

import asyncio
from pathlib import Path

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
    module_name = call.arguments.get("module")
    output_dir = context.output_dir

    try:
        if layer == 1:
            return ToolResult(tool_call_id=call.id, content="Layer 1 is user-maintained. Use layer3-mcp for dependency graph analysis.", is_error=True)

        if layer == 2:
            from ai_code2doc.generator.layer2_modules import Layer2ModuleGenerator
            from ai_code2doc.generator.markdown_writer import MarkdownWriter
            gen = Layer2ModuleGenerator(context.settings)
            docs = asyncio.run(
                gen.generate(context.project_root, output_dir, use_llm=bool(context.settings.llm_api_key), changed_files=None)
            )
            writer = MarkdownWriter()
            paths = []
            for doc in docs:
                if module_name and module_name.lower() not in doc.title.lower():
                    continue
                p = output_dir / "layer2" / f"{doc.id}.md"
                writer.write_doc(p, doc)
                paths.append(str(p))
            msg = f"Updated Layer 2 modules ({len(paths)} docs):"
            if module_name:
                msg = f"Updated Layer 2 for '{module_name}' ({len(paths)} docs):"
            return ToolResult(tool_call_id=call.id, content=msg + "\n" + "\n".join(f"  - {p}" for p in paths) if paths else f"No matching modules found for '{module_name}'.")

        elif layer == 3:
            return ToolResult(tool_call_id=call.id, content="Layer 3 is handled by the standalone layer3-mcp package. Use `layer3-mcp --repo <path>` for dependency graph analysis.", is_error=True)

        else:
            return ToolResult(tool_call_id=call.id, content=f"Unknown layer: {layer}", is_error=True)

    except Exception as exc:
        return ToolResult(tool_call_id=call.id, content=f"Document update failed: {exc}", is_error=True)