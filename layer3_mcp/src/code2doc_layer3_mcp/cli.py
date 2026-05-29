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
        ...,
        help="Path to dependency-graph.db",
        exists=True,
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
        layer3-mcp <db_path> [--transport http] [--host 0.0.0.0] [--port 8000]
    """
    if transport not in ("stdio", "http"):
        typer.echo(f"Unknown transport: {transport}. Use 'stdio' or 'http'.", err=True)
        raise typer.Exit(code=1)

    from code2doc_layer3_mcp.server import create_server

    server = create_server(db_path.resolve())

    if transport == "http":
        import sys

        print(
            f"code2doc-layer3-mcp HTTP server starting on {host}:{port}",
            file=sys.stderr,
        )
        print(f"DB: {db_path.resolve()}", file=sys.stderr)
        server.run(transport="streamable-http", host=host, port=port)
    else:
        server.run(transport="stdio")
