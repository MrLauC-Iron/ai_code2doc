from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_code2doc.agent.context import AgentContext, AnalysisResult


class TestAgentContext:
    def test_create_minimal(self, tmp_path: Path) -> None:
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())
        assert ctx.project_root == tmp_path
        assert ctx.analysis_result is None

    def test_llm_client_lazy_init(self, tmp_path: Path) -> None:
        settings = MagicMock()
        ctx = AgentContext(project_root=tmp_path, settings=settings)
        with patch("ai_code2doc.llm.client.LLMClient") as mock_llm_cls:
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
        ctx.analysis_result = AnalysisResult(total_files=10, total_lines=500)
        ctx.analysis_result.target_files = [Path("a.py"), Path("b.py")]
        prompt = ctx.build_system_prompt()
        assert "Total files analyzed: 10" in prompt
        assert "gpt-4o" in prompt