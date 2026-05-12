from __future__ import annotations

PROMPT_LAYER1 = """You are a code architecture analyst. Analyze the following project structure and generate a comprehensive project overview.

Project Name: {project_name}
Tech Stack: {tech_stack}
Directory Structure:
{directory_tree}

Entry Points: {entry_points}
Key Files: {key_files}

Generate a project overview covering:
1. Project purpose and description
2. Architecture type (MVC, microservices, monolith, etc.)
3. Key design patterns used
4. Technology choices and their implications
5. Overall code organization assessment

Respond in Markdown format with clear sections.
"""

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

PROMPT_LAYER3 = """You are a dependency analysis expert. Analyze the following dependency graph and provide insights.

Dependency Graph:
{mermaid_graph}

Cycles Detected: {cycles}
Key Metrics: {metrics}

Provide:
1. Architecture dependency patterns
2. Critical dependency paths
3. Coupling assessment
4. Recommendations for improvement

Respond in Markdown format.
"""


def format_layer1_prompt(
    project_name: str, tech_stack: str, directory_tree: str,
    entry_points: str, key_files: str,
) -> str:
    return PROMPT_LAYER1.format(
        project_name=project_name, tech_stack=tech_stack,
        directory_tree=directory_tree, entry_points=entry_points,
        key_files=key_files,
    )


def format_layer2_prompt(
    module_name: str, module_path: str, file_summaries: str,
    dependencies: str, dependents: str,
) -> str:
    return PROMPT_LAYER2.format(
        module_name=module_name, module_path=module_path,
        file_summaries=file_summaries, dependencies=dependencies,
        dependents=dependents,
    )


def format_layer3_prompt(mermaid_graph: str, cycles: str, metrics: str) -> str:
    return PROMPT_LAYER3.format(
        mermaid_graph=mermaid_graph, cycles=cycles, metrics=metrics,
    )
