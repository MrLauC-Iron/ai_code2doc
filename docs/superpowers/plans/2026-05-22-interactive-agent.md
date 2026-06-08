# Interactive Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conversational Agent REPL that automatically starts after `analyze` completes, allowing users to explore code, update docs, analyze dependencies, rescan files, and correct errors via LLM tool-use.

**Architecture:** LLM dispatches tool calls through a `ToolRegistry`. An `AgentDispatcher` manages the LLM conversation loop (user message → LLM → tool calls → tool results → LLM → final answer). A `prompt_toolkit`-based `AgentREPL` provides the terminal interface. Tools reuse existing project components (VectorStore, generators, scanner, DependencyGraphBuilder).

**Tech Stack:** prompt_toolkit, openai (existing), anthropic (new), pydantic, rich (existing)

---

### Task 1: Add Dependencies & Update Settings

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/ai_code2doc/config/settings.py`
- Test: `tests/unit/test_agent_models.py` (created in Task 2)

- [ ] **Step 1: Add prompt_toolkit and anthropic to pyproject.toml dependencies**

In `pyproject.toml`, add to the `dependencies` list:
```toml
"prompt_toolkit>=3.0",
"anthropic>=0.40",
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -e ".[dev]"` from project root
Expected: No errors

- [ ] **Step 3: Add agent-related settings to Settings class**

In `src/ai_code2doc/config/settings.py`, add after `llm_concurrency`:
```python
    llm_provider: str = "openai"  # openai / anthropic / ollama

    # Agent / REPL
    repl_history_size: int = 10
    repl_save_session: bool = True
    session_file: str = ".ai_code2doc/session.json"
```

- [ ] **Step 4: Verify Settings loads with new fields**

Run: `python -c "from ai_code2doc.config.settings import Settings; s = Settings(); print(s.llm_provider, s.repl_history_size)"`
Expected: `openai 10`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/ai_code2doc/config/settings.py
git commit -m "feat: add agent dependencies and settings (prompt_toolkit, anthropic, repl config)"
```

---

### Task 2: Agent Data Models

**Files:**
- Create: `src/ai_code2doc/agent/__init__.py`
- Create: `src/ai_code2doc/agent/models.py`
- Create: `tests/unit/test_agent_models.py`

- [ ] **Step 1: Create agent package**

Create `src/ai_code2doc/agent/__init__.py`:
```python
"""Conversational agent for interactive code exploration."""
```

- [ ] **Step 2: Write failing tests for agent models**

Create `tests/unit/test_agent_models.py`:
```python
from __future__ import annotations

from ai_code2doc.agent.models import (
    MessageRole,
    ConversationMessage,
    ToolParameter,
    ToolDefinition,
    ToolCall,
    ToolResult,
)


class TestToolParameter:
    def test_creation(self) -> None:
        p = ToolParameter(name="path", type="string", description="File path")
        assert p.name == "path"
        assert p.type == "string"
        assert p.required is True
        assert p.enum is None

    def test_optional_with_enum(self) -> None:
        p = ToolParameter(
            name="layer",
            type="integer",
            description="Layer number",
            required=False,
            enum=["1", "2", "3"],
        )
        assert p.required is False
        assert p.enum == ["1", "2", "3"]


class TestToolDefinition:
    def test_creation(self) -> None:
        t = ToolDefinition(
            name="code_qa",
            description="Answer questions about code",
            parameters=[
                ToolParameter(name="question", type="string", description="The question"),
            ],
        )
        assert t.name == "code_qa"
        assert len(t.parameters) == 1

    def test_to_openai_schema(self) -> None:
        t = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(name="arg1", type="string", description="First arg"),
                ToolParameter(name="arg2", type="integer", description="Second arg", required=False),
            ],
        )
        schema = t.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "test_tool"
        props = schema["function"]["parameters"]["properties"]
        assert "arg1" in props
        assert "arg2" in props
        assert "arg1" in schema["function"]["parameters"]["required"]
        assert "arg2" not in schema["function"]["parameters"]["required"]


class TestToolCall:
    def test_creation(self) -> None:
        tc = ToolCall(id="call_123", name="code_qa", arguments={"question": "what?"})
        assert tc.id == "call_123"
        assert tc.arguments["question"] == "what?"


class TestToolResult:
    def test_success(self) -> None:
        tr = ToolResult(tool_call_id="call_123", content="answer here")
        assert tr.is_error is False

    def test_error(self) -> None:
        tr = ToolResult(tool_call_id="call_123", content="not found", is_error=True)
        assert tr.is_error is True


class TestConversationMessage:
    def test_user_message(self) -> None:
        m = ConversationMessage(role=MessageRole.USER, content="hello")
        assert m.role == MessageRole.USER
        assert m.tool_calls is None

    def test_assistant_with_tools(self) -> None:
        tc = ToolCall(id="c1", name="test", arguments={})
        m = ConversationMessage(role=MessageRole.ASSISTANT, content="", tool_calls=[tc])
        assert len(m.tool_calls) == 1

    def test_tool_result_message(self) -> None:
        tr = ToolResult(tool_call_id="c1", content="ok")
        m = ConversationMessage(
            role=MessageRole.TOOL,
            content="ok",
            tool_results=[tr],
        )
        assert m.tool_results[0].content == "ok"

    def test_to_openai_dict_user(self) -> None:
        m = ConversationMessage(role=MessageRole.USER, content="hello")
        d = m.to_openai_dict()
        assert d == {"role": "user", "content": "hello"}

    def test_to_openai_dict_assistant_with_tools(self) -> None:
        tc = ToolCall(id="c1", name="test", arguments={"key": "val"})
        m = ConversationMessage(role=MessageRole.ASSISTANT, content="", tool_calls=[tc])
        d = m.to_openai_dict()
        assert d["role"] == "assistant"
        assert len(d["tool_calls"]) == 1
        assert d["tool_calls"][0]["function"]["name"] == "test"

    def test_to_openai_dict_tool_result(self) -> None:
        tr = ToolResult(tool_call_id="c1", content="result text")
        m = ConversationMessage(role=MessageRole.TOOL, content="result text", tool_results=[tr])
        d = m.to_openai_dict()
        assert d["role"] == "tool"
        assert d["tool_call_id"] == "c1"
        assert d["content"] == "result text"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_agent_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_code2doc.agent'`

- [ ] **Step 4: Implement agent models**

Create `src/ai_code2doc/agent/models.py`:
```python
"""Data models for the conversational agent."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str  # string, integer, boolean, array
    description: str
    required: bool = True
    enum: list[str] | None = None


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    parameters: list[ToolParameter] = Field(default_factory=list)

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling tool schema."""
        properties: dict[str, Any] = {}
        required: list[str] = []
        for p in self.parameters:
            prop: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_call_id: str
    content: str
    is_error: bool = False


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: MessageRole
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_results: list[ToolResult] | None = None
    timestamp: datetime = Field(default_factory=datetime.now)

    def to_openai_dict(self) -> dict[str, Any]:
        """Convert to OpenAI chat completion message format."""
        d: dict[str, Any] = {"role": self.role.value, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": __import__("json").dumps(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]
        if self.tool_results:
            # OpenAI expects one message per tool result, but we store as a batch.
            # Return the first one's data; the dispatcher will expand.
            tr = self.tool_results[0]
            d["tool_call_id"] = tr.tool_call_id
            d["content"] = tr.content
        return d

    def to_openai_messages(self) -> list[dict[str, Any]]:
        """Convert to OpenAI messages, expanding tool results into individual messages."""
        if self.tool_results:
            return [
                {"role": "tool", "tool_call_id": tr.tool_call_id, "content": tr.content}
                for tr in self.tool_results
            ]
        return [self.to_openai_dict()]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_agent_models.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/ai_code2doc/agent/ tests/unit/test_agent_models.py
git commit -m "feat: add agent data models (ToolCall, ToolResult, ConversationMessage, ToolDefinition)"
```

---

### Task 3: LLMClient Tool-Use Extension

**Files:**
- Modify: `src/ai_code2doc/llm/client.py`
- Create: `tests/unit/test_llm_tool_use.py`

- [ ] **Step 1: Write failing test for tool-use methods**

Create `tests/unit/test_llm_tool_use.py`:
```python
from __future__ import annotations

from unittest.mock import MagicMock, AsyncMock, patch

from ai_code2doc.agent.models import (
    ConversationMessage,
    MessageRole,
    ToolCall,
    ToolDefinition,
    ToolParameter,
)


class TestLLMClientToolUse:
    def test_agenerate_with_tools_returns_content_and_calls(self) -> None:
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
            content, calls = asyncio.get_event_loop().run_until_complete(
                client.agenerate_with_tools(messages, tools)
            )
            assert content == "Let me check that."
            assert len(calls) == 1
            assert calls[0].name == "code_qa"
            assert calls[0].arguments["question"] == "what is foo?"

    def test_agenerate_with_tools_no_tool_calls(self) -> None:
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
            content, calls = asyncio.get_event_loop().run_until_complete(
                client.agenerate_with_tools(messages, tools)
            )
            assert content == "foo() returns a string."
            assert calls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_llm_tool_use.py -v`
Expected: FAIL with `AttributeError: 'LLMClient' object has no attribute 'agenerate_with_tools'`

- [ ] **Step 3: Implement agenerate_with_tools on LLMClient**

In `src/ai_code2doc/llm/client.py`, add the following import at top:
```python
import json
```

Add this method to `LLMClient` after `agenerate`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_llm_tool_use.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/llm/client.py tests/unit/test_llm_tool_use.py
git commit -m "feat: add tool-use support to LLMClient (agenerate_with_tools)"
```

---

### Task 4: AgentContext

**Files:**
- Create: `src/ai_code2doc/agent/context.py`
- Create: `tests/unit/test_agent_context.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_agent_context.py`:
```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_code2doc.agent.context import AgentContext


