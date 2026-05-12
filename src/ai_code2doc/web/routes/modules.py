from __future__ import annotations

from pathlib import Path
from typing import Any

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
    layer2_dir = root / ".ai_code2doc" / "layer2"
    modules = []
    if layer2_dir.exists():
        for f in sorted(layer2_dir.glob("*.md")):
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
    md_path = root / ".ai_code2doc" / "layer2" / f"{module_path}.md"
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
