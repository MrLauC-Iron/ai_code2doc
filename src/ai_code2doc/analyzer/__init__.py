"""Analyzer sub-package for ai_code2doc."""

from __future__ import annotations

from ai_code2doc.analyzer.tech_stack import TechStackDetector
from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
from ai_code2doc.analyzer.metrics import FileMetrics, ProjectMetrics, MetricsCalculator
from ai_code2doc.analyzer.call_extractor import PythonCallExtractor

__all__ = [
    "TechStackDetector",
    "DependencyGraphBuilder",
    "FileMetrics",
    "ProjectMetrics",
    "MetricsCalculator",
    "PythonCallExtractor",
]
