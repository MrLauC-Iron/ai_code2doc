"""OpenAI-compatible provider (also used for Ollama and custom endpoints)."""

from __future__ import annotations

import json

from openai import AsyncOpenAI

from ai_code2doc.llm.provider import LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(self, settings) -> None:
        self._model = settings.llm_model
        self._client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "dummy",
        )

    async def generate_with_tools(
        self,
        messages,
        tools=None,
        system="",
        model="",
        max_tokens=4096,
        temperature=0.1,
    ) -> tuple[str, list]:
        from ai_code2doc.agent.models import ToolCall

        api_messages = []
        if system:
            api_messages.append({"role": "system", "content": system})
        for msg in messages:
            api_messages.extend(msg.to_openai_messages())

        kwargs = {
            "model": model or self._model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = [t.to_openai_schema() for t in tools]

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        content = choice.message.content or ""
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {"raw": tc.function.arguments}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        return content, tool_calls
