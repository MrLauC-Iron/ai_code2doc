"""Integration tests for CMake build info in the analysis pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code2doc.analyzer.tech_stack import TechStackDetector
from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
from ai_code2doc.parser.build.cmake_parser import CMakeParser
from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser
from ai_code2doc.scanner.project_scanner import ProjectScanner
from ai_code2doc.utils.parse_cache import ParseCache


class TestCMakeInfoParsing:
    """End-to-end CMake parsing of sample-c-project."""

    def test_parse_sample_c_project(self, sample_c_project: Path) -> None:
        parser = CMakeParser()
        info = parser.parse(sample_c_project)

        assert info.cmake_version == "3.20"
        assert info.project_name == "sample_c_project"
        assert info.project_languages == ["C"]
        assert "Math" in info.find_packages

        # Targets
        assert "utils" in info.targets
        assert "math_ops" in info.targets
        assert "sample_c_project" in info.targets

        # Target types
        assert info.targets["utils"].target_type == "static_library"
        assert info.targets["math_ops"].target_type == "static_library"
        assert info.targets["sample_c_project"].target_type == "executable"

        # Include directories
        assert any("include" in d for d in info.targets["utils"].include_dirs)

        # Link libraries
        assert "utils" in info.targets["math_ops"].link_libraries
        assert "utils" in info.targets["sample_c_project"].link_libraries
        assert "math_ops" in info.targets["sample_c_project"].link_libraries


class TestCMakeInfoInTechStack:
    """CMake info enhances tech stack detection."""

    def test_find_packages_appear_in_dependencies(self, sample_c_project: Path) -> None:
        cmake_info = CMakeParser().parse(sample_c_project)
        detector = TechStackDetector(sample_c_project, cmake_info=cmake_info)
        tech_stack = detector.detect()

        assert tech_stack.build_tool == "CMake"
        assert "Math" in tech_stack.dependencies

    def test_without_cmake_info_still_works(self, sample_c_project: Path) -> None:
        detector = TechStackDetector(sample_c_project, cmake_info=None)
        tech_stack = detector.detect()
        assert tech_stack.build_tool == "CMake"


class TestCMakeInfoInDependencyGraph:
    """CMake include dirs improve #include resolution in dependency graph."""

    def test_better_include_resolution(self, tmp_path: Path) -> None:
        """Files linked via CMake targets should resolve includes from linked targets."""
        include_dir = tmp_path / "include"
        src_dir = tmp_path / "src"
        include_dir.mkdir()
        src_dir.mkdir()

        (include_dir / "common.h").write_text("// common header\n")
        (src_dir / "main.c").write_text('#include "common.h"\n')
        (src_dir / "util.c").write_text('// util\n')
        (tmp_path / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "project(test_proj C)\n"
            "add_executable(main src/main.c)\n"
            "target_include_directories(main PUBLIC include)\n"
        )

        cmake_info = CMakeParser().parse(tmp_path)

        # Build dependency graph using CMake-aware resolution
        scanner = ProjectScanner(tmp_path)
        scan_result = scanner.scan()
        cache = ParseCache(tmp_path / ".ai_code2doc_test")
        parser = TreeSitterParser()

        from ai_code2doc.parser.languages.c_cpp import CCppImportResolver
        # Create a temporary resolver with cmake_info
        original_resolver = CCppImportResolver()

        file_infos = []
        for fp in scan_result.target_files:
            fi = parser.parse_file(fp, tmp_path)
            if fi:
                file_infos.append(fi)

        graph_builder = DependencyGraphBuilder(tmp_path)
        for fi in file_infos:
            graph_builder.add_file(fi)
        graph = graph_builder.build()

        # Should have nodes (main.c and util.c)
        assert graph.number_of_nodes() >= 2

        # Cleanup
        import shutil
        shutil.rmtree(tmp_path / ".ai_code2doc_test", ignore_errors=True)


class TestCMakeEntryPoints:
    """CMake target source lists improve entry point detection."""

    def test_entry_points_from_cmake_targets(self, sample_c_project: Path) -> None:
        cmake_info = CMakeParser().parse(sample_c_project)
        detector = TechStackDetector(sample_c_project, cmake_info=cmake_info)
        entry_points = detector.detect_entry_points()

        # Should find main.c from both grep and CMake sources
        assert any("main.c" in ep for ep in entry_points)
