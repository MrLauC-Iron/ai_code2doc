"""CLI entry point for code2doc-layer3-mcp."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(
    name="layer3-mcp",
    help="MCP server for Layer 3 dependency graph queries.",
    no_args_is_help=True,
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def main(
    db_path: Path = typer.Argument(
        None,
        help="Path to dependency-graph.db (mutually exclusive with --project)",
    ),
    project: Path = typer.Option(
        None,
        "--project", "-P",
        help="Project root directory (auto-detect git branch)",
    ),
    transport: str = typer.Option(
        "stdio",
        "--transport", "-t",
        help="Transport mode: stdio (local) or http (remote server)",
    ),
    host: str = typer.Option(
        "0.0.0.0",
        "--host",
        help="Bind address for HTTP transport",
    ),
    port: int = typer.Option(
        8000,
        "--port", "-p",
        help="Port for HTTP transport",
    ),
) -> None:
    """Start the MCP server for dependency graph queries.

    Usage:
        layer3-mcp <db_path>              # Direct DB path
        layer3-mcp --project .            # Auto-detect git branch
        layer3-mcp --project . --transport http --port 8000
    """
    if db_path and project:
        typer.echo(
            "Provide either DB_PATH or --project, not both.", err=True
        )
        raise typer.Exit(code=1)

    if project:
        from code2doc_layer3_mcp.git import get_layer3_db_path

        resolved_project = project.resolve()
        db_path = get_layer3_db_path(resolved_project)

    if db_path is None:
        typer.echo(
            "Usage: layer3-mcp DB_PATH or layer3-mcp --project PROJECT_DIR",
            err=True,
        )
        raise typer.Exit(code=1)

    resolved_db = db_path.resolve()
    if not resolved_db.exists():
        typer.echo(
            f"Dependency graph not found at {resolved_db}\n"
            f"Run 'ai-code2doc analyze' first.",
            err=True,
        )
        raise typer.Exit(code=1)

    if transport not in ("stdio", "http"):
        typer.echo(f"Unknown transport: {transport}. Use 'stdio' or 'http'.", err=True)
        raise typer.Exit(code=1)

    from code2doc_layer3_mcp.server import create_server

    server = create_server(resolved_db)

    if transport == "http":
        import sys

        print(
            f"code2doc-layer3-mcp HTTP server starting on {host}:{port}",
            file=sys.stderr,
        )
        print(f"DB: {resolved_db}", file=sys.stderr)
        server.run(transport="streamable-http", host=host, port=port)
    else:
        server.run(transport="stdio")
