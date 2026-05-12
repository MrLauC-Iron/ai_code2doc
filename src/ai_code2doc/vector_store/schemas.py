from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """A chunk of documentation to be embedded."""

    id: str
    content: str
    metadata: dict = Field(default_factory=dict)


class SearchResult(BaseModel):
    """Result from a vector search."""

    id: str
    content: str
    score: float
    metadata: dict = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Response from a search query."""

    query: str
    results: list[SearchResult] = Field(default_factory=list)
    total: int = 0
