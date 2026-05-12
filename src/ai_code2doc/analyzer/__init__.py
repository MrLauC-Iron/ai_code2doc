"""Analyzer sub-package for ai_code2doc."""

from __future__ import annotations

from ai_code2doc.analyzer.tech_stack import TechStackDetector
from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
from ai_code2doc.analyzer.metrics import FileMetrics, ProjectMetrics, MetricsCalculator

__all__ = [
    "TechStackDetector",
    "DependencyGraphBuilder",
    "FileMetrics",
    "ProjectMetrics",
    "MetricsCalculator",
]
