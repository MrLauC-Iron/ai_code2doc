from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

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