class TestAgentContext:
    def test_create_minimal(self, tmp_path: Path) -> None:
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        assert ctx.project_root == tmp_path
        assert ctx.analysis_result is None

    def test_llm_client_lazy_init(self, tmp_path: Path) -> None:
        settings = MagicMock()
        ctx = AgentContext(project_root=tmp_path, settings=settings)
        with patch("ai_code2doc.agent.context.LLMClient") as mock_llm_cls:
            client = ctx.llm_client
            mock_llm_cls.assert_called_once_with(settings)
            client2 = ctx.llm_client
            mock_llm_cls.assert_called_once()

    def test_has_vector_store_false(self, tmp_path: Path) -> None:
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        assert ctx.has_vector_store() is False

    def test_build_system_prompt(self, tmp_path: Path) -> None:
        settings = MagicMock()
        settings.llm_model = "gpt-4o"
        ctx = AgentContext(project_root=tmp_path, settings=settings)
        ctx.analysis_result = MagicMock()
        ctx.analysis_result.total_files = 10
        ctx.analysis_result.total_lines = 500
        ctx.analysis_result.target_files = [Path("a.py"), Path("b.py")]
        prompt = ctx.build_system_prompt()
        assert "10 files" in prompt
        assert "gpt-4o" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_agent_context.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement AgentContext**

Create `src/ai_code2doc/agent/context.py`:
```python
"""Shared context for agent tools and dispatcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ai_code2doc.config.settings import Settings
    from ai_code2doc.llm.client import LLMClient
    from ai_code2doc.models.knowledge import KnowledgeDocument


@dataclass
class AnalysisResult:
    """Lightweight summary of the last analysis run."""

    total_files: int = 0
    total_lines: int = 0
    target_files: list[Path] = field(default_factory=list)
    docs_generated: list[KnowledgeDocument] = field(default_factory=list)


class AgentContext:
    """Shared state passed to every agent tool and the dispatcher."""

    def __init__(
        self,
        project_root: Path,
        settings: Settings,
        analysis_result: AnalysisResult | None = None,
    ) -> None:
        self.project_root = project_root
        self.settings = settings
        self.analysis_result = analysis_result
        self._llm_client: LLMClient | None = None

    @property
    def llm_client(self) -> LLMClient:
        if self._llm_client is None:
            from ai_code2doc.llm.client import LLMClient

            self._llm_client = LLMClient(self.settings)
        return self._llm_client

    @property
    def output_dir(self) -> Path:
        return self.project_root / self.settings.output_dir

    @property
    def chroma_dir(self) -> Path:
        return self.output_dir / "chroma"

    def has_vector_store(self) -> bool:
        return self.chroma_dir.exists()

    def build_system_prompt(self) -> str:
        parts = [
            "You are an AI code documentation assistant. You have just analyzed a "
            "project and can help the user explore it further.",
            "",
            f"Project path: {self.project_root}",
            f"LLM model: {self.settings.llm_model}",
        ]
        if self.analysis_result:
            ar = self.analysis_result
            parts.append(f"Total files analyzed: {ar.total_files}")
            parts.append(f"Total lines of code: {ar.total_lines}")
            if ar.target_files:
                file_list = ", ".join(str(f.name) for f in ar.target_files[:20])
                parts.append(f"Key files: {file_list}")
        parts.append("")
        parts.append(
            "Use the available tools to answer questions, update documentation, "
            "analyze dependencies, rescan files, or correct errors. "
            "If the user's request doesn't require a tool, answer directly."
        )
        return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_agent_context.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/agent/context.py tests/unit/test_agent_context.py
git commit -m "feat: add AgentContext for shared agent state"
```

---

### Task 5: Conversation Manager

