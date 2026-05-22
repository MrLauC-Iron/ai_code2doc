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
        (tmp_path / ".ai_code2doc" / "layer1").mkdir(parents=True)
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        ctx.settings.output_dir = ".ai_code2doc"

        mock_gen = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.title = "README"
        mock_doc.content = "new content"
        mock_doc.id = "README"
        mock_gen.generate = AsyncMock(return_value=[mock_doc])

        with patch("ai_code2doc.generator.layer1_overview.Layer1OverviewGenerator", return_value=mock_gen):
            with patch("ai_code2doc.generator.markdown_writer.MarkdownWriter") as MockWriter:
                mock_writer = MagicMock()
                mock_writer.write_doc = MagicMock(return_value=Path("README.md"))
                MockWriter.return_value = mock_writer

                tc = ToolCall(id="c1", name="update_doc", arguments={"layer": 1, "instruction": "rewrite architecture"})
                result = execute(tc, ctx)
                assert not result.is_error