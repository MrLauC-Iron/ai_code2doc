"""``status`` sub-command -- shows analysis state for a project."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

console = Console()


def register(app: typer.Typer) -> None:
    """Register the *status* command on the main Typer application."""

    @app.command()
    def status(
        project_path: Path = typer.Argument(
            ...,
            help="Path to the analysed TS/JS project.",
            exists=True,
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            "-v",
            help="Show per-file details.",
        ),
    ) -> None:
        """Show the analysis state and output summary for a project."""
        from ai_code2doc.config.settings import Settings
        from ai_code2doc.models.analysis_state import AnalysisState

        settings = Settings()
        project_root = project_path.resolve()
        output_dir = project_root / settings.output_dir

        # -- header ------------------------------------------------------------
        console.print(
            Panel(
                f"[bold]Project:[/] {project_root}",
                title="ai-code2doc status",
                border_style="blue",
            )
        )

        # -- check output directory -------------------------------------------
        if not output_dir.exists():
            console.print(
                "[yellow]No analysis output found.[/yellow]\n"
                f"Run [bold]ai-code2doc analyze {project_path}[/bold] first."
            )
            raise typer.Exit()

        # -- load analysis state -----------------------------------------------
        state_file = output_dir / "analysis_state.json"
        if state_file.exists():
            try:
                state_data = json.loads(state_file.read_text(encoding="utf-8"))
                state = AnalysisState.model_validate(state_data)
                _display_state(state, console, verbose=verbose)
            except Exception as exc:
                console.print(
                    f"[yellow]Warning:[/yellow] Could not parse state file: {exc}"
                )
        else:
            console.print(
                "[yellow]No analysis state file found.[/yellow] "
                "The project may have been analysed with an older version."
            )

        # -- output directory contents -----------------------------------------
        _display_output_tree(output_dir, console)

        # -- vector store info -------------------------------------------------
        chroma_dir = output_dir / "chroma"
        if chroma_dir.exists():
            try:
                from ai_code2doc.vector_store.store import VectorStore

                vs = VectorStore(settings, str(chroma_dir))
                count = vs.count()
                console.print(f"\n  [bold]Vector store:[/bold] {count} indexed chunks")
            except Exception as exc:
                console.print(
                    f"\n  [yellow]Vector store:[/yellow] exists but could not "
                    f"be read ({exc})"
                )
        else:
            console.print("\n  [dim]Vector store: not built (run without --no-vector-store)[/dim]")

        console.print()  # trailing newline


def _display_state(
    state: AnalysisState,
    console: Console,
    *,
    verbose: bool = False,
) -> None:
    """Pretty-print the analysis state."""

    # -- summary table -------------------------------------------------------
    summary = Table(show_header=False, box=None, padding=(0, 2))
    summary.add_column("Key", style="bold cyan")
    summary.add_column("Value")

    summary.add_row("Project root", state.project_root)
    summary.add_row("Tracked files", str(len(state.file_states)))

    if state.last_full_analysis:
        summary.add_row(
            "Last full analysis",
            state.last_full_analysis.strftime("%Y-%m-%d %H:%M:%S"),
        )
    else:
        summary.add_row("Last full analysis", "[dim]never[/dim]")

    summary.add_row("State version", str(state.version))
    console.print(summary)

    # -- per-file details -----------------------------------------------------
    if verbose and state.file_states:
        console.print("\n[bold]Tracked files:[/bold]")

        file_table = Table(show_header=True, header_style="bold cyan")
        file_table.add_column("File", no_wrap=True)
        file_table.add_column("Hash", width=32)
        file_table.add_column("Last analysed", width=20)

        for path, fs in sorted(state.file_states.items()):
            file_table.add_row(
                path,
                fs.hash,
                fs.last_analyzed.strftime("%Y-%m-%d %H:%M:%S"),
            )

        console.print(file_table)
    elif state.file_states:
        console.print(
            f"  [dim]({len(state.file_states)} tracked files -- "
            f"use --verbose to list)[/dim]"
        )


def _display_output_tree(output_dir: Path, console: Console) -> None:
    """Render a tree view of the output directory contents."""
    console.print("\n[bold]Output files:[/bold]")

    tree = Tree(str(output_dir.name))

    def _add_branch(parent: Tree, directory: Path, prefix: str = "") -> None:
        """Recursively add directory contents to a rich Tree."""
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return

        for entry in entries:
            # Skip chroma internals to keep the tree readable
            if entry.name == "chroma":
                parent.add(f"[dim]{entry.name}/[/dim] (vector store)")
                continue
            if entry.name == "analysis_state.json":
                parent.add(f"[green]{entry.name}[/green]")
                continue
            if entry.is_dir():
                branch = parent.add(f"[bold]{entry.name}/[/bold]")
                _add_branch(branch, entry)
            else:
                size_kb = entry.stat().st_size / 1024
                if size_kb >= 1024:
                    size_str = f"{size_kb / 1024:.1f} MB"
                else:
                    size_str = f"{size_kb:.1f} KB"
                parent.add(f"{entry.name}  [dim]({size_str})[/dim]")

    _add_branch(tree, output_dir)
    console.print(tree)
