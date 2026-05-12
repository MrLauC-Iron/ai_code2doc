from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class GraphResponse(BaseModel):
    mermaid: str
    edges: list[dict]
    cycles: list[dict]


@router.get("", response_model=GraphResponse)
async def get_graph(request: Request) -> GraphResponse:
    """Get the full dependency graph."""
    root = _get_root(request)

    # Try to read cached graph
    graph_md = root / ".ai_code2doc" / "layer3" / "dependency-graph.md"
    mermaid_file = root / ".ai_code2doc" / "layer3" / "dependency-graph.mmd"

    mermaid = ""
    if mermaid_file.exists():
        mermaid = mermaid_file.read_text(encoding="utf-8")

    content = ""
    if graph_md.exists():
        content = graph_md.read_text(encoding="utf-8")

    return GraphResponse(
        mermaid=mermaid,
        edges=[],
        cycles=[],
    )


@router.get("/mermaid")
async def get_mermaid(request: Request) -> str:
    """Get Mermaid format dependency graph."""
    root = _get_root(request)
    mermaid_file = root / ".ai_code2doc" / "layer3" / "dependency-graph.mmd"
    if mermaid_file.exists():
        return mermaid_file.read_text(encoding="utf-8")
    return "graph TD\n    NoData[Run ai-code2doc analyze first]"


def _get_root(request: Request) -> Path:
    return request.app.state.project_root
