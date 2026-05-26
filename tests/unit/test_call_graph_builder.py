from __future__ import annotations

from pathlib import Path
from ai_code2doc.analyzer.call_graph_builder import CallGraphBuilder
from ai_code2doc.models.graph import CallSite, SymbolDefinition


class TestCallGraphBuilder:
    def test_build_single_file(self) -> None:
        from ai_code2doc.models.module import FileInfo, FunctionInfo
        builder = CallGraphBuilder(Path("/project"))
        fi = FileInfo(
            path=Path("src/main.py"), name="main.py",
            functions=[FunctionInfo(name="main", start_line=1, end_line=10)],
        )
        # Need to set source_text on the FileInfo for call extraction
        fi.source_text = "def main():\n    helper()\n    parse()\n"
        sites = builder.build_for_files([fi])
        assert len(sites) >= 2

    def test_build_with_resolution(self) -> None:
        from ai_code2doc.models.module import FileInfo, FunctionInfo
        builder = CallGraphBuilder(Path("/project"))

        fi_a = FileInfo(path=Path("a.py"), name="a.py",
                        functions=[FunctionInfo(name="run", start_line=1, end_line=5)])
        fi_a.source_text = "def run():\n    helper()\n"

        fi_b = FileInfo(path=Path("b.py"), name="b.py",
                        functions=[FunctionInfo(name="helper", start_line=1, end_line=10)])
        fi_b.source_text = "def helper():\n    pass\n"

        sites = builder.build_for_files([fi_a, fi_b])
        resolved = [s for s in sites if s.callee_fqn is not None]
        assert len(resolved) >= 1
        helper_sites = [s for s in resolved if s.callee_name == "helper"]
        assert any("b.py" in s.callee_fqn for s in helper_sites)

    def test_build_empty(self) -> None:
        builder = CallGraphBuilder(Path("/project"))
        sites = builder.build_for_files([])
        assert sites == []

    def test_build_with_class_methods(self) -> None:
        from ai_code2doc.models.module import FileInfo, FunctionInfo, ClassInfo
        builder = CallGraphBuilder(Path("/project"))
        fi = FileInfo(
            path=Path("service.py"), name="service.py",
            classes=[ClassInfo(
                name="UserService", start_line=1, end_line=6,
                methods=[
                    FunctionInfo(name="authenticate", start_line=2, end_line=3),
                    FunctionInfo(name="validate", start_line=5, end_line=6),
                ],
            )],
        )
        fi.source_text = (
            "class UserService:\n"
            "    def authenticate(self, token):\n"
            "        self.validate(token)\n"
            "\n"
            "    def validate(self, token):\n"
            "        pass\n"
        )
        sites = builder.build_for_files([fi])
        # Should find self.validate call inside authenticate
        validate_calls = [s for s in sites if "validate" in s.callee_name]
        assert len(validate_calls) >= 1

    def test_ccpp_extraction_dispatch(self, tmp_path: Path) -> None:
        from ai_code2doc.models.module import FileInfo, FunctionInfo
        builder = CallGraphBuilder(tmp_path)
        fi = FileInfo(
            path=tmp_path / "calc.cpp", name="calc.cpp",
            functions=[FunctionInfo(name="add", start_line=1, end_line=4)],
        )
        fi.source_text = (
            "int add(int a, int b) {\n"
            "    int result = compute(a, b);\n"
            "    return result;\n"
            "}\n"
        )
        sites = builder.build_for_files([fi])
        compute_sites = [s for s in sites if s.callee_name == "compute"]
        assert len(compute_sites) >= 1
        # The C++ extractor should NOT confuse the function definition
        # "int add(...)" with a call to "add" (Python extractor does this).
        add_sites = [s for s in sites if s.callee_name == "add"]
        assert len(add_sites) == 0

    def test_build_no_source_text(self) -> None:
        from ai_code2doc.models.module import FileInfo, FunctionInfo
        builder = CallGraphBuilder(Path("/project"))
        fi = FileInfo(
            path=Path("no_source.py"), name="no_source.py",
            functions=[FunctionInfo(name="func", start_line=1, end_line=5)],
        )
        # No source_text set — should gracefully return no sites
        sites = builder.build_for_files([fi])
        assert sites == []
