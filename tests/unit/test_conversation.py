from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from ai_code2doc.agent.conversation import ConversationManager
from ai_code2doc.agent.models import (
    ConversationMessage,
    MessageRole,
    ToolCall,
    ToolResult,
)


class TestConversationManager:
    def test_add_and_get_messages(self) -> None:
        cm = ConversationManager(max_history=5)
        cm.add_user("hello")
        cm.add_assistant("hi there", tool_calls=None)
        msgs = cm.get_context_messages()
        assert len(msgs) == 2
        assert msgs[0].content == "hello"
        assert msgs[1].content == "hi there"

    def test_sliding_window(self) -> None:
        cm = ConversationManager(max_history=3)
        cm.add_user("q1")
        cm.add_assistant("a1", tool_calls=None)
        cm.add_user("q2")
        cm.add_assistant("a2", tool_calls=None)
        cm.add_user("q3")
        cm.add_assistant("a3", tool_calls=None)
        msgs = cm.get_context_messages()
        assert len(msgs) == 3
        assert msgs[0].content == "q2"

    def test_add_tool_results(self) -> None:
        cm = ConversationManager(max_history=10)
        cm.add_user("what is foo?")
        tc = ToolCall(id="c1", name="code_qa", arguments={"question": "foo"})
        cm.add_assistant("", tool_calls=[tc])
        tr = ToolResult(tool_call_id="c1", content="foo is a function")
        cm.add_tool_results([tr])
        msgs = cm.get_context_messages()
        assert len(msgs) == 3
        assert msgs[2].role == MessageRole.TOOL

    def test_to_openai_messages(self) -> None:
        cm = ConversationManager(max_history=10)
        cm.add_user("hello")
        api_msgs = cm.to_openai_messages()
        assert len(api_msgs) == 1
        assert api_msgs[0] == {"role": "user", "content": "hello"}

    def test_to_openai_messages_with_tools(self) -> None:
        cm = ConversationManager(max_history=10)
        cm.add_user("check foo")
        tc = ToolCall(id="c1", name="code_qa", arguments={"question": "foo"})
        cm.add_assistant("", tool_calls=[tc])
        tr = ToolResult(tool_call_id="c1", content="result")
        cm.add_tool_results([tr])
        api_msgs = cm.to_openai_messages()
        assert len(api_msgs) == 3
        assert api_msgs[2]["role"] == "tool"
        assert api_msgs[2]["content"] == "result"

    def test_save_and_load(self, tmp_path: Path) -> None:
        cm = ConversationManager(max_history=5)
        cm.add_user("test message")
        path = tmp_path / "session.json"
        cm.save(path)
        cm2 = ConversationManager(max_history=5)
        cm2.load(path)
        msgs = cm2.get_context_messages()
        assert len(msgs) == 1
        assert msgs[0].content == "test message"

    def test_clear(self) -> None:
        cm = ConversationManager(max_history=10)
        cm.add_user("hello")
        cm.clear()
        assert len(cm.get_context_messages()) == 0