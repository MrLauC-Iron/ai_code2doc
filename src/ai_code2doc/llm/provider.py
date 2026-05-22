"""LLM provider factory and abstract interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_code2doc.agent.models import ToolCall, ToolDefinition


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate_with_tools(
        self,
        messages: list,
        tools: list[ToolDefinition] | None = None,
        system: str = "",
        model: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> tuple[str, list[ToolCall]]:
        """Generate a response, optionally using tools. Returns (content, tool_calls)."""
        ...


def create_provider(settings) -> LLMProvider:
    """Create a provider based on settings."""
    provider_name = settings.llm_provider.lower()

    if provider_name in ("openai", "ollama", "custom"):
        from ai_code2doc.llm.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(settings)
    elif provider_name == "anthropic":
        from ai_code2doc.llm.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings)
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
