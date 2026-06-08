"""LLM client for Layer 2 knowledge extraction."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from code2doc_layer2_mcp.config import Layer2Settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a technical documentation writer. Given information about a code module \
and recent changes, produce an updated module documentation file in Markdown.

## Rules
- Keep the document factual and concise.
- Preserve existing sections that are still accurate.
- Update or add sections based on new changes.
- Use proper Markdown formatting with headers, code blocks, and lists.
- If existing content is provided, merge the new information into it rather \
than replacing everything.
- Respond with ONLY the Markdown content, no explanations outside it.
"""


class Layer2LLMClient:
    """Async LLM client for module knowledge extraction."""

    def __init__(self, settings: Layer2Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "dummy",
        )

    async def extract_module_knowledge(
        self,
        module_name: str,
        task_description: str,
        layer1_overview: str,
        existing_content: str,
        code_changes: list[dict[str, str]],
    ) -> str:
        """Extract/update module documentation from task context.

        Args:
            module_name: Name of the target module.
            task_description: What task was performed.
            layer1_overview: Project overview (Layer 1 doc).
            existing_content: Current module doc content (if any).
            code_changes: List of dicts with 'file', 'diff', 'action' keys.

        Returns:
            Updated module documentation in Markdown.
        """
        changes_text = "\n".join(
            f"- **{c.get('file', '?')}** ({c.get('action', 'modified')}):\n```diff\n{c.get('diff', '')}\n```"
            for c in code_changes
        )

        user_prompt = f"""\
## Task
{task_description}

## Module
{module_name}

## Project Overview (Layer 1)
{layer1_overview}

## Existing Module Documentation
{existing_content if existing_content else '(No existing documentation)'}

## Code Changes
{changes_text if changes_text else '(No code changes provided)'}

Produce an updated Markdown documentation file for the '{module_name}' module.
"""

        response = await self._client.chat.completions.create(
            model=self._settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self._settings.llm_max_tokens,
            temperature=self._settings.llm_temperature,
        )

        choice = response.choices[0]
        return choice.message.content or ""
