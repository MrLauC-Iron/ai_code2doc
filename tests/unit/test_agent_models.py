from __future__ import annotations

from ai_code2doc.agent.models import (
    MessageRole,
    ConversationMessage,
    ToolParameter,
    ToolDefinition,
    ToolCall,
    ToolResult,
)


class TestToolParameter:
    def test_creation(self) -> None:
        p = ToolParameter(name="path", type="string", description="File path")
        assert p.name == "path"
        assert p.type == "string"
        assert p.required is True
        assert p.enum is None

    def test_optional_with_enum(self) -> None:
        p = ToolParameter(
            name="layer",
            type="integer",
            description="Layer number",
            required=False,
            enum=["1", "2", "3"],
        )
        assert p.required is False
        assert p.enum == ["1", "2", "3"]


class TestToolDefinition:
    def test_creation(self) -> None:
        t = ToolDefinition(
            name="code_qa",
            description="Answer questions about code",
            parameters=[
                ToolParameter(name="question", type="string", description="The question"),
            ],
        )
        assert t.name == "code_qa"
        assert len(t.parameters) == 1

    def test_to_openai_schema(self) -> None:
        t = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(name="arg1", type="string", description="First arg"),
                ToolParameter(name="arg2", type="integer", description="Second arg", required=False),
            ],
        )
        schema = t.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "test_tool"
        props = schema["function"]["parameters"]["properties"]
        assert "arg1" in props
        assert "arg2" in props
        assert "arg1" in schema["function"]["parameters"]["required"]
        assert "arg2" not in schema["function"]["parameters"]["required"]


class TestToolCall:
    def test_creation(self) -> None:
        tc = ToolCall(id="call_123", name="code_qa", arguments={"question": "what?"})
        assert tc.id == "call_123"
        assert tc.arguments["question"] == "what?"


class TestToolResult:
    def test_success(self) -> None:
        tr = ToolResult(tool_call_id="call_123", content="answer here")
        assert tr.is_error is False

    def test_error(self) -> None:
        tr = ToolResult(tool_call_id="call_123", content="not found", is_error=True)
        assert tr.is_error is True


class TestConversationMessage:
    def test_user_message(self) -> None:
        m = ConversationMessage(role=MessageRole.USER, content="hello")
        assert m.role == MessageRole.USER
        assert m.tool_calls is None

    def test_assistant_with_tools(self) -> None:
        tc = ToolCall(id="c1", name="test", arguments={})
        m = ConversationMessage(role=MessageRole.ASSISTANT, content="", tool_calls=[tc])
        assert len(m.tool_calls) == 1

    def test_tool_result_message(self) -> None:
        tr = ToolResult(tool_call_id="c1", content="ok")
        m = ConversationMessage(
            role=MessageRole.TOOL,
            content="ok",
            tool_results=[tr],
        )
        assert m.tool_results[0].content == "ok"

    def test_to_openai_dict_user(self) -> None:
        m = ConversationMessage(role=MessageRole.USER, content="hello")
        d = m.to_openai_dict()
        assert d == {"role": "user", "content": "hello"}

    def test_to_openai_dict_assistant_with_tools(self) -> None:
        tc = ToolCall(id="c1", name="test", arguments={"key": "val"})
        m = ConversationMessage(role=MessageRole.ASSISTANT, content="", tool_calls=[tc])
        d = m.to_openai_dict()
        assert d["role"] == "assistant"
        assert len(d["tool_calls"]) == 1
        assert d["tool_calls"][0]["function"]["name"] == "test"

    def test_to_openai_dict_tool_result(self) -> None:
        tr = ToolResult(tool_call_id="c1", content="result text")
        m = ConversationMessage(role=MessageRole.TOOL, content="result text", tool_results=[tr])
        d = m.to_openai_dict()
        assert d["role"] == "tool"
        assert d["tool_call_id"] == "c1"
        assert d["content"] == "result text"