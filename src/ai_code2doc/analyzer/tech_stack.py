"""Technology stack detection for ai_code2doc.

Delegates to language-specific detectors registered in the
:class:`~ai_code2doc.parser.language_registry.LanguageRegistry`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ai_code2doc.models.project import TechStack

if TYPE_CHECKING:
    from ai_code2doc.models.build import CMakeProjectInfo


class TechStackDetector:
    """Detects the technology stack of a project by delegating to language adapters."""

    def __init__(
        self,
        project_root: Path,
        cmake_info: CMakeProjectInfo | None = None,
    ) -> None:
        self.root = project_root
        self.cmake_info = cmake_info

    def _detect_languages_in_project(self) -> list[str]:
        """Scan project files to determine which languages are present."""
        from ai_code2doc.parser.language_registry import LanguageRegistry

        seen_lang_ids: set[str] = set()
        ext_set = LanguageRegistry.all_extensions()
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            ext = path.suffix.lower()
            if ext in ext_set:
                adapter = LanguageRegistry.get_by_extension(ext)
                if adapter is not None:
                    seen_lang_ids.add(adapter.language_id)
        return list(seen_lang_ids)

    def detect(self) -> TechStack:
        """Detect tech stack by combining results from all language adapters."""
        # Ensure languages are registered.
        import ai_code2doc.parser.languages  # noqa: F401
        from ai_code2doc.parser.language_registry import LanguageRegistry

        lang_ids = self._detect_languages_in_project()

        if not lang_ids:
            return TechStack()

        # Merge tech stacks from all detected languages.
        merged_deps: dict[str, str] = {}
        merged_dev_deps: dict[str, str] = {}
        frameworks: list[str] = []
        build_tools: list[str] = []
        languages: list[str] = []
        package_managers: list[str] = []

        for lang_id in lang_ids:
            adapter = LanguageRegistry.get_by_id(lang_id)
            if adapter is None:
                continue
            # Pass cmake_info to c_cpp detector if available.
            ts = adapter.detect_tech_stack(self.root, cmake_info=self.cmake_info)
            merged_deps.update(ts.dependencies)
            merged_dev_deps.update(ts.dev_dependencies)
            if ts.framework and ts.framework != "Unknown":
                frameworks.append(ts.framework)
            if ts.build_tool and ts.build_tool != "Unknown":
                build_tools.append(ts.build_tool)
            if ts.language:
                languages.append(ts.language)
            if ts.package_manager:
                package_managers.append(ts.package_manager)

        return TechStack(
            framework=frameworks[0] if frameworks else "Unknown",
            build_tool=build_tools[0] if build_tools else "Unknown",
            language=" / ".join(dict.fromkeys(languages)) if languages else "Unknown",
            dependencies=merged_deps,
            dev_dependencies=merged_dev_deps,
            package_manager=package_managers[0] if package_managers else "Unknown",
        )

    def detect_entry_points(self) -> list[str]:
        """Detect entry points from all language adapters."""
        import ai_code2doc.parser.languages  # noqa: F401
        from ai_code2doc.parser.language_registry import LanguageRegistry

        lang_ids = self._detect_languages_in_project()
        entry_points: list[str] = []

        for lang_id in lang_ids:
            adapter = LanguageRegistry.get_by_id(lang_id)
            if adapter is None:
                continue
            eps = adapter.detect_entry_points(self.root, cmake_info=self.cmake_info)
            entry_points.extend(eps)

        return list(set(entry_points))
