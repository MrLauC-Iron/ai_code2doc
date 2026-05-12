# ai_code2doc

AI Agent that analyzes Python/C/C++ projects and generates layered code knowledge systems.

## Features

- **Three-layer knowledge generation**: Project overview (Layer 1), module summaries (Layer 2), dependency graphs (Layer 3)
- **Multi-language support**: Python, C, and C++ via tree-sitter with extensible language registry
- **Incremental analysis**: Only re-analyzes changed files using BLAKE2b hashing and parse caching
- **LLM-enhanced documentation**: Uses OpenAI-compatible APIs for rich documentation
- **Vector store search**: ChromaDB-backed semantic search over code knowledge
- **Web UI**: Interactive documentation viewer with API endpoints
- **CLI**: Full command-line interface for analysis, serving, and querying

## Supported Languages

| Language | Extensions | Framework Detection |
|----------|-----------|-------------------|
| Python | `.py`, `.pyi`, `.pyw` | FastAPI, Django, Flask |
| C | `.c`, `.h` | CMake, Make |
| C++ | `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hxx` | CMake, Make, Qt, Boost |

## Quick Start

```bash
pip install -e ".[dev]"

# Analyze a project
ai-code2doc analyze /path/to/project

# Full analysis (ignore incremental state)
ai-code2doc analyze /path/to/project --full

# Static documentation only (no LLM)
ai-code2doc analyze /path/to/project --no-llm

# Start web server
ai-code2doc serve /path/to/project --port 8420

# Query from CLI
ai-code2doc query /path/to/project "How does authentication work?"

# Check analysis status
ai-code2doc status /path/to/project
```

## Architecture

```
ai_code2doc/
├── cli/                    # CLI commands (analyze, serve, query, status)
├── config/                 # Settings and default configuration
├── parser/
│   ├── languages/
│   │   ├── python.py       # Python extractor + import resolver
│   │   └── c_cpp.py        # C/C++ extractor + include resolver
│   └── language_registry.py # Extensible language registry
├── scanner/                # File scanning, filtering, change detection
├── analyzer/               # Dependency graph, metrics, tech stack detection
├── generator/              # Layer 1/2/3 document generation
├── llm/                    # LLM client, token tracker, text chunker
├── vector_store/           # ChromaDB semantic search
├── models/                 # Pydantic data models
├── utils/                  # Hashing, path utils, markdown utils, parse cache
└── web/                    # FastAPI routes + static frontend
```

## Configuration

Set via environment variables with prefix `AI_CODE2DOC_`, or create `.env` file:

```
AI_CODE2DOC_LLM_BASE_URL=https://api.openai.com/v1
AI_CODE2DOC_LLM_API_KEY=sk-...
AI_CODE2DOC_LLM_MODEL=gpt-4
AI_CODE2DOC_LOG_LEVEL=INFO
```

## Testing

```bash
python -m pytest tests/ -v --tb=short
```

See `report/test-report.md` for the full test report (177 test cases, 15 functional dimensions).
