"""``query`` sub-command -- searches the vector store and optionally uses RAG."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

console = Console()


def register(app: typer.Typer) -> None:
    """Register the *query* command on the main Typer application."""

    @app.command()
    def query(
        project_path: Path = typer.Argument(
            ...,
            help="Path to the analysed TS/JS project.",
            exists=True,
        ),
        question: str = typer.Argument(
            ...,
            help="Natural-language question about the project.",
        ),
        n_results: int = typer.Option(
            5,
            "--n-results",
            "-n",
            help="Number of search results to return.",
        ),
        layer: Optional[int] = typer.Option(
            None,
            "--layer",
            "-l",
            help="Restrict search to a specific layer (1, 2, or 3).",
        ),
        no_rag: bool = typer.Option(
            False,
            "--no-rag",
            help="Skip LLM-powered RAG answer; show raw search results only.",
        ),
    ) -> None:
        """Query the project knowledge base with a natural-language question."""
        from ai_code2doc.config.settings import Settings

        settings = Settings()
        project_root = project_path.resolve()
        output_dir = project_root / settings.output_dir
        chroma_dir = output_dir / "chroma"

        # -- validate ----------------------------------------------------------
        if not chroma_dir.exists():
            console.print(
                f"[red]Error:[/red] No vector store found at {chroma_dir}\n"
                f"Run [bold]ai-code2doc analyze {project_path}[/bold] first."
            )
            raise typer.Exit(code=1)

        console.print(
            Panel(
                f"[bold]Question:[/] {question}",
                title="ai-code2doc query",
                border_style="blue",
            )
        )

        # -- search vector store -----------------------------------------------
        try:
            from ai_code2doc.vector_store.store import VectorStore

            vs = VectorStore(settings, str(chroma_dir))
        except Exception as exc:
            console.print(f"[red]Error loading vector store:[/red] {exc}")
            raise typer.Exit(code=1)

        response = vs.search(question, n_results=n_results, layer=layer)

        if not response.results:
            console.print("[yellow]No results found.[/yellow]")
            raise typer.Exit()

        # -- display raw results -----------------------------------------------
        console.print(f"\n[bold]Found {response.total} relevant chunks:[/bold]\n")

        results_table = Table(show_header=True, header_style="bold cyan")
        results_table.add_column("#", style="dim", width=4)
        results_table.add_column("Score", justify="right", width=8)
        results_table.add_column("Layer", justify="center", width=6)
        results_table.add_column("Source", width=40)
        results_table.add_column("Preview", max_width=60)

        for idx, result in enumerate(response.results, 1):
            layer_val = str(result.metadata.get("layer", "?"))
            source = result.metadata.get("source_path", "unknown")
            preview = result.content[:120].replace("\n", " ")
            results_table.add_row(
                str(idx),
                f"{result.score:.2f}",
                layer_val,
                source,
                preview,
            )

        console.print(results_table)

        # -- RAG answer via LLM -----------------------------------------------
        if not no_rag and settings.llm_api_key:
            console.print("\n[bold]Generating answer with RAG...[/bold]\n")
            try:
                from ai_code2doc.llm.client import LLMClient

                llm = LLMClient(settings)

                # Build context from top results
                context_parts: list[str] = []
                for result in response.results:
                    source = result.metadata.get("source_path", "unknown")
                    context_parts.append(
                        f"### Source: {source} (score: {result.score:.2f})\n"
                        f"{result.content}"
                    )
                context = "\n\n---\n\n".join(context_parts)

                prompt = (
                    "You are a senior software architect answering questions "
                    "about a codebase.  Use ONLY the context below to answer "
                    "the question.  If the context does not contain enough "
                    "information, say so clearly.\n\n"
                    f"## Context\n\n{context}\n\n"
                    f"## Question\n\n{question}\n\n"
                    "Provide a concise, well-structured answer in Markdown."
                )

                async def _generate() -> str:
                    result = await llm.agenerate(prompt, system="You are a helpful code documentation assistant.")
                    return result.content

                answer = asyncio.run(_generate())

                console.print(
                    Panel(
                        Markdown(answer),
                        title="Answer",
                        border_style="green",
                    )
                )

                # Token report
                u = llm.token_tracker.usage
                if u.request_count > 0:
                    console.print(
                        f"[dim]Tokens used: {u.total_tokens:,} "
                        f"({u.prompt_tokens:,} prompt + "
                        f"{u.completion_tokens:,} completion)[/dim]"
                    )

            except Exception as exc:
                console.print(
                    f"[yellow]Warning:[/yellow] RAG generation failed: {exc}"
                )
        elif not no_rag and not settings.llm_api_key:
            console.print(
                "\n[yellow]No LLM API key configured -- skipping RAG answer.[/yellow] "
                "Set AI_CODE2DOC_LLM_API_KEY to enable."
            )

        console.print()  # trailing newline
