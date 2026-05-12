"""``serve`` sub-command -- starts the web UI backed by a FastAPI application."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def register(app: typer.Typer) -> None:
    """Register the *serve* command on the main Typer application."""

    @app.command()
    def serve(
        project_path: Path = typer.Argument(
            ...,
            help="Path to the analysed project.",
            exists=True,
        ),
        port: int = typer.Option(
            8420,
            "--port",
            "-p",
            help="Port to listen on.",
        ),
        host: str = typer.Option(
            "0.0.0.0",
            "--host",
            "-h",
            help="Host/interface to bind to.",
        ),
        reload: bool = typer.Option(
            False,
            "--reload",
            help="Enable auto-reload for development.",
        ),
    ) -> None:
        """Serve the documentation web UI for an analysed project."""
        from ai_code2doc.config.settings import Settings

        settings = Settings()
        project_root = project_path.resolve()
        output_dir = project_root / settings.output_dir

        # Verify that the project has been analysed
        if not output_dir.exists():
            console.print(
                f"[red]Error:[/red] No analysis output found at {output_dir}\n"
                f"Run [bold]ai-code2doc analyze {project_path}[/bold] first."
            )
            raise typer.Exit(code=1)

        # Determine static files directory
        static_dir = Path(__file__).resolve().parent.parent / "web" / "static"
        if not static_dir.exists():
            static_dir.mkdir(parents=True, exist_ok=True)

        console.print(
            Panel(
                f"[bold]Serving documentation for:[/] {project_root}\n"
                f"[bold]Output:[/] {output_dir}\n"
                f"[bold]URL:[/] http://{host}:{port}",
                title="ai-code2doc serve",
                border_style="blue",
            )
        )

        # Build the FastAPI application inside the command so that import
        # errors (e.g. missing uvicorn) are only raised when the user
        # actually runs ``serve``.
        try:
            import uvicorn
        except ImportError as exc:
            console.print(
                "[red]Error:[/red] uvicorn is required to run the server. "
                "Install it with: [bold]pip install uvicorn[/bold]"
            )
            raise typer.Exit(code=1) from exc

        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles

        web_app = FastAPI(
            title="ai-code2doc",
            description="Interactive documentation viewer for analysed projects.",
        )

        # Store project root so route handlers can access it.
        web_app.state.project_root = project_root
        web_app.state.output_dir = output_dir

        # -- API routes -------------------------------------------------------
        from ai_code2doc.web.routes import create_router

        api_router = create_router(project_root, output_dir, settings)
        web_app.include_router(api_router, prefix="/api")

        # -- static files (frontend SPA) --------------------------------------
        if static_dir.exists() and any(static_dir.iterdir()):
            web_app.mount(
                "/",
                StaticFiles(directory=str(static_dir), html=True),
                name="static",
            )

        @web_app.on_event("startup")
        async def _on_startup() -> None:
            console.print(
                f"  [green]\u2713[/green] Server ready at "
                f"[bold cyan]http://{host}:{port}[/bold cyan]"
            )

        # -- run ---------------------------------------------------------------
        # Store the app in an env var so that uvicorn can import it when
        # ``--reload`` is used.  For the common non-reload case we hand the
        # app object directly to ``uvicorn.run``.
        os.environ["AI_CODE2DOC_PROJECT_ROOT"] = str(project_root)
        os.environ["AI_CODE2DOC_OUTPUT_DIR"] = str(output_dir)

        console.print("  Starting server... (press CTRL+C to stop)\n")

        uvicorn.run(
            web_app,
            host=host,
            port=port,
            log_level=settings.log_level.lower(),
            reload=reload,
            reload_dirs=[str(static_dir)] if reload else None,
        )
