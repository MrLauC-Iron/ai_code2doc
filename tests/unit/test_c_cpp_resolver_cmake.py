"""Unit tests for CCppImportResolver with CMake include directories."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code2doc.models.build import CMakeProjectInfo, CMakeTarget
from ai_code2doc.parser.languages.c_cpp import CCppImportResolver


class TestResolverWithCMakeInfo:
    """Test that CMake include directories improve include resolution."""

    def test_resolves_via_target_include_directories(self, tmp_path: Path) -> None:
        """#include "utils.h" resolves via target_include_directories."""
        # Project structure:
        #   src/main.c   -> #include "utils.h"
        #   include/utils.h
        #   CMakeLists.txt -> target_include_directories(main PUBLIC include)
        src_dir = tmp_path / "src"
        include_dir = tmp_path / "include"
        src_dir.mkdir()
        include_dir.mkdir()

        (src_dir / "main.c").write_text(
            '#include "utils.h"\n'
        )
        (include_dir / "utils.h").write_text("// header\n")
        (tmp_path / "CMakeLists.txt").write_text("")

        cmake_info = CMakeProjectInfo(
            targets={
                "main": CMakeTarget(
                    name="main",
                    target_type="executable",
                    sources=["src/main.c"],
                    include_dirs=["include"],
                ),
            },
        )

        resolver = CCppImportResolver(cmake_info=cmake_info)
        result = resolver.resolve(
            import_source="utils.h",
            from_file=tmp_path / "src" / "main.c",
            project_root=tmp_path,
        )
        assert result is not None
        assert result == Path("include/utils.h")

    def test_backward_compat_without_cmake_info(self, tmp_path: Path) -> None:
        """Without cmake_info, resolver falls back to default behavior."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        (src_dir / "main.c").write_text(
            '#include "local.h"\n'
        )
        (src_dir / "local.h").write_text("// local header\n")

        resolver = CCppImportResolver(cmake_info=None)
        result = resolver.resolve(
            import_source="local.h",
            from_file=tmp_path / "src" / "main.c",
            project_root=tmp_path,
        )
        assert result is not None
        assert result == Path("src/local.h")

    def test_unresolved_includes_return_none(self, tmp_path: Path) -> None:
        """Unresolvable includes return None."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.c").write_text("// empty\n")

        resolver = CCppImportResolver(cmake_info=None)
        result = resolver.resolve(
            import_source="nonexistent.h",
            from_file=tmp_path / "src" / "main.c",
            project_root=tmp_path,
        )
        assert result is None

    def test_resolves_via_transitive_include_dirs(self, tmp_path: Path) -> None:
        """Include dirs from linked targets are also searched."""
        # lib has include dir "include", app links lib -> app can find headers in include/
        include_dir = tmp_path / "include"
        include_dir.mkdir()
        (include_dir / "lib_header.h").write_text("// lib header\n")

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "app.c").write_text('include "lib_header.h"\n')

        cmake_info = CMakeProjectInfo(
            targets={
                "lib": CMakeTarget(
                    name="lib",
                    target_type="static_library",
                    sources=["src/lib.c"],
                    include_dirs=["include"],
                ),
                "app": CMakeTarget(
                    name="app",
                    target_type="executable",
                    sources=["src/app.c"],
                    link_libraries=["lib"],
                ),
            },
        )

        resolver = CCppImportResolver(cmake_info=cmake_info)
        result = resolver.resolve(
            import_source="lib_header.h",
            from_file=tmp_path / "src" / "app.c",
            project_root=tmp_path,
        )
        assert result is not None

    def test_sample_c_project_include_resolution(self, sample_c_project: Path) -> None:
        """Test include resolution on the sample C project with CMake info."""
        from ai_code2doc.parser.build.cmake_parser import CMakeParser

        cmake_info = CMakeParser().parse(sample_c_project)
        resolver = CCppImportResolver(cmake_info=cmake_info)

        # main.c includes "utils.h" which is in include/
        result = resolver.resolve(
            import_source="utils.h",
            from_file=sample_c_project / "src" / "main.c",
            project_root=sample_c_project,
        )
        assert result is not None
        assert "utils.h" in str(result)
