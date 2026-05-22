from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

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

        settings = MagicMock()
        settings.output_dir = ".ai_code2doc"
        settings.llm_api_key = "test-key"
        settings.llm_concurrency = 1
        ctx = AgentContext(project_root=tmp_path, settings=settings)

        # Mock the LLM client
        mock_llm_result = AsyncMock()
        mock_llm_result.content = "# Overview\nNew accurate content"
        ctx.llm_client.agenerate.return_value = mock_llm_result

        tc = ToolCall(id="c1", name="correct", arguments={
            "target": "layer1/README.md",
            "correction": "Replace 'Old content' with 'New accurate content'",
        })
        result = execute(tc, ctx)
        assert not result.is_error