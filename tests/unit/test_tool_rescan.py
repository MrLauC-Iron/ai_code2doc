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
            with patch("ai_code2doc.agent.tools.rescan.ChangeDetector") as MockDetector:
                mock_detector = MagicMock()
                mock_detector.detect_changes.return_value = ([Path("src/app.py")], [])
                MockDetector.return_value = mock_detector

                tc = ToolCall(id="c1", name="rescan", arguments={})
                result = execute(tc, ctx)
                assert not result.is_error
                assert "1" in result.content