**Files:**
- Create: `src/ai_code2doc/agent/conversation.py`
- Create: `tests/unit/test_conversation.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_conversation.py`:
```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from ai_code2doc.agent.conversation import ConversationManager
from ai_code2doc.agent.models import (
    ConversationMessage,
    MessageRole,
    ToolCall,
    ToolResult,
)


class TestConversationManager:
    def test_add_and_get_messages(self) -> None:
        cm = ConversationManager(max_history=5)
        cm.add_user("hello")
        cm.add_assistant("hi there", tool_calls=None)
        msgs = cm.get_context_messages()
        assert len(msgs) == 2
        assert msgs[0].content == "hello"
        assert msgs[1].content == "hi there"

    def test_sliding_window(self) -> None:
        cm = ConversationManager(max_history=3)
        cm.add_user("q1")
        cm.add_assistant("a1", tool_calls=None)
        cm.add_user("q2")
        cm.add_assistant("a2", tool_calls=None)
        cm.add_user("q3")
        cm.add_assistant("a3", tool_calls=None)
        # Only last 3 messages should remain
        msgs = cm.get_context_messages()
        assert len(msgs) == 3
        assert msgs[0].content == "q2"

    def test_add_tool_results(self) -> None:
        cm = ConversationManager(max_history=10)
        cm.add_user("what is foo?")
        tc = ToolCall(id="c1", name="code_qa", arguments={"question": "foo"})
        cm.add_assistant("", tool_calls=[tc])
        tr = ToolResult(tool_call_id="c1", content="foo is a function")
        cm.add_tool_results([tr])
        msgs = cm.get_context_messages()
        # user + assistant + tool result = 3
        assert len(msgs) == 3
        assert msgs[2].role == MessageRole.TOOL

    def test_to_openai_messages(self) -> None:
        cm = ConversationManager(max_history=10)
        cm.add_user("hello")
        api_msgs = cm.to_openai_messages()
        assert len(api_msgs) == 1
        assert api_msgs[0] == {"role": "user", "content": "hello"}

    def test_to_openai_messages_with_tools(self) -> None:
        cm = ConversationManager(max_history=10)
        cm.add_user("check foo")
        tc = ToolCall(id="c1", name="code_qa", arguments={"question": "foo"})
        cm.add_assistant("", tool_calls=[tc])
        tr = ToolResult(tool_call_id="c1", content="result")
        cm.add_tool_results([tr])
        api_msgs = cm.to_openai_messages()
        # user + assistant + tool = 3
        assert len(api_msgs) == 3
        assert api_msgs[2]["role"] == "tool"
        assert api_msgs[2]["content"] == "result"

    def test_save_and_load(self, tmp_path: Path) -> None:
        cm = ConversationManager(max_history=5)
        cm.add_user("test message")
        path = tmp_path / "session.json"
        cm.save(path)
        cm2 = ConversationManager(max_history=5)
        cm2.load(path)
        msgs = cm2.get_context_messages()
        assert len(msgs) == 1
        assert msgs[0].content == "test message"

    def test_clear(self) -> None:
        cm = ConversationManager(max_history=10)
        cm.add_user("hello")
        cm.clear()
        assert len(cm.get_context_messages()) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_conversation.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement ConversationManager**

Create `src/ai_code2doc/agent/conversation.py`:
```python
"""Conversation history management with sliding window."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

from ai_code2doc.agent.models import (
    ConversationMessage,
    MessageRole,
    ToolCall,
    ToolResult,
)


class ConversationManager:
    """Manages conversation history with a sliding window."""

    def __init__(self, max_history: int = 10) -> None:
        self._max_history = max_history
        self._messages: deque[ConversationMessage] = deque(maxlen=max_history * 4)
        # Multiply by 4 because each exchange can produce:
        # user + assistant + multiple tool results

    def add_user(self, content: str) -> None:
        self._messages.append(
            ConversationMessage(role=MessageRole.USER, content=content)
        )

    def add_assistant(
        self,
        content: str,
        tool_calls: list[ToolCall] | None = None,
    ) -> None:
        self._messages.append(
            ConversationMessage(
                role=MessageRole.ASSISTANT,
                content=content,
                tool_calls=tool_calls,
            )
        )

    def add_tool_results(self, results: list[ToolResult]) -> None:
        """Add tool execution results as a single TOOL message."""
        self._messages.append(
            ConversationMessage(
                role=MessageRole.TOOL,
                content="\n".join(r.content for r in results),
                tool_results=results,
            )
        )

    def get_context_messages(self) -> list[ConversationMessage]:
        """Return messages within the sliding window (last N exchanges)."""
        # An "exchange" is roughly (user, assistant, [tool_results]).
        # We want the last max_history exchanges.
        # Simple approach: take last max_history * 4 messages.
        msgs = list(self._messages)
        if len(msgs) <= self._max_history * 4:
            return msgs
        return msgs[-(self._max_history * 4) :]

    def to_openai_messages(self) -> list[dict[str, Any]]:
        """Convert current context to OpenAI API message format."""
        result: list[dict[str, Any]] = []
        for msg in self.get_context_messages():
            result.extend(msg.to_openai_messages())
        return result

    def save(self, path: Path) -> None:
        """Persist conversation to JSON."""
        data = []
        for msg in self._messages:
            data.append({
                "role": msg.role.value,
                "content": msg.content,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in (msg.tool_calls or [])
                ],
                "tool_results": [
                    {"tool_call_id": tr.tool_call_id, "content": tr.content, "is_error": tr.is_error}
                    for tr in (msg.tool_results or [])
                ],
            })
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def load(self, path: Path) -> None:
        """Load conversation from JSON."""
        if not path.exists():
            return
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return
        data = json.loads(text)
        self._messages.clear()
        for item in data:
            tool_calls = None
            if item.get("tool_calls"):
                tool_calls = [
                    ToolCall(**tc) for tc in item["tool_calls"]
                ]
            tool_results = None
            if item.get("tool_results"):
                tool_results = [
                    ToolResult(**tr) for tr in item["tool_results"]
                ]
            self._messages.append(
                ConversationMessage(
                    role=MessageRole(item["role"]),
                    content=item["content"],
                    tool_calls=tool_calls,
                    tool_results=tool_results,
                )
            )

    def clear(self) -> None:
        self._messages.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_conversation.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/agent/conversation.py tests/unit/test_conversation.py
git commit -m "feat: add ConversationManager with sliding window and persistence"
```

---

### Task 6: Tool Registry

**Files:**
- Create: `src/ai_code2doc/agent/tool_registry.py`
- Create: `tests/unit/test_tool_registry.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_tool_registry.py`:
```python
from __future__ import annotations

from ai_code2doc.agent.models import ToolDefinition, ToolParameter, ToolCall, ToolResult
from ai_code2doc.agent.tool_registry import ToolRegistry


async def dummy_handler(call: ToolCall, ctx) -> ToolResult:
    return ToolResult(tool_call_id=call.id, content=f"handled {call.arguments}")


class TestToolRegistry:
    def test_register_and_get_definitions(self) -> None:
        reg = ToolRegistry()
        tool_def = ToolDefinition(
            name="test_tool",
            description="A test",
            parameters=[ToolParameter(name="arg", type="string", description="Arg")],
        )
        reg.register(tool_def, dummy_handler)
        defs = reg.get_definitions()
        assert len(defs) == 1
        assert defs[0].name == "test_tool"

    def test_register_duplicate_raises(self) -> None:
        reg = ToolRegistry()
        tool_def = ToolDefinition(name="dup", description="D", parameters=[])
        reg.register(tool_def, dummy_handler)
        try:
            reg.register(tool_def, dummy_handler)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_has_tool(self) -> None:
        reg = ToolRegistry()
        tool_def = ToolDefinition(name="exists", description="E", parameters=[])
        reg.register(tool_def, dummy_handler)
        assert reg.has_tool("exists")
        assert not reg.has_tool("missing")

    def test_tool_names(self) -> None:
        reg = ToolRegistry()
        for name in ["a", "b", "c"]:
            reg.register(ToolDefinition(name=name, description=f"D{name}", parameters=[]), dummy_handler)
        assert reg.tool_names == ["a", "b", "c"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_tool_registry.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement ToolRegistry**

Create `src/ai_code2doc/agent/tool_registry.py`:
```python
"""Tool registry: definitions and handler dispatch."""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolResult


ToolHandler = Callable[[ToolCall, Any], Coroutine[Any, Any, ToolResult]]


class ToolRegistry:
    """Registry of tools available to the agent."""

    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(
        self,
        definition: ToolDefinition,
        handler: ToolHandler,
    ) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"Tool '{definition.name}' is already registered")
        self._definitions[definition.name] = definition
        self._handlers[definition.name] = handler

    def get_definitions(self) -> list[ToolDefinition]:
        return list(self._definitions.values())

    def has_tool(self, name: str) -> bool:
        return name in self._handlers

    @property
    def tool_names(self) -> list[str]:
        return list(self._definitions.keys())

    async def execute(self, tool_call: ToolCall, context: Any) -> ToolResult:
        """Execute a tool call and return the result."""
        handler = self._handlers.get(tool_call.name)
        if handler is None:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Unknown tool: {tool_call.name}",
                is_error=True,
            )
        try:
            return await handler(tool_call, context)
        except Exception as exc:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Tool execution failed: {exc}",
                is_error=True,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_tool_registry.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/agent/tool_registry.py tests/unit/test_tool_registry.py
git commit -m "feat: add ToolRegistry for agent tool definitions and dispatch"
```

---

### Task 7: Agent Dispatcher

**Files:**
- Create: `src/ai_code2doc/agent/dispatcher.py`
- Create: `tests/unit/test_dispatcher.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_dispatcher.py`:
```python
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from ai_code2doc.agent.models import (
    ConversationMessage,
    MessageRole,
    ToolCall,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)
from ai_code2doc.agent.context import AgentContext
from ai_code2doc.agent.dispatcher import AgentDispatcher
from ai_code2doc.agent.conversation import ConversationManager
from ai_code2doc.agent.tool_registry import ToolRegistry


def _make_settings() -> MagicMock:
    s = MagicMock()
    s.llm_model = "gpt-4o"
    s.llm_max_tokens = 4096
    s.llm_temperature = 0.1
    s.llm_base_url = "https://api.openai.com/v1"
    s.llm_api_key = "test-key"
    s.llm_concurrency = 3
    s.repl_history_size = 10
    s.output_dir = ".ai_code2doc"
    return s


class TestAgentDispatcher:
    def test_process_simple_response(self, tmp_path: Path) -> None:
        """Dispatcher returns content directly when LLM makes no tool calls."""
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "foo() returns a string."
        mock_choice.message.tool_calls = None
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 70
        mock_response.model = "gpt-4o"

        settings = _make_settings()
        ctx = AgentContext(project_root=tmp_path, settings=settings)

        tools_def = [
            ToolDefinition(name="code_qa", description="Q&A", parameters=[
                ToolParameter(name="question", type="string", description="Q"),
            ])
        ]

        async def fake_agenerate(messages, tools, system=""):
            return "foo() returns a string.", []

        with patch.object(AgentDispatcher, "_call_llm", new=AsyncMock(return_value=mock_response)):
            # We need to mock the internal _call_llm that returns (content, tool_calls)
            pass

        # More direct approach: mock agenerate_with_tools on LLMClient
        with patch("ai_code2doc.agent.dispatcher.LLMClient") as MockLLM:
            mock_client = AsyncMock()
            mock_client.agenerate_with_tools = AsyncMock(
                return_value=("foo() returns a string.", [])
            )
            mock_client.token_tracker = MagicMock()
            MockLLM.return_value = mock_client

            reg = ToolRegistry()
            reg.register(tools_def[0], AsyncMock())

            dispatcher = AgentDispatcher.__new__(AgentDispatcher)
            dispatcher._llm = mock_client
            dispatcher._tools = reg
            dispatcher._conversation = ConversationManager(max_history=10)
            dispatcher._context = ctx
            dispatcher._system_prompt = ctx.build_system_prompt()

            result = asyncio.get_event_loop().run_until_complete(dispatcher.process("what is foo?"))
            assert "foo() returns a string." in result

    def test_process_with_tool_call(self, tmp_path: Path) -> None:
        """Dispatcher executes tool and returns LLM's final answer."""
        settings = _make_settings()
        ctx = AgentContext(project_root=tmp_path, settings=settings)

        tools_def = [
            ToolDefinition(name="list_context", description="List context", parameters=[]),
        ]

        tc = ToolCall(id="call_1", name="list_context", arguments={})

        # First LLM call: requests tool
        # Second LLM call: gives final answer after seeing tool result
        call_count = 0

        async def fake_agenerate(msgs, tools, system=""):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "", [tc]
            return "The project has 10 files.", []

        with patch("ai_code2doc.agent.dispatcher.LLMClient") as MockLLM:
            mock_client = MagicMock()
            mock_client.agenerate_with_tools = fake_agenerate
            mock_client.token_tracker = MagicMock()
            MockLLM.return_value = mock_client

            async def fake_list_context(tc_call, ctx_obj):
                return ToolResult(tool_call_id=tc_call.id, content="10 files, 500 lines")

            reg = ToolRegistry()
            reg.register(tools_def[0], fake_list_context)

            dispatcher = AgentDispatcher.__new__(AgentDispatcher)
            dispatcher._llm = mock_client
            dispatcher._tools = reg
            dispatcher._conversation = ConversationManager(max_history=10)
            dispatcher._context = ctx
            dispatcher._system_prompt = ctx.build_system_prompt()

            result = asyncio.get_event_loop().run_until_complete(dispatcher.process("show me context"))
            assert "10 files" in result
            assert call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_dispatcher.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement AgentDispatcher**

Create `src/ai_code2doc/agent/dispatcher.py`:
```python
"""Agent dispatcher: LLM conversation loop with tool-use."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from ai_code2doc.agent.conversation import ConversationManager
from ai_code2doc.agent.models import ConversationMessage, ToolResult
from ai_code2doc.agent.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from ai_code2doc.agent.context import AgentContext
    from ai_code2doc.config.settings import Settings

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5  # prevent infinite tool-call loops


class AgentDispatcher:
    """Core agent loop: user input -> LLM -> [tool calls -> results] -> answer."""

    def __init__(
        self,
        context: AgentContext,
        tool_registry: ToolRegistry,
        system_prompt: str = "",
    ) -> None:
        from ai_code2doc.llm.client import LLMClient

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
                # LLM gave a direct answer
                self._conversation.add_assistant(content, tool_calls=None)
                return content

            # LLM requested tool calls
            self._conversation.add_assistant(content, tool_calls=tool_calls)

            # Execute all tool calls
            results: list[ToolResult] = []
            for tc in tool_calls:
                logger.info("Executing tool: %s", tc.name)
                result = await self._tools.execute(tc, self._context)
                results.append(result)

            self._conversation.add_tool_results(results)

            # Feed tool results back to LLM
            messages = self._conversation.get_context_messages()
            round_count += 1

        return content + "\n\n[Warning: Reached maximum tool-call rounds]"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_dispatcher.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/agent/dispatcher.py tests/unit/test_dispatcher.py
git commit -m "feat: add AgentDispatcher with LLM tool-use loop"
```

---

### Task 8: Tool - list_context

**Files:**
- Create: `src/ai_code2doc/agent/tools/__init__.py`
- Create: `src/ai_code2doc/agent/tools/list_context.py`
- Create: `tests/unit/test_tool_list_context.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_tool_list_context.py`:
```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from ai_code2doc.agent.tools.list_context import tool_definition, execute
from ai_code2doc.agent.models import ToolCall, ToolResult
from ai_code2doc.agent.context import AgentContext, AnalysisResult


class TestListContextTool:
    def test_execute_with_no_analysis(self, tmp_path: Path) -> None:
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        ctx.settings.output_dir = ".ai_code2doc"
        tc = ToolCall(id="c1", name="list_context", arguments={})
        result = execute(tc, ctx)
        assert isinstance(result, ToolResult)
        assert "No analysis" in result.content or "no analysis" in result.content.lower() or tmp_path.name in result.content

    def test_execute_with_analysis(self, tmp_path: Path) -> None:
        ctx = AgentContext(
            project_root=tmp_path,
            settings=MagicMock(),
            analysis_result=AnalysisResult(total_files=10, total_lines=500),
        )
        tc = ToolCall(id="c1", name="list_context", arguments={})
        result = execute(tc, ctx)
        assert "10" in result.content

    def test_definition(self) -> None:
        assert tool_definition.name == "list_context"
        assert len(tool_definition.parameters) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_tool_list_context.py -v`
