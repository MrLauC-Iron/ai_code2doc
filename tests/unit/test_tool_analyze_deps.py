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
        mock_graph = MagicMock()
        mock_builder = MagicMock()
        mock_chains = [MagicMock(description="a -> b -> c", start="a", end="c", path=["a", "b", "c"])]
        mock_builder.find_call_chains.return_value = mock_chains
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())

        with patch("ai_code2doc.agent.tools.analyze_deps._build_graph", return_value=mock_graph):
            with patch("ai_code2doc.analyzer.dependency_graph.DependencyGraphBuilder", return_value=mock_builder):
                tc = ToolCall(id="c1", name="analyze_deps", arguments={"target": "a", "mode": "call_chains", "end": "c"})
                result = execute(tc, ctx)
                assert not result.is_error

    def test_execute_impact(self, tmp_path: Path) -> None:
        mock_graph = MagicMock()
        mock_impact = MagicMock(affected_modules=["b", "c"], change_target="a", risk_level="high")
        mock_graph.compute_impact.return_value = mock_impact
        ctx = AgentContext(project_root=tmp_path, settings=MagicMock())

        with patch("ai_code2doc.agent.tools.analyze_deps._build_graph", return_value=mock_graph):
            tc = ToolCall(id="c1", name="analyze_deps", arguments={"target": "a", "mode": "impact"})
            result = execute(tc, ctx)
            assert "a" in result.content