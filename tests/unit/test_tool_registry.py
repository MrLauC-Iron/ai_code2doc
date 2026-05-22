from __future__ import annotations

from ai_code2doc.agent.models import ToolDefinition, ToolParameter, ToolCall, ToolResult
from ai_code2doc.agent.tool_registry import ToolRegistry


async def dummy_handler(call: ToolCall, ctx) -> ToolResult:
    return ToolResult(tool_call_id=call.id, content=f"handled {call.arguments}")


class TestToolRegistry:
    def test_register_and_get_definitions(self) -> None:
        reg = ToolRegistry()
        tool_def = ToolDefinition(
            name="test_tool",
            description="A test",
            parameters=[ToolParameter(name="arg", type="string", description="Arg")],
        )
        reg.register(tool_def, dummy_handler)
        defs = reg.get_definitions()
        assert len(defs) == 1
        assert defs[0].name == "test_tool"

    def test_register_duplicate_raises(self) -> None:
        reg = ToolRegistry()
        tool_def = ToolDefinition(name="dup", description="D", parameters=[])
        reg.register(tool_def, dummy_handler)
        try:
            reg.register(tool_def, dummy_handler)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_has_tool(self) -> None:
        reg = ToolRegistry()
        tool_def = ToolDefinition(name="exists", description="E", parameters=[])
        reg.register(tool_def, dummy_handler)
        assert reg.has_tool("exists")
        assert not reg.has_tool("missing")

    def test_tool_names(self) -> None:
        reg = ToolRegistry()
        for name in ["a", "b", "c"]:
            reg.register(ToolDefinition(name=name, description=f"D{name}", parameters=[]), dummy_handler)
        assert reg.tool_names == ["a", "b", "c"]