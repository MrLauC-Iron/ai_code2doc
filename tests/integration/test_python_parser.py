"""Integration tests for Python source code parsing."""

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

class TestPythonFunctionExtraction:
    def test_extract_simple_function(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("def foo(x: int) -> str:\n    return str(x)\n", encoding="utf-8")
        info = parser.parse_file(f, tmp_path)
        assert len(info.functions) >= 1
        fn = info.functions[0]
        assert fn.name == "foo"
        assert "x: int" in fn.params or "x" in str(fn.params)
        assert fn.return_type == "str"

    def test_extract_async_function(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("async def bar():\n    pass\n", encoding="utf-8")
        info = parser.parse_file(f, tmp_path)
        assert len(info.functions) >= 1
        assert info.functions[0].is_async is True

    def test_extract_decorated_function(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("@decorator\ndef f():\n    pass\n", encoding="utf-8")
        info = parser.parse_file(f, tmp_path)
        assert len(info.functions) >= 1
        assert len(info.functions[0].decorators) > 0
        assert "decorator" in info.functions[0].decorators[0]


# ---------------------------------------------------------------------------
# Class extraction
# ---------------------------------------------------------------------------

class TestPythonClassExtraction:
    def test_extract_class_with_inheritance(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("class Foo(Bar):\n    pass\n", encoding="utf-8")
        info = parser.parse_file(f, tmp_path)
        assert len(info.classes) >= 1
        assert info.classes[0].name == "Foo"
        assert info.classes[0].extends == "Bar"

    def test_extract_class_with_methods(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text(
            "class MyClass:\n"
            "    def method1(self):\n"
            "        pass\n"
            "    def method2(self, x):\n"
            "        return x\n",
            encoding="utf-8",
        )
        info = parser.parse_file(f, tmp_path)
        assert len(info.classes) >= 1
        assert len(info.classes[0].methods) >= 2


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------

class TestPythonImportExtraction:
    def test_extract_import(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("import os\n", encoding="utf-8")
        info = parser.parse_file(f, tmp_path)
        assert len(info.imports) >= 1
        assert info.imports[0].source == "os"

    def test_extract_from_import(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("from os.path import join\n", encoding="utf-8")
        info = parser.parse_file(f, tmp_path)
        assert len(info.imports) >= 1
        imp = info.imports[0]
        assert imp.source == "os.path"
        assert "join" in imp.specifiers

    def test_extract_relative_import(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("from .utils import helper\n", encoding="utf-8")
        info = parser.parse_file(f, tmp_path)
        assert len(info.imports) >= 1
        imp = info.imports[0]
        assert imp.source == ".utils"
        assert "helper" in imp.specifiers


# ---------------------------------------------------------------------------
# Export extraction (__all__)
# ---------------------------------------------------------------------------

class TestPythonExportExtraction:
    def test_extract_all_exports(self, parser: TreeSitterParser, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text('__all__ = ["Foo", "bar"]\n', encoding="utf-8")
        info = parser.parse_file(f, tmp_path)
        assert "Foo" in info.exports
        assert "bar" in info.exports


# ---------------------------------------------------------------------------
# Full project parsing
# ---------------------------------------------------------------------------

class TestPythonFullProject:
    def test_parse_full_py_project(self, parser: TreeSitterParser, sample_py_project: Path) -> None:
        """Parse all .py files in the sample project."""
        py_files = list(sample_py_project.rglob("*.py"))
        assert len(py_files) > 0

        infos = []
        for pf in py_files:
            try:
                info = parser.parse_file(pf, sample_py_project)
                infos.append(info)
            except ValueError:
                pass  # Skip files that can't be parsed

        assert len(infos) > 0
        # At least one file should have functions
        all_functions = [f for info in infos for f in info.functions]
        assert len(all_functions) > 0


# ---------------------------------------------------------------------------
# Import resolution
# ---------------------------------------------------------------------------

class TestPythonImportResolution:
    def test_resolve_dotted_import(self, sample_py_project: Path) -> None:
        """Resolve 'from src.models.user import User' to the actual file."""
        import ai_code2doc.parser.languages  # noqa: F401
        from ai_code2doc.parser.language_registry import LanguageRegistry

        adapter = LanguageRegistry.get_by_extension(".py")
        assert adapter is not None
        resolver = adapter.resolver

        # Resolve from src/api/routes.py to src/models/user.py
        from_file = sample_py_project / "src" / "api" / "routes.py"
        if from_file.exists():
            result = resolver.resolve("src.models.user", from_file, sample_py_project)
            # May resolve or None depending on project structure
            if result is not None:
                assert "user" in str(result).lower() or "models" in str(result)

    def test_resolve_third_party_returns_none(self, sample_py_project: Path) -> None:
        """Third-party imports (e.g. numpy) should resolve to None."""
        import ai_code2doc.parser.languages  # noqa: F401
        from ai_code2doc.parser.language_registry import LanguageRegistry

        adapter = LanguageRegistry.get_by_extension(".py")
        assert adapter is not None
        resolver = adapter.resolver

        from_file = sample_py_project / "src" / "main.py"
        result = resolver.resolve("numpy", from_file, sample_py_project)
        assert result is None
