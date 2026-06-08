# Layer 2 MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the batch Layer 2 generation in ai_code2doc with a standalone HTTP server (`layer2_mcp`) that accepts task context via POST to update module docs, and serves module docs via GET for AI-assisted development.

**Architecture:** New independent `layer2_mcp` package (same level as `layer3_mcp`). Pure HTTP REST server using FastAPI + uvicorn. POST /update receives task context, server-side LLM extracts knowledge and writes `modules/{name}.md`. GET endpoints serve module docs. No auth, simple deployment.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, openai (AsyncOpenAI), pydantic, typer (CLI), code2doc-core (shared lib)

---

### Task 1: Create layer2_mcp package skeleton

**Files:**
- Create: `layer2_mcp/pyproject.toml`
- Create: `layer2_mcp/src/code2doc_layer2_mcp/__init__.py`
- Create: `layer2_mcp/src/code2doc_layer2_mcp/config.py`
- Create: `layer2_mcp/tests/__init__.py`
- Create: `layer2_mcp/tests/conftest.py`

- [ ] **Step 1: Create package directories**

```bash
mkdir -p layer2_mcp/src/code2doc_layer2_mcp
mkdir -p layer2_mcp/tests
```

- [ ] **Step 2: Write `layer2_mcp/pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "code2doc-layer2-mcp"
version = "0.1.0"
description = "HTTP server for Layer 2 module documentation management"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [{name = "ai-code2doc contributors"}]
keywords = ["documentation", "code-analysis", "module-docs"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development",
]
dependencies = [
    "code2doc-core",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "typer>=0.12",
    "openai>=1.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
]

[project.scripts]
layer2-mcp = "code2doc_layer2_mcp.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/code2doc_layer2_mcp"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 3: Write `layer2_mcp/src/code2doc_layer2_mcp/__init__.py`**

```python
"""code2doc-layer2-mcp: HTTP server for Layer 2 module documentation management."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Write `layer2_mcp/src/code2doc_layer2_mcp/config.py`**

```python
"""Configuration for layer2_mcp server."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Layer2Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LAYER2_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # LLM settings
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.1

    # Server settings
    modules_dir: str = "modules"
    host: str = "0.0.0.0"
    port: int = 8001
```

- [ ] **Step 5: Write `layer2_mcp/tests/conftest.py`**

```python
"""Shared fixtures for layer2_mcp tests."""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def tmp_modules_dir(tmp_path: Path) -> Path:
    """Create a temporary modules directory with a sample module."""
    modules = tmp_path / "modules"
    modules.mkdir()
    (modules / "auth.md").write_text(
        "# Module: auth\n\nPath: `src/api/auth`\n\nAuthentication module.\n",
        encoding="utf-8",
    )
    return modules
```

- [ ] **Step 6: Write `layer2_mcp/tests/__init__.py`** (empty file)

```python
```

- [ ] **Step 7: Install the package in development mode**

```bash
cd layer2_mcp && pip install -e ".[dev]"
```

Expected: Successfully installed code2doc-layer2-mcp

- [ ] **Step 8: Commit**

```bash
git add layer2_mcp/
git commit -m "feat: create layer2_mcp package skeleton"
```

---

### Task 2: Implement module store (CRUD for module markdown files)

**Files:**
- Create: `layer2_mcp/src/code2doc_layer2_mcp/module_store.py`
- Create: `layer2_mcp/tests/test_module_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# layer2_mcp/tests/test_module_store.py
"""Tests for module_store."""

from __future__ import annotations

from pathlib import Path

import pytest

from code2doc_layer2_mcp.module_store import ModuleStore


