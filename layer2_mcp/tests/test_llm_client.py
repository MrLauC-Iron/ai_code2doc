"""Tests for LLM client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from code2doc_layer2_mcp.config import Layer2Settings
from code2doc_layer2_mcp.llm_client import Layer2LLMClient


class TestLayer2LLMClient:
    def test_init_with_settings(self) -> None:
        settings = Layer2Settings(
            llm_api_key="test-key",
            llm_model="gpt-4o",
        )
        client = Layer2LLMClient(settings)
        assert client is not None

    @pytest.mark.asyncio
    async def test_extract_module_knowledge(self) -> None:
        settings = Layer2Settings(
            llm_api_key="test-key",
            llm_model="gpt-4o",
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="## Auth Module\nAuth handles login."))]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        mock_async_client = AsyncMock()
        mock_async_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("code2doc_layer2_mcp.llm_client.AsyncOpenAI", return_value=mock_async_client):
            client = Layer2LLMClient(settings)
            result = await client.extract_module_knowledge(
                module_name="auth",
                task_description="Implement JWT login",
                layer1_overview="Auth module handles user authentication",
                existing_content="## Auth Module\nBasic auth.",
                code_changes=[{"file": "auth.py", "diff": "+def login()"}],
            )
        assert "## Auth Module" in result
