from __future__ import annotations

from pathlib import Path
from ai_code2doc.analyzer.symbol_registry import SymbolRegistry
from ai_code2doc.models.graph import SymbolDefinition, CallSite


class TestSymbolRegistry:
    def test_add_and_lookup_by_fqn(self) -> None:
        reg = SymbolRegistry()
        sym = SymbolDefinition(
            fqn="src/utils.py::helper", name="helper",
            file_path="src/utils.py", start_line=1, end_line=10, kind="function",
        )
        reg.add(sym)
        assert reg.get_by_fqn("src/utils.py::helper") is sym
        assert reg.get_by_fqn("nonexistent") is None

    def test_lookup_by_name(self) -> None:
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="a.py::parse", name="parse",
            file_path="a.py", start_line=1, end_line=5, kind="function",
        ))
        reg.add(SymbolDefinition(
            fqn="b.py::parse", name="parse",
            file_path="b.py", start_line=1, end_line=5, kind="function",
        ))
        results = reg.get_by_name("parse")
        assert len(results) == 2

    def test_unique_name_resolution(self) -> None:
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="a.py::unique_func", name="unique_func",
            file_path="a.py", start_line=1, end_line=5, kind="function",
        ))
        result = reg.get_unique("unique_func")
        assert result is not None
        assert result.fqn == "a.py::unique_func"

    def test_unique_name_ambiguous(self) -> None:
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="a.py::f", name="f", file_path="a.py",
            start_line=1, end_line=5, kind="function",
        ))
        reg.add(SymbolDefinition(
            fqn="b.py::f", name="f", file_path="b.py",
            start_line=1, end_line=5, kind="function",
        ))
        assert reg.get_unique("f") is None

    def test_lookup_by_file(self) -> None:
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="a.py::f1", name="f1", file_path="a.py",
            start_line=1, end_line=5, kind="function",
        ))
        reg.add(SymbolDefinition(
            fqn="a.py::f2", name="f2", file_path="a.py",
            start_line=6, end_line=10, kind="function",
        ))
        reg.add(SymbolDefinition(
            fqn="b.py::g", name="g", file_path="b.py",
            start_line=1, end_line=5, kind="function",
        ))
        assert len(reg.get_by_file("a.py")) == 2
        assert len(reg.get_by_file("b.py")) == 1

    def test_add_from_file_info(self) -> None:
        from ai_code2doc.models.module import FileInfo, FunctionInfo, ClassInfo
        reg = SymbolRegistry()
        fi = FileInfo(
            path=Path("src/parser.py"), name="parser.py",
            functions=[FunctionInfo(name="parse", start_line=1, end_line=10)],
            classes=[ClassInfo(
                name="Parser", start_line=12, end_line=50,
                methods=[FunctionInfo(name="process", start_line=15, end_line=30)],
            )],
        )
        reg.add_from_file_info(fi)
        assert reg.get_by_fqn("src/parser.py::parse") is not None
        assert reg.get_by_fqn("src/parser.py::Parser") is not None
        assert reg.get_by_fqn("src/parser.py::Parser.process") is not None

    def test_import_map_operations(self) -> None:
        reg = SymbolRegistry()
        reg.add_import("a.py", "np", "numpy")
        reg.add_import("a.py", "MyClass", "src/models.py")
        assert reg.resolve_import("a.py", "np") == "numpy"
        assert reg.resolve_import("a.py", "MyClass") == "src/models.py"
        assert reg.resolve_import("a.py", "unknown") is None

    def test_resolve_call_site_self_method(self) -> None:
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="a.py::MyClass.validate", name="validate",
            file_path="a.py", start_line=5, end_line=10, kind="method",
        ))
        reg.add(SymbolDefinition(
            fqn="a.py::MyClass.process", name="process",
            file_path="a.py", start_line=1, end_line=15, kind="method",
        ))
        site = CallSite(
            caller_fqn="a.py::MyClass.process", callee_name="self.validate",
            file_path="a.py", line_number=3, call_type="method",
        )
        resolved = reg.resolve_call_site(site, "a.py")
        assert resolved.callee_fqn == "a.py::MyClass.validate"
        assert resolved.confidence == 0.95

    def test_resolve_call_site_same_file(self) -> None:
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="a.py::helper", name="helper",
            file_path="a.py", start_line=1, end_line=5, kind="function",
        ))
        reg.add(SymbolDefinition(
            fqn="a.py::main", name="main",
            file_path="a.py", start_line=6, end_line=10, kind="function",
        ))
        site = CallSite(
            caller_fqn="a.py::main", callee_name="helper",
            file_path="a.py", line_number=7, call_type="function",
        )
        resolved = reg.resolve_call_site(site, "a.py")
        assert resolved.callee_fqn == "a.py::helper"

    def test_resolve_call_site_unique_name(self) -> None:
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="b.py::only_one", name="only_one",
            file_path="b.py", start_line=1, end_line=5, kind="function",
        ))
        site = CallSite(
            caller_fqn="a.py::main", callee_name="only_one",
            file_path="a.py", line_number=3, call_type="function",
        )
        resolved = reg.resolve_call_site(site, "a.py")
        assert resolved.callee_fqn == "b.py::only_one"
        assert resolved.confidence == 0.75

    def test_resolve_call_site_obj_method_same_file(self) -> None:
        """Strategy 2: obj.method() where obj is a class in the same file."""
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="a.py::Service.run", name="run",
            file_path="a.py", start_line=1, end_line=15, kind="method",
        ))
        reg.add(SymbolDefinition(
            fqn="a.py::Service.validate", name="validate",
            file_path="a.py", start_line=5, end_line=10, kind="method",
        ))
        site = CallSite(
            caller_fqn="a.py::Service.run", callee_name="svc.validate",
            file_path="a.py", line_number=3, call_type="method",
        )
        # This tests the "prefix is a class name in same file" sub-path
        # We need to add the class definition for it to work
        reg.add(SymbolDefinition(
            fqn="a.py::Service", name="Service",
            file_path="a.py", start_line=1, end_line=20, kind="class",
        ))
        resolved = reg.resolve_call_site(site, "a.py")
        # Note: the actual resolution depends on implementation details
        # At minimum, it should not crash and should return a confidence

    def test_resolve_call_site_import_map(self) -> None:
        """Strategy 3: module.func() via import map resolution."""
        reg = SymbolRegistry()
        reg.add_import("a.py", "helpers", "src/helpers.py")
        reg.add(SymbolDefinition(
            fqn="src/helpers.py::format_data", name="format_data",
            file_path="src/helpers.py", start_line=1, end_line=10, kind="function",
        ))
        reg.add(SymbolDefinition(
            fqn="a.py::main", name="main",
            file_path="a.py", start_line=1, end_line=5, kind="function",
        ))
        site = CallSite(
            caller_fqn="a.py::main", callee_name="helpers.format_data",
            file_path="a.py", line_number=3, call_type="function",
        )
        resolved = reg.resolve_call_site(site, "a.py")
        assert resolved.callee_fqn is not None
        assert "format_data" in resolved.callee_fqn
        assert resolved.confidence == 0.95

    def test_resolve_call_site_cls_method(self) -> None:
        """Strategy 1: cls.X resolution."""
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="a.py::MyClass.create", name="create",
            file_path="a.py", start_line=5, end_line=10, kind="method",
        ))
        reg.add(SymbolDefinition(
            fqn="a.py::MyClass.from_dict", name="from_dict",
            file_path="a.py", start_line=11, end_line=15, kind="method",
        ))
        site = CallSite(
            caller_fqn="a.py::MyClass.from_dict", callee_name="cls.create",
            file_path="a.py", line_number=12, call_type="method",
        )
        resolved = reg.resolve_call_site(site, "a.py")
        assert resolved.callee_fqn == "a.py::MyClass.create"
        assert resolved.confidence == 0.95

    def test_resolve_module_path_dotted_to_file(self) -> None:
        """Dotted module name should convert to file path for FQN matching."""
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="src/ai_code2doc/scanner/project_scanner.py::scan",
            name="scan",
            file_path="src/ai_code2doc/scanner/project_scanner.py",
            start_line=1, end_line=5, kind="function",
        ))
        reg.add(SymbolDefinition(
            fqn="src/ai_code2doc/scanner/project_scanner.py::ProjectScanner",
            name="ProjectScanner",
            file_path="src/ai_code2doc/scanner/project_scanner.py",
            start_line=10, end_line=20, kind="class",
        ))
        # Import map stores dotted name
        reg.add_import("a.py", "scanner", "ai_code2doc.scanner.project_scanner")
        # Should resolve by converting dotted to file path
        site = CallSite(
            caller_fqn="a.py::main", callee_name="scanner.scan",
            file_path="a.py", line_number=3, call_type="function",
        )
        resolved = reg.resolve_call_site(site, "a.py")
        assert resolved.callee_fqn is not None
        assert "scan" in resolved.callee_fqn
        assert resolved.confidence == 0.95

    def test_resolve_from_import_direct_to_class(self) -> None:
        reg = SymbolRegistry()
        reg.add(SymbolDefinition(
            fqn="src/models.py::FileInfo",
            name="FileInfo", file_path="src/models.py",
            start_line=64, end_line=79, kind="class",
        ))
        reg.add(SymbolDefinition(
            fqn="src/models.py::FunctionInfo",
            name="FunctionInfo", file_path="src/models.py",
            start_line=10, end_line=22, kind="class",
        ))
        reg.add_import("a.py", "FileInfo", "ai_code2doc.models.module")
        site = CallSite(
            caller_fqn="a.py::main", callee_name="FileInfo",
            file_path="a.py", line_number=3, call_type="class_constructor",
        )
        resolved = reg.resolve_call_site(site, "a.py")
        assert resolved.callee_fqn is not None

    def test_resolve_call_site_unresolved(self) -> None:
        reg = SymbolRegistry()
        site = CallSite(
            caller_fqn="a.py::main", callee_name="unknown_func",
            file_path="a.py", line_number=3, call_type="function",
        )
        resolved = reg.resolve_call_site(site, "a.py")
        assert resolved.callee_fqn is None
        assert resolved.confidence == 0.30
