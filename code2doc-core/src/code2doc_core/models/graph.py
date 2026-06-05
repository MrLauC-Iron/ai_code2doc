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
    callee_name: str | None = None
    caller_name: str | None = None
    confidence: float = 1.0
    line_number: int | None = None


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


class CallSite(BaseModel):
    """A single function/method call extracted from source code."""

    model_config = ConfigDict(extra="forbid")

    caller_fqn: str
    callee_name: str
    callee_fqn: str | None = None
    file_path: str
    line_number: int
    call_type: str  # "function", "method", "static_method", "class_constructor", "super_call"
    confidence: float = 1.0


class SymbolDefinition(BaseModel):
    """A function or class definition that can be the target of calls."""

    model_config = ConfigDict(extra="forbid")

    fqn: str
    name: str
    file_path: str
    start_line: int
    end_line: int
    kind: str  # "function", "method", "class"
    is_exported: bool = False
