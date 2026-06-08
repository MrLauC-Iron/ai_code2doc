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
