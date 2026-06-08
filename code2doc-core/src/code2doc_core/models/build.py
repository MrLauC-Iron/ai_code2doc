"""Build-system models for ai_code2doc.

Provides data models for representing CMake build configuration
extracted from CMakeLists.txt files.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CMakeTarget(BaseModel):
    """A CMake build target (executable or library).

    Attributes
    ----------
    name:
        Target name, e.g. ``"my_app"``.
    target_type:
        One of ``"executable"``, ``"static_library"``, ``"shared_library"``,
        ``"module_library"``, ``"object_library"``, ``"interface_library"``.
    sources:
        Source file paths relative to the CMakeLists.txt that defines the target.
    include_dirs:
        Include directories (relative to project root) declared via
        ``target_include_directories``.
    link_libraries:
        Library names from ``target_link_libraries``.
    cmake_file:
        Relative path (from project root) of the CMakeLists.txt that
        defines this target.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    target_type: str = "executable"
    sources: list[str] = Field(default_factory=list)
    include_dirs: list[str] = Field(default_factory=list)
    link_libraries: list[str] = Field(default_factory=list)
    cmake_file: str = ""


class CMakeProjectInfo(BaseModel):
    """Aggregated CMake build information for an entire project.

    Extracted by parsing all CMakeLists.txt files found in the project tree.
    """

    model_config = ConfigDict(extra="forbid")

    cmake_version: str = ""
    project_name: str = ""
    project_languages: list[str] = Field(default_factory=list)
    subdirectories: list[str] = Field(default_factory=list)
    find_packages: list[str] = Field(default_factory=list)
    targets: dict[str, CMakeTarget] = Field(default_factory=dict)
