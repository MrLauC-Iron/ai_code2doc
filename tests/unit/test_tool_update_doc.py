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

    def test_execute_layer1_error(self, tmp_path: Path) -> None:
        (tmp_path / ".ai_code2doc" / "layer1").mkdir(parents=True)
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        ctx.settings.output_dir = ".ai_code2doc"

        tc = ToolCall(id="c1", name="update_doc", arguments={"layer": 1, "instruction": "rewrite architecture"})
        result = execute(tc, ctx)
        assert result.is_error
        assert "user-maintained" in result.content.lower()