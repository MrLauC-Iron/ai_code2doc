"""Generator sub-package for ai_code2doc.

Produces layered knowledge documents:
  - Layer 2: Module-level summaries
"""

from __future__ import annotations

from ai_code2doc.generator.base_generator import BaseGenerator
from ai_code2doc.generator.layer2_modules import Layer2ModuleGenerator
from ai_code2doc.generator.markdown_writer import MarkdownWriter
from ai_code2doc.generator.prompt_templates import format_layer2_prompt

__all__ = [
    "BaseGenerator",
    "Layer2ModuleGenerator",
    "MarkdownWriter",
    "format_layer2_prompt",
]
