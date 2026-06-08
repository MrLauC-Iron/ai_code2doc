from __future__ import annotations

PROMPT_LAYER2 = """You are a code module analyst. Analyze the following module and generate a detailed summary.

Module: {module_name}
Path: {module_path}

Files in this module:
{file_summaries}

Module Dependencies: {dependencies}
Module Dependents: {dependents}

Generate a module summary covering:
1. Module purpose and responsibility
2. Key functions and classes
3. API endpoints (if any)
4. Business rules and constraints
5. Relationships with other modules

Respond in Markdown format.
"""

def format_layer2_prompt(
    module_name: str, module_path: str, file_summaries: str,
    dependencies: str, dependents: str,
) -> str:
    return PROMPT_LAYER2.format(
        module_name=module_name, module_path=module_path,
        file_summaries=file_summaries, dependencies=dependencies,
        dependents=dependents,
    )
