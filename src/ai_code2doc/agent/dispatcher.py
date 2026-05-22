"""Agent dispatcher: LLM conversation loop with tool-use."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ai_code2doc.agent.conversation import ConversationManager
from ai_code2doc.agent.models import ConversationMessage, ToolResult
from ai_code2doc.agent.tool_registry import ToolRegistry
from ai_code2doc.llm.client import LLMClient

if TYPE_CHECKING:
    from ai_code2doc.agent.context import AgentContext

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5


class AgentDispatcher:
    """Core agent loop: user input -> LLM -> [tool calls -> results] -> answer."""

    def __init__(
        self,
        context: "AgentContext",
        tool_registry: ToolRegistry,
        system_prompt: str = "",
    ) -> None:
        self._context = context
        self._tools = tool_registry
        self._system_prompt = system_prompt or context.build_system_prompt()
        self._llm = context.llm_client
        self._conversation = ConversationManager(
            max_history=context.settings.repl_history_size
        )

    @property
    def conversation(self) -> ConversationManager:
        return self._conversation

    async def process(self, user_input: str) -> str:
        """Process a user message and return the agent's response."""
        self._conversation.add_user(user_input)

        messages = self._conversation.get_context_messages()
        tool_defs = self._tools.get_definitions()

        round_count = 0
        while round_count < MAX_TOOL_ROUNDS:
            content, tool_calls = await self._llm.agenerate_with_tools(
                messages=messages,
                tools=tool_defs if tool_defs else None,
                system=self._system_prompt,
            )

            if not tool_calls:
                self._conversation.add_assistant(content, tool_calls=None)
                return content

            self._conversation.add_assistant(content, tool_calls=tool_calls)

            results: list[ToolResult] = []
            for tc in tool_calls:
                logger.info("Executing tool: %s", tc.name)
                result = await self._tools.execute(tc, self._context)
                results.append(result)

            self._conversation.add_tool_results(results)
            messages = self._conversation.get_context_messages()
            round_count += 1

        return content + "\n\n[Warning: Reached maximum tool-call rounds]"
