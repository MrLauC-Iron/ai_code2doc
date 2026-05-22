"""Shared context for agent tools and dispatcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ai_code2doc.config.settings import Settings
    from ai_code2doc.llm.client import LLMClient
    from ai_code2doc.models.knowledge import KnowledgeDocument


@dataclass
class AnalysisResult:
    """Lightweight summary of the last analysis run."""

    total_files: int = 0
    total_lines: int = 0
    target_files: list[Path] = field(default_factory=list)
    docs_generated: list[KnowledgeDocument] = field(default_factory=list)


class AgentContext:
    """Shared state passed to every agent tool and the dispatcher."""

    def __init__(
        self,
        project_root: Path,
        settings: Settings,
        analysis_result: AnalysisResult | None = None,
    ) -> None:
        self.project_root = project_root
        self.settings = settings
        self.analysis_result = analysis_result
        self._llm_client: LLMClient | None = None

    @property
    def llm_client(self) -> LLMClient:
        if self._llm_client is None:
            from ai_code2doc.llm.client import LLMClient

            self._llm_client = LLMClient(self.settings)
        return self._llm_client

    @property
    def output_dir(self) -> Path:
        return self.project_root / self.settings.output_dir

    @property
    def chroma_dir(self) -> Path:
        return self.output_dir / "chroma"

    def has_vector_store(self) -> bool:
        return self.chroma_dir.exists()

    def build_system_prompt(self) -> str:
        parts = [
            "You are an AI code documentation assistant. You have just analyzed a "
            "project and can help the user explore it further.",
            "",
            f"Project path: {self.project_root}",
            f"LLM model: {self.settings.llm_model}",
        ]
        if self.analysis_result:
            ar = self.analysis_result
            parts.append(f"Total files analyzed: {ar.total_files}")
            parts.append(f"Total lines of code: {ar.total_lines}")
            if ar.target_files:
                file_list = ", ".join(str(f.name) for f in ar.target_files[:20])
                parts.append(f"Key files: {file_list}")
        parts.append("")
        parts.append(
            "Use the available tools to answer questions, update documentation, "
            "analyze dependencies, rescan files, or correct errors. "
            "If the user's request doesn't require a tool, answer directly."
        )
        return "\n".join(parts)