"""correct tool: apply user-reported corrections to generated documentation."""

from __future__ import annotations

import asyncio
from pathlib import Path

from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolParameter, ToolResult


tool_definition = ToolDefinition(
    name="correct",
    description="Apply a correction to generated documentation. Use when the user points out an error.",
    parameters=[
        ToolParameter(name="target", type="string", description="Relative path to the documentation file"),
        ToolParameter(name="correction", type="string", description="Description of the correction to apply"),
    ],
)


def execute(call: ToolCall, context) -> ToolResult:
    target = call.arguments.get("target", "")
    correction = call.arguments.get("correction", "")

    if not target or not correction:
        return ToolResult(tool_call_id=call.id, content="Both 'target' and 'correction' are required.", is_error=True)

    file_path = context.output_dir / target
    if not file_path.exists():
        return ToolResult(tool_call_id=call.id, content=f"File not found: {file_path}", is_error=True)

    try:
        original = file_path.read_text(encoding="utf-8")

        if context.settings.llm_api_key:
            prompt = (
                "You are editing a documentation file. Apply the following correction.\n\n"
                f"## Original file content\n\n{original}\n\n"
                f"## Correction instruction\n\n{correction}\n\n"
                "Return the COMPLETE corrected file content. Do not add explanations."
            )
            result = asyncio.get_event_loop().run_until_complete(
                context.llm_client.agenerate(prompt, system="You are a documentation editor.")
            )
            new_content = result.content.strip()
            if new_content.startswith("```"):
                lines = new_content.split("\n")
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                new_content = "\n".join(lines)
            file_path.write_text(new_content, encoding="utf-8")
            return ToolResult(tool_call_id=call.id, content=f"Corrected {target} based on instruction: {correction}")
        else:
            return ToolResult(tool_call_id=call.id, content="No LLM API key configured. Cannot apply corrections automatically.", is_error=True)

    except Exception as exc:
        return ToolResult(tool_call_id=call.id, content=f"Correction failed: {exc}", is_error=True)