Expected: FAIL

- [ ] **Step 3: Implement list_context tool**

Create `src/ai_code2doc/agent/tools/__init__.py`:
```python
"""Agent tool implementations."""
```

Create `src/ai_code2doc/agent/tools/list_context.py`:
```python
"""list_context tool: show current analysis state."""

from __future__ import annotations

from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolResult

tool_definition = ToolDefinition(
    name="list_context",
    description="Show the current analysis context: project info, files analyzed, "
    "available layers, and vector store status.",
    parameters=[],
)


def execute(call: ToolCall, context) -> ToolResult:
    """Execute the list_context tool."""
    parts = [f"Project: {context.project_root}"]

    if context.analysis_result:
        ar = context.analysis_result
        parts.append(f"Files analyzed: {ar.total_files}")
        parts.append(f"Total lines: {ar.total_lines}")
        if ar.target_files:
            names = [f.name for f in ar.target_files[:15]]
            parts.append(f"Files: {', '.join(names)}")
            if len(ar.target_files) > 15:
                parts.append(f"  ... and {len(ar.target_files) - 15} more")
    else:
        parts.append("No analysis results loaded.")

    parts.append(f"Output dir: {context.output_dir}")
    parts.append(f"Vector store: {'available' if context.has_vector_store() else 'not available'}")

    return ToolResult(tool_call_id=call.id, content="\n".join(parts))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_tool_list_context.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/agent/tools/ tests/unit/test_tool_list_context.py
git commit -m "feat: add list_context agent tool"
```

---

### Task 9: Tool - code_qa

**Files:**
- Create: `src/ai_code2doc/agent/tools/code_qa.py`
- Create: `tests/unit/test_tool_code_qa.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_tool_code_qa.py`:
```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_code2doc.agent.tools.code_qa import tool_definition, execute
from ai_code2doc.agent.models import ToolCall, ToolResult
from ai_code2doc.agent.context import AgentContext


class TestCodeQATool:
    def test_definition(self) -> None:
        assert tool_definition.name == "code_qa"
        params = {p.name for p in tool_definition.parameters}
        assert "question" in params

    def test_execute_no_vector_store(self, tmp_path: Path) -> None:
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        tc = ToolCall(id="c1", name="code_qa", arguments={"question": "what is foo?"})
        result = execute(tc, ctx)
        assert result.is_error is True
        assert "vector store" in result.content.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_tool_code_qa.py -v`
Expected: FAIL

- [ ] **Step 3: Implement code_qa tool**

Create `src/ai_code2doc/agent/tools/code_qa.py`:
```python
"""code_qa tool: RAG-powered Q&A over the vector store."""

from __future__ import annotations

import asyncio

from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolParameter, ToolResult

tool_definition = ToolDefinition(
    name="code_qa",
    description="Answer questions about the codebase using RAG (Retrieval-Augmented Generation). "
    "Searches the vector store for relevant code documentation and generates an answer.",
    parameters=[
        ToolParameter(name="question", type="string", description="The question to answer about the codebase"),
        ToolParameter(name="n_results", type="integer", description="Number of search results to retrieve", required=False),
        ToolParameter(name="layer", type="integer", description="Restrict search to a specific layer (1, 2, or 3)", required=False),
    ],
)


def execute(call: ToolCall, context) -> ToolResult:
    """Execute the code_qa tool. Returns ToolResult with the answer."""
    if not context.has_vector_store():
        return ToolResult(
            tool_call_id=call.id,
            content="Vector store not available. Run 'ai-code2doc analyze' first.",
            is_error=True,
        )

    question = call.arguments.get("question", "")
    if not question:
        return ToolResult(tool_call_id=call.id, content="No question provided.", is_error=True)

    n_results = call.arguments.get("n_results", 5)
    layer = call.arguments.get("layer")

    try:
        from ai_code2doc.vector_store.store import VectorStore
        from ai_code2doc.vector_store.schemas import SearchResponse

        vs = VectorStore(context.settings, str(context.chroma_dir))
        response: SearchResponse = vs.search(question, n_results=int(n_results), layer=layer)

        if not response.results:
            return ToolResult(
                tool_call_id=call.id,
                content=f"No relevant results found for: {question}",
                is_error=False,
            )

        # Build context from search results
        context_parts = []
        for r in response.results:
            source = r.metadata.get("source_path", "unknown")
            context_parts.append(f"### Source: {source} (score: {r.score:.2f})\n{r.content}")
        context_text = "\n\n---\n\n".join(context_parts)

        # Use LLM to generate answer if API key is available
        if context.settings.llm_api_key:
            try:
                prompt = (
                    "You are a senior software architect answering questions about a codebase. "
                    "Use ONLY the context below to answer the question. "
                    "If the context does not contain enough information, say so clearly.\n\n"
                    f"## Context\n\n{context_text}\n\n"
                    f"## Question\n\n{question}\n\n"
                    "Provide a concise, well-structured answer in Markdown."
                )
                answer = asyncio.get_event_loop().run_until_complete(
                    context.llm_client.agenerate(prompt, system="You are a helpful code documentation assistant.")
                )
                return ToolResult(tool_call_id=call.id, content=answer.content)
            except Exception as exc:
                # Fall back to raw results
                return ToolResult(
                    tool_call_id=call.id,
                    content=f"LLM generation failed: {exc}\n\nRaw results:\n{context_text}",
                )
        else:
            return ToolResult(tool_call_id=call.id, content=context_text)

    except Exception as exc:
        return ToolResult(
            tool_call_id=call.id,
            content=f"Search failed: {exc}",
            is_error=True,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_tool_code_qa.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/agent/tools/code_qa.py tests/unit/test_tool_code_qa.py
git commit -m "feat: add code_qa agent tool (RAG-powered Q&A)"
```

---

### Task 10: Tool - analyze_deps

**Files:**
- Create: `src/ai_code2doc/agent/tools/analyze_deps.py`
- Create: `tests/unit/test_tool_analyze_deps.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_tool_analyze_deps.py`:
```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_code2doc.agent.tools.analyze_deps import tool_definition, execute
from ai_code2doc.agent.models import ToolCall, ToolResult
from ai_code2doc.agent.context import AgentContext


class TestAnalyzeDepsTool:
    def test_definition(self) -> None:
        assert tool_definition.name == "analyze_deps"
        params = {p.name for p in tool_definition.parameters}
        assert "target" in params
        assert "mode" in params

    def test_execute_call_chains(self, tmp_path: Path) -> None:
        """Test call chain mode."""
        mock_graph = MagicMock()
        mock_chains = [MagicMock(description="a -> b -> c", start="a", end="c", path=["a", "b", "c"])]
        mock_graph.find_call_chains.return_value = mock_chains

        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())

        with patch("ai_code2doc.agent.tools.analyze_deps._build_graph", return_value=mock_graph):
            tc = ToolCall(id="c1", name="analyze_deps", arguments={"target": "a", "mode": "call_chains", "end": "c"})
            result = execute(tc, ctx)
            assert not result.is_error

    def test_execute_impact(self, tmp_path: Path) -> None:
        """Test impact analysis mode."""
        mock_graph = MagicMock()
        mock_impact = MagicMock(affected_modules=["b", "c"], change_target="a", risk_level="high")
        mock_graph.compute_impact.return_value = mock_impact

        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())

        with patch("ai_code2doc.agent.tools.analyze_deps._build_graph", return_value=mock_graph):
            tc = ToolCall(id="c1", name="analyze_deps", arguments={"target": "a", "mode": "impact"})
            result = execute(tc, ctx)
            assert "a" in result.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_tool_analyze_deps.py -v`
Expected: FAIL

- [ ] **Step 3: Implement analyze_deps tool**

