"""Module store: CRUD operations on module markdown files."""

from __future__ import annotations

from pathlib import Path


class ModuleStore:
    """Manages module documentation files on disk.

    Modules are stored as ``{modules_dir}/{name}.md``.
    """

    def __init__(self, modules_dir: Path | str) -> None:
        self._modules_dir = Path(modules_dir)
        self._modules_dir.mkdir(parents=True, exist_ok=True)

    def list_modules(self) -> list[dict[str, str]]:
        """Return metadata and content for all modules."""
        modules: list[dict[str, str]] = []
        for f in sorted(self._modules_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            modules.append({
                "name": f.stem,
                "content": content,
            })
        return modules

    def get_module(self, name: str) -> dict[str, str] | None:
        """Return a single module's content, or None if not found."""
        path = self._safe_path(name)
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        return {"name": name, "content": content}

    def search_modules(self, query: str) -> list[dict[str, str]]:
        """Search modules by name or content substring."""
        query_lower = query.lower()
        results: list[dict[str, str]] = []
        for mod in self.list_modules():
            if query_lower in mod["name"].lower() or query_lower in mod["content"].lower():
                results.append(mod)
        return results

    def save_module(self, name: str, content: str) -> None:
        """Write (or overwrite) a module document."""
        path = self._safe_path(name)
        path.write_text(content, encoding="utf-8")

    def delete_module(self, name: str) -> bool:
        """Delete a module document. Returns True if it existed."""
        path = self._safe_path(name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def _safe_path(self, name: str) -> Path:
        """Resolve a module name to a safe filesystem path.

        Rejects path traversal attempts (e.g. '../../etc/passwd').
        """
        safe_name = name.replace("\\", "/").rstrip("/")
        safe_name = safe_name.split("/")[-1]
        if not safe_name or safe_name.startswith("."):
            safe_name = "unnamed"
        return self._modules_dir / f"{safe_name}.md"
