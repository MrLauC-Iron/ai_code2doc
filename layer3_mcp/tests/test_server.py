"""Tests for MCP server protocol and tool listing."""

from __future__ import annotations

from pathlib import Path

import pytest

from code2doc_layer3_mcp.server import create_server

EXPECTED_TOOLS = {
    "dependents",
    "dependencies",
    "callers",
    "callees",
    "hotspots",
    "subgraph",
    "impact",
    "path",
    "stats",
    "get_edges",
}


class TestServerCreation:
    def test_create_server(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        assert mcp.name == "code2doc-layer3-mcp"

    @pytest.mark.asyncio
    async def test_tools_registered(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        tools_result = await mcp.list_tools()
        tool_names = {t.name for t in tools_result}
        assert tool_names == EXPECTED_TOOLS

    @pytest.mark.asyncio
    async def test_tool_count(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        tools_result = await mcp.list_tools()
        assert len(tools_result) == 10


class TestToolSchemas:
    @pytest.mark.asyncio
    async def test_dependents_schema(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        tools_result = await mcp.list_tools()
        dep_tool = next(t for t in tools_result if t.name == "dependents")
        schema = dep_tool.inputSchema
        assert "target" in schema["properties"]
        assert "target" in schema["required"]

    @pytest.mark.asyncio
    async def test_hotspots_schema_no_required(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        tools_result = await mcp.list_tools()
        hot_tool = next(t for t in tools_result if t.name == "hotspots")
        schema = hot_tool.inputSchema
        assert schema.get("required", []) == []

    @pytest.mark.asyncio
    async def test_path_schema_required_fields(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        tools_result = await mcp.list_tools()
        path_tool = next(t for t in tools_result if t.name == "path")
        schema = path_tool.inputSchema
        required = set(schema["required"])
        assert "target" in required
        assert "end" in required

    @pytest.mark.asyncio
    async def test_callers_has_confidence_param(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        tools_result = await mcp.list_tools()
        callers_tool = next(t for t in tools_result if t.name == "callers")
        schema = callers_tool.inputSchema
        assert "confidence_threshold" in schema["properties"]


class TestToolCallProtocol:
    @pytest.mark.asyncio
    async def test_call_tool_returns_content(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("stats", {})
        content_list = result[0]
        assert len(content_list) == 1
        assert content_list[0].type == "text"

    @pytest.mark.asyncio
    async def test_call_unknown_tool_raises(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        with pytest.raises(Exception):
            await mcp.call_tool("nonexistent_tool", {})

    def test_instructions_present(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        assert mcp.instructions is not None
        assert "dependency" in mcp.instructions.lower()