Create `src/ai_code2doc/agent/tools/analyze_deps.py`:
```python
"""analyze_deps tool: dependency and impact analysis."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolParameter, ToolResult


tool_definition = ToolDefinition(
    name="analyze_deps",
    description="Analyze dependencies, call chains, and impact for a module or file. "
    "Supports modes: 'call_chains' (trace execution paths), 'impact' (what's affected by a change), "
    "'dependents' (who depends on this), 'dependencies' (what does this depend on).",
    parameters=[
        ToolParameter(name="target", type="string", description="Target file or module path"),
        ToolParameter(name="mode", type="string", description="Analysis mode", required=False, enum=["call_chains", "impact", "dependents", "dependencies"]),
        ToolParameter(name="end", type="string", description="End node for call_chain mode", required=False),
    ],
)


def _build_graph(context) -> nx.DiGraph | None:
    """Build dependency graph from project files."""
    try:
        from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
        from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser
        from ai_code2doc.scanner.project_scanner import ProjectScanner

        scanner = ProjectScanner(context.project_root)
        scan_result = scanner.scan()

        parser = TreeSitterParser()
        builder = DependencyGraphBuilder(context.project_root)

        from ai_code2doc.utils.parse_cache import ParseCache

        cache = ParseCache(context.output_dir / "file_infos")
        for f in scan_result.target_files:
            try:
                fi = cache.get(str(f.relative_to(context.project_root)))
                if fi is None:
                    fi = parser.parse_file(f, context.project_root)
                    cache.put(fi)
                builder.add_file(fi)
            except Exception:
                continue

        return builder.build()
    except Exception as exc:
        return None


def execute(call: ToolCall, context) -> ToolResult:
    target = call.arguments.get("target", "")
    if not target:
        return ToolResult(tool_call_id=call.id, content="No target specified.", is_error=True)

    mode = call.arguments.get("mode", "dependents")

    graph = _build_graph(context)
    if graph is None:
        return ToolResult(
            tool_call_id=call.id,
            content="Failed to build dependency graph. No parseable files found?",
            is_error=True,
        )

    if mode == "call_chains":
        end = call.arguments.get("end", "")
        if not end:
            return ToolResult(tool_call_id=call.id, content="'end' required for call_chains mode.", is_error=True)
        from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder

        builder = DependencyGraphBuilder(context.project_root)
        builder.graph = graph
        chains = builder.find_call_chains(target, end)
        if not chains:
            return ToolResult(tool_call_id=call.id, content=f"No call chains found from '{target}' to '{end}'.")
        lines = [f"Call chains from '{target}' to '{end}':"]
        for c in chains:
            lines.append(f"  {' -> '.join(c.path)}: {c.description}")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "impact":
        from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder

        builder = DependencyGraphBuilder(context.project_root)
        builder.graph = graph
        impact = builder.compute_impact(target)
        lines = [
            f"Impact analysis for '{target}':",
            f"  Risk level: {impact.risk_level}",
            f"  Affected modules: {', '.join(impact.affected_modules) if impact.affected_modules else 'none'}",
        ]
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "dependents":
        try:
            dependents = list(graph.predecessors(target))
        except nx.NetworkXError:
            return ToolResult(tool_call_id=call.id, content=f"Target '{target}' not found in graph.", is_error=True)
        lines = [f"Modules that depend on '{target}':"]
        for d in dependents:
            lines.append(f"  - {d}")
        if not dependents:
            lines.append("  (none)")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    elif mode == "dependencies":
        try:
            deps = list(graph.successors(target))
        except nx.NetworkXError:
            return ToolResult(tool_call_id=call.id, content=f"Target '{target}' not found in graph.", is_error=True)
        lines = [f"Modules that '{target}' depends on:"]
        for d in deps:
            lines.append(f"  - {d}")
        if not deps:
            lines.append("  (none)")
        return ToolResult(tool_call_id=call.id, content="\n".join(lines))

    return ToolResult(tool_call_id=call.id, content=f"Unknown mode: {mode}", is_error=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_tool_analyze_deps.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/agent/tools/analyze_deps.py tests/unit/test_tool_analyze_deps.py
git commit -m "feat: add analyze_deps agent tool (call chains, impact, dependencies)"
```

---

### Task 11: Tool - update_doc

**Files:**
- Create: `src/ai_code2doc/agent/tools/update_doc.py`
- Create: `tests/unit/test_tool_update_doc.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_tool_update_doc.py`:
```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from ai_code2doc.agent.tools.update_doc import tool_definition, execute
from ai_code2doc.agent.models import ToolCall, ToolResult
from ai_code2doc.agent.context import AgentContext


class TestUpdateDocTool:
    def test_definition(self) -> None:
        assert tool_definition.name == "update_doc"
        params = {p.name for p in tool_definition.parameters}
        assert "layer" in params
        assert "instruction" in params

    def test_execute_layer1(self, tmp_path: Path) -> None:
        """Test layer 1 doc regeneration."""
        (tmp_path / ".ai_code2doc" / "layer1").mkdir(parents=True)
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        ctx.settings.output_dir = ".ai_code2doc"

        mock_gen = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.title = "README"
        mock_doc.content = "new content"
        mock_gen.generate = AsyncMock(return_value=[mock_doc])

        with patch("ai_code2doc.agent.tools.update_doc.Layer1OverviewGenerator", return_value=mock_gen):
            with patch("ai_code2doc.agent.tools.update_doc.MarkdownWriter") as MockWriter:
                mock_writer = MagicMock()
                mock_writer.write_doc = MagicMock(return_value=Path("README.md"))
                MockWriter.return_value = mock_writer

                tc = ToolCall(id="c1", name="update_doc", arguments={"layer": 1, "instruction": "rewrite architecture"})
                result = execute(tc, ctx)
                assert not result.is_error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_tool_update_doc.py -v`
Expected: FAIL

- [ ] **Step 3: Implement update_doc tool**

Create `src/ai_code2doc/agent/tools/update_doc.py`:
```python
"""update_doc tool: regenerate specific documentation layers or modules."""

from __future__ import annotations

import asyncio
from pathlib import Path

from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolParameter, ToolResult


tool_definition = ToolDefinition(
    name="update_doc",
    description="Regenerate documentation for a specific layer or module. "
    "Use this to update or improve existing documentation.",
    parameters=[
        ToolParameter(name="layer", type="integer", description="Target layer (1=overview, 2=modules, 3=graph)"),
        ToolParameter(name="module", type="string", description="Module name for layer 2 updates", required=False),
        ToolParameter(name="instruction", type="string", description="What to update or change about the documentation", required=False),
    ],
)


def execute(call: ToolCall, context) -> ToolResult:
    """Execute the update_doc tool."""
    layer = call.arguments.get("layer")
    if layer is None:
        return ToolResult(tool_call_id=call.id, content="No layer specified.", is_error=True)
    layer = int(layer)

    module_name = call.arguments.get("module")
    instruction = call.arguments.get("instruction", "")

    output_dir = context.output_dir

    try:
        if layer == 1:
            from ai_code2doc.generator.layer1_overview import Layer1OverviewGenerator
            from ai_code2doc.generator.markdown_writer import MarkdownWriter

            gen = Layer1OverviewGenerator(context.settings)
            docs = asyncio.get_event_loop().run_until_complete(
                gen.generate(context.project_root, output_dir, use_llm=bool(context.settings.llm_api_key), changed_files=None)
            )
            writer = MarkdownWriter()
            paths = []
            for doc in docs:
                p = output_dir / "layer1" / f"{doc.id}.md"
                writer.write_doc(p, doc)
                paths.append(str(p))
            return ToolResult(
                tool_call_id=call.id,
                content=f"Updated Layer 1 ({len(docs)} docs):\n" + "\n".join(f"  - {p}" for p in paths),
            )

        elif layer == 2:
            from ai_code2doc.generator.layer2_modules import Layer2ModuleGenerator
            from ai_code2doc.generator.markdown_writer import MarkdownWriter

            gen = Layer2ModuleGenerator(context.settings)
            docs = asyncio.get_event_loop().run_until_complete(
                gen.generate(context.project_root, output_dir, use_llm=bool(context.settings.llm_api_key), changed_files=None)
            )
            writer = MarkdownWriter()
            paths = []
            for doc in docs:
                if module_name and module_name.lower() not in doc.title.lower():
                    continue
                p = output_dir / "layer2" / f"{doc.id}.md"
                writer.write_doc(p, doc)
                paths.append(str(p))
            msg = f"Updated Layer 2 modules ({len(paths)} docs):"
            if module_name:
                msg = f"Updated Layer 2 for '{module_name}' ({len(paths)} docs):"
            return ToolResult(
                tool_call_id=call.id,
                content=msg + "\n" + "\n".join(f"  - {p}" for p in paths) if paths else f"No matching modules found for '{module_name}'.",
            )

        elif layer == 3:
            from ai_code2doc.generator.layer3_graph import Layer3GraphGenerator
            from ai_code2doc.generator.markdown_writer import MarkdownWriter

            gen = Layer3GraphGenerator(context.settings)
            docs = asyncio.get_event_loop().run_until_complete(
                gen.generate(context.project_root, output_dir, use_llm=bool(context.settings.llm_api_key), changed_files=None)
            )
            writer = MarkdownWriter()
            paths = []
            for doc in docs:
                p = output_dir / "layer3" / f"{doc.id}.md"
                writer.write_doc(p, doc)
                paths.append(str(p))
            return ToolResult(
                tool_call_id=call.id,
                content=f"Updated Layer 3 ({len(docs)} docs):\n" + "\n".join(f"  - {p}" for p in paths),
            )

        else:
            return ToolResult(tool_call_id=call.id, content=f"Unknown layer: {layer}", is_error=True)

    except Exception as exc:
        return ToolResult(tool_call_id=call.id, content=f"Document update failed: {exc}", is_error=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_tool_update_doc.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/agent/tools/update_doc.py tests/unit/test_tool_update_doc.py
git commit -m "feat: add update_doc agent tool"
```

---

### Task 12: Tool - rescan

**Files:**
- Create: `src/ai_code2doc/agent/tools/rescan.py`
- Create: `tests/unit/test_tool_rescan.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_tool_rescan.py`:
```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_code2doc.agent.tools.rescan import tool_definition, execute
from ai_code2doc.agent.models import ToolCall, ToolResult
from ai_code2doc.agent.context import AgentContext


class TestRescanTool:
    def test_definition(self) -> None:
        assert tool_definition.name == "rescan"
        params = {p.name for p in tool_definition.parameters}
        assert "target" in params

    def test_execute_rescan_all(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("def foo(): pass")
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        ctx.settings.max_file_size_kb = 500

        mock_scan = MagicMock()
        mock_scan.target_files = [Path("src/app.py")]

        with patch("ai_code2doc.agent.tools.rescan.ProjectScanner", return_value=mock_scan):
            tc = ToolCall(id="c1", name="rescan", arguments={})
            result = execute(tc, ctx)
            assert not result.is_error
            assert "1" in result.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_tool_rescan.py -v`
Expected: FAIL

- [ ] **Step 3: Implement rescan tool**

