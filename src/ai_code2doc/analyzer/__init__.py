"""Analyzer sub-package for ai_code2doc."""

from __future__ import annotations

from code2doc_core.analyzer.tech_stack import TechStackDetector
from code2doc_core.analyzer.dependency_graph import DependencyGraphBuilder
from code2doc_core.analyzer.metrics import FileMetrics, ProjectMetrics, MetricsCalculator
from code2doc_core.analyzer.call_extractor import PythonCallExtractor
from code2doc_core.analyzer.call_graph_builder import CallGraphBuilder

__all__ = [
    "TechStackDetector",
    "DependencyGraphBuilder",
    "FileMetrics",
    "ProjectMetrics",
    "MetricsCalculator",
    "PythonCallExtractor",
    "CallGraphBuilder",
]
