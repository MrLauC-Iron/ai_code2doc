"""Abstract base class for language-specific import resolution.

Each language has its own import / include semantics.  Concrete
subclasses resolve an import source string to a file path relative to
the project root (or ``None`` if the import refers to an external /
standard-library dependency).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseImportResolver(ABC):
    """Resolve import source strings to concrete file paths."""

    @abstractmethod
    def resolve(
        self,
        import_source: str,
        from_file: Path,
        project_root: Path,
    ) -> Path | None:
        """Resolve *import_source* to a real file path.

        Parameters
        ----------
        import_source:
            The raw string from the import / include statement.
        from_file:
            Absolute path of the file that contains the import.
        project_root:
            Absolute path of the project root.

        Returns
        -------
        Path | None
            The resolved file path **relative to** *project_root*,
            or ``None`` if the import cannot be resolved.
        """
        ...
