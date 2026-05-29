"""Tests for MCP tool handlers."""

from __future__ import annotations

from pathlib import Path

import pytest

from code2doc_layer3_mcp.server import create_server


def _extract_text(result: tuple) -> str:
    """Extract text content from call_tool tuple result."""
    content_list = result[0]
    return content_list[0].text


class TestDependents:
    @pytest.mark.asyncio
    async def test_dependents(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("dependents", {"target": "b.py"})
        text = _extract_text(result)
        assert "a.py" in text
        assert "Modules that depend on 'b.py'" in text

    @pytest.mark.asyncio
    async def test_dependents_nonexistent(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("dependents", {"target": "nonexistent.py"})
        assert "No modules depend" in _extract_text(result)


class TestDependencies:
    @pytest.mark.asyncio
    async def test_dependencies(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("dependencies", {"target": "a.py"})
        text = _extract_text(result)
        assert "b.py" in text
        assert "c.py" in text

    @pytest.mark.asyncio
    async def test_dependencies_nonexistent(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("dependencies", {"target": "nonexistent.py"})
        assert "no dependencies" in _extract_text(result)


class TestCallers:
    @pytest.mark.asyncio
    async def test_callers(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("callers", {"target": "b.py::func_b"})
        text = _extract_text(result)
        assert "a.py::func_a" in text
        assert "95%" in text

    @pytest.mark.asyncio
    async def test_callers_confidence_filter(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool(
            "callers",
            {"target": "d.py::func_d", "confidence_threshold": 0.80},
        )
        text = _extract_text(result)
        assert "c.py::func_c" in text
        assert "b.py::func_b" not in text  # confidence 0.70 < 0.80

    @pytest.mark.asyncio
    async def test_callers_empty(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool(
            "callers",
            {"target": "nonexistent", "confidence_threshold": 0.80},
        )
        assert "No callers found" in _extract_text(result)


class TestCallees:
    @pytest.mark.asyncio
    async def test_callees(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("callees", {"target": "a.py::func_a"})
        text = _extract_text(result)
        assert "b.py::func_b" in text
        assert "c.py::func_c" in text

    @pytest.mark.asyncio
    async def test_callees_confidence_filter(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool(
            "callees",
            {"target": "a.py::func_a", "confidence_threshold": 0.90},
        )
        text = _extract_text(result)
        assert "b.py::func_b" in text  # 0.95
        assert "c.py::func_c" not in text  # 0.85 < 0.90


class TestHotspots:
    @pytest.mark.asyncio
    async def test_hotspots(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("hotspots", {})
        text = _extract_text(result)
        assert "hotspots" in text.lower()

    @pytest.mark.asyncio
    async def test_hotspots_with_n(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("hotspots", {"top_n": 2})
        text = _extract_text(result)
        lines = [l for l in text.split("\n") if l.strip().startswith(("1.", "2.", "3."))]
        assert len(lines) <= 2


class TestSubgraph:
    @pytest.mark.asyncio
    async def test_subgraph_single_file(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("subgraph", {"target": "a.py"})
        text = _extract_text(result)
        assert "=== a.py ===" in text

    @pytest.mark.asyncio
    async def test_subgraph_multiple_files(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("subgraph", {"files": "a.py, b.py"})
        text = _extract_text(result)
        assert "=== a.py ===" in text
        assert "=== b.py ===" in text

    @pytest.mark.asyncio
    async def test_subgraph_empty(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("subgraph", {})
        assert "No target" in _extract_text(result)


class TestImpact:
    @pytest.mark.asyncio
    async def test_impact(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("impact", {"target": "d.py"})
        text = _extract_text(result)
        assert "Risk level:" in text
        assert "Affected modules" in text
        assert "b.py" in text
        assert "c.py" in text

    @pytest.mark.asyncio
    async def test_impact_no_affected(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("impact", {"target": "nonexistent.py"})
        text = _extract_text(result)
        assert "low" in text
        assert "(0)" in text


class TestPath:
    @pytest.mark.asyncio
    async def test_path(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("path", {"target": "a.py", "end": "d.py"})
        text = _extract_text(result)
        assert "Path:" in text
        assert "a.py" in text
        assert "d.py" in text

    @pytest.mark.asyncio
    async def test_path_same_node(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("path", {"target": "a.py", "end": "a.py"})
        assert "start and end are the same" in _extract_text(result)

    @pytest.mark.asyncio
    async def test_path_no_connection(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool(
            "path", {"target": "nonexistent1", "end": "nonexistent2"}
        )
        assert "No path found" in _extract_text(result)


class TestStats:
    @pytest.mark.asyncio
    async def test_stats(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("stats", {})
        text = _extract_text(result)
        assert "Nodes:" in text
        assert "8" in text  # 4 files + 4 symbols
        assert "Edges by type:" in text
        assert "import:" in text


class TestGetEdges:
    @pytest.mark.asyncio
    async def test_get_edges_by_type(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("get_edges", {"edge_type": "call"})
        text = _extract_text(result)
        assert "Found 5 edges" in text

    @pytest.mark.asyncio
    async def test_get_edges_by_source(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool("get_edges", {"source_id": "a.py::func_a"})
        text = _extract_text(result)
        assert "a.py::func_a" in text

    @pytest.mark.asyncio
    async def test_get_edges_empty(self, db_path: Path) -> None:
        mcp = create_server(db_path)
        result = await mcp.call_tool(
            "get_edges",
            {"source_id": "nonexistent", "edge_type": "call"},
        )
        assert "No edges found" in _extract_text(result)
