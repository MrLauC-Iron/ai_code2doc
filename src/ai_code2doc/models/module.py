"""Module and file-level models for ai_code2doc."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class FunctionInfo(BaseModel):
    """Metadata about a single function or method."""

    model_config = ConfigDict(extra="forbid")

    name: str
    start_line: int
    end_line: int
    params: list[str] = Field(default_factory=list)
    return_type: str | None = None
    is_exported: bool = False
    is_async: bool = False
    decorators: list[str] = Field(default_factory=list)


class ClassInfo(BaseModel):
    """Metadata about a class declaration."""

    model_config = ConfigDict(extra="forbid")

    name: str
    start_line: int
    end_line: int
    methods: list[FunctionInfo] = Field(default_factory=list)
    properties: list[str] = Field(default_factory=list)
    extends: str | None = None
    implements: list[str] = Field(default_factory=list)
    is_exported: bool = False
    decorators: list[str] = Field(default_factory=list)


class InterfaceInfo(BaseModel):
    """Metadata about a TypeScript-style interface."""

    model_config = ConfigDict(extra="forbid")

    name: str
    start_line: int
    end_line: int
    properties: list[str] = Field(default_factory=list)
    extends: list[str] = Field(default_factory=list)
    is_exported: bool = False


class ImportInfo(BaseModel):
    """Metadata about a single import statement."""

    model_config = ConfigDict(extra="forbid")

    source: str
    specifiers: list[str] = Field(default_factory=list)
    is_type_only: bool = False


class FileInfo(BaseModel):
    """Detailed structural information about a single source file."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    name: str
    size_bytes: int = 0
    line_count: int = 0
    functions: list[FunctionInfo] = Field(default_factory=list)
    classes: list[ClassInfo] = Field(default_factory=list)
    interfaces: list[InterfaceInfo] = Field(default_factory=list)
    imports: list[ImportInfo] = Field(default_factory=list)
    exports: list[str] = Field(default_factory=list)
    file_hash: str = ""


class ModuleSummary(BaseModel):
    """Aggregated summary of a logical module (directory / package)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    path: str
    description: str = ""
    files: list[FileInfo] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    dependents: list[str] = Field(default_factory=list)
    api_endpoints: list[str] = Field(default_factory=list)
    key_business_rules: list[str] = Field(default_factory=list)
    total_lines: int = 0
