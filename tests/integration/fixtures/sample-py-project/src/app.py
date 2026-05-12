"""FastAPI application factory."""

from fastapi import FastAPI

from src.api.routes import router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Sample App", version="0.1.0")
    app.include_router(router)
    return app
