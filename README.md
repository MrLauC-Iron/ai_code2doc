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
- **MCP Server**: Layer 3 dependency graph queries via Model Context Protocol

## Supported Languages

| Language | Extensions | Framework Detection |
|----------|-----------|-------------------|
| Python | `.py`, `.pyi`, `.pyw` | FastAPI, Django, Flask |
| C | `.c`, `.h` | CMake, Make |
| C++ | `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hxx` | CMake, Make, Qt, Boost |

## Quick Start

```bash
# Install all packages (in the monorepo root)
pip install -e code2doc-core/
pip install -e ".[dev]"
pip install -e layer3_mcp/

# Analyze a project (Layer 1 + Layer 2)
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

## Layer 3: Dependency Graph (layer3-mcp)

Layer 3 is a standalone package that generates and queries dependency graphs via MCP.

### Generate + Query with on-demand branch builds

```bash
# Start MCP server (HTTP mode, builds branch DB on first query)
layer3-mcp --repo /path/to/repo --transport http --port 8000

# Start with stdio transport (for Claude Desktop / IDE integrations)
layer3-mcp --repo /path/to/repo

# Start with periodic polling (every 5 minutes)
layer3-mcp --repo /path/to/repo --poll-interval 300
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `dependents` | Find modules that depend on a target |
| `dependencies` | Find modules that a target depends on |
| `callers` | Find functions that call a target symbol |
| `callees` | Find functions called by a target symbol |
| `hotspots` | List most-called symbols in the codebase |
| `impact` | Impact analysis: which modules are affected if a target changes |
| `path` | Find shortest dependency path between two modules |
| `subgraph` | Show internal structure (edges) of a file |
| `stats` | Dependency graph summary statistics |
| `get_edges` | Raw edge query with filters |
| `ensure_branch` | Ensure a branch DB is built and ready |
| `branch_status` | Check build status for branches |
| `poll_start` | Start background git poller |
| `poll_stop` | Stop background git poller |
| `poll_status` | Get poller status (last poll, last rebuild) |

### Generate only (no server)

```bash
# Direct DB path mode (local)
layer3-mcp /path/to/dependency-graph.db

# Project mode (auto-detect current branch)
layer3-mcp --project /path/to/project
```

## Project Structure

```
ai_code2doc/
├── code2doc-core/              # Shared core library
│   └── src/code2doc_core/
│       ├── parser/            # Tree-sitter parsing, language adapters
│       ├── scanner/           # Project scanning, change detection
│       ├── analyzer/          # Dependency graph, call graph, metrics
│       ├── models/            # FileInfo, KnowledgeDocument, Graph types
│       └── utils/             # Hashing, git utilities, parse cache
│
├── src/ai_code2doc/            # Main application
│   └── ai_code2doc/
│       ├── cli/                # analyze, serve, query, chat, status
│       ├── generator/          # Layer 1 & 2 document generation
│       ├── agent/              # REPL agent with tool registry
│       ├── web/                # FastAPI web UI
│       ├── config/             # Settings and defaults
│       ├── llm/                # LLM client, token tracker
│       ├── vector_store/       # ChromaDB semantic search
│       └── utils/             # Markdown, logging (main-package-only)
│
├── layer3_mcp/                 # Standalone Layer 3 package
│   └── src/code2doc_layer3_mcp/
│       ├── server.py           # MCP query server
│       ├── generator/          # Layer 3 graph generation
│       ├── branch_manager.py   # Git branch management
│       ├── git_poller.py      # Periodic git polling + rebuild
│       └── cli.py              # CLI entry point
│
├── tests/                      # Main package tests
├── docs/                       # Design docs and plans
└── web-ui/                     # Vue.js frontend (development)
```

### Package Dependencies

```
code2doc-core   ← shared infrastructure (parser, scanner, analyzer, models, utils)
      ↑                 ↑
ai_code2doc      layer3_mcp
(layer 1/2)       (layer 3: generate + query + poll)
```

`ai_code2doc` and `layer3_mcp` have no direct dependency — both depend only on `code2doc-core`.

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
# Main package tests
python -m pytest tests/ -v --tb=short

# layer3_mcp tests
cd layer3_mcp && python -m pytest tests/ -v --tb=short
```

See `report/test-report.md` for the full test report.
