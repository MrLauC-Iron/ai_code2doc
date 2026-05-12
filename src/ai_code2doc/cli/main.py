"""CLI entry point for ai-code2doc."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="ai-code2doc",
    help="AI Agent that analyzes Python/C/C++ projects and generates layered code knowledge systems.",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Register sub-commands
# ---------------------------------------------------------------------------
from ai_code2doc.cli.analyze_cmd import register as register_analyze
from ai_code2doc.cli.serve_cmd import register as register_serve
from ai_code2doc.cli.query_cmd import register as register_query
from ai_code2doc.cli.status_cmd import register as register_status

register_analyze(app)
register_serve(app)
register_query(app)
register_status(app)
