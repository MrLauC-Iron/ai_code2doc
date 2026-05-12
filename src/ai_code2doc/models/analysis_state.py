"""Incremental analysis state models for ai_code2doc."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FileState(BaseModel):
    """Persisted analysis state for a single file."""

    model_config = ConfigDict(extra="forbid")

    path: str
    hash: str
    last_analyzed: datetime = Field(default_factory=datetime.now)


class AnalysisState(BaseModel):
    """Full incremental-analysis state for a project.

    Tracks per-file hashes and timestamps so that subsequent runs can skip
    unchanged files and only re-process what has been modified.
    """

    model_config = ConfigDict(extra="forbid")

    project_root: str
    file_states: dict[str, FileState] = Field(default_factory=dict)
    last_full_analysis: datetime | None = None
    version: int = 1
