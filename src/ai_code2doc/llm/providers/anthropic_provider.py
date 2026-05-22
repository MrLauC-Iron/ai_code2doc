"""Anthropic provider using the native Anthropic SDK."""

from __future__ import annotations

from ai_code2doc.llm.provider import LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, settings) -> None:
        self._model = settings.llm_model or "claude-sonnet-4-20250514"
        self._api_key = settings.llm_api_key or "dummy"
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

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

        anthropic_messages = []
        for msg in messages:
            if msg.role.value == "tool":
                for tr in msg.tool_results or []:
                    anthropic_messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tr.tool_call_id,
                                    "content": tr.content,
                                }
                            ],
                        }
                    )
            elif msg.role.value == "assistant" and msg.tool_calls:
                content_blocks = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
                anthropic_messages.append({"role": "assistant", "content": content_blocks})
            elif msg.role.value == "system":
                pass
            else:
                anthropic_messages.append({"role": msg.role.value, "content": msg.content})

        anthropic_tools = None
        if tools:
            anthropic_tools = []
            for t in tools:
                param_schema = {"type": "object", "properties": {}, "required": []}
                if t.parameters:
                    properties = {}
                    required = []
                    for p in t.parameters:
                        prop = {"type": p.type, "description": p.description}
                        if p.enum:
                            prop["enum"] = p.enum
                        properties[p.name] = prop
                        if p.required:
                            required.append(p.name)
                    param_schema["properties"] = properties
                    param_schema["required"] = required
                anthropic_tools.append(
                    {
                        "name": t.name,
                        "description": t.description,
                        "input_schema": param_schema,
                    }
                )

        client = self._get_client()
        kwargs = {
            "model": model or self._model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = await client.messages.create(**kwargs)

        content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input or {}))

        return content, tool_calls