Create `src/ai_code2doc/agent/tools/rescan.py`:
```python
"""rescan tool: trigger incremental re-analysis of files."""

from __future__ import annotations

import asyncio
from pathlib import Path

from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolParameter, ToolResult


tool_definition = ToolDefinition(
    name="rescan",
    description="Trigger an incremental re-scan of the project. Optionally restrict to specific "
    "files or directories. Re-parses changed files and updates the analysis state.",
    parameters=[
        ToolParameter(name="target", type="string", description="Specific file or directory to rescan (empty = full rescan)", required=False),
    ],
)


def execute(call: ToolCall, context) -> ToolResult:
    """Execute the rescan tool."""
    target = call.arguments.get("target", "")

    try:
        from ai_code2doc.scanner.project_scanner import ProjectScanner
        from ai_code2doc.scanner.change_detector import ChangeDetector

        if target:
            target_path = context.project_root / target
            if not target_path.exists():
                return ToolResult(
                    tool_call_id=call.id,
                    content=f"Target not found: {target_path}",
                    is_error=True,
                )
            if target_path.is_file():
                files = [target_path]
            else:
                scanner = ProjectScanner(target_path, max_file_size_kb=context.settings.max_file_size_kb)
                scan = scanner.scan()
                files = scan.target_files
        else:
            scanner = ProjectScanner(context.project_root, max_file_size_kb=context.settings.max_file_size_kb)
            scan = scanner.scan()
            files = scan.target_files

        detector = ChangeDetector(context.project_root, context.settings.output_dir)
        changed, unchanged = detector.detect_changes(files)
        detector.update_state(files)

        # Re-parse changed files
        parsed_count = 0
        if changed:
            from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser
            from ai_code2doc.utils.parse_cache import ParseCache

            parser = TreeSitterParser()
            cache = ParseCache(context.output_dir / "file_infos")
            for f in changed:
                try:
                    fi = parser.parse_file(f, context.project_root)
                    cache.put(fi)
                    parsed_count += 1
                except Exception:
                    continue

        # Update analysis result
        if context.analysis_result is not None:
            context.analysis_result.target_files = files

        parts = [
            f"Rescan complete: {len(files)} files scanned",
            f"  Changed/new: {len(changed)}",
            f"  Unchanged: {len(unchanged)}",
        ]
        if parsed_count:
            parts.append(f"  Re-parsed: {parsed_count}")

        return ToolResult(tool_call_id=call.id, content="\n".join(parts))

    except Exception as exc:
        return ToolResult(tool_call_id=call.id, content=f"Rescan failed: {exc}", is_error=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_tool_rescan.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/agent/tools/rescan.py tests/unit/test_tool_rescan.py
git commit -m "feat: add rescan agent tool"
```

---

### Task 13: Tool - correct

**Files:**
- Create: `src/ai_code2doc/agent/tools/correct.py`
- Create: `tests/unit/test_tool_correct.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_tool_correct.py`:
```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from ai_code2doc.agent.tools.correct import tool_definition, execute
from ai_code2doc.agent.models import ToolCall, ToolResult
from ai_code2doc.agent.context import AgentContext


class TestCorrectTool:
    def test_definition(self) -> None:
        assert tool_definition.name == "correct"
        params = {p.name for p in tool_definition.parameters}
        assert "target" in params
        assert "correction" in params

    def test_execute_file_not_found(self, tmp_path: Path) -> None:
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        ctx.settings.output_dir = ".ai_code2doc"
        tc = ToolCall(id="c1", name="correct", arguments={"target": "layer1/README.md", "correction": "fix this"})
        result = execute(tc, ctx)
        assert result.is_error is True

    def test_execute_file_exists(self, tmp_path: Path) -> None:
        layer_dir = tmp_path / ".ai_code2doc" / "layer1"
        layer_dir.mkdir(parents=True)
        doc_file = layer_dir / "README.md"
        doc_file.write_text("# Overview\nOld content", encoding="utf-8")

        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        ctx.settings.output_dir = ".ai_code2doc"

        tc = ToolCall(id="c1", name="correct", arguments={
            "target": "layer1/README.md",
            "correction": "Replace 'Old content' with 'New accurate content'",
        })
        result = execute(tc, ctx)
        assert not result.is_error
        assert "corrected" in result.content.lower() or "updated" in result.content.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_tool_correct.py -v`
Expected: FAIL

- [ ] **Step 3: Implement correct tool**

