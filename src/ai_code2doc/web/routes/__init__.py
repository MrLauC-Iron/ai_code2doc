"""Web API routes for ai_code2doc."""

from __future__ import annotations

from fastapi import APIRouter
from pathlib import Path

from ai_code2doc.config.settings import Settings
from ai_code2doc.web.routes import overview, modules, graph, search, ask


def create_router(
    project_root: Path,
    output_dir: Path,
    settings: Settings,
) -> APIRouter:
    """Create a FastAPI APIRouter with all route sub-modules mounted.

    Parameters
    ----------
    project_root:
        Absolute path to the analysed project.
    output_dir:
        Absolute path to the analysis output directory.
    settings:
        Application settings.

    Returns
    -------
    APIRouter
        A router that can be included in a FastAPI application.
    """
    router = APIRouter()

    # Store shared state in router state so route handlers can access it.
    router.state.project_root = project_root
    router.state.output_dir = output_dir
    router.state.settings = settings

    router.include_router(overview.router, tags=["overview"])
    router.include_router(modules.router, tags=["modules"])
    router.include_router(graph.router, tags=["graph"])
    router.include_router(search.router, tags=["search"])
    router.include_router(ask.router, tags=["ask"])

    return router
