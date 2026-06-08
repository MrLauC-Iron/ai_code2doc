from __future__ import annotations

# Re-exported from code2doc-core for backward compatibility
from code2doc_core.constants import DEFAULT_IGNORE_PATTERNS, DEFAULT_IGNORE_EXTENSIONS  # noqa: F401

# Extensions to keep even if a broader pattern above would exclude them.
KEEP_EXTENSIONS: list[str] = [
    "__init__.py",
]

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

PROMPT_LAYER1: str = """\
You are a senior software architect analysing a codebase to produce a \
high-level overview document.

## Task
Examine the following project structure and produce a concise project overview \
that covers:

1. **Purpose** - What does this project do? What problem does it solve?
2. **Technology Stack** - Key languages, frameworks, and libraries used.
3. **Architecture** - High-level architectural pattern (monolith, microservices, \
modular library, etc.) and major subsystems.
4. **Directory Layout** - Brief description of the top-level directories and \
their roles.
5. **Entry Points** - Main entry files and how the application is started or \
consumed.

## Project Structure
```
{tree}
```

## Key Files (extracts)
{key_files}

Respond in well-structured Markdown. Be factual - only describe what you can \
infer from the provided information. If something is uncertain, say so.
"""

PROMPT_LAYER2: str = """\
You are a senior software engineer writing module-level documentation.

## Task
For the module at **{module_path}**, produce a summary that covers:

1. **Responsibility** - What does this module do? What problem does it solve \
within the larger project?
2. **Public API** - Key classes, functions, and constants exported by this \
module. For each, give a one-line description including parameter types and \
return types where obvious.
3. **Internal Design** - How is the module organised internally? Mention any \
notable design patterns or abstractions used.
4. **Dependencies** - Other modules or external packages this module depends on.
5. **Consumers** - Which other modules are likely to import or use this module?

## Module Source
```{language}
{source}
```

Respond in well-structured Markdown. Use fenced code blocks for identifiers. \
Be concise but precise.
"""
