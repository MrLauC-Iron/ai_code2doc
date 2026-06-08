"""Project metadata models for ai_code2doc."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class TechStack(BaseModel):
    """Technology stack details for a project."""

    model_config = ConfigDict(extra="forbid")

    framework: str = ""
    build_tool: str = ""
    language: str = ""
    dependencies: dict[str, str] = Field(default_factory=dict)
    dev_dependencies: dict[str, str] = Field(default_factory=dict)
    package_manager: str = ""


class ProjectMetadata(BaseModel):
    """High-level metadata describing an analysed project."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    root_path: Path
    tech_stack: TechStack = Field(default_factory=TechStack)
    entry_points: list[str] = Field(default_factory=list)
    architecture_type: str | None = None
    total_files: int = 0
    total_lines: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
