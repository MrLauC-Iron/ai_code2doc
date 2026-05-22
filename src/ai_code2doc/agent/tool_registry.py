"""Tool registry: definitions and handler dispatch."""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolResult


ToolHandler = Callable[[ToolCall, Any], Coroutine[Any, Any, ToolResult]]


class ToolRegistry:
    """Registry of tools available to the agent."""

    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(
        self,
        definition: ToolDefinition,
        handler: ToolHandler,
    ) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"Tool '{definition.name}' is already registered")
        self._definitions[definition.name] = definition
        self._handlers[definition.name] = handler

    def get_definitions(self) -> list[ToolDefinition]:
        return list(self._definitions.values())

    def has_tool(self, name: str) -> bool:
        return name in self._handlers

    @property
    def tool_names(self) -> list[str]:
        return list(self._definitions.keys())

    async def execute(self, tool_call: ToolCall, context: Any) -> ToolResult:
        handler = self._handlers.get(tool_call.name)
        if handler is None:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Unknown tool: {tool_call.name}",
                is_error=True,
            )
        try:
            return await handler(tool_call, context)
        except Exception as exc:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Tool execution failed: {exc}",
                is_error=True,
            )