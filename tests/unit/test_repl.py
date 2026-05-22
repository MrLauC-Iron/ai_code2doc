from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

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
        registry = MagicMock()
        registry.tool_names = ["list_context", "code_qa"]
        repl._registry = registry
        msg = repl._build_welcome()
        assert "10" in msg

    def test_parse_slash_command_quit(self) -> None:
        assert AgentREPL._parse_slash_command("/quit") == ("quit", "")

    def test_parse_slash_command_help(self) -> None:
        assert AgentREPL._parse_slash_command("/help") == ("help", "")

    def test_parse_slash_command_not_slash(self) -> None:
        assert AgentREPL._parse_slash_command("hello") is None

    def test_parse_slash_command_with_args(self) -> None:
        assert AgentREPL._parse_slash_command("/context extra") == ("context", "extra")
