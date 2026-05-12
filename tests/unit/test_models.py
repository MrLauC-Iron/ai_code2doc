"""Tests for ai_code2doc data models."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from ai_code2doc.models.module import (
    FunctionInfo,
    ClassInfo,
    InterfaceInfo,
    ImportInfo,
    FileInfo,
    ModuleSummary,
)
from ai_code2doc.models.graph import DependencyEdge, CallChain, ImpactHint, CycleInfo
from ai_code2doc.models.knowledge import KnowledgeDocument
from ai_code2doc.models.analysis_state import AnalysisState, FileState
from ai_code2doc.models.project import TechStack


# ---------------------------------------------------------------------------
# FunctionInfo
# ---------------------------------------------------------------------------

class TestFunctionInfo:
    def test_basic_creation(self) -> None:
        f = FunctionInfo(name="foo", start_line=1, end_line=5, params=["x", "y"])
        assert f.name == "foo"
        assert f.params == ["x", "y"]
        assert f.is_exported is False
        assert f.is_async is False
        assert f.decorators == []
        assert f.return_type is None

    def test_async_function(self) -> None:
        f = FunctionInfo(name="bar", start_line=1, end_line=3, is_async=True)
        assert f.is_async is True

    def test_with_decorators(self) -> None:
        f = FunctionInfo(
            name="f", start_line=1, end_line=2,
            decorators=["@staticmethod", "@property"],
        )
        assert f.decorators == ["@staticmethod", "@property"]

    def test_with_return_type(self) -> None:
        f = FunctionInfo(name="g", start_line=1, end_line=2, return_type="str")
        assert f.return_type == "str"

    def test_exported(self) -> None:
        f = FunctionInfo(name="h", start_line=1, end_line=2, is_exported=True)
        assert f.is_exported is True


# ---------------------------------------------------------------------------
# ClassInfo
# ---------------------------------------------------------------------------

class TestClassInfo:
    def test_basic_creation(self) -> None:
        c = ClassInfo(name="Foo", start_line=1, end_line=10, extends="Bar")
        assert c.name == "Foo"
        assert c.extends == "Bar"
        assert c.methods == []
        assert c.implements == []

    def test_with_methods(self) -> None:
        m = FunctionInfo(name="method", start_line=3, end_line=5)
        c = ClassInfo(name="Cls", start_line=1, end_line=10, methods=[m])
        assert len(c.methods) == 1
        assert c.methods[0].name == "method"

    def test_with_implements(self) -> None:
        c = ClassInfo(name="Impl", start_line=1, end_line=5, implements=["IFoo", "IBar"])
        assert c.implements == ["IFoo", "IBar"]

    def test_with_decorators(self) -> None:
        c = ClassInfo(
            name="D", start_line=1, end_line=5,
            decorators=["@dataclass"],
        )
        assert c.decorators == ["@dataclass"]


# ---------------------------------------------------------------------------
# InterfaceInfo
# ---------------------------------------------------------------------------

class TestInterfaceInfo:
    def test_basic_creation(self) -> None:
        i = InterfaceInfo(name="IFoo", start_line=1, end_line=5, properties=["x"])
        assert i.name == "IFoo"
        assert i.properties == ["x"]
        assert i.is_exported is False

    def test_with_extends(self) -> None:
        i = InterfaceInfo(name="IBar", start_line=1, end_line=3, extends=["IBase"])
        assert i.extends == ["IBase"]


# ---------------------------------------------------------------------------
# ImportInfo
# ---------------------------------------------------------------------------

class TestImportInfo:
    def test_basic_import(self) -> None:
        i = ImportInfo(source="os", specifiers=["path", "sys"])
        assert i.source == "os"
        assert i.specifiers == ["path", "sys"]
        assert i.is_type_only is False

    def test_type_only_import(self) -> None:
        i = ImportInfo(source="typing", is_type_only=True)
        assert i.is_type_only is True

    def test_empty_specifiers(self) -> None:
        i = ImportInfo(source="json")
        assert i.specifiers == []


# ---------------------------------------------------------------------------
# FileInfo
# ---------------------------------------------------------------------------

class TestFileInfo:
    def test_basic_creation(self) -> None:
        fi = FileInfo(path=Path("src/main.py"), name="main.py")
        assert fi.name == "main.py"
        assert fi.functions == []
        assert fi.imports == []
        assert fi.file_hash == ""

    def test_full_creation(self) -> None:
        fn = FunctionInfo(name="foo", start_line=1, end_line=3)
        imp = ImportInfo(source="os")
        fi = FileInfo(
            path=Path("src/app.py"),
            name="app.py",
            size_bytes=1024,
            line_count=50,
            functions=[fn],
            imports=[imp],
            exports=["main"],
            file_hash="abc123",
        )
        assert len(fi.functions) == 1
        assert len(fi.imports) == 1
        assert fi.exports == ["main"]
        assert fi.size_bytes == 1024

    def test_json_roundtrip(self) -> None:
        fi = FileInfo(
            path=Path("src/test.py"),
            name="test.py",
            functions=[FunctionInfo(name="fn", start_line=1, end_line=2)],
        )
        json_str = fi.model_dump_json()
        restored = FileInfo.model_validate_json(json_str)
        assert restored.name == fi.name
        assert restored.functions[0].name == "fn"


# ---------------------------------------------------------------------------
# ModuleSummary
# ---------------------------------------------------------------------------

class TestModuleSummary:
    def test_basic_creation(self) -> None:
        ms = ModuleSummary(name="api", path="src/api")
        assert ms.name == "api"
        assert ms.description == ""
        assert ms.files == []
        assert ms.dependencies == []


# ---------------------------------------------------------------------------
# DependencyEdge / CallChain / ImpactHint / CycleInfo
# ---------------------------------------------------------------------------

class TestDependencyEdge:
    def test_basic_creation(self) -> None:
        e = DependencyEdge(source="a.py", target="b.py")
        assert e.source == "a.py"
        assert e.target == "b.py"
        assert e.weight == 1
        assert e.edge_type == "import"


class TestCallChain:
    def test_basic_creation(self) -> None:
        c = CallChain(start="a.py", end="c.py", path=["a.py", "b.py", "c.py"])
        assert c.path == ["a.py", "b.py", "c.py"]


class TestImpactHint:
    def test_basic_creation(self) -> None:
        ih = ImpactHint(
            change_target="core.py",
            affected_modules=["a.py", "b.py"],
            risk_level="low",
        )
        assert ih.risk_level == "low"
        assert len(ih.affected_modules) == 2


class TestCycleInfo:
    def test_basic_creation(self) -> None:
        ci = CycleInfo(nodes=["a.py", "b.py"], description="a.py -> b.py -> a.py")
        assert len(ci.nodes) == 2
        assert "a.py" in ci.description


# ---------------------------------------------------------------------------
# KnowledgeDocument
# ---------------------------------------------------------------------------

class TestKnowledgeDocument:
    def test_basic_creation(self) -> None:
        kd = KnowledgeDocument(
            id="doc-1",
            layer=1,
            source_path="src/main.py",
            title="Overview",
            content="Some content",
        )
        assert kd.id == "doc-1"
        assert kd.layer == 1
        assert kd.tags == []
        assert kd.metadata == {}

    def test_with_tags_and_metadata(self) -> None:
        kd = KnowledgeDocument(
            id="doc-2",
            layer=2,
            source_path="src/app.py",
            title="Module Summary",
            content="Details",
            tags=["api", "core"],
            metadata={"lines": 100},
        )
        assert kd.tags == ["api", "core"]
        assert kd.metadata["lines"] == 100


# ---------------------------------------------------------------------------
# TechStack
# ---------------------------------------------------------------------------

class TestTechStack:
    def test_basic_creation(self) -> None:
        ts = TechStack(framework="Flask", language="Python")
        assert ts.framework == "Flask"
        assert ts.language == "Python"
        assert ts.dependencies == {}

    def test_defaults(self) -> None:
        ts = TechStack()
        assert ts.framework == ""
        assert ts.build_tool == ""
        assert ts.package_manager == ""


# ---------------------------------------------------------------------------
# AnalysisState / FileState
# ---------------------------------------------------------------------------

class TestAnalysisState:
    def test_basic_creation(self) -> None:
        state = AnalysisState(project_root="/tmp/project")
        assert state.project_root == "/tmp/project"
        assert state.file_states == {}
        assert state.version == 1

    def test_with_file_states(self) -> None:
        fs = FileState(path="main.py", hash="abc123")
        state = AnalysisState(
            project_root="/tmp/project",
            file_states={"main.py": fs},
        )
        assert "main.py" in state.file_states
        assert state.file_states["main.py"].hash == "abc123"

    def test_json_roundtrip(self) -> None:
        fs = FileState(path="a.py", hash="deadbeef")
        state = AnalysisState(
            project_root="/tmp/project",
            file_states={"a.py": fs},
        )
        json_str = state.model_dump_json()
        restored = AnalysisState.model_validate_json(json_str)
        assert restored.project_root == state.project_root
        assert "a.py" in restored.file_states
