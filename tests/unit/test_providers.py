from __future__ import annotations

from unittest.mock import MagicMock

from ai_code2doc.llm.provider import create_provider


class TestCreateProvider:
    def test_create_openai(self) -> None:
        settings = MagicMock()
        settings.llm_provider = "openai"
        settings.llm_base_url = "https://api.openai.com/v1"
        settings.llm_api_key = "test"
        p = create_provider(settings)
        assert p.__class__.__name__ == "OpenAIProvider"

    def test_create_ollama(self) -> None:
        settings = MagicMock()
        settings.llm_provider = "ollama"
        settings.llm_base_url = "http://localhost:11434/v1"
        settings.llm_api_key = "ollama"
        p = create_provider(settings)
        assert p.__class__.__name__ == "OpenAIProvider"

    def test_create_anthropic(self) -> None:
        settings = MagicMock()
        settings.llm_provider = "anthropic"
        settings.llm_base_url = "https://api.anthropic.com"
        settings.llm_api_key = "test"
        p = create_provider(settings)
        assert p.__class__.__name__ == "AnthropicProvider"

    def test_unknown_provider_raises(self) -> None:
        settings = MagicMock()
        settings.llm_provider = "unknown_provider"
        try:
            create_provider(settings)
            assert False, "Should have raised"
        except ValueError:
            pass
