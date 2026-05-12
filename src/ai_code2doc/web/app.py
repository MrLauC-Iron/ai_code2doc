from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from ai_code2doc.web.routes import overview, modules, graph, search, ask


def create_app(project_root: Path | None = None) -> FastAPI:
    app = FastAPI(
        title="ai-code2doc",
        description="AI Code Knowledge System API",
        version="0.1.0",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store project root in app state
    if project_root:
        app.state.project_root = project_root.resolve()

    # Register routes
    app.include_router(overview.router, prefix="/api/v1", tags=["overview"])
    app.include_router(modules.router, prefix="/api/v1/modules", tags=["modules"])
    app.include_router(graph.router, prefix="/api/v1/graph", tags=["graph"])
    app.include_router(search.router, prefix="/api/v1", tags=["search"])
    app.include_router(ask.router, prefix="/api/v1", tags=["ask"])

    # Serve static frontend
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
