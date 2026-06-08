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
