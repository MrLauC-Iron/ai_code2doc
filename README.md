# ai_code2doc

AI-powered code knowledge system for Python/C/C++ projects. Generates layered documentation (overview, module docs, dependency graphs) with LLM enhancement and serves them via HTTP/MCP.

## Architecture

```
code2doc-core        shared infrastructure (parser, scanner, analyzer, models)
      ↑     ↑     ↑
ai_code2doc  layer2_mcp  layer3_mcp
Layer 1       Layer 2      Layer 3
overview      module docs  dependency graph
```

All three application packages depend only on `code2doc-core` — no cross-dependencies.

## Quick Start

```bash
# Install
pip install code2doc-core/
pip install -e .
pip install layer2_mcp/
pip install layer3_mcp/

# Analyze (Layer 1, static, no LLM)
ai-code2doc analyze /path/to/project --no-llm

# Analyze with LLM
AI_CODE2DOC_LLM_API_KEY=sk-... ai-code2doc analyze /path/to/project

# Start Layer 2 server
layer2-mcp serve /path/to/project

# Start Layer 3 MCP server (HTTP)
layer3-mcp --repo /path/to/repo --transport http --port 8000
```

## Configuration

All packages read configuration from **environment variables** and `.env` file in the project root.

### ai_code2doc (Layer 1)

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_CODE2DOC_LLM_BASE_URL` | `https://api.openai.com/v1` | LLM API base URL |
| `AI_CODE2DOC_LLM_API_KEY` | *(empty)* | API key |
| `AI_CODE2DOC_LLM_MODEL` | `gpt-4o` | Model name |
| `AI_CODE2DOC_LLM_MAX_TOKENS` | `4096` | Max tokens per response |
| `AI_CODE2DOC_LLM_TEMPERATURE` | `0.1` | LLM temperature |
| `AI_CODE2DOC_LLM_CONCURRENCY` | `3` | Parallel LLM requests |
| `AI_CODE2DOC_LLM_PROVIDER` | `openai` | Provider: `openai` / `anthropic` / `ollama` |
| `AI_CODE2DOC_LOG_LEVEL` | `INFO` | Logging level |
| `AI_CODE2DOC_OUTPUT_DIR` | `.ai_code2doc` | Output directory |

Also supports `ai_code2doc.toml` for non-LLM settings.

### layer2_mcp (Layer 2)

| Variable | Default | Description |
|----------|---------|-------------|
| `LAYER2_LLM_API_KEY` | *(empty)* | API key (required for `POST /update`) |
| `LAYER2_LLM_BASE_URL` | `https://api.openai.com/v1` | LLM API base URL |
| `LAYER2_LLM_MODEL` | `gpt-4o` | Model name |
| `LAYER2_LLM_MAX_TOKENS` | `4096` | Max tokens per response |
| `LAYER2_LLM_TEMPERATURE` | `0.1` | LLM temperature |

### layer3_mcp (Layer 3)

Layer 3 generation (`ai-code2doc analyze --layers 3`) uses the same `AI_CODE2DOC_LLM_*` settings as Layer 1. The MCP query server (`layer3-mcp`) does **not** call LLM — it only queries the SQLite database.

### Example .env

```bash
# .env (place in project root)
AI_CODE2DOC_LLM_API_KEY=sk-...
AI_CODE2DOC_LLM_BASE_URL=https://api.openai.com/v1
AI_CODE2DOC_LLM_MODEL=gpt-4o
LAYER2_LLM_API_KEY=sk-...
```

## Layer 2: Module Documentation Server

MCP server for module-level documentation. Serves pre-generated docs and updates them on-the-fly via LLM.

```bash
# Stdio (Claude Desktop / IDE integration)
layer2-mcp --project /path/to/project

# HTTP (remote access)
layer2-mcp --project /path/to/project --transport http --port 8001

# Direct modules directory
layer2-mcp --modules-dir /path/to/modules
```

Docs are stored under `<project>/modules/`.

### MCP Tools

| Tool | Description |
|------|-------------|
| `list_modules` | List all modules |
| `get_module` | Get documentation for a module |
| `search_modules` | Search modules by keyword |
| `update_modules` | Update module docs with task context (requires LLM) |

**update_modules** parameters:
- `modules` (required): Comma-separated module names
- `task_description` (required): What was done
- `code_changes`: Description of changed files
- `layer1_overview`: Optional project context

## Layer 3: Dependency Graph Server

Standalone MCP server for dependency graph queries. Supports on-demand branch builds via git worktree.

```bash
# Repo mode: on-demand branch builds (stdio / HTTP)
layer3-mcp --repo /path/to/repo
layer3-mcp --repo /path/to/repo --transport http --port 8000

# With periodic git polling (every 5 minutes)
layer3-mcp --repo /path/to/repo --poll-interval 300

# Direct DB path (local, no branch management)
layer3-mcp /path/to/dependency-graph.db

# Auto-detect current branch
layer3-mcp --project /path/to/project
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `context` | Full context for a symbol: position, callers, callees, siblings, dependencies |
| `dependents` | Modules that depend on a target |
| `dependencies` | Modules that a target depends on |
| `callers` | Functions that call a target symbol |
| `callees` | Functions called by a target symbol |
| `hotspots` | Most-called symbols in the codebase |
| `impact` | Impact analysis: modules affected if a target changes |
| `path` | Shortest dependency path between two modules |
| `subgraph` | Internal structure (edges) of a file |
| `stats` | Graph summary statistics |
| `get_edges` | Raw edge query with filters |
| `ensure_branch` | Trigger branch DB build |
| `branch_status` | Check branch build status |
| `poll_start` | Start background git poller |
| `poll_stop` | Stop background git poller |
| `poll_status` | Poller status |

## Project Structure

```
ai_code2doc/
├── code2doc-core/          # Parser, scanner, analyzer, models, utils
├── src/ai_code2doc/        # Layer 1: CLI, web UI, agent, vector store
├── layer2_mcp/             # Layer 2: Module docs HTTP server
├── layer3_mcp/             # Layer 3: Dependency graph MCP server
├── tests/
└── docs/
```

## Testing

```bash
python -m pytest tests/ -v
cd layer2_mcp && python -m pytest tests/ -v
cd layer3_mcp && python -m pytest tests/ -v
```
