"""FastMCP server for Layer 2 module documentation management."""

from __future__ import annotations

import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from code2doc_layer2_mcp.config import Layer2Settings
from code2doc_layer2_mcp.module_store import ModuleStore

logger = logging.getLogger(__name__)

# Module-level state set by create_server()
_store: ModuleStore | None = None
_settings: Layer2Settings | None = None


def create_server(
    modules_dir: Path,
    settings: Layer2Settings | None = None,
) -> FastMCP:
    """Create and configure a FastMCP instance for Layer 2.

    Args:
        modules_dir: Directory where module markdown files are stored.
        settings: Optional pre-configured settings (created from env if None).
    """
    global _store, _settings

    _settings = settings or Layer2Settings()
    _store = ModuleStore(modules_dir)

    llm_client = None
    if _settings.llm_api_key:
        from code2doc_layer2_mcp.llm_client import Layer2LLMClient
        llm_client = Layer2LLMClient(_settings)

    mcp = FastMCP(
        "code2doc-layer2-mcp",
        instructions=(
            "Manage module documentation for a codebase. "
            "Use list_modules to see all modules, get_module to read docs, "
            "search_modules to find modules by keyword, "
            "update_modules to regenerate docs after code changes via LLM."
        ),
    )

    # ------------------------------------------------------------------
    # Read tools
    # ------------------------------------------------------------------

    @mcp.tool()
    async def list_modules() -> str:
        """List all modules with their names."""
        modules = _store.list_modules()
        if not modules:
            return "No modules found."
        lines = [f"Modules ({len(modules)}):"]
        for m in modules:
            preview = m["content"][:80].replace("\n", " ").strip()
            lines.append(f"  - {m['name']}: {preview}...")
        return "\n".join(lines)

    @mcp.tool()
    async def get_module(name: str) -> str:
        """Get documentation content for a specific module."""
        doc = _store.get_module(name)
        if doc is None:
            return f"Module not found: '{name}'. Use list_modules to see available modules."
        return doc["content"]

    @mcp.tool()
    async def search_modules(query: str) -> str:
        """Search modules by name or content keyword."""
        results = _store.search_modules(query)
        if not results:
            return f"No modules matching '{query}'."
        lines = [f"Matches for '{query}' ({len(results)}):"]
        for m in results:
            preview = m["content"][:80].replace("\n", " ").strip()
            lines.append(f"  - {m['name']}: {preview}...")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Write tool
    # ------------------------------------------------------------------

    @mcp.tool()
    async def update_modules(
        modules: str,
        task_description: str,
        code_changes: str = "",
        layer1_overview: str = "",
    ) -> str:
        """Update module documentation after code changes using LLM.

        Args:
            modules: Comma-separated module names to update.
            task_description: What task was performed (e.g. 'Add refresh token rotation').
            code_changes: Description of files changed, e.g. 'Modified src/auth/tokens.py: added refresh logic'.
            layer1_overview: Optional project overview for context.
        """
        if llm_client is None:
            return (
                "Error: LLM not configured. "
                "Set LAYER2_LLM_API_KEY environment variable."
            )

        module_names = [m.strip() for m in modules.split(",") if m.strip()]
        if not module_names:
            return "Error: no module names provided."

        changes_dicts = [
            {"file": line.split(":")[0].strip(), "description": line, "action": "modified"}
            for line in code_changes.strip().split("\n")
            if line.strip()
        ] if code_changes.strip() else []

        updated: list[str] = []
        failed: list[str] = []

        for module_name in module_names:
            try:
                existing = _store.get_module(module_name)
                existing_content = existing["content"] if existing else ""

                new_content = await llm_client.extract_module_knowledge(
                    module_name=module_name,
                    task_description=task_description,
                    layer1_overview=layer1_overview,
                    existing_content=existing_content,
                    code_changes=changes_dicts,
                )

                _store.save_module(module_name, new_content)
                updated.append(module_name)
                logger.info("Updated module: %s", module_name)
            except Exception as exc:
                logger.error("Failed to update module %s: %s", module_name, exc)
                failed.append(module_name)

        lines = []
        if updated:
            lines.append(f"Updated: {', '.join(updated)}")
        if failed:
            lines.append(f"Failed: {', '.join(failed)}")
        return "\n".join(lines) if lines else "No modules to update."

    return mcp
