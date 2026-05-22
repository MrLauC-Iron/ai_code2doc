from __future__ import annotations

import asyncio

from unittest.mock import MagicMock, AsyncMock, patch

from ai_code2doc.agent.models import (
    ConversationMessage,
    MessageRole,
    ToolCall,
    ToolDefinition,
    ToolParameter,
)


class TestLLMClientToolUse:
    async def test_agenerate_with_tools_returns_content_and_calls(self) -> None:
        """agenerate_with_tools returns (content, tool_calls) from OpenAI response."""
        import asyncio

        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Let me check that."
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_abc"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "code_qa"
        mock_tool_call.function.arguments = '{"question": "what is foo?"}'
        mock_choice.message.tool_calls = [mock_tool_call]
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150
        mock_response.model = "gpt-4o"

        tools = [
            ToolDefinition(
                name="code_qa",
                description="Q&A",
                parameters=[ToolParameter(name="question", type="string", description="Q")],
            )
        ]
        messages = [ConversationMessage(role=MessageRole.USER, content="what is foo?")]

        settings_mock = MagicMock()
        settings_mock.llm_model = "gpt-4o"
        settings_mock.llm_max_tokens = 4096
        settings_mock.llm_temperature = 0.1
        settings_mock.llm_base_url = "https://api.openai.com/v1"
        settings_mock.llm_api_key = "test"
        settings_mock.llm_concurrency = 3

        with patch("ai_code2doc.llm.client.AsyncOpenAI") as mock_async_openai:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_async_openai.return_value = mock_client

            from ai_code2doc.llm.client import LLMClient

            client = LLMClient(settings_mock)
            content, calls = await client.agenerate_with_tools(messages, tools)
            assert content == "Let me check that."
            assert len(calls) == 1
            assert calls[0].name == "code_qa"
            assert calls[0].arguments["question"] == "what is foo?"

    async def test_agenerate_with_tools_no_tool_calls(self) -> None:
        """When LLM returns no tool_calls, returns (content, [])."""
        import asyncio

        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "foo() returns a string."
        mock_choice.message.tool_calls = None
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 70
        mock_response.model = "gpt-4o"

        messages = [ConversationMessage(role=MessageRole.USER, content="what is foo?")]
        tools = [
            ToolDefinition(
                name="code_qa",
                description="Q&A",
                parameters=[ToolParameter(name="question", type="string", description="Q")],
            )
        ]

        settings_mock = MagicMock()
        settings_mock.llm_model = "gpt-4o"
        settings_mock.llm_max_tokens = 4096
        settings_mock.llm_temperature = 0.1
        settings_mock.llm_base_url = "https://api.openai.com/v1"
        settings_mock.llm_api_key = "test"
        settings_mock.llm_concurrency = 3

        with patch("ai_code2doc.llm.client.AsyncOpenAI") as mock_async_openai:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_async_openai.return_value = mock_client

            from ai_code2doc.llm.client import LLMClient

            client = LLMClient(settings_mock)
            content, calls = await client.agenerate_with_tools(messages, tools)
            assert content == "foo() returns a string."
            assert calls == []