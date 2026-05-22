from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from ai_code2doc.agent.models import (
    ConversationMessage,
    MessageRole,
    ToolCall,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)
from ai_code2doc.agent.context import AgentContext
from ai_code2doc.agent.dispatcher import AgentDispatcher
from ai_code2doc.agent.conversation import ConversationManager
from ai_code2doc.agent.tool_registry import ToolRegistry


def _make_settings() -> MagicMock:
    s = MagicMock()
    s.llm_model = "gpt-4o"
    s.llm_max_tokens = 4096
    s.llm_temperature = 0.1
    s.llm_base_url = "https://api.openai.com/v1"
    s.llm_api_key = "test-key"
    s.llm_concurrency = 3
    s.repl_history_size = 10
    s.output_dir = ".ai_code2doc"
    return s


class TestAgentDispatcher:
    def test_process_simple_response(self, tmp_path: Path) -> None:
        """Dispatcher returns content directly when LLM makes no tool calls."""
        settings = _make_settings()
        ctx = AgentContext(project_root=tmp_path, settings=settings)

        tools_def = [
            ToolDefinition(name="code_qa", description="Q&A", parameters=[
                ToolParameter(name="question", type="string", description="Q"),
            ])
        ]

        with patch("ai_code2doc.agent.dispatcher.LLMClient") as MockLLM:
            mock_client = MagicMock()
            mock_client.agenerate_with_tools = AsyncMock(
                return_value=("foo() returns a string.", [])
            )
            mock_client.token_tracker = MagicMock()
            MockLLM.return_value = mock_client

            reg = ToolRegistry()
            reg.register(tools_def[0], AsyncMock())

            dispatcher = AgentDispatcher.__new__(AgentDispatcher)
            dispatcher._llm = mock_client
            dispatcher._tools = reg
            dispatcher._conversation = ConversationManager(max_history=10)
            dispatcher._context = ctx
            dispatcher._system_prompt = ctx.build_system_prompt()

            result = asyncio.run(dispatcher.process("what is foo?"))
            assert "foo() returns a string." in result

    def test_process_with_tool_call(self, tmp_path: Path) -> None:
        """Dispatcher executes tool and returns LLM's final answer."""
        settings = _make_settings()
        ctx = AgentContext(project_root=tmp_path, settings=settings)

        tools_def = [
            ToolDefinition(name="list_context", description="List context", parameters=[]),
        ]

        tc = ToolCall(id="call_1", name="list_context", arguments={})

        call_count = 0

        async def fake_agenerate(messages, tools, system=""):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "", [tc]
            return "The project has 10 files.", []

        with patch("ai_code2doc.agent.dispatcher.LLMClient") as MockLLM:
            mock_client = MagicMock()
            mock_client.agenerate_with_tools = fake_agenerate
            mock_client.token_tracker = MagicMock()
            MockLLM.return_value = mock_client

            async def fake_list_context(tc_call, ctx_obj):
                return ToolResult(tool_call_id=tc_call.id, content="10 files, 500 lines")

            reg = ToolRegistry()
            reg.register(tools_def[0], fake_list_context)

            dispatcher = AgentDispatcher.__new__(AgentDispatcher)
            dispatcher._llm = mock_client
            dispatcher._tools = reg
            dispatcher._conversation = ConversationManager(max_history=10)
            dispatcher._context = ctx
            dispatcher._system_prompt = ctx.build_system_prompt()

            result = asyncio.run(dispatcher.process("show me context"))
            assert "10 files" in result
            assert call_count == 2
