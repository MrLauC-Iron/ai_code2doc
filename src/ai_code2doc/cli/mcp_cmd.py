"""``mcp`` sub-command — starts an MCP stdio server for dependency graph queries."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

console = Console()


def register(app: typer.Typer) -> None:
    """Register the *mcp* command on the main Typer application."""

    @app.command()
    def mcp(
        project_path: Path = typer.Argument(
            ...,
            help="Path to the analysed project.",
            exists=True,
        ),
    ) -> None:
        """Start MCP server for dependency graph queries over stdio."""
        from ai_code2doc.config.settings import Settings
        from ai_code2doc.mcp.server import MCPServer
        from ai_code2doc.mcp.tools import register_all_tools

        settings = Settings()
        project_root = project_path.resolve()
        db_path = project_root / settings.output_dir / "layer3" / "dependency-graph.db"

        if not db_path.exists():
            console.print(
                f"[red]Error:[/red] Dependency graph not found at {db_path}\n"
                f"Run [bold]ai-code2doc analyze {project_path}[/bold] first."
            )
            raise typer.Exit(code=1)

        server = MCPServer(name="ai-code2doc", version="0.1.0")
        register_all_tools(server, db_path)

        # Log to stderr so it doesn't corrupt the stdio protocol
        import sys
        print(
            f"ai-code2doc MCP server ready. DB: {db_path}",
            file=sys.stderr,
        )

        server.run()
