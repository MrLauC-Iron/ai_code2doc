"""``analyze`` sub-command -- scans a project and generates layered documentation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


def register(app: typer.Typer) -> None:
    """Register the *analyze* command on the main Typer application."""

    @app.command()
    def analyze(
        project_path: Path = typer.Argument(
            ...,
            help="Path to the project to analyse.",
            exists=True,
        ),
        full: bool = typer.Option(
            False,
            "--full",
            help="Force full analysis (ignore incremental state).",
        ),
        incremental: bool = typer.Option(
            True,
            "--incremental",
            help="Only analyse files that changed since the last run.",
        ),
        layers: str = typer.Option(
            "1,2,3",
            "--layers",
            help="Comma-separated list of layers to generate (e.g. 1,2,3).",
        ),
        no_llm: bool = typer.Option(
            False,
            "--no-llm",
            help="Skip LLM calls and generate static documentation only.",
        ),
        no_vector_store: bool = typer.Option(
            False,
            "--no-vector-store",
            help="Skip vector-store indexing step.",
        ),
    ) -> None:
        """Analyse a project and generate knowledge documentation."""
        from ai_code2doc.config.settings import Settings
        from ai_code2doc.scanner.change_detector import ChangeDetector

        settings = Settings()
        project_root = project_path.resolve()
        output_dir = project_root / settings.output_dir

        # -- header -----------------------------------------------------------
        console.print(
            Panel(
                f"[bold]Analysing:[/] {project_root}",
                title="ai-code2doc",
                border_style="blue",
            )
        )

        # Parse requested layers
        try:
            selected_layers = [int(l.strip()) for l in layers.split(",")]
        except ValueError:
            console.print(
                "[red]Error:[/red] --layers must be comma-separated integers (e.g. 1,2,3)"
            )
            raise typer.Exit(code=1)

        # -- resolve incremental vs. full ------------------------------------
        use_incremental = incremental and not full

        # -- LLM client -------------------------------------------------------
        llm_client = None
        if not no_llm and settings.llm_api_key:
            from ai_code2doc.llm.client import LLMClient

            llm_client = LLMClient(settings)
            console.print(
                f"  LLM enabled: [cyan]{settings.llm_model}[/cyan] "
                f"via [dim]{settings.llm_base_url}[/dim]"
            )
        elif not no_llm and not settings.llm_api_key:
            console.print(
                "  [yellow]Warning:[/yellow] No LLM API key configured. "
                "Falling back to static generation."
            )
            no_llm = True

        # -- scan project -----------------------------------------------------
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning project files...", total=None)

            from ai_code2doc.scanner.project_scanner import ProjectScanner

            scanner = ProjectScanner(
                project_root,
                max_file_size_kb=settings.max_file_size_kb,
            )
            scan_result = scanner.scan()

            progress.update(task, completed=True)

        console.print(
            f"  Found [bold]{len(scan_result.target_files)}[/bold] target files"
        )

        # -- detect changes (incremental) -------------------------------------
        changed_files: list[Path] | None = None
        detector = ChangeDetector(project_root, settings.output_dir)

        if use_incremental:
            changed, unchanged = detector.detect_changes(scan_result.target_files)
            changed_files = changed
            console.print(
                f"  Incremental mode: [bold]{len(changed)}[/bold] changed / new, "
                f"[dim]{len(unchanged)}[/dim] unchanged"
            )

        # -- run generators ---------------------------------------------------
        all_docs: list = []

        async def _run_generators() -> None:
            nonlocal all_docs

            if 1 in selected_layers:
                from ai_code2doc.generator.layer1_overview import Layer1OverviewGenerator

                gen1 = Layer1OverviewGenerator(settings)
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        "Generating Layer 1: Project overview...", total=None
                    )
                    docs = await gen1.generate(
                        project_root,
                        output_dir,
                        use_llm=not no_llm,
                        changed_files=changed_files,
                    )
                    all_docs.extend(docs)
                    progress.update(task, completed=True)

                if docs:
                    console.print(
                        "  [green]\u2713[/green] Layer 1: Project overview generated"
                    )
                else:
                    console.print(
                        "  [dim]Layer 1: Skipped (no changes)[/dim]"
                    )

            if 2 in selected_layers:
                from ai_code2doc.generator.layer2_modules import Layer2ModuleGenerator

                gen2 = Layer2ModuleGenerator(settings)
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        "Generating Layer 2: Module summaries...", total=None
                    )
                    docs = await gen2.generate(
                        project_root,
                        output_dir,
                        use_llm=not no_llm,
                        changed_files=changed_files,
                    )
                    all_docs.extend(docs)
                    progress.update(task, completed=True)

                if docs:
                    console.print(
                        f"  [green]\u2713[/green] Layer 2: "
                        f"{len(docs)} module summaries generated"
                    )
                else:
                    console.print(
                        "  [dim]Layer 2: Skipped (no changes)[/dim]"
                    )

            if 3 in selected_layers:
                from ai_code2doc.generator.layer3_graph import Layer3GraphGenerator

                gen3 = Layer3GraphGenerator(settings)
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        "Generating Layer 3: Dependency graph...", total=None
                    )
                    docs = await gen3.generate(
                        project_root,
                        output_dir,
                        use_llm=not no_llm,
                        changed_files=changed_files,
                    )
                    all_docs.extend(docs)
                    progress.update(task, completed=True)

                if docs:
                    console.print(
                        "  [green]\u2713[/green] Layer 3: Dependency graph generated"
                    )
                else:
                    console.print(
                        "  [dim]Layer 3: Skipped (no changes)[/dim]"
                    )

        asyncio.run(_run_generators())

        # -- vector-store indexing ---------------------------------------------
        if not no_vector_store and all_docs:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Indexing documents in vector store...", total=None
                )
                try:
                    from ai_code2doc.vector_store.store import VectorStore

                    vs = VectorStore(settings, str(output_dir / "chroma"))
                    vs.add_documents(all_docs)
                    chunk_count = vs.count()
                    progress.update(task, completed=True)

                    console.print(
                        f"  [green]\u2713[/green] Indexed {chunk_count} chunks "
                        f"in vector store"
                    )
                except Exception as exc:
                    progress.update(task, completed=True)
                    console.print(
                        f"  [yellow]\u26A0[/yellow] Vector store indexing "
                        f"skipped: {exc}"
                    )

        # -- update analysis state --------------------------------------------
        detector.update_state(scan_result.target_files)

        # -- token usage report ------------------------------------------------
        if llm_client is not None:
            tracker = llm_client.token_tracker
            u = tracker.usage
            if u.request_count > 0:
                table = Table(title="Token Usage", show_header=True)
                table.add_column("Metric", style="cyan")
                table.add_column("Value", justify="right")
                table.add_row("Requests", str(u.request_count))
                table.add_row("Prompt tokens", f"{u.prompt_tokens:,}")
                table.add_row("Completion tokens", f"{u.completion_tokens:,}")
                table.add_row("Total tokens", f"{u.total_tokens:,}")
                console.print(table)

        # -- done --------------------------------------------------------------
        console.print(
            Panel(
                f"[bold green]Analysis complete![/bold green]\n"
                f"Output directory: {output_dir}",
                title="Done",
                border_style="green",
            )
        )
