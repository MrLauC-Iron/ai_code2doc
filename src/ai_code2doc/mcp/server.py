"""Minimal MCP stdio server using JSON-RPC 2.0 over stdin/stdout."""

import json
import sys
from typing import Any, Callable


class MCPServer:
    """A synchronous MCP (Model Context Protocol) server that communicates
    via newline-delimited JSON-RPC 2.0 messages on stdin/stdout."""

    PROTOCOL_VERSION = "2024-11-05"

    # Standard JSON-RPC error codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    def __init__(self, name: str, version: str) -> None:
        self.name = name
        self.version = version
        self.tools: list[dict[str, Any]] = []
        self._handlers: dict[str, Callable[..., str]] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[..., str],
    ) -> None:
        """Register a tool with its JSON Schema and handler function.

        Args:
            name: Tool name used in tools/call requests.
            description: Human-readable description of the tool.
            input_schema: JSON Schema object describing the tool's parameters.
            handler: Callable that receives **kwargs and returns a result string.
        """
        self.tools.append(
            {
                "name": name,
                "description": description,
                "inputSchema": input_schema,
            }
        )
        self._handlers[name] = handler

    def _send(self, message: dict[str, Any]) -> None:
        """Write a JSON message to stdout followed by newline."""
        sys.stdout.write(json.dumps(message) + "\n")
        sys.stdout.flush()

    def _make_result(self, request_id: Any, result: Any) -> dict[str, Any]:
        """Build a JSON-RPC success response."""
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _make_error(self, request_id: Any, code: int, message: str) -> dict[str, Any]:
        """Build a JSON-RPC error response."""
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def _handle_initialize(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Handle initialize request. Return result dict."""
        return self._make_result(
            request_id,
            {
                "protocolVersion": self.PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": self.name, "version": self.version},
            },
        )

    def _handle_tools_list(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tools/list request. Return result dict with tools list."""
        return self._make_result(request_id, {"tools": self.tools})

    def _handle_tools_call(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tools/call request. Dispatch to registered handler.

        The handler receives **arguments as kwargs and should return a string.
        On success returns a result dict with content list.
        On failure returns an error dict.
        """
        tool_name = params.get("name", "") if params else ""
        arguments = params.get("arguments", {}) if params else {}

        if not tool_name:
            return self._make_error(request_id, self.INVALID_PARAMS, "Missing tool name")

        handler = self._handlers.get(tool_name)
        if handler is None:
            return self._make_error(
                request_id, self.METHOD_NOT_FOUND, f"Tool '{tool_name}' not found"
            )

        try:
            result_text = handler(**arguments)
            return self._make_result(
                request_id,
                {"content": [{"type": "text", "text": result_text}]},
            )
        except TypeError as exc:
            return self._make_error(
                request_id, self.INVALID_PARAMS, f"Invalid arguments: {exc}"
            )
        except Exception as exc:
            return self._make_error(
                request_id, self.INTERNAL_ERROR, f"Internal error: {exc}"
            )

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Route a JSON-RPC message to the appropriate handler.

        Returns None for notifications (messages with no id) —
        these should not produce a response.
        """
        # Validate basic JSON-RPC 2.0 structure
        jsonrpc = message.get("jsonrpc")
        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params")

        if jsonrpc != "2.0" or not isinstance(method, str):
            if request_id is not None:
                return self._make_error(request_id, self.INVALID_REQUEST, "Invalid Request")
            return None

        # Notifications have no id — no response needed
        if request_id is None:
            return None

        dispatch = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
        }

        handler = dispatch.get(method)
        if handler is None:
            return self._make_error(
                request_id, self.METHOD_NOT_FOUND, f"Method '{method}' not found"
            )

        return handler(request_id, params)

    def run(self) -> None:
        """Main loop: read lines from stdin, parse JSON, handle, write response."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                self._send(
                    self._make_error(None, self.PARSE_ERROR, f"Parse error: {exc}")
                )
                continue

            response = self.handle_message(message)
            if response is not None:
                self._send(response)


if __name__ == "__main__":
    server = MCPServer(name="ai_code2doc-test", version="0.0.1")

    def echo(**kwargs: Any) -> str:
        """Dummy tool that echoes its arguments back as a JSON string."""
        return json.dumps(kwargs)

    def add(**kwargs: Any) -> str:
        """Dummy tool that adds two numbers."""
        a = kwargs.get("a", 0)
        b = kwargs.get("b", 0)
        return str(int(a) + int(b))

    server.register_tool(
        name="echo",
        description="Echo the input arguments back as a JSON string.",
        input_schema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The message to echo."},
            },
            "required": [],
        },
        handler=echo,
    )

    server.register_tool(
        name="add",
        description="Add two numbers together.",
        input_schema={
            "type": "object",
            "properties": {
                "a": {"type": "integer", "description": "First number."},
                "b": {"type": "integer", "description": "Second number."},
            },
            "required": ["a", "b"],
        },
        handler=add,
    )

    server.run()
