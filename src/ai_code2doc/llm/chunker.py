from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chunk:
    index: int
    content: str
    start_line: int
    end_line: int
    token_estimate: int  # rough estimate: chars/4


class Chunker:
    def __init__(self, max_tokens: int = 3000, chars_per_token: float = 4.0):
        self.max_tokens = max_tokens
        self.chars_per_token = chars_per_token
        self.max_chars = int(max_tokens * chars_per_token)

    def chunk_content(self, content: str) -> list[Chunk]:
        """Split content into chunks respecting function/class boundaries."""
        lines = content.split("\n")
        chunks: list[Chunk] = []
        current_lines: list[str] = []
        current_start = 0

        for i, line in enumerate(lines):
            current_lines.append(line)
            current_text = "\n".join(current_lines)

            # Check if we should split here
            if len(current_text) >= self.max_chars:
                # Try to find a good split point (empty line or closing brace)
                split_idx = len(current_lines) - 1
                for j in range(len(current_lines) - 1, max(0, len(current_lines) - 20), -1):
                    stripped = current_lines[j].strip()
                    if stripped == "" or stripped == "}":
                        split_idx = j
                        break

                chunk_lines = current_lines[:split_idx + 1]
                chunk_text = "\n".join(chunk_lines)
                chunks.append(Chunk(
                    index=len(chunks),
                    content=chunk_text,
                    start_line=current_start + 1,
                    end_line=current_start + len(chunk_lines),
                    token_estimate=len(chunk_text) // 4,
                ))

                current_lines = current_lines[split_idx + 1:]
                current_start = current_start + split_idx + 1

        # Remaining lines
        if current_lines:
            chunk_text = "\n".join(current_lines)
            chunks.append(Chunk(
                index=len(chunks),
                content=chunk_text,
                start_line=current_start + 1,
                end_line=current_start + len(current_lines),
                token_estimate=len(chunk_text) // 4,
            ))

        return chunks

    def chunk_file(self, file_path: Path) -> list[Chunk]:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return self.chunk_content(content)
