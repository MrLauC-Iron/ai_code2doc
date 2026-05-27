"""Protocol-level tests for MCPServer."""

from __future__ import annotations

from ai_code2doc.mcp.server import MCPServer


class TestMCPServerInit:
    def test_init(self) -> None:
        server = MCPServer(name="test-server", version="1.0.0")
        assert server.name == "test-server"
        assert server.version == "1.0.0"
        assert server.tools == []
        assert server._handlers == {}


class TestInitialize:
    def test_initialize_response(self) -> None:
        server = MCPServer(name="my-server", version="2.3.4")
        result = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"},
                },
            }
        )
        assert result is not None
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "result" in result
        assert result["result"]["protocolVersion"] == "2024-11-05"
        assert result["result"]["capabilities"] == {"tools": {}}
        assert result["result"]["serverInfo"]["name"] == "my-server"
        assert result["result"]["serverInfo"]["version"] == "2.3.4"


class TestToolsList:
    def test_tools_list_empty(self) -> None:
        server = MCPServer(name="test", version="1.0.0")
        result = server.handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        )
        assert result is not None
        assert result["result"]["tools"] == []

    def test_tools_list(self) -> None:
        server = MCPServer(name="test", version="1.0.0")
        server.register_tool(
            name="echo",
            description="Echo tool",
            input_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
            handler=lambda **kw: kw.get("msg", ""),
        )
        server.register_tool(
            name="add",
            description="Add tool",
            input_schema={"type": "object", "properties": {"a": {"type": "integer"}}},
            handler=lambda **kw: str(int(kw.get("a", 0)) + 1),
        )
        result = server.handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        )
        assert result is not None
        tools = result["result"]["tools"]
        assert len(tools) == 2
        names = {t["name"] for t in tools}
        assert names == {"echo", "add"}
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool


class TestToolsCall:
    def test_tools_call_success(self) -> None:
        server = MCPServer(name="test", version="1.0.0")
        server.register_tool(
            name="echo",
            description="Echo tool",
            input_schema={"type": "object"},
            handler=lambda **kw: "hello",
        )
        result = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "echo", "arguments": {"msg": "hi"}},
            }
        )
        assert result is not None
        assert result["result"]["content"][0]["text"] == "hello"

    def test_tools_call_not_found(self) -> None:
        server = MCPServer(name="test", version="1.0.0")
        result = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "nonexistent", "arguments": {}},
            }
        )
        assert result is not None
        assert result["error"]["code"] == -32601

    def test_tools_call_missing_name(self) -> None:
        server = MCPServer(name="test", version="1.0.0")
        result = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"arguments": {}},
            }
        )
        assert result is not None
        assert result["error"]["code"] == -32602

    def test_tools_call_handler_exception(self) -> None:
        server = MCPServer(name="test", version="1.0.0")

        def bad_handler(**kwargs):
            raise ValueError("boom")

        server.register_tool(
            name="bad",
            description="Bad tool",
            input_schema={"type": "object"},
            handler=bad_handler,
        )
        result = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "bad", "arguments": {}},
            }
        )
        assert result is not None
        assert result["error"]["code"] == -32603


class TestNotifications:
    def test_initialized_notification(self) -> None:
        server = MCPServer(name="test", version="1.0.0")
        result = server.handle_message(
            {"jsonrpc": "2.0", "method": "initialized", "params": None}
        )
        assert result is None


class TestMethodNotFound:
    def test_unknown_method(self) -> None:
        server = MCPServer(name="test", version="1.0.0")
        result = server.handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}
        )
        assert result is not None
        assert result["error"]["code"] == -32601


class TestInvalidRequest:
    def test_missing_jsonrpc(self) -> None:
        server = MCPServer(name="test", version="1.0.0")
        result = server.handle_message({"id": 1, "method": "test"})
        assert result is not None
        assert result["error"]["code"] == -32600

    def test_missing_method(self) -> None:
        server = MCPServer(name="test", version="1.0.0")
        result = server.handle_message({"jsonrpc": "2.0", "id": 1})
        assert result is not None
        assert result["error"]["code"] == -32600