class TestModuleStoreList:
    def test_list_empty(self, tmp_path: Path) -> None:
        store = ModuleStore(tmp_path / "modules")
        result = store.list_modules()
        assert result == []

    def test_list_modules(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        result = store.list_modules()
        assert len(result) == 1
        assert result[0]["name"] == "auth"
        assert "# Module: auth" in result[0]["content"]


class TestModuleStoreGet:
    def test_get_existing(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        doc = store.get_module("auth")
        assert doc is not None
        assert "auth" in doc["name"]
        assert "Authentication" in doc["content"]

    def test_get_missing(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        doc = store.get_module("nonexistent")
        assert doc is None

    def test_get_creates_modules_dir_if_missing(self, tmp_path: Path) -> None:
        store = ModuleStore(tmp_path / "new_modules")
        doc = store.get_module("anything")
        assert doc is None
        assert (tmp_path / "new_modules").exists()


class TestModuleStoreSearch:
    def test_search_by_name(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        results = store.search_modules("auth")
        assert len(results) == 1
        assert results[0]["name"] == "auth"

    def test_search_no_match(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        results = store.search_modules("database")
        assert results == []

    def test_search_in_content(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        results = store.search_modules("Authentication")
        assert len(results) == 1


class TestModuleStoreWrite:
    def test_write_new(self, tmp_path: Path) -> None:
        store = ModuleStore(tmp_path / "modules")
        store.save_module("user", "# Module: user\n\nUser management.")
        doc = store.get_module("user")
        assert doc is not None
        assert "# Module: user" in doc["content"]

    def test_write_overwrites(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        store.save_module("auth", "# Module: auth\n\nUpdated content.")
        doc = store.get_module("auth")
        assert "Updated content" in doc["content"]

    def test_write_sanitizes_name(self, tmp_path: Path) -> None:
        store = ModuleStore(tmp_path / "modules")
        store.save_module("../etc/passwd", "hacked")
        assert not (tmp_path / "modules" / "../etc/passwd.md").exists()


class TestModuleStoreDelete:
    def test_delete_existing(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        result = store.delete_module("auth")
        assert result is True
        assert store.get_module("auth") is None

    def test_delete_missing(self, tmp_modules_dir: Path) -> None:
        store = ModuleStore(tmp_modules_dir)
        result = store.delete_module("nonexistent")
        assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd layer2_mcp && python -m pytest tests/test_module_store.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'code2doc_layer2_mcp.module_store'`

- [ ] **Step 3: Write the implementation**

```python
# layer2_mcp/src/code2doc_layer2_mcp/module_store.py
"""Module store: CRUD operations on module markdown files."""

from __future__ import annotations

import os
from pathlib import Path


class ModuleStore:
    """Manages module documentation files on disk.

    Modules are stored as ``{modules_dir}/{name}.md``.
    """

    def __init__(self, modules_dir: Path | str) -> None:
        self._modules_dir = Path(modules_dir)
        self._modules_dir.mkdir(parents=True, exist_ok=True)

    def list_modules(self) -> list[dict[str, str]]:
        """Return metadata and content for all modules."""
        modules: list[dict[str, str]] = []
        for f in sorted(self._modules_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            modules.append({
                "name": f.stem,
                "content": content,
            })
        return modules

    def get_module(self, name: str) -> dict[str, str] | None:
        """Return a single module's content, or None if not found."""
        path = self._safe_path(name)
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        return {"name": name, "content": content}

    def search_modules(self, query: str) -> list[dict[str, str]]:
        """Search modules by name or content substring."""
        query_lower = query.lower()
        results: list[dict[str, str]] = []
        for mod in self.list_modules():
            if query_lower in mod["name"].lower() or query_lower in mod["content"].lower():
                results.append(mod)
        return results

    def save_module(self, name: str, content: str) -> None:
        """Write (or overwrite) a module document."""
        path = self._safe_path(name)
        path.write_text(content, encoding="utf-8")

    def delete_module(self, name: str) -> bool:
        """Delete a module document. Returns True if it existed."""
        path = self._safe_path(name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def _safe_path(self, name: str) -> Path:
        """Resolve a module name to a safe filesystem path.

        Rejects path traversal attempts (e.g. '../../etc/passwd').
        """
        # Strip any path separators or parent references
        safe_name = name.replace("\\", "/").rstrip("/")
        safe_name = safe_name.split("/")[-1]  # Take only the last component
        if not safe_name or safe_name.startswith("."):
            safe_name = "unnamed"
        return self._modules_dir / f"{safe_name}.md"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd layer2_mcp && python -m pytest tests/test_module_store.py -v
```

Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add layer2_mcp/src/code2doc_layer2_mcp/module_store.py layer2_mcp/tests/test_module_store.py
git commit -m "feat(layer2_mcp): add module store with CRUD operations"
```

---

### Task 3: Implement LLM client for knowledge extraction

**Files:**
- Create: `layer2_mcp/src/code2doc_layer2_mcp/llm_client.py`
- Create: `layer2_mcp/tests/test_llm_client.py`

- [ ] **Step 1: Write the failing test**

```python
# layer2_mcp/tests/test_llm_client.py
"""Tests for LLM client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from code2doc_layer2_mcp.config import Layer2Settings
from code2doc_layer2_mcp.llm_client import Layer2LLMClient


class TestLayer2LLMClient:
    def test_init_with_settings(self) -> None:
        settings = Layer2Settings(
            llm_api_key="test-key",
            llm_model="gpt-4o",
        )
        client = Layer2LLMClient(settings)
        assert client is not None

    @pytest.mark.asyncio
    async def test_extract_module_knowledge(self) -> None:
        settings = Layer2Settings(
            llm_api_key="test-key",
            llm_model="gpt-4o",
        )
        client = Layer2LLMClient(settings)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="## Auth Module\nAuth handles login."))]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        mock_async_client = AsyncMock()
        mock_async_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("code2doc_layer2_mcp.llm_client.AsyncOpenAI", return_value=mock_async_client):
            result = await client.extract_module_knowledge(
                module_name="auth",
                task_description="Implement JWT login",
                layer1_overview="Auth module handles user authentication",
                existing_content="## Auth Module\nBasic auth.",
                code_changes=[{"file": "auth.py", "diff": "+def login()"}],
            )
        assert "## Auth Module" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd layer2_mcp && python -m pytest tests/test_llm_client.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# layer2_mcp/src/code2doc_layer2_mcp/llm_client.py
"""LLM client for Layer 2 knowledge extraction."""

from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from code2doc_layer2_mcp.config import Layer2Settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a technical documentation writer. Given information about a code module \
and recent changes, produce an updated module documentation file in Markdown.

## Rules
- Keep the document factual and concise.
- Preserve existing sections that are still accurate.
- Update or add sections based on new changes.
- Use proper Markdown formatting with headers, code blocks, and lists.
- If existing content is provided, merge the new information into it rather \
than replacing everything.
- Respond with ONLY the Markdown content, no explanations outside it.
"""


class Layer2LLMClient:
    """Async LLM client for module knowledge extraction."""

    def __init__(self, settings: Layer2Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "dummy",
        )

    async def extract_module_knowledge(
        self,
        module_name: str,
        task_description: str,
        layer1_overview: str,
        existing_content: str,
        code_changes: list[dict[str, str]],
    ) -> str:
        """Extract/update module documentation from task context.

        Args:
            module_name: Name of the target module.
            task_description: What task was performed.
            layer1_overview: Project overview (Layer 1 doc).
            existing_content: Current module doc content (if any).
            code_changes: List of dicts with 'file', 'diff', 'action' keys.

        Returns:
            Updated module documentation in Markdown.
        """
        changes_text = "\n".join(
            f"- **{c.get('file', '?')}** ({c.get('action', 'modified')}):\n```diff\n{c.get('diff', '')}\n```"
            for c in code_changes
        )

        user_prompt = f"""\
## Task
{task_description}

## Module
{module_name}

## Project Overview (Layer 1)
{layer1_overview}

## Existing Module Documentation
{existing_content if existing_content else '(No existing documentation)'}

## Code Changes
{changes_text if changes_text else '(No code changes provided)'}

Produce an updated Markdown documentation file for the '{module_name}' module.
"""

        response = await self._client.chat.completions.create(
            model=self._settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self._settings.llm_max_tokens,
            temperature=self._settings.llm_temperature,
        )

        choice = response.choices[0]
        return choice.message.content or ""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd layer2_mcp && python -m pytest tests/test_llm_client.py -v
```

Expected: 1 test PASS

- [ ] **Step 5: Commit**

```bash
git add layer2_mcp/src/code2doc_layer2_mcp/llm_client.py layer2_mcp/tests/test_llm_client.py
git commit -m "feat(layer2_mcp): add LLM client for knowledge extraction"
```

---

### Task 4: Implement FastAPI HTTP server

**Files:**
- Create: `layer2_mcp/src/code2doc_layer2_mcp/server.py`
- Create: `layer2_mcp/tests/test_server.py`

- [ ] **Step 1: Write the failing tests**

```python
# layer2_mcp/tests/test_server.py
"""Tests for HTTP server endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from code2doc_layer2_mcp.config import Layer2Settings
from code2doc_layer2_mcp.server import create_app


@pytest.fixture
def modules_dir(tmp_path: Path) -> Path:
    modules = tmp_path / "modules"
    modules.mkdir()
    (modules / "auth.md").write_text("# Module: auth\n\nAuth docs.\n", encoding="utf-8")
    (modules / "user.md").write_text("# Module: user\n\nUser docs.\n", encoding="utf-8")
    return modules


@pytest.fixture
def settings(modules_dir: Path) -> Layer2Settings:
    return Layer2Settings(
        llm_api_key="test-key",
        modules_dir=str(modules_dir),
    )


@pytest.fixture
def app(settings: Layer2Settings):
    return create_app(settings)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestListModules:
    @pytest.mark.asyncio
    async def test_list_all(self, client: AsyncClient) -> None:
        resp = await client.get("/modules")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["modules"]) == 2
        names = [m["name"] for m in data["modules"]]
        assert "auth" in names
        assert "user" in names


class TestGetModule:
    @pytest.mark.asyncio
    async def test_get_existing(self, client: AsyncClient) -> None:
        resp = await client.get("/modules/auth")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "auth"
        assert "# Module: auth" in data["content"]

    @pytest.mark.asyncio
    async def test_get_missing(self, client: AsyncClient) -> None:
        resp = await client.get("/modules/nonexistent")
        assert resp.status_code == 404


class TestSearchModules:
    @pytest.mark.asyncio
    async def test_search_match(self, client: AsyncClient) -> None:
        resp = await client.get("/modules?query=auth")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["modules"]) == 1
        assert data["modules"][0]["name"] == "auth"

    @pytest.mark.asyncio
    async def test_search_no_match(self, client: AsyncClient) -> None:
        resp = await client.get("/modules?query=database")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["modules"]) == 0


class TestUpdateModule:
    @pytest.mark.asyncio
    async def test_update_success(self, client: AsyncClient) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="# Module: auth\n\nUpdated docs."))]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        mock_async_client = AsyncMock()
        mock_async_client.chat.completions.create = AsyncMock(return_value=mock_response)

        payload = {
            "modules": ["auth"],
            "task_description": "Add OAuth2 support",
            "background": "Need OAuth2 for third-party login",
            "layer1_overview": "Project has auth module at src/api/auth",
            "code_changes": [
                {"file": "auth.py", "diff": "+def oauth_login()", "action": "modified"},
            ],
        }

        with patch("code2doc_layer2_mcp.server.AsyncOpenAI", return_value=mock_async_client):
            resp = await client.post("/update", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["updated"]) == 1
        assert "auth" in data["updated"]

    @pytest.mark.asyncio
    async def test_update_missing_modules(self, client: AsyncClient) -> None:
        payload = {
            "task_description": "Some task",
        }
        resp = await client.post("/update", json=payload)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_no_api_key(self, client: AsyncClient) -> None:
        from code2doc_layer2_mcp.config import Layer2Settings

        settings_no_key = Layer2Settings(
            llm_api_key="",
            modules_dir="modules",
        )
        app_no_key = create_app(settings_no_key)
        transport = ASGITransport(app=app_no_key)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            payload = {
                "modules": ["auth"],
                "task_description": "Some task",
            }
            resp = await ac.post("/update", json=payload)
        assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd layer2_mcp && python -m pytest tests/test_server.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# layer2_mcp/src/code2doc_layer2_mcp/server.py
"""FastAPI HTTP server for Layer 2 module documentation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from code2doc_layer2_mcp.config import Layer2Settings
from code2doc_layer2_mcp.llm_client import Layer2LLMClient
from code2doc_layer2_mcp.module_store import ModuleStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CodeChange(BaseModel):
    file: str
    diff: str
    action: str = "modified"


class UpdateRequest(BaseModel):
    modules: list[str] = Field(..., min_length=1, description="Module names to update")
    task_description: str = Field(..., description="What task was performed")
    background: str = ""
    layer1_overview: str = ""
    code_changes: list[CodeChange] = Field(default_factory=list)


class ModuleResponse(BaseModel):
    name: str
    content: str


class ModuleListResponse(BaseModel):
    modules: list[ModuleResponse]


class UpdateResponse(BaseModel):
    updated: list[str]
    failed: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(settings: Layer2Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = settings or Layer2Settings()
    modules_dir = Path(settings.modules_dir)
    store = ModuleStore(modules_dir)
    llm_client = Layer2LLMClient(settings) if settings.llm_api_key else None

    app = FastAPI(
        title="Layer 2 Module Documentation Server",
        version="0.1.0",
        description="HTTP server for managing module documentation. "
        "POST task context to update docs, GET to retrieve them.",
    )

    app.state.settings = settings
    app.state.store = store
    app.state.llm_client = llm_client

    # ------------------------------------------------------------------
    # GET endpoints
    # ------------------------------------------------------------------

    @app.get("/modules", response_model=ModuleListResponse)
    async def list_modules(
        query: Optional[str] = Query(None, description="Search query for module name or content"),
    ) -> ModuleListResponse:
        """List all modules, optionally filtered by search query."""
        if query:
            mods = store.search_modules(query)
        else:
            mods = store.list_modules()
        return ModuleListResponse(
            modules=[ModuleResponse(name=m["name"], content=m["content"]) for m in mods],
        )

    @app.get("/modules/{module_name}", response_model=ModuleResponse)
    async def get_module(module_name: str) -> ModuleResponse:
        """Get a specific module's documentation."""
        doc = store.get_module(module_name)
        if doc is None:
            raise HTTPException(status_code=404, detail=f"Module not found: {module_name}")
        return ModuleResponse(name=doc["name"], content=doc["content"])

    # ------------------------------------------------------------------
    # POST endpoint
    # ------------------------------------------------------------------

    @app.post("/update", response_model=UpdateResponse)
    async def update_modules(request: UpdateRequest) -> UpdateResponse:
        """Receive task context and update module documentation via LLM."""
        if llm_client is None:
            raise HTTPException(
                status_code=400,
                detail="LLM not configured. Set LAYER2_LLM_API_KEY environment variable.",
            )

        updated: list[str] = []
        failed: list[str] = []

        changes_dicts = [c.model_dump() for c in request.code_changes]

        for module_name in request.modules:
            try:
                existing = store.get_module(module_name)
                existing_content = existing["content"] if existing else ""

                new_content = await llm_client.extract_module_knowledge(
                    module_name=module_name,
                    task_description=request.task_description,
                    layer1_overview=request.layer1_overview,
                    existing_content=existing_content,
                    code_changes=changes_dicts,
                )

                store.save_module(module_name, new_content)
                updated.append(module_name)
                logger.info("Updated module: %s", module_name)

            except Exception as exc:
                logger.error("Failed to update module %s: %s", module_name, exc)
                failed.append(module_name)

        return UpdateResponse(updated=updated, failed=failed)

    return app
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd layer2_mcp && python -m pytest tests/test_server.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add layer2_mcp/src/code2doc_layer2_mcp/server.py layer2_mcp/tests/test_server.py
git commit -m "feat(layer2_mcp): add FastAPI server with GET/POST endpoints"
```

---

### Task 5: Implement CLI entry point

**Files:**
- Create: `layer2_mcp/src/code2doc_layer2_mcp/cli.py`

- [ ] **Step 1: Write the implementation**

```python
# layer2_mcp/src/code2doc_layer2_mcp/cli.py
"""CLI entry point for code2doc-layer2-mcp."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

app = typer.Typer(
    name="layer2-mcp",
    help="HTTP server for Layer 2 module documentation management.",
    no_args_is_help=True,
)


@app.command()
def serve(
    project: Path = typer.Argument(
        ...,
        help="Project root directory (modules stored under project/modules/).",
        exists=True,
    ),
    host: str = typer.Option(
        "0.0.0.0",
        "--host",
        help="Bind address",
    ),
    port: int = typer.Option(
        8001,
        "--port", "-p",
        help="Port to listen on",
    ),
) -> None:
    """Start the Layer 2 module documentation HTTP server."""
    from code2doc_layer2_mcp.config import Layer2Settings
    from code2doc_layer2_mcp.server import create_app

    import uvicorn

    project_root = project.resolve()
    modules_dir = project_root / "modules"

    settings = Layer2Settings(
        modules_dir=str(modules_dir),
        host=host,
        port=port,
    )

    app = create_app(settings)

    print(
        f"layer2-mcp HTTP server starting on {host}:{port}",
        file=sys.stderr,
    )
    print(f"Project: {project_root}", file=sys.stderr)
    print(f"Modules: {modules_dir}", file=sys.stderr)
    if not settings.llm_api_key:
        print("WARNING: No LLM API key set. POST /update will not work.", file=sys.stderr)
        print("Set LAYER2_LLM_API_KEY environment variable.", file=sys.stderr)

    uvicorn.run(app, host=host, port=port, log_level="info")
```

- [ ] **Step 2: Verify the CLI entry point works**

```bash
cd layer2_mcp && layer2-mcp --help
```

Expected: Shows help text with `serve` command

- [ ] **Step 3: Commit**

```bash
git add layer2_mcp/src/code2doc_layer2_mcp/cli.py
git commit -m "feat(layer2_mcp): add CLI entry point with serve command"
```

---

### Task 6: Remove Layer 2 from ai_code2doc main package

**Files:**
- Delete: `src/ai_code2doc/generator/layer2_modules.py`
- Delete: `src/ai_code2doc/generator/base_generator.py`
- Delete: `src/ai_code2doc/generator/markdown_writer.py`
- Delete: `src/ai_code2doc/generator/prompt_templates.py`
- Delete: `src/ai_code2doc/generator/__init__.py`
- Delete: `tests/unit/test_prompt_templates.py`
- Delete: `tests/unit/test_markdown_writer.py`
- Modify: `src/ai_code2doc/cli/analyze_cmd.py`
- Modify: `src/ai_code2doc/agent/tools/update_doc.py`
- Modify: `src/ai_code2doc/config/defaults.py`
- Modify: `src/ai_code2doc/web/routes/modules.py`
- Modify: `src/ai_code2doc/web/routes/__init__.py`

- [ ] **Step 1: Delete generator files**

```bash
rm src/ai_code2doc/generator/layer2_modules.py
rm src/ai_code2doc/generator/base_generator.py
rm src/ai_code2doc/generator/markdown_writer.py
rm src/ai_code2doc/generator/prompt_templates.py
rm src/ai_code2doc/generator/__init__.py
rm tests/unit/test_prompt_templates.py
rm tests/unit/test_markdown_writer.py
```

- [ ] **Step 2: Update `analyze_cmd.py` — replace layer 2 block with guidance**

In `src/ai_code2doc/cli/analyze_cmd.py`, replace lines 149-178 (the `if 2 in selected_layers:` block) with:

```python
            if 2 in selected_layers:
                console.print(
                    "  [yellow]Layer 2 is now handled by the standalone layer2-mcp package.[/yellow]"
                )
                console.print(
                    "  Run [bold]layer2-mcp serve <project>[/bold] to start the module documentation server."
                )
                selected_layers = [l for l in selected_layers if l != 2]
```

Also update the `--layers` default from `"1,2,3"` to `"1,2,3"` (keep as is, the blocks now just print guidance).

- [ ] **Step 3: Update `update_doc.py` — replace layer 2 block with guidance**

In `src/ai_code2doc/agent/tools/update_doc.py`, replace the layer 2 handling (lines 34-52) with:

```python
        if layer == 2:
            return ToolResult(tool_call_id=call.id, content="Layer 2 is handled by the standalone layer2-mcp package. Use `layer2-mcp serve <project>` for module documentation management.", is_error=True)
```

- [ ] **Step 4: Clean up `config/defaults.py` — remove PROMPT_LAYER2**

Remove the entire `PROMPT_LAYER2` string from `src/ai_code2doc/config/defaults.py`. The file should only contain the imports from code2doc-core and the `KEEP_EXTENSIONS` list.

- [ ] **Step 5: Update `web/routes/modules.py` — point to `modules/` dir**

Replace the `layer2_dir` references with `modules_dir`:

```python
"""Web routes for serving module documentation."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ModuleInfo(BaseModel):
    name: str
    path: str
    content: str
    file_count: int = 0


class ModuleListResponse(BaseModel):
    modules: list[ModuleInfo]


@router.get("", response_model=ModuleListResponse)
async def list_modules(request: Request) -> ModuleListResponse:
    """List all modules."""
    root = _get_root(request)
    modules_dir = root / "modules"
    modules = []
    if modules_dir.exists():
        for f in sorted(modules_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            modules.append(
                ModuleInfo(
                    name=f.stem,
                    path=f.stem,
                    content=content,
                    file_count=content.count("### "),
                )
            )
    return ModuleListResponse(modules=modules)


@router.get("/{module_path:path}", response_model=ModuleInfo)
async def get_module(request: Request, module_path: str) -> ModuleInfo:
    """Get a specific module's details."""
    root = _get_root(request)
    md_path = root / "modules" / f"{module_path}.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail=f"Module not found: {module_path}")
    content = md_path.read_text(encoding="utf-8")
    return ModuleInfo(
        name=module_path,
        path=module_path,
        content=content,
        file_count=content.count("### "),
    )


def _get_root(request: Request) -> Path:
    return request.app.state.project_root
```

- [ ] **Step 6: Run all ai_code2doc tests**

```bash
cd /path/to/ai_code2doc && python -m pytest tests/ -x --tb=short
```

Expected: All tests pass (some tests referencing removed modules will fail — fix imports)

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: remove layer2 generation from ai_code2doc, replaced by layer2_mcp"
```

---

### Task 7: Run full test suite and fix any failures

**Files:**
- Any files with failing tests discovered during this task

- [ ] **Step 1: Run full ai_code2doc test suite**

```bash
python -m pytest tests/ -x --tb=short
```

- [ ] **Step 2: Run layer2_mcp test suite**

```bash
cd layer2_mcp && python -m pytest tests/ -v
```

- [ ] **Step 3: Fix any failures and re-run**

Address import errors, missing references, or assertion failures.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve test failures after layer2 removal"
```

---

### Task 8: Integration test — start server and exercise endpoints

**Files:**
- Create: `layer2_mcp/tests/test_integration.py`

- [ ] **Step 1: Write the integration test**

```python
# layer2_mcp/tests/test_integration.py
"""Integration tests: start server, exercise all endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from code2doc_layer2_mcp.config import Layer2Settings
from code2doc_layer2_mcp.server import create_app


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    modules = tmp_path / "modules"
    modules.mkdir()
    (modules / "auth.md").write_text("# Module: auth\n\nLogin and registration.", encoding="utf-8")
    (modules / "user.md").write_text("# Module: user\n\nUser profile management.", encoding="utf-8")
    return tmp_path


@pytest.fixture
def settings(project_dir: Path) -> Layer2Settings:
    return Layer2Settings(llm_api_key="test-key", modules_dir=str(project_dir / "modules"))


@pytest.fixture
async def client(settings: Layer2Settings):
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_full_workflow(client: AsyncClient) -> None:
    """Test the complete workflow: list -> get -> search -> update -> verify."""

    # 1. List all modules
    resp = await client.get("/modules")
    assert resp.status_code == 200
    modules = resp.json()["modules"]
    assert len(modules) == 2

    # 2. Get specific module
    resp = await client.get("/modules/auth")
    assert resp.status_code == 200
    assert "Login" in resp.json()["content"]

    # 3. Search modules
    resp = await client.get("/modules?query=user")
    assert resp.status_code == 200
    assert len(resp.json()["modules"]) == 1
    assert resp.json()["modules"][0]["name"] == "user"

    # 4. Update a module via POST
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="# Module: auth\n\nUpdated: JWT login added."))]
    mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    mock_async_client = AsyncMock()
    mock_async_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("code2doc_layer2_mcp.server.AsyncOpenAI", return_value=mock_async_client):
        resp = await client.post("/update", json={
            "modules": ["auth"],
            "task_description": "Add JWT authentication",
            "background": "Replacing session-based auth",
            "layer1_overview": "Auth module at src/api/auth handles login/logout",
            "code_changes": [
                {"file": "auth.py", "diff": "+def jwt_login(token)", "action": "modified"},
            ],
        })
    assert resp.status_code == 200
    assert "auth" in resp.json()["updated"]

    # 5. Verify the update
    resp = await client.get("/modules/auth")
    assert resp.status_code == 200
    assert "JWT" in resp.json()["content"]
```

- [ ] **Step 2: Run the integration test**

```bash
cd layer2_mcp && python -m pytest tests/test_integration.py -v
```

Expected: 1 test PASS

- [ ] **Step 3: Commit**

```bash
git add layer2_mcp/tests/test_integration.py
git commit -m "test(layer2_mcp): add integration test for full workflow"
```

---

### Task 9: Update README documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README to reflect new architecture**

In the README, update or add a section for Layer 2 MCP:

Replace any existing Layer 2 documentation with:

```
### Layer 2: Module Documentation (layer2_mcp)

Standalone HTTP server for managing module documentation.

```bash
# Install
pip install ./layer2_mcp

# Start server
layer2-mcp serve /path/to/project --port 8001

# Endpoints
GET  /modules                 # List all modules
GET  /modules/{name}          # Get module doc
GET  /modules?query=xxx       # Search modules
POST /update                  # Update modules via task context
```

Environment variables:
- `LAYER2_LLM_API_KEY` — LLM API key (required for POST /update)
- `LAYER2_LLM_BASE_URL` — LLM endpoint URL
- `LAYER2_LLM_MODEL` — Model name (default: gpt-4o)
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with layer2_mcp usage"
```

---

### Task 10: Push all changes to remote

- [ ] **Step 1: Push to origin**

```bash
git push origin main
```
