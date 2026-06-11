"""Tests for MCP server protocol and tool registration."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestServerCreation:
    def test_create_server(self, tmp_modules_dir: Path) -> None:
        from code2doc_layer2_mcp.mcp_server import create_server

        mcp = create_server(tmp_modules_dir)
        assert mcp.name == "code2doc-layer2-mcp"


EXPECTED_TOOLS = {
    "list_modules",
    "get_module",
    "search_modules",
    "update_modules",
}


class TestToolRegistration:
    @pytest.mark.asyncio
    async def test_tools_registered(self, tmp_modules_dir: Path) -> None:
        from code2doc_layer2_mcp.mcp_server import create_server

        mcp = create_server(tmp_modules_dir)
        tools_result = await mcp.list_tools()
        tool_names = {t.name for t in tools_result}
        assert tool_names == EXPECTED_TOOLS

    @pytest.mark.asyncio
    async def test_tool_count(self, tmp_modules_dir: Path) -> None:
        from code2doc_layer2_mcp.mcp_server import create_server

        mcp = create_server(tmp_modules_dir)
        tools_result = await mcp.list_tools()
        assert len(tools_result) == 4


class TestToolSchemas:
    @pytest.mark.asyncio
    async def test_get_module_has_name_param(self, tmp_modules_dir: Path) -> None:
        from code2doc_layer2_mcp.mcp_server import create_server

        mcp = create_server(tmp_modules_dir)
        tools_result = await mcp.list_tools()
        tool = next(t for t in tools_result if t.name == "get_module")
        assert "name" in tool.inputSchema["properties"]
        assert "name" in tool.inputSchema["required"]

    @pytest.mark.asyncio
    async def test_update_modules_required_params(self, tmp_modules_dir: Path) -> None:
        from code2doc_layer2_mcp.mcp_server import create_server

        mcp = create_server(tmp_modules_dir)
        tools_result = await mcp.list_tools()
        tool = next(t for t in tools_result if t.name == "update_modules")
        required = set(tool.inputSchema["required"])
        assert "modules" in required
        assert "task_description" in required
        assert "code_changes" not in required  # optional

    @pytest.mark.asyncio
    async def test_search_modules_has_query_param(self, tmp_modules_dir: Path) -> None:
        from code2doc_layer2_mcp.mcp_server import create_server

        mcp = create_server(tmp_modules_dir)
        tools_result = await mcp.list_tools()
        tool = next(t for t in tools_result if t.name == "search_modules")
        assert "query" in tool.inputSchema["properties"]
        assert "query" in tool.inputSchema["required"]


class TestToolCalls:
    @pytest.mark.asyncio
    async def test_list_modules(self, tmp_modules_dir: Path) -> None:
        from code2doc_layer2_mcp.mcp_server import create_server

        mcp = create_server(tmp_modules_dir)
        result = await mcp.call_tool("list_modules", {})
        text = result[0][0].text
        assert "auth" in text

    @pytest.mark.asyncio
    async def test_list_modules_empty(self, tmp_path: Path) -> None:
        from code2doc_layer2_mcp.mcp_server import create_server

        empty_dir = tmp_path / "empty_modules"
        empty_dir.mkdir()
        mcp = create_server(empty_dir)
        result = await mcp.call_tool("list_modules", {})
        text = result[0][0].text
        assert "No modules found" in text

    @pytest.mark.asyncio
    async def test_get_module_found(self, tmp_modules_dir: Path) -> None:
        from code2doc_layer2_mcp.mcp_server import create_server

        mcp = create_server(tmp_modules_dir)
        result = await mcp.call_tool("get_module", {"name": "auth"})
        text = result[0][0].text
        assert "Authentication" in text

    @pytest.mark.asyncio
    async def test_get_module_not_found(self, tmp_modules_dir: Path) -> None:
        from code2doc_layer2_mcp.mcp_server import create_server

        mcp = create_server(tmp_modules_dir)
        result = await mcp.call_tool("get_module", {"name": "nonexistent"})
        text = result[0][0].text
        assert "not found" in text

    @pytest.mark.asyncio
    async def test_search_modules_match(self, tmp_modules_dir: Path) -> None:
        from code2doc_layer2_mcp.mcp_server import create_server

        mcp = create_server(tmp_modules_dir)
        result = await mcp.call_tool("search_modules", {"query": "auth"})
        text = result[0][0].text
        assert "auth" in text

    @pytest.mark.asyncio
    async def test_search_modules_no_match(self, tmp_modules_dir: Path) -> None:
        from code2doc_layer2_mcp.mcp_server import create_server

        mcp = create_server(tmp_modules_dir)
        result = await mcp.call_tool("search_modules", {"query": "zzzzz"})
        text = result[0][0].text
        assert "No modules matching" in text

    @pytest.mark.asyncio
    async def test_update_modules_no_api_key(self, tmp_modules_dir: Path) -> None:
        from code2doc_layer2_mcp.mcp_server import create_server

        mcp = create_server(tmp_modules_dir)
        result = await mcp.call_tool("update_modules", {
            "modules": "auth",
            "task_description": "test task",
        })
        text = result[0][0].text
        assert "LLM not configured" in text

    @pytest.mark.asyncio
    async def test_instructions_present(self, tmp_modules_dir: Path) -> None:
        from code2doc_layer2_mcp.mcp_server import create_server

        mcp = create_server(tmp_modules_dir)
        assert mcp.instructions is not None
        assert "module" in mcp.instructions.lower()
