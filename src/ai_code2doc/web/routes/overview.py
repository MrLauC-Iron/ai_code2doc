from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class OverviewResponse(BaseModel):
    project_name: str
    tech_stack: dict[str, Any]
    entry_points: list[str]
    statistics: dict[str, int]
    overview_content: str


@router.get("/project", response_model=dict)
async def get_project(request: Request) -> dict:
    """Get project metadata."""
    root = _get_root(request)
    from ai_code2doc.analyzer.tech_stack import TechStackDetector

    detector = TechStackDetector(root)
    tech_stack = detector.detect()
    entry_points = detector.detect_entry_points()
    return {
        "name": root.name,
        "root_path": str(root),
        "tech_stack": tech_stack.model_dump(),
        "entry_points": entry_points,
    }


@router.get("/project/overview", response_model=OverviewResponse)
async def get_overview(request: Request) -> OverviewResponse:
    """Get Layer 1 project overview."""
    root = _get_root(request)
    content = _read_layer_file(root, "layer1/README.md")

    from ai_code2doc.analyzer.tech_stack import TechStackDetector

    detector = TechStackDetector(root)
    tech_stack = detector.detect()
    entry_points = detector.detect_entry_points()

    return OverviewResponse(
        project_name=root.name,
        tech_stack=tech_stack.model_dump(),
        entry_points=entry_points,
        statistics={"total_files": 0},
        overview_content=content,
    )


def _get_root(request: Request) -> Path:
    return request.app.state.project_root


def _read_layer_file(root: Path, relative: str) -> str:
    output_dir = root / ".ai_code2doc"
    path = output_dir / relative
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "# Not yet generated\n\nRun `ai-code2doc analyze` to generate this content."
