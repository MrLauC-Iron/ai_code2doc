"""Abstract parser interface for ai_code2doc."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ai_code2doc.models.module import FileInfo


class BaseParser(ABC):
    """Base class that every language parser must implement."""

    @abstractmethod
    def parse_file(self, file_path: Path, project_root: Path) -> FileInfo:
        """Parse a single source file and return its structural metadata.

        Parameters
        ----------
        file_path:
            Absolute path to the file to parse.
        project_root:
            Absolute path to the project root (used to compute relative paths).

        Returns
        -------
        FileInfo
            Populated structural information about *file_path*.
        """
        ...

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return the list of file extensions this parser can handle.

        Returns
        -------
        list[str]
            Extensions **including** the leading dot, e.g. ``[".py", ".c"]``.
        """
        ...
