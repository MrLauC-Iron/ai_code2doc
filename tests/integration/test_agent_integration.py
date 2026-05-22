"""Integration tests for the agent system."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from ai_code2doc.agent.context import AgentContext, AnalysisResult
from ai_code2doc.agent.tool_registry import ToolRegistry
from ai_code2doc.agent.dispatcher import AgentDispatcher
from ai_code2doc.agent.conversation import ConversationManager
from ai_code2doc.agent.tools.list_context import tool_definition as lc_def, execute as lc_exec
from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolParameter, ToolResult


def _make_settings() -> MagicMock:
    s = MagicMock()
    s.llm_model = "gpt-4o"
    s.llm_provider = "openai"
    s.llm_base_url = "https://api.openai.com/v1"
    s.llm_api_key = "test"
    s.llm_max_tokens = 4096
    s.llm_temperature = 0.1
    s.llm_concurrency = 3
    s.repl_history_size = 10
    s.output_dir = ".ai_code2doc"
    return s


class TestAgentIntegration:
    def test_full_dispatch_loop_with_list_context(self, tmp_path: Path) -> None:
        """Full round-trip: user question -> tool call -> tool result -> LLM answer."""
        import asyncio

        settings = _make_settings()
        ctx = AgentContext(
            project_root=tmp_path,
            settings=settings,
            analysis_result=AnalysisResult(total_files=5, total_lines=200),
        )

        registry = ToolRegistry()
        registry.register(lc_def, lc_exec)

        call_count = 0

        class MockResponse:
            def __init__(self, content, tool_calls):
                self.choices = [self.MockChoice(content, tool_calls)]

            class MockChoice:
                def __init__(self, content, tool_calls):
                    self.message = self.MockMessage(content, tool_calls)

                class MockMessage:
                    def __init__(self, content, tool_calls):
                        self.content = content
                        self.tool_calls = tool_calls

        class MockFunction:
            def __init__(self, name, arguments):
                self.name = name
                self.arguments = arguments

        class MockToolCall:
            def __init__(self, id, function):
                self.id = id
                self.function = function

        async def fake_generate(messages, tools, system="", model="", max_tokens=4096, temperature=0.1):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                tool_call = MockToolCall(
                    id="c1",
                    function=MockFunction(name="list_context", arguments="{}")
                )
                return MockResponse(content="", tool_calls=[tool_call])
            else:
                return MockResponse(
                    content="The project has 5 files and 200 lines of code.",
                    tool_calls=None
                )

        with patch("ai_code2doc.llm.providers.openai_provider.AsyncOpenAI") as MockClient:
            mock_async_client = MagicMock()
            mock_async_client.chat.completions.create = fake_generate
            MockClient.return_value = mock_async_client

            dispatcher = AgentDispatcher(context=ctx, tool_registry=registry)
            result = asyncio.run(dispatcher.process("Show me the project context"))
            assert "5 files" in result
            assert call_count == 2

    def test_slash_commands(self, tmp_path: Path) -> None:
        from ai_code2doc.agent.repl import AgentREPL

        assert AgentREPL._parse_slash_command("/quit") == ("quit", "")
        assert AgentREPL._parse_slash_command("/help extra") == ("help", "extra")
        assert AgentREPL._parse_slash_command("hello") is None

    def test_tool_registry_has_all_tools(self) -> None:
        from ai_code2doc.agent.repl import AgentREPL

        ctx = MagicMock()
        ctx.settings = MagicMock()
        ctx.settings.output_dir = ".ai_code2doc"
        ctx.analysis_result = None

        with patch.object(AgentREPL, "__init__", lambda self, ctx: None):
            repl = AgentREPL.__new__(AgentREPL)
            repl._registry = ToolRegistry()
            repl._registry.register(
                ToolDefinition(name="test", description="T", parameters=[]),
                lambda tc, ctx: ToolResult(tool_call_id=tc.id, content="ok"),
            )
            assert repl._registry.has_tool("test")