"""Agent REPL: interactive terminal interface using prompt_toolkit."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from ai_code2doc.agent.dispatcher import AgentDispatcher
from ai_code2doc.agent.tool_registry import ToolRegistry
from ai_code2doc.agent.tools.list_context import tool_definition as list_context_def, execute as list_context_exec
from ai_code2doc.agent.tools.code_qa import tool_definition as code_qa_def, execute as code_qa_exec
from ai_code2doc.agent.tools.analyze_deps import tool_definition as analyze_deps_def, execute as analyze_deps_exec
from ai_code2doc.agent.tools.update_doc import tool_definition as update_doc_def, execute as update_doc_exec
from ai_code2doc.agent.tools.rescan import tool_definition as rescan_def, execute as rescan_exec
from ai_code2doc.agent.tools.correct import tool_definition as correct_def, execute as correct_exec

if TYPE_CHECKING:
    from ai_code2doc.agent.context import AgentContext

console = Console()

HELP_TEXT = """Available slash commands:
  /help      - Show this help message
  /quit      - Exit the REPL
  /history   - Show conversation history
  /save      - Save current session
  /context   - Show current context status
  /clear     - Clear conversation history

Or just type a natural language question and the agent will respond."""


class AgentREPL:
    """Interactive REPL for the agent."""

    def __init__(self, context: "AgentContext") -> None:
        self._context = context

        self._registry = ToolRegistry()
        self._registry.register(list_context_def, list_context_exec)
        self._registry.register(code_qa_def, code_qa_exec)
        self._registry.register(analyze_deps_def, analyze_deps_exec)
        self._registry.register(update_doc_def, update_doc_exec)
        self._registry.register(rescan_def, rescan_exec)
        self._registry.register(correct_def, correct_exec)

        self._dispatcher = AgentDispatcher(
            context=context,
            tool_registry=self._registry,
        )

    def _build_welcome(self) -> str:
        parts = ["\n  Analysis complete! Entering interactive mode."]
        if self._context.analysis_result:
            ar = self._context.analysis_result
            parts.append(f"  Files: {ar.total_files} | Lines: {ar.total_lines}")
        parts.append(f"  Tools: {', '.join(self._registry.tool_names)}")
        parts.append("  Type /help for commands, /quit to exit.\n")
        return "\n".join(parts)

    @staticmethod
    def _parse_slash_command(text: str) -> tuple[str, str] | None:
        text = text.strip()
        if not text.startswith("/"):
            return None
        parts = text.split(None, 1)
        cmd = parts[0][1:].lower()  # strip leading '/'
        args = parts[1] if len(parts) > 1 else ""
        return (cmd, args)

    def _handle_slash_command(self, cmd: str, args: str) -> bool:
        if cmd == "/quit":
            console.print("[dim]Goodbye![/dim]")
            return False
        elif cmd == "/help":
            console.print(Panel(HELP_TEXT, title="Help", border_style="blue"))
        elif cmd == "/history":
            msgs = self._dispatcher.conversation.get_context_messages()
            if not msgs:
                console.print("[dim]No conversation history.[/dim]")
            else:
                for msg in msgs:
                    role = msg.role.value
                    console.print(f"[dim]{role}:[/dim] {msg.content[:100]}")
        elif cmd == "/save":
            path = self._context.output_dir / self._context.settings.session_file
            self._dispatcher.conversation.save(path)
            console.print(f"[green]Session saved to {path}[/green]")
        elif cmd == "/context":
            from ai_code2doc.agent.models import ToolCall
            from ai_code2doc.agent.tools.list_context import execute as lc_exec
            tc = ToolCall(id="repl", name="list_context", arguments={})
            result = lc_exec(tc, self._context)
            console.print(Panel(result.content, title="Context", border_style="cyan"))
        elif cmd == "/clear":
            self._dispatcher.conversation.clear()
            console.print("[green]Conversation history cleared.[/green]")
        else:
            console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
        return True

    def run(self) -> None:
        console.print(self._build_welcome())

        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import InMemoryHistory
            session = PromptSession(history=InMemoryHistory())
        except ImportError:
            console.print("[yellow]prompt_toolkit not installed. Using basic input mode.[/yellow]\n")
            self._run_basic_input()
            return

        while True:
            try:
                user_input = session.prompt("> ")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye![/dim]")
                break

            if not user_input.strip():
                continue

            parsed = self._parse_slash_command(user_input)
            if parsed:
                if not self._handle_slash_command(parsed[0], parsed[1]):
                    break
                continue

            try:
                with console.status("[bold green]Thinking...[/bold green]"):
                    response = asyncio.get_event_loop().run_until_complete(
                        self._dispatcher.process(user_input)
                    )
                console.print(Markdown(response))
                console.print()
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted. Type /quit to exit.[/yellow]")
            except Exception as exc:
                console.print(f"[red]Error:[/red] {exc}")

        if self._context.settings.repl_save_session:
            path = self._context.output_dir / self._context.settings.session_file
            try:
                self._dispatcher.conversation.save(path)
                console.print(f"[dim]Session saved to {path}[/dim]")
            except Exception:
                pass

    def _run_basic_input(self) -> None:
        while True:
            try:
                user_input = input("> ")
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break

            if not user_input.strip():
                continue

            parsed = self._parse_slash_command(user_input)
            if parsed:
                if not self._handle_slash_command(parsed[0], parsed[1]):
                    break
                continue

            try:
                response = asyncio.get_event_loop().run_until_complete(
                    self._dispatcher.process(user_input)
                )
                print(response)
                print()
            except KeyboardInterrupt:
                print("\nInterrupted. Type /quit to exit.")
            except Exception as exc:
                print(f"Error: {exc}")
