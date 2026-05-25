"""Tests for call-graph-level models: CallSite, SymbolDefinition, and DependencyEdge extensions."""

from __future__ import annotations

from ai_code2doc.models.graph import CallSite, DependencyEdge, SymbolDefinition


class TestCallSite:
    def test_creation(self) -> None:
        site = CallSite(
            caller_fqn="src/main.py::process",
            callee_name="helper",
            callee_fqn="src/utils.py::helper",
            file_path="src/main.py",
            line_number=10,
            call_type="function",
            confidence=0.95,
        )
        assert site.caller_fqn == "src/main.py::process"
        assert site.callee_name == "helper"
        assert site.callee_fqn == "src/utils.py::helper"
        assert site.file_path == "src/main.py"
        assert site.line_number == 10
        assert site.call_type == "function"
        assert site.confidence == 0.95

    def test_defaults(self) -> None:
        site = CallSite(
            caller_fqn="a.py::f",
            callee_name="g",
            file_path="a.py",
            line_number=1,
            call_type="function",
        )
        assert site.callee_fqn is None
        assert site.confidence == 1.0


class TestSymbolDefinition:
    def test_creation(self) -> None:
        sym = SymbolDefinition(
            fqn="src/models.py::User",
            name="User",
            file_path="src/models.py",
            start_line=10,
            end_line=50,
            kind="class",
            is_exported=True,
        )
        assert sym.fqn == "src/models.py::User"
        assert sym.name == "User"
        assert sym.file_path == "src/models.py"
        assert sym.start_line == 10
        assert sym.end_line == 50
        assert sym.kind == "class"
        assert sym.is_exported is True

    def test_defaults(self) -> None:
        sym = SymbolDefinition(
            fqn="a.py::f",
            name="f",
            file_path="a.py",
            start_line=1,
            end_line=5,
            kind="function",
        )
        assert sym.is_exported is False


class TestDependencyEdgeBackwardCompat:
    def test_import_edge_no_extra_fields(self) -> None:
        edge = DependencyEdge(source="a.py", target="b.py", edge_type="import")
        assert edge.source == "a.py"
        assert edge.target == "b.py"
        assert edge.callee_name is None
        assert edge.caller_name is None
        assert edge.confidence == 1.0
        assert edge.line_number is None
        assert edge.weight == 1

    def test_call_edge_with_fields(self) -> None:
        edge = DependencyEdge(
            source="a.py::f",
            target="b.py::g",
            edge_type="call",
            callee_name="g",
            caller_name="f",
            confidence=0.95,
            line_number=10,
        )
        assert edge.edge_type == "call"
        assert edge.callee_name == "g"
        assert edge.caller_name == "f"
        assert edge.confidence == 0.95
        assert edge.line_number == 10

    def test_extra_fields_forbidden(self) -> None:
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DependencyEdge(source="a", target="b", bogus_field="oops")
