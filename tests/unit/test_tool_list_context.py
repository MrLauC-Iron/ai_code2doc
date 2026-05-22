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
        assert tmp_path.name in result.content or "No analysis" in result.content

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