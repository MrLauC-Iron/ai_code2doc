"""Tests for ai_code2doc prompt templates."""

from __future__ import annotations

from ai_code2doc.generator.prompt_templates import (
    format_layer1_prompt,
    format_layer2_prompt,
    format_layer3_prompt,
)


class TestFormatLayer1Prompt:
    def test_contains_all_fields(self) -> None:
        result = format_layer1_prompt(
            project_name="myproject",
            tech_stack="Python, FastAPI",
            directory_tree="src/\n  main.py",
            entry_points="main.py",
            key_files="main.py: entry point",
        )
        assert "myproject" in result
        assert "Python, FastAPI" in result
        assert "src/" in result
        assert "main.py" in result

    def test_contains_project_name_and_instructions(self) -> None:
        result = format_layer1_prompt(
            project_name="test", tech_stack="C",
            directory_tree=".", entry_points="main.c", key_files="",
        )
        assert "test" in result
        assert "project overview" in result.lower() or "overview" in result.lower()


class TestFormatLayer2Prompt:
    def test_contains_module_info(self) -> None:
        result = format_layer2_prompt(
            module_name="api",
            module_path="src/api",
            file_summaries="routes.py: API routes",
            dependencies="models",
            dependents="main",
        )
        assert "api" in result
        assert "src/api" in result
        assert "routes.py" in result
        assert "models" in result
        assert "main" in result


class TestFormatLayer3Prompt:
    def test_contains_graph_info(self) -> None:
        result = format_layer3_prompt(
            mermaid_graph="graph TD\n  A --> B",
            cycles="None detected",
            metrics="5 nodes, 4 edges",
        )
        assert "graph TD" in result
        assert "None detected" in result
        assert "5 nodes" in result
