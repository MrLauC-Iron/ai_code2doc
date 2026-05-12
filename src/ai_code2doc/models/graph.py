"""Dependency graph models for ai_code2doc."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DependencyEdge(BaseModel):
    """A directed edge in the project dependency graph."""

    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    weight: int = 1
    edge_type: str = "import"


class CallChain(BaseModel):
    """A call chain between two nodes in the dependency graph."""

    model_config = ConfigDict(extra="forbid")

    start: str
    end: str
    path: list[str] = Field(default_factory=list)
    description: str = ""


class ImpactHint(BaseModel):
    """Hint about the blast-radius of a change to a given target."""

    model_config = ConfigDict(extra="forbid")

    change_target: str
    affected_modules: list[str] = Field(default_factory=list)
    risk_level: str = "medium"


class CycleInfo(BaseModel):
    """Information about a dependency cycle detected in the graph."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[str] = Field(default_factory=list)
    description: str = ""
