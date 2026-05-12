from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ai_code2doc.models.knowledge import KnowledgeDocument


class BaseGenerator(ABC):
    @abstractmethod
    async def generate(
        self,
        project_root: Path,
        output_dir: Path,
        use_llm: bool = True,
        changed_files: list[Path] | None = None,
    ) -> list[KnowledgeDocument]:
        """Generate knowledge documents for this layer.

        Parameters
        ----------
        changed_files:
            Files that have changed since the last analysis.  When ``None``
            a full analysis is performed.  When an empty list the layer may
            skip generation entirely.
        """
        ...

    @property
    @abstractmethod
    def layer_number(self) -> int: ...

    @property
    @abstractmethod
    def layer_name(self) -> str: ...
