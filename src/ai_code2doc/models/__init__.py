"""Pydantic v2 data models for ai_code2doc."""

from __future__ import annotations

from ai_code2doc.models.analysis_state import AnalysisState, FileState
from ai_code2doc.models.graph import CallChain, CycleInfo, DependencyEdge, ImpactHint
from ai_code2doc.models.knowledge import KnowledgeDocument
from ai_code2doc.models.module import (
    ClassInfo,
    FileInfo,
    FunctionInfo,
    ImportInfo,
    InterfaceInfo,
    ModuleSummary,
)
from ai_code2doc.models.project import ProjectMetadata, TechStack

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
    "ImpactHint",
    "CycleInfo",
    # knowledge
    "KnowledgeDocument",
    # analysis_state
    "FileState",
    "AnalysisState",
]
