"""Unified knowledge document model for ai_code2doc."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeDocument(BaseModel):
    """A single document in the layered knowledge base.

    Each document corresponds to one piece of extracted knowledge at a given
    abstraction layer (e.g. file-level, module-level, project-level).
    """

    model_config = ConfigDict(extra="allow")

    id: str
    layer: int
    source_path: str
    title: str
    content: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)