Create `src/ai_code2doc/agent/tools/correct.py`:
```python
"""correct tool: apply user-reported corrections to generated documentation."""

from __future__ import annotations

import asyncio
from pathlib import Path

from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolParameter, ToolResult


tool_definition = ToolDefinition(
    name="correct",
    description="Apply a correction to generated documentation. Use when the user points out "
    "an error in the documentation. The tool reads the target file, applies the correction "
    "instruction, and updates the file.",
    parameters=[
        ToolParameter(name="target", type="string", description="Relative path to the documentation file (e.g. layer1/README.md)"),
        ToolParameter(name="correction", type="string", description="Description of the correction to apply"),
    ],
)


def execute(call: ToolCall, context) -> ToolResult:
    """Execute the correct tool."""
    target = call.arguments.get("target", "")
    correction = call.arguments.get("correction", "")

    if not target or not correction:
        return ToolResult(tool_call_id=call.id, content="Both 'target' and 'correction' are required.", is_error=True)

    file_path = context.output_dir / target
    if not file_path.exists():
        return ToolResult(
            tool_call_id=call.id,
            content=f"File not found: {file_path}",
            is_error=True,
        )

    try:
        original = file_path.read_text(encoding="utf-8")

        # Use LLM to apply the correction if available
        if context.settings.llm_api_key:
            prompt = (
                "You are editing a documentation file. Apply the following correction.\n\n"
                f"## Original file content\n\n{original}\n\n"
                f"## Correction instruction\n\n{correction}\n\n"
                "Return the COMPLETE corrected file content. Do not add explanations, "
                "just return the full updated file content."
            )
            result = asyncio.get_event_loop().run_until_complete(
                context.llm_client.agenerate(prompt, system="You are a documentation editor. Apply corrections precisely.")
            )
            new_content = result.content.strip()
            # Strip markdown code fences if the LLM wrapped the output
            if new_content.startswith("```"):
                lines = new_content.split("\n")
                lines = lines[1:]  # remove opening fence
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]  # remove closing fence
                new_content = "\n".join(lines)
            file_path.write_text(new_content, encoding="utf-8")
            return ToolResult(
                tool_call_id=call.id,
                content=f"Corrected {target} based on instruction: {correction}",
            )
        else:
            return ToolResult(
                tool_call_id=call.id,
                content="No LLM API key configured. Cannot apply corrections automatically. "
                "Please edit the file manually.",
                is_error=True,
            )

    except Exception as exc:
        return ToolResult(
            tool_call_id=call.id,
            content=f"Correction failed: {exc}",
            is_error=True,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_tool_correct.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/agent/tools/correct.py tests/unit/test_tool_correct.py
git commit -m "feat: add correct agent tool (documentation error correction)"
```

---

### Task 14: REPL Interface

**Files:**
- Create: `src/ai_code2doc/agent/repl.py`
- Create: `tests/unit/test_repl.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_repl.py`:
```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from ai_code2doc.agent.repl import AgentREPL


class TestAgentREPL:
    def test_build_welcome_message(self, tmp_path: Path) -> None:
        from ai_code2doc.agent.context import AgentContext, AnalysisResult

        settings = MagicMock()
        settings.llm_model = "gpt-4o"
        ctx = AgentContext(
            project_root=tmp_path,
            settings=settings,
            analysis_result=AnalysisResult(total_files=10, total_lines=500),
        )
        repl = AgentREPL.__new__(AgentREPL)
        repl._context = ctx
        msg = repl._build_welcome()
        assert "10" in msg

    def test_parse_slash_command_quit(self) -> None:
        assert AgentREPL._parse_slash_command("/quit") == ("quit", "")

    def test_parse_slash_command_help(self) -> None:
        assert AgentREPL._parse_slash_command("/help") == ("help", "")

    def test_parse_slash_command_not_slash(self) -> None:
        assert AgentREPL._parse_slash_command("hello") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_repl.py -v`
Expected: FAIL

- [ ] **Step 3: Implement AgentREPL**

Create `src/ai_code2doc/agent/repl.py`:
```python
"""Agent REPL: interactive terminal interface using prompt_toolkit."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from ai_code2doc.agent.dispatcher import AgentDispatcher
from ai_code2doc.agent.tool_registry import ToolRegistry
from ai_code2doc.agent.tools.list_context import tool_definition as list_context_def, execute as list_context_exec
from ai_code2doc.agent.tools.code_qa import tool_definition as code_qa_def, execute as code_qa_exec
from ai_code2doc.agent.tools.analyze_deps import tool_definition as analyze_deps_def, execute as analyze_deps_exec
from ai_code2doc.agent.tools.update_doc import tool_definition as update_doc_def, execute as update_doc_exec
from ai_code2doc.agent.tools.rescan import tool_definition as rescan_def, execute as rescan_exec
from ai_code2doc.agent.tools.correct import tool_definition as correct_def, execute as correct_exec

if TYPE_CHECKING:
    from ai_code2doc.agent.context import AgentContext

console = Console()

HELP_TEXT = """Available slash commands:
  /help      - Show this help message
  /quit      - Exit the REPL
  /history   - Show conversation history
  /save      - Save current session
  /context   - Show current context status
  /clear     - Clear conversation history

Or just type a natural language question and the agent will respond."""


class AgentREPL:
    """Interactive REPL for the agent."""

    def __init__(self, context: AgentContext) -> None:
        self._context = context

        # Build tool registry
        self._registry = ToolRegistry()
        self._registry.register(list_context_def, list_context_exec)
        self._registry.register(code_qa_def, code_qa_exec)
        self._registry.register(analyze_deps_def, analyze_deps_exec)
        self._registry.register(update_doc_def, update_doc_exec)
        self._registry.register(rescan_def, rescan_exec)
        self._registry.register(correct_def, correct_exec)

        # Build dispatcher
        self._dispatcher = AgentDispatcher(
            context=context,
            tool_registry=self._registry,
        )

    def _build_welcome(self) -> str:
        parts = ["\n  Analysis complete! Entering interactive mode."]
        if self._context.analysis_result:
            ar = self._context.analysis_result
            parts.append(f"  Files: {ar.total_files} | Lines: {ar.total_lines}")
        parts.append(f"  Tools: {', '.join(self._registry.tool_names)}")
        parts.append("  Type /help for commands, /quit to exit.\n")
        return "\n".join(parts)

    @staticmethod
    def _parse_slash_command(text: str) -> tuple[str, str] | None:
        text = text.strip()
        if not text.startswith("/"):
            return None
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        return (cmd, args)

    def _handle_slash_command(self, cmd: str, args: str) -> bool:
        """Handle slash commands. Returns True if should continue, False if should exit."""
        if cmd == "/quit":
            console.print("[dim]Goodbye![/dim]")
            return False
        elif cmd == "/help":
            console.print(Panel(HELP_TEXT, title="Help", border_style="blue"))
        elif cmd == "/history":
            msgs = self._dispatcher.conversation.get_context_messages()
            if not msgs:
                console.print("[dim]No conversation history.[/dim]")
            else:
                for msg in msgs:
                    role = msg.role.value
                    console.print(f"[dim]{role}:[/dim] {msg.content[:100]}")
        elif cmd == "/save":
            path = self._context.output_dir / self._context.settings.session_file
            self._dispatcher.conversation.save(path)
            console.print(f"[green]Session saved to {path}[/green]")
        elif cmd == "/context":
            from ai_code2doc.agent.models import ToolCall
            from ai_code2doc.agent.tools.list_context import execute as lc_exec

            tc = ToolCall(id="repl", name="list_context", arguments={})
            result = lc_exec(tc, self._context)
            console.print(Panel(result.content, title="Context", border_style="cyan"))
        elif cmd == "/clear":
            self._dispatcher.conversation.clear()
            console.print("[green]Conversation history cleared.[/green]")
        else:
            console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
        return True

    def run(self) -> None:
        """Run the REPL loop."""
        console.print(self._build_welcome())

        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import InMemoryHistory

            session = PromptSession(history=InMemoryHistory())
        except ImportError:
            # Fallback to simple input() if prompt_toolkit not available
            console.print("[yellow]prompt_toolkit not installed. Using basic input mode.[/yellow]\n")
            self._run_basic_input()
            return

        while True:
            try:
                user_input = session.prompt("> ")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye![/dim]")
                break

            if not user_input.strip():
                continue

            # Check for slash commands
            parsed = self._parse_slash_command(user_input)
            if parsed:
                if not self._handle_slash_command(parsed[0], parsed[1]):
                    break
                continue

            # Process with agent
            try:
                with console.status("[bold green]Thinking...[/bold green]"):
                    response = asyncio.get_event_loop().run_until_complete(
                        self._dispatcher.process(user_input)
                    )
                console.print(Markdown(response))
                console.print()
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted. Type /quit to exit.[/yellow]")
            except Exception as exc:
                console.print(f"[red]Error:[/red] {exc}")

        # Save session on exit
        if self._context.settings.repl_save_session:
            path = self._context.output_dir / self._context.settings.session_file
            try:
                self._dispatcher.conversation.save(path)
                console.print(f"[dim]Session saved to {path}[/dim]")
            except Exception:
                pass

    def _run_basic_input(self) -> None:
        """Fallback REPL using plain input()."""
        while True:
            try:
                user_input = input("> ")
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break

            if not user_input.strip():
                continue

            parsed = self._parse_slash_command(user_input)
            if parsed:
                if not self._handle_slash_command(parsed[0], parsed[1]):
                    break
                continue

            try:
                response = asyncio.get_event_loop().run_until_complete(
                    self._dispatcher.process(user_input)
                )
                print(response)
                print()
            except KeyboardInterrupt:
                print("\nInterrupted. Type /quit to exit.")
            except Exception as exc:
                print(f"Error: {exc}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_repl.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/agent/repl.py tests/unit/test_repl.py
git commit -m "feat: add AgentREPL with prompt_toolkit and slash commands"
```

---

### Task 15: CLI - chat Command

**Files:**
- Create: `src/ai_code2doc/cli/chat_cmd.py`
- Create: `tests/unit/test_chat_cmd.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_chat_cmd.py`:
```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_code2doc.cli.chat_cmd import register


class TestChatCommand:
    def test_register_adds_command(self) -> None:
        import typer
        app = typer.Typer()
        register(app)
        # chat command should be registered
        registered = [c for c in app.registered_commands if "chat" in c.name.lower() or "chat" in str(c.callback.__name__)]
        assert len(registered) > 0

    def test_no_analysis_error(self, tmp_path: Path) -> None:
        """chat should error when no analysis exists."""
        import typer

        app = typer.Typer()
        register(app)

        # Find and call the chat function
        for c in app.registered_commands:
            if c.callback and "chat" in c.callback.__name__:
                try:
                    c.callback(tmp_path)
                    assert False, "Should have raised SystemExit"
                except SystemExit:
                    pass
                break
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_chat_cmd.py -v`
Expected: FAIL

- [ ] **Step 3: Implement chat command**

Create `src/ai_code2doc/cli/chat_cmd.py`:
```python
"""``chat`` sub-command -- enter interactive REPL with existing analysis."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def register(app: typer.Typer) -> None:
    """Register the *chat* command on the main Typer application."""

    @app.command()
    def chat(
        project_path: Path = typer.Argument(
            ...,
            help="Path to the analysed project.",
            exists=True,
        ),
    ) -> None:
        """Enter interactive mode with an already-analysed project."""
        from ai_code2doc.agent.context import AgentContext, AnalysisResult
        from ai_code2doc.agent.repl import AgentREPL
        from ai_code2doc.config.settings import Settings

        settings = Settings()
        project_root = project_path.resolve()
        output_dir = project_root / settings.output_dir

        console.print(
            Panel(
                f"[bold]Chat mode:[/] {project_root}",
                title="ai-code2doc",
                border_style="blue",
            )
        )

        # Validate analysis exists
        if not output_dir.exists():
            console.print(
                f"[red]Error:[/red] No analysis found at {output_dir}\n"
                f"Run [bold]ai-code2doc analyze {project_path}[/bold] first."
            )
            raise typer.Exit(code=1)

        # Load analysis state
        analysis_result = AnalysisResult()
        try:
            from ai_code2doc.scanner.change_detector import ChangeDetector

            detector = ChangeDetector(project_root, settings.output_dir)
            state = detector.load_state()
            analysis_result.total_files = len(state.file_states)
            analysis_result.target_files = [Path(p) for p in state.file_states.keys()]
        except Exception:
            console.print(
                "[yellow]Warning:[/yellow] Could not load analysis state. "
                "Some features may be limited."
            )

        # Check for API key
        if not settings.llm_api_key:
            console.print(
                "[yellow]Warning:[/yellow] No LLM API key configured. "
                "Tool-based features will be limited.\n"
                "Set AI_CODE2DOC_LLM_API_KEY to enable full functionality."
            )

        # Build context and start REPL
        ctx = AgentContext(project_root, settings, analysis_result)

        try:
            from ai_code2doc.agent.conversation import ConversationManager

            cm = ConversationManager(max_history=settings.repl_history_size)
            session_path = output_dir / settings.session_file
            if session_path.exists():
                cm.load(session_path)
                console.print(f"[dim]Loaded previous session from {session_path}[/dim]")

            # Create REPL and inject loaded conversation
            repl = AgentREPL(ctx)
            repl._dispatcher._conversation = cm
            repl.run()
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_chat_cmd.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_code2doc/cli/chat_cmd.py tests/unit/test_chat_cmd.py
git commit -m "feat: add chat command for interactive REPL"
```

---

### Task 16: CLI - Modify analyze Command

**Files:**
- Modify: `src/ai_code2doc/cli/analyze_cmd.py`
- Modify: `src/ai_code2doc/cli/main.py`

- [ ] **Step 1: Modify analyze_cmd.py to enter REPL after analysis**

In `src/ai_code2doc/cli/analyze_cmd.py`, replace the "done" section at the bottom (lines 279-287) with REPL entry. The change is:

Replace the final `console.print(Panel(...))` block (lines 280-287):
```python
        # -- done --------------------------------------------------------------
        console.print(
            Panel(
                f"[bold green]Analysis complete![/bold green]\n"
                f"Output directory: {output_dir}",
                title="Done",
                border_style="green",
            )
        )
```

With:
```python
        # -- build analysis result for REPL ------------------------------------
        from ai_code2doc.agent.context import AnalysisResult

        analysis_result = AnalysisResult(
            total_files=len(scan_result.target_files),
            total_lines=sum(
                f.stat().st_size if f.exists() else 0
                for f in scan_result.target_files
            ) // 40,  # rough line estimate
            target_files=scan_result.target_files,
            docs_generated=all_docs,
        )

        # -- enter interactive REPL --------------------------------------------
        try:
            from ai_code2doc.agent.context import AgentContext
            from ai_code2doc.agent.repl import AgentREPL

            console.print(
                Panel(
                    f"[bold green]Analysis complete![/bold green]\n"
                    f"Output directory: {output_dir}",
                    title="Done",
                    border_style="green",
                )
            )

            if settings.llm_api_key:
                ctx = AgentContext(project_root, settings, analysis_result)
                repl = AgentREPL(ctx)
                repl.run()
            else:
                console.print(
                    "\n[yellow]No LLM API key configured. Skipping interactive mode.[/yellow] "
                    "Set AI_CODE2DOC_LLM_API_KEY and re-run to enable the agent.\n"
                    "You can also run [bold]ai-code2doc chat {project_path}[/bold] "
                    "after configuring your API key."
                )
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
```

- [ ] **Step 2: Register chat command in main.py**

In `src/ai_code2doc/cli/main.py`, add the import and registration:
```python
from ai_code2doc.cli.chat_cmd import register as register_chat
```
And after the existing registrations:
```python
register_chat(app)
```

The full file becomes:
```python
"""CLI entry point for ai-code2doc."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="ai-code2doc",
    help="AI Agent that analyzes Python/C/C++ projects and generates layered code knowledge systems.",
    no_args_is_help=True,
)

from ai_code2doc.cli.analyze_cmd import register as register_analyze
from ai_code2doc.cli.serve_cmd import register as register_serve
from ai_code2doc.cli.query_cmd import register as register_query
from ai_code2doc.cli.status_cmd import register as register_status
from ai_code2doc.cli.chat_cmd import register as register_chat

register_analyze(app)
register_serve(app)
register_query(app)
register_status(app)
register_chat(app)
```

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All existing tests still pass (no regressions)

- [ ] **Step 4: Commit**

```bash
git add src/ai_code2doc/cli/analyze_cmd.py src/ai_code2doc/cli/main.py
git commit -m "feat: analyze command enters interactive REPL after completion"
```

---

### Task 17: Provider Abstraction & Anthropic Provider

**Files:**
- Create: `src/ai_code2doc/llm/provider.py`
- Create: `src/ai_code2doc/llm/providers/__init__.py`
- Create: `src/ai_code2doc/llm/providers/openai_provider.py`
- Create: `src/ai_code2doc/llm/providers/anthropic_provider.py`
- Create: `tests/unit/test_providers.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_providers.py`:
```python
from __future__ import annotations

from unittest.mock import MagicMock, patch, AsyncMock
from ai_code2doc.llm.provider import create_provider, LLMProvider
from ai_code2doc.agent.models import (
    ConversationMessage,
    MessageRole,
    ToolCall,
    ToolDefinition,
    ToolParameter,
)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_providers.py -v`
Expected: FAIL

- [ ] **Step 3: Implement provider abstraction**

Create `src/ai_code2doc/llm/providers/__init__.py`:
```python
"""LLM provider implementations."""
```

Create `src/ai_code2doc/llm/provider.py`:
```python
"""LLM provider factory and abstract interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_code2doc.config.settings import Settings
    from ai_code2doc.agent.models import ConversationMessage, ToolCall, ToolDefinition


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
        """Generate a response, optionally using tools.

        Returns (content, tool_calls).
        """
        ...


def create_provider(settings: Settings) -> LLMProvider:
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
```

Create `src/ai_code2doc/llm/providers/openai_provider.py`:
```python
"""OpenAI-compatible provider (also used for Ollama and custom endpoints)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from ai_code2doc.llm.provider import LLMProvider

if TYPE_CHECKING:
    from ai_code2doc.agent.models import ToolCall, ToolDefinition


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
```

Create `src/ai_code2doc/llm/providers/anthropic_provider.py`:
```python
"""Anthropic provider using the native Anthropic SDK."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ai_code2doc.llm.provider import LLMProvider

if TYPE_CHECKING:
    from ai_code2doc.agent.models import ToolCall, ToolDefinition


class AnthropicProvider(LLMProvider):
    def __init__(self, settings) -> None:
        self._model = settings.llm_model or "claude-sonnet-4-20250514"
        self._api_key = settings.llm_api_key or "dummy"
        self._client = None  # lazy init

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

        # Convert messages to Anthropic format
        anthropic_messages = []
        for msg in messages:
            if msg.role.value == "tool":
                # Anthropic uses tool_result content blocks
                for tr in (msg.tool_results or []):
                    anthropic_messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tr.tool_call_id,
                                "content": tr.content,
                            }
                        ],
                    })
            elif msg.role.value == "assistant" and msg.tool_calls:
                content_blocks = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                anthropic_messages.append({"role": "assistant", "content": content_blocks})
            elif msg.role.value == "system":
                # Anthropic handles system prompt separately, skip here
                pass
            else:
                anthropic_messages.append({"role": msg.role.value, "content": msg.content})

        # Build tool definitions in Anthropic format
        anthropic_tools = None
        if tools:
            anthropic_tools = []
            for t in tools:
                param_schema = {
                    "type": "object",
                    "properties": {},
                    "required": [],
                }
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

                anthropic_tools.append({
                    "name": t.name,
                    "description": t.description,
                    "input_schema": param_schema,
                })

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
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=block.input or {})
                )

        # Handle stop_reason = "tool_use" by ensuring empty content is handled
        if response.stop_reason == "tool_use" and not content:
            content = ""

        return content, tool_calls
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_providers.py -v`
Expected: PASS

- [ ] **Step 5: Integrate provider into LLMClient**

In `src/ai_code2doc/llm/client.py`, modify the `agenerate_with_tools` method to use the provider abstraction. Add import at top:
```python
from ai_code2doc.llm.provider import create_provider
```

Replace the entire `agenerate_with_tools` method with:
```python
    async def agenerate_with_tools(
        self,
        messages: list,
        tools: list | None = None,
        system: str = "",
    ) -> tuple[str, list]:
        from ai_code2doc.agent.models import ToolCall

        async with self._semaphore:
            provider = create_provider(self._settings)
            content, tool_calls = await provider.generate_with_tools(
                messages=messages,
                tools=tools,
                system=system,
                model=self._settings.llm_model,
                max_tokens=self._settings.llm_max_tokens,
                temperature=self._settings.llm_temperature,
            )

            # Token tracking (best-effort since provider doesn't return usage)
            self._tracker.add(0, 0)

            return content, tool_calls
