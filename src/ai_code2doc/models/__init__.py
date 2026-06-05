"""Pydantic v2 data models for ai_code2doc."""

from __future__ import annotations

from code2doc_core.models.analysis_state import AnalysisState, FileState
from code2doc_core.models.graph import (
    CallChain,
    CallSite,
    CycleInfo,
    DependencyEdge,
    ImpactHint,
    SymbolDefinition,
)
from code2doc_core.models.knowledge import KnowledgeDocument
from code2doc_core.models.module import (
    ClassInfo,
    FileInfo,
    FunctionInfo,
    ImportInfo,
    InterfaceInfo,
    ModuleSummary,
)
from code2doc_core.models.project import ProjectMetadata, TechStack

__all__ = [
    # project
    "TechStack",
    "ProjectMetadata",
    # module
    "FunctionInfo",
    "ClassInfo",
    "InterfaceInfo",
    "ImportInfo",
    "FileInfo",
    "ModuleSummary",
    # graph
    "DependencyEdge",
    "CallChain",
    "CallSite",
    "SymbolDefinition",
    "ImpactHint",
    "CycleInfo",
    # knowledge
    "KnowledgeDocument",
    # analysis_state
    "FileState",
    "AnalysisState",
]
