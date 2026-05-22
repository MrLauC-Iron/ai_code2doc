from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from openai import OpenAI, AsyncOpenAI

from ai_code2doc.config.settings import Settings
from ai_code2doc.llm.token_tracker import TokenTracker


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMClient:
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or Settings()
        self._tracker = TokenTracker()
        self._semaphore = asyncio.Semaphore(self._settings.llm_concurrency)

        client_kwargs = {
            "base_url": self._settings.llm_base_url,
            "api_key": self._settings.llm_api_key or "dummy",
        }
        self._sync_client = OpenAI(**client_kwargs)
        self._async_client = AsyncOpenAI(**client_kwargs)

    @property
    def token_tracker(self) -> TokenTracker:
        return self._tracker

    def generate(self, prompt: str, system: str = "") -> LLMResponse:
        """Synchronous generation."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._sync_client.chat.completions.create(
            model=self._settings.llm_model,
            messages=messages,
            max_tokens=self._settings.llm_max_tokens,
            temperature=self._settings.llm_temperature,
        )

        choice = response.choices[0]
        usage = response.usage

        result = LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
        )
        self._tracker.add(result.prompt_tokens, result.completion_tokens)
        return result

    async def agenerate(self, prompt: str, system: str = "") -> LLMResponse:
        """Async generation with concurrency control."""
        async with self._semaphore:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = await self._async_client.chat.completions.create(
                model=self._settings.llm_model,
                messages=messages,
                max_tokens=self._settings.llm_max_tokens,
                temperature=self._settings.llm_temperature,
            )

            choice = response.choices[0]
            usage = response.usage

            result = LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            )
            self._tracker.add(result.prompt_tokens, result.completion_tokens)
            return result

    async def agenerate_with_tools(
        self,
        messages: list,
        tools: list | None = None,
        system: str = "",
    ) -> tuple[str, list]:
        """Async generation with tool-use support.

        Args:
            messages: List of ConversationMessage objects.
            tools: List of ToolDefinition objects.
            system: Optional system prompt override.

        Returns:
            Tuple of (content, tool_calls) where tool_calls is a list of
            ai_code2doc.agent.models.ToolCall objects.
        """
        from ai_code2doc.agent.models import ToolCall

        async with self._semaphore:
            api_messages = []
            if system:
                api_messages.append({"role": "system", "content": system})
            for msg in messages:
                api_messages.extend(msg.to_openai_messages())

            kwargs: dict = {
                "model": self._settings.llm_model,
                "messages": api_messages,
                "max_tokens": self._settings.llm_max_tokens,
                "temperature": self._settings.llm_temperature,
            }
            if tools:
                kwargs["tools"] = [t.to_openai_schema() for t in tools]

            response = await self._async_client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            usage = response.usage

            if usage:
                self._tracker.add(usage.prompt_tokens, usage.completion_tokens)

            content = choice.message.content or ""
            raw_tool_calls = choice.message.tool_calls

            tool_calls_list: list[ToolCall] = []
            if raw_tool_calls:
                for tc in raw_tool_calls:
                    args = {}
                    if tc.function.arguments:
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            args = {"raw_arguments": tc.function.arguments}
                    tool_calls_list.append(
                        ToolCall(id=tc.id, name=tc.function.name, arguments=args)
                    )

            return content, tool_calls_list
