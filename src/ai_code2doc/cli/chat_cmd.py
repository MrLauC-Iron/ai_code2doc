"""``chat`` sub-command -- enter interactive REPL with existing analysis."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def register(app: typer.Typer) -> None:
    """Register the *chat* command on the main Typer application."""

    @app.command()
    def chat(
        project_path: Path = typer.Argument(
            ...,
            help="Path to the analysed project.",
            exists=True,
        ),
    ) -> None:
        """Enter interactive mode with an already-analysed project."""
        from ai_code2doc.agent.context import AgentContext, AnalysisResult
        from ai_code2doc.agent.repl import AgentREPL
        from ai_code2doc.config.settings import Settings

        settings = Settings()
        project_root = project_path.resolve()
        output_dir = project_root / settings.output_dir

        console.print(
            Panel(
                f"[bold]Chat mode:[/] {project_root}",
                title="ai-code2doc",
                border_style="blue",
            )
        )

        if not output_dir.exists():
            console.print(
                f"[red]Error:[/red] No analysis found at {output_dir}\n"
                f"Run [bold]ai-code2doc analyze {project_path}[/bold] first."
            )
            raise typer.Exit(code=1)

        analysis_result = AnalysisResult()
        try:
            from ai_code2doc.scanner.change_detector import ChangeDetector
            detector = ChangeDetector(project_root, settings.output_dir)
            state = detector.load_state()
            analysis_result.total_files = len(state.file_states)
            analysis_result.target_files = [Path(p) for p in state.file_states.keys()]
        except Exception:
            console.print("[yellow]Warning:[/yellow] Could not load analysis state.")

        if not settings.llm_api_key:
            console.print(
                "[yellow]Warning:[/yellow] No LLM API key configured. "
                "Set AI_CODE2DOC_LLM_API_KEY to enable full functionality."
            )

        ctx = AgentContext(project_root, settings, analysis_result)

        try:
            from ai_code2doc.agent.conversation import ConversationManager
            cm = ConversationManager(max_history=settings.repl_history_size)
            session_path = output_dir / settings.session_file
            if session_path.exists():
                cm.load(session_path)
                console.print(f"[dim]Loaded previous session from {session_path}[/dim]")
            repl = AgentREPL(ctx)
            repl._dispatcher._conversation = cm
            repl.run()
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
