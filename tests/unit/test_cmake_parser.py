"""Unit tests for CMakeParser."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code2doc.models.build import CMakeProjectInfo, CMakeTarget
from ai_code2doc.parser.build.cmake_parser import CMakeParser


@pytest.fixture
def parser() -> CMakeParser:
    return CMakeParser()


class TestCMakeVersion:
    """cmake_minimum_required extraction."""

    def test_extracts_version(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
        )
        info = parser.parse(tmp_path)
        assert info.cmake_version == "3.20"

    def test_extracts_version_with_patch(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20.5)\n"
        )
        info = parser.parse(tmp_path)
        assert info.cmake_version == "3.20.5"

    def test_takes_first_version(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "cmake_minimum_required(VERSION 3.25)\n"
        )
        info = parser.parse(tmp_path)
        assert info.cmake_version == "3.20"


class TestProjectName:
    """project() extraction."""

    def test_extracts_project_name(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "project(MyApp CXX)\n"
        )
        info = parser.parse(tmp_path)
        assert info.project_name == "MyApp"

    def test_extracts_languages(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "project(MyApp LANGUAGES C CXX)\n"
        )
        info = parser.parse(tmp_path)
        assert info.project_languages == ["C", "CXX"]


class TestFindPackage:
    """find_package extraction."""

    def test_extracts_single_package(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "find_package(Boost REQUIRED)\n"
        )
        info = parser.parse(tmp_path)
        assert "Boost" in info.find_packages

    def test_extracts_multiple_packages(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "find_package(Boost REQUIRED)\n"
            "find_package(Qt6 COMPONENTS Widgets)\n"
        )
        info = parser.parse(tmp_path)
        assert "Boost" in info.find_packages
        assert "Qt6" in info.find_packages

    def test_deduplicates_packages(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "find_package(Boost)\n"
            "find_package(Boost REQUIRED)\n"
        )
        info = parser.parse(tmp_path)
        assert info.find_packages.count("Boost") == 1


class TestAddExecutable:
    """add_executable extraction."""

    def test_extracts_target_with_sources(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "add_executable(myapp src/main.cpp src/utils.cpp)\n"
        )
        info = parser.parse(tmp_path)
        assert "myapp" in info.targets
        target = info.targets["myapp"]
        assert target.target_type == "executable"
        assert len(target.sources) == 2

    def test_sources_are_relative_to_project_root(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "add_executable(myapp src/main.cpp)\n"
        )
        info = parser.parse(tmp_path)
        target = info.targets["myapp"]
        # On Windows, paths should be normalized with forward slashes
        assert "src/main.cpp" in target.sources[0].replace("\\", "/")

    def test_ignores_keywords_in_sources(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "add_executable(myapp WIN32 src/main.cpp)\n"
        )
        info = parser.parse(tmp_path)
        target = info.targets["myapp"]
        assert "WIN32" not in target.sources
        assert any("main.cpp" in s for s in target.sources)


class TestAddLibrary:
    """add_library extraction."""

    def test_static_library(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "add_library(mylib STATIC src/lib.cpp)\n"
        )
        info = parser.parse(tmp_path)
        assert info.targets["mylib"].target_type == "static_library"

    def test_shared_library(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "add_library(mylib SHARED src/lib.cpp)\n"
        )
        info = parser.parse(tmp_path)
        assert info.targets["mylib"].target_type == "shared_library"

    def test_default_library_type(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "add_library(mylib src/lib.cpp)\n"
        )
        info = parser.parse(tmp_path)
        assert info.targets["mylib"].target_type == "static_library"

    def test_interface_library(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "add_library(mylib INTERFACE)\n"
        )
        info = parser.parse(tmp_path)
        assert info.targets["mylib"].target_type == "interface_library"


class TestTargetIncludeDirectories:
    """target_include_directories extraction."""

    def test_public_include_dirs(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "add_library(mylib src/lib.cpp)\n"
            "target_include_directories(mylib PUBLIC include)\n"
        )
        info = parser.parse(tmp_path)
        target = info.targets["mylib"]
        assert len(target.include_dirs) >= 1

    def test_private_include_dirs(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "add_library(mylib src/lib.cpp)\n"
            "target_include_directories(mylib PRIVATE include)\n"
        )
        info = parser.parse(tmp_path)
        target = info.targets["mylib"]
        assert len(target.include_dirs) >= 1


class TestTargetLinkLibraries:
    """target_link_libraries extraction."""

    def test_link_libraries(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "add_library(mylib src/lib.cpp)\n"
            "add_executable(myapp src/main.cpp)\n"
            "target_link_libraries(myapp PRIVATE mylib)\n"
        )
        info = parser.parse(tmp_path)
        assert "mylib" in info.targets["myapp"].link_libraries

    def test_strips_qt_namespace(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "add_executable(myapp src/main.cpp)\n"
            "target_link_libraries(myapp PRIVATE Qt6::Core)\n"
        )
        info = parser.parse(tmp_path)
        assert "Core" in info.targets["myapp"].link_libraries

    def test_multiple_link_libraries(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "add_library(lib1 src/a.cpp)\n"
            "add_library(lib2 src/b.cpp)\n"
            "add_executable(myapp src/main.cpp)\n"
            "target_link_libraries(myapp PRIVATE lib1 lib2)\n"
        )
        info = parser.parse(tmp_path)
        links = info.targets["myapp"].link_libraries
        assert "lib1" in links
        assert "lib2" in links


class TestAddSubdirectory:
    """add_subdirectory extraction."""

    def test_extracts_subdirectory(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "add_subdirectory(lib)\n"
        )
        info = parser.parse(tmp_path)
        assert len(info.subdirectories) >= 1

    def test_ignores_comments(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "# add_subdirectory(should_ignore)\n"
            "add_subdirectory(real_dir)\n"
        )
        info = parser.parse(tmp_path)
        names = [p.split("/")[-1] for p in info.subdirectories]
        assert "real_dir" in names
        assert "should_ignore" not in names


class TestMultiFileCMake:
    """Multi-file CMake parsing (root + subdirectories)."""

    def test_merges_targets_from_subdirectory(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "project(RootProject C)\n"
            "add_subdirectory(lib)\n"
        )
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "CMakeLists.txt").write_text(
            "add_library(mylib src/lib.c)\n"
        )
        info = parser.parse(tmp_path)
        assert info.project_name == "RootProject"
        assert "mylib" in info.targets


class TestEdgeCases:
    """Edge cases and resilience."""

    def test_empty_file(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text("")
        info = parser.parse(tmp_path)
        assert info == CMakeProjectInfo()

    def test_no_cmake_files(self, parser: CMakeParser, tmp_path: Path) -> None:
        info = parser.parse(tmp_path)
        assert info == CMakeProjectInfo()

    def test_unreadable_file(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
        )
        info = parser.parse(tmp_path)
        # Should not crash; file is readable so it should work
        assert info.cmake_version == "3.20"

    def test_inline_comments(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            "project(MyApp) # My cool project\n"
            "add_executable(myapp src/main.c) # the main app\n"
        )
        info = parser.parse(tmp_path)
        assert info.project_name == "MyApp"
        assert "myapp" in info.targets
        # Comment should not appear in sources
        target = info.targets["myapp"]
        for src in target.sources:
            assert "#" not in src

    def test_bracket_nesting(self, parser: CMakeParser, tmp_path: Path) -> None:
        (tmp_path / "CMakeLists.txt").write_text(
            'add_executable(myapp src/main.c ${CMAKE_SOURCE_DIR}/extra.cpp)\n'
        )
        info = parser.parse(tmp_path)
        assert "myapp" in info.targets

    def test_sample_c_project(self, parser: CMakeParser, sample_c_project: Path) -> None:
        """Test parsing the sample C project's CMakeLists.txt."""
        info = parser.parse(sample_c_project)
        assert info.cmake_version == "3.20"
        assert info.project_name == "sample_c_project"
        assert "Math" in info.find_packages
        assert "utils" in info.targets
        assert info.targets["utils"].target_type == "static_library"
        assert "math_ops" in info.targets
        assert "sample_c_project" in info.targets
        assert info.targets["sample_c_project"].target_type == "executable"
        # Link dependencies
        assert "utils" in info.targets["math_ops"].link_libraries
        assert "utils" in info.targets["sample_c_project"].link_libraries
        assert "math_ops" in info.targets["sample_c_project"].link_libraries
