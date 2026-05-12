from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0


class TokenTracker:
    def __init__(self):
        self._usage = TokenUsage()

    def add(self, prompt_tokens: int, completion_tokens: int) -> None:
        self._usage.prompt_tokens += prompt_tokens
        self._usage.completion_tokens += completion_tokens
        self._usage.total_tokens += prompt_tokens + completion_tokens
        self._usage.request_count += 1

    @property
    def usage(self) -> TokenUsage:
        return self._usage

    def report(self) -> str:
        u = self._usage
        return (
            f"Token Usage: {u.total_tokens:,} total "
            f"({u.prompt_tokens:,} prompt + {u.completion_tokens:,} completion) "
            f"across {u.request_count} requests"
        )

    def print_report(self) -> None:
        Console().print(self.report(), style="bold blue")
