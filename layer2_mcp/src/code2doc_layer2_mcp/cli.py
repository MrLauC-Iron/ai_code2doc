"""CLI entry point for code2doc-layer2-mcp."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

app = typer.Typer(
    name="layer2-mcp",
    help="MCP server for Layer 2 module documentation management.",
    no_args_is_help=True,
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def main(
    project: Path = typer.Option(
        None,
        "--project", "-P",
        help="Project root directory (modules stored under <project>/modules/).",
    ),
    modules_dir: Path = typer.Option(
        None,
        "--modules-dir",
        help="Direct path to modules directory (overrides --project).",
    ),
    transport: str = typer.Option(
        "stdio",
        "--transport", "-t",
        help="Transport mode: stdio (local) or http (remote server).",
    ),
    host: str = typer.Option(
        "0.0.0.0",
        "--host",
        help="Bind address for HTTP transport.",
    ),
    port: int = typer.Option(
        8001,
        "--port", "-p",
        help="Port for HTTP transport.",
    ),
) -> None:
    """Start the MCP server for module documentation management.

    Usage:
        layer2-mcp --project /path/to/project
        layer2-mcp --modules-dir /path/to/modules
        layer2-mcp --project . --transport http --port 8001
    """
    if not project and not modules_dir:
        typer.echo(
            "Provide --project or --modules-dir.",
            err=True,
        )
        raise typer.Exit(code=1)

    if transport not in ("stdio", "http"):
        typer.echo(
            f"Unknown transport: {transport}. Use 'stdio' or 'http'.",
            err=True,
        )
        raise typer.Exit(code=1)

    from code2doc_layer2_mcp.mcp_server import create_server

    if modules_dir:
        resolved_dir = modules_dir.resolve()
    else:
        resolved_dir = project.resolve() / "modules"

    server = create_server(resolved_dir)

    if transport == "http":
        print(
            f"code2doc-layer2-mcp HTTP server starting on {host}:{port}",
            file=sys.stderr,
        )
        print(f"Modules directory: {resolved_dir}", file=sys.stderr)

        from code2doc_layer2_mcp.config import Layer2Settings
        settings = Layer2Settings()
        if not settings.llm_api_key:
            print(
                "WARNING: LAYER2_LLM_API_KEY not set. update_modules tool will not work.",
                file=sys.stderr,
            )

        server.run(transport="streamable-http", host=host, port=port)
    else:
        server.run(transport="stdio")
