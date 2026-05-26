"""Tests for TypeInferrer – lightweight type inference from assignment patterns."""

from __future__ import annotations

from ai_code2doc.analyzer.type_inferrer import TypeInferrer


class TestTypeInferrer:
    def test_simple_assignment(self) -> None:
        source = (
            "def run():\n"
            "    scanner = ProjectScanner()\n"
            "    scanner.scan()\n"
        )
        scopes = TypeInferrer.infer(source, "a.py")
        assert scopes.lookup("scanner") == "ProjectScanner"

    def test_class_constructor(self) -> None:
        source = (
            "def run():\n"
            "    builder = DependencyGraphBuilder(root)\n"
        )
        scopes = TypeInferrer.infer(source, "a.py")
        assert scopes.lookup("builder") == "DependencyGraphBuilder"

    def test_attribute_access(self) -> None:
        source = (
            "def run(self):\n"
            "    self.data = Cache()\n"
        )
        scopes = TypeInferrer.infer(source, "a.py", enclosing_class="MyClass")
        assert scopes.lookup("self.data") == "Cache"

    def test_from_import_type(self) -> None:
        source = (
            "def run():\n"
            "    fi = parser.parse_file(f, root)\n"
            "    return fi\n"
        )
        scopes = TypeInferrer.infer(source, "a.py")
        # The RHS is an attribute call `parser.parse_file(...)`.
        # The inferrer returns the full dotted name, not the resolved return type.
        assert scopes.lookup("fi") == "parser.parse_file"

    def test_unknown_type(self) -> None:
        source = (
            "def run():\n"
            "    x = some_unknown_thing()\n"
        )
        scopes = TypeInferrer.infer(source, "a.py")
        assert scopes.lookup("x") == "some_unknown_thing"

    def test_string_literal(self) -> None:
        source = 'def run():\n    name = "hello"\n'
        scopes = TypeInferrer.infer(source, "a.py")
        assert scopes.lookup("name") is None

    def test_self_type(self) -> None:
        source = "def process(self):\n    pass\n"
        scopes = TypeInferrer.infer(source, "a.py", enclosing_class="Service")
        assert scopes.lookup("self") == "Service"