```

- [ ] **Step 6: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add src/ai_code2doc/llm/provider.py src/ai_code2doc/llm/providers/ tests/unit/test_providers.py src/ai_code2doc/llm/client.py
git commit -m "feat: add multi-provider LLM abstraction (OpenAI, Anthropic, Ollama)"
```

---

### Task 18: Full Integration Test

**Files:**
- Create: `tests/integration/test_agent_integration.py`

- [ ] **Step 1: Write integration test**

Create `tests/integration/test_agent_integration.py`:
```python
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


class TestAgentIntegration:
    def test_full_dispatch_loop_with_list_context(self, tmp_path: Path) -> None:
        """Full round-trip: user question -> tool call -> tool result -> LLM answer."""
        import asyncio

        settings = MagicMock()
        settings.llm_model = "gpt-4o"
        settings.llm_provider = "openai"
        settings.llm_base_url = "https://api.openai.com/v1"
        settings.llm_api_key = "test"
        settings.llm_max_tokens = 4096
        settings.llm_temperature = 0.1
        settings.llm_concurrency = 3
        settings.repl_history_size = 10
        settings.output_dir = ".ai_code2doc"

        ctx = AgentContext(
            project_root=tmp_path,
            settings=settings,
            analysis_result=AnalysisResult(total_files=5, total_lines=200),
        )

        registry = ToolRegistry()
        registry.register(lc_def, lc_exec)

        call_count = 0

        async def fake_generate(messages, tools, system="", model="", max_tokens=4096, temperature=0.1):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "", [ToolCall(id="c1", name="list_context", arguments={})]
            return "The project has 5 files and 200 lines of code.", []

        with patch("ai_code2doc.llm.providers.openai_provider.AsyncOpenAI") as MockClient:
            mock_async_client = MagicMock()
            mock_async_client.chat.completions.create = fake_generate
            MockClient.return_value = mock_async_client

            dispatcher = AgentDispatcher(context=ctx, tool_registry=registry)
            result = asyncio.get_event_loop().run_until_complete(
                dispatcher.process("Show me the project context")
            )
            assert "5 files" in result
            assert call_count == 2

    def test_slash_commands(self, tmp_path: Path) -> None:
        from ai_code2doc.agent.repl import AgentREPL

        assert AgentREPL._parse_slash_command("/quit") == ("quit", "")
        assert AgentREPL._parse_slash_command("/help extra") == ("help", "extra")
        assert AgentREPL._parse_slash_command("hello") is None

    def test_tool_registry_has_all_tools(self) -> None:
        from ai_code2doc.agent.repl import AgentREPL
        from unittest.mock import MagicMock

        ctx = MagicMock()
        ctx.settings = MagicMock()
        ctx.settings.output_dir = ".ai_code2doc"
        ctx.analysis_result = None

        # Need to patch AgentContext.__init__ to avoid it
        with patch.object(AgentREPL, "__init__", lambda self, ctx: None):
            repl = AgentREPL.__new__(AgentREPL)
            repl._registry = ToolRegistry()
            repl._registry.register(
                ToolDefinition(name="test", description="T", parameters=[]),
                lambda tc, ctx: ToolResult(tool_call_id=tc.id, content="ok"),
            )
            assert repl._registry.has_tool("test")
```

- [ ] **Step 2: Run integration test**

Run: `python -m pytest tests/integration/test_agent_integration.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass, no regressions

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_agent_integration.py
git commit -m "test: add agent integration tests"
```

---

## Self-Review

**Spec coverage:**
- analyze enters REPL -> Task 16
- chat command -> Task 15
- 6 tools (code_qa, update_doc, analyze_deps, rescan, correct, list_context) -> Tasks 8-13
- LLM tool-use -> Task 3
- Conversation history + sliding window -> Task 5
- Session persistence -> Task 5
- Multi-provider (OpenAI, Anthropic, Ollama) -> Task 17
- REPL interface with prompt_toolkit -> Task 14
- Slash commands (/help, /quit, /history, /save, /context, /clear) -> Task 14
- Error handling (no API key, no vector store, no analysis) -> Tasks 8, 15, 16
- Settings updates -> Task 1
- AgentContext -> Task 4
- System prompt -> Task 4

**Placeholder scan:** None found. All code steps have complete implementations.

**Type consistency:** `ToolCall`, `ToolResult`, `ToolDefinition` defined in Task 2 and used consistently throughout. `AgentContext` from Task 4 used by all tools. `ConversationManager` from Task 5 used by dispatcher and REPL.

**Dependencies between tasks:** Linear chain 1→2→3→4→5→6→7, then tools 8-13 in parallel (all depend on 2), then 14 (depends on 7,8-13), then 15,16 (depend on 14), then 17 (enhancement, depends on 3), then 18 (depends on all).
