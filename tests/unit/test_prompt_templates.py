"""Tests for ai_code2doc prompt templates."""

from __future__ import annotations

from ai_code2doc.generator.prompt_templates import (
    format_layer2_prompt,
)


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
