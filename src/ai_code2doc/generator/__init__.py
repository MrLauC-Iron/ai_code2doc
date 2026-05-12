"""Generator sub-package for ai_code2doc.

Produces layered knowledge documents:
  - Layer 1: Project overview
  - Layer 2: Module-level summaries
  - Layer 3: Dependency graph analysis
"""

from __future__ import annotations

from ai_code2doc.generator.base_generator import BaseGenerator
from ai_code2doc.generator.layer1_overview import Layer1OverviewGenerator
from ai_code2doc.generator.layer2_modules import Layer2ModuleGenerator
from ai_code2doc.generator.layer3_graph import Layer3GraphGenerator
from ai_code2doc.generator.markdown_writer import MarkdownWriter
from ai_code2doc.generator.prompt_templates import (
    format_layer1_prompt,
    format_layer2_prompt,
    format_layer3_prompt,
)

__all__ = [
    "BaseGenerator",
    "Layer1OverviewGenerator",
    "Layer2ModuleGenerator",
    "Layer3GraphGenerator",
    "MarkdownWriter",
    "format_layer1_prompt",
    "format_layer2_prompt",
    "format_layer3_prompt",
]
