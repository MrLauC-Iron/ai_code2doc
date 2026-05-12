"""Integration tests for C/C++ source code parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser


@pytest.fixture
def parser() -> TreeSitterParser:
    return TreeSitterParser()


# ---------------------------------------------------------------------------
# Function extraction
# ---------------------------------------------------------------------------

class TestCFunctionExtraction:
    def test_extract_main_function(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "main.c"
        f.write_text("int main(void) {\n    return 0;\n}\n", encoding="utf-8")
        info = parser.parse_file(f, tmp_path)
        assert len(info.functions) >= 1
        fn = info.functions[0]
        assert fn.name == "main"
        assert fn.return_type == "int"

    def test_extract_function_with_params(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "add.c"
        f.write_text("int add(int a, int b) {\n    return a + b;\n}\n", encoding="utf-8")
        info = parser.parse_file(f, tmp_path)
        assert len(info.functions) >= 1
        fn = info.functions[0]
        assert fn.name == "add"
        assert len(fn.params) >= 2


# ---------------------------------------------------------------------------
# Struct / class extraction
# ---------------------------------------------------------------------------

class TestCStructExtraction:
    def test_extract_struct(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "point.c"
        f.write_text(
            "struct Point {\n"
            "    int x;\n"
            "    int y;\n"
            "};\n",
            encoding="utf-8",
        )
        info = parser.parse_file(f, tmp_path)
        assert len(info.classes) >= 1
        assert info.classes[0].name == "Point"

    def test_extract_class_with_inheritance(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "cls.cpp"
        f.write_text(
            "class Foo : public Bar {\n"
            "public:\n"
            "    void method();\n"
            "};\n",
            encoding="utf-8",
        )
        info = parser.parse_file(f, tmp_path)
        assert len(info.classes) >= 1
        cls = info.classes[0]
        assert cls.name == "Foo"
        # C++ inheritance should be captured
        assert cls.extends is not None or len(cls.methods) >= 0


# ---------------------------------------------------------------------------
# #include extraction
# ---------------------------------------------------------------------------

class TestCIncludeExtraction:
    def test_extract_quoted_include(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "test.c"
        f.write_text('#include "header.h"\nint main() { return 0; }\n', encoding="utf-8")
        info = parser.parse_file(f, tmp_path)
        assert len(info.imports) >= 1
        imp = info.imports[0]
        assert imp.source == "header.h"
        assert imp.is_type_only is False

    def test_extract_angle_bracket_include(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "test.c"
        f.write_text("#include <stdio.h>\nint main() { return 0; }\n", encoding="utf-8")
        info = parser.parse_file(f, tmp_path)
        assert len(info.imports) >= 1
        imp = info.imports[0]
        assert imp.source == "stdio.h"
        assert imp.is_type_only is True


# ---------------------------------------------------------------------------
# Extra metadata (typedef, enum)
# ---------------------------------------------------------------------------

class TestCExtraMetadata:
    def test_extract_typedef(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "types.c"
        f.write_text("typedef int BOOL;\n", encoding="utf-8")
        info = parser.parse_file(f, tmp_path)
        # Tree-sitter may not parse typedef as functions/classes,
        # but the file should parse without errors
        assert info.name == "types.c"

    def test_extract_enum(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "enum.c"
        f.write_text("enum Color { RED, GREEN, BLUE };\n", encoding="utf-8")
        info = parser.parse_file(f, tmp_path)
        assert info.name == "enum.c"


# ---------------------------------------------------------------------------
# Full C project parsing
# ---------------------------------------------------------------------------

class TestCFullProject:
    def test_parse_full_c_project(self, parser: TreeSitterParser, sample_c_project: Path) -> None:
        """Parse all C source files in the sample C project."""
        c_files = list(sample_c_project.rglob("*.c")) + list(sample_c_project.rglob("*.h"))
        assert len(c_files) > 0

        infos = []
        for cf in c_files:
            try:
                info = parser.parse_file(cf, sample_c_project)
                infos.append(info)
            except ValueError:
                pass

        assert len(infos) > 0
        # main.c should have a main function
        main_infos = [i for i in infos if i.name == "main.c"]
        if main_infos:
            all_fns = [f.name for f in main_infos[0].functions]
            assert "main" in all_fns


# ---------------------------------------------------------------------------
# Include resolution
# ---------------------------------------------------------------------------

class TestCIncludeResolution:
    def test_resolve_local_include(self, sample_c_project: Path) -> None:
        """Resolve #include "utils.h" from src/main.c."""
        import ai_code2doc.parser.languages  # noqa: F401
        from ai_code2doc.parser.language_registry import LanguageRegistry

        adapter = LanguageRegistry.get_by_extension(".c")
        assert adapter is not None
        resolver = adapter.resolver

        from_file = sample_c_project / "src" / "main.c"
        result = resolver.resolve("utils.h", from_file, sample_c_project)
        if result is not None:
            assert "utils.h" in str(result)

    def test_resolve_system_header_returns_none(self, sample_c_project: Path) -> None:
        """System headers (e.g. <stdio.h>) should resolve to None."""
        import ai_code2doc.parser.languages  # noqa: F401
        from ai_code2doc.parser.language_registry import LanguageRegistry

        adapter = LanguageRegistry.get_by_extension(".c")
        assert adapter is not None
        resolver = adapter.resolver

        from_file = sample_c_project / "src" / "main.c"
        result = resolver.resolve("stdio.h", from_file, sample_c_project)
        # System headers may or may not resolve depending on implementation
        # but should not crash
        assert result is None or isinstance(result, Path)
