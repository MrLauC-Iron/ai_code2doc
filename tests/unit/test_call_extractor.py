from __future__ import annotations

from ai_code2doc.analyzer.call_extractor import PythonCallExtractor
from ai_code2doc.models.graph import CallSite


class TestPythonCallExtractor:
    def test_simple_function_call(self) -> None:
        source = (
            "def process():\n"
            "    helper()\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "process", "test.py")
        assert len(sites) == 1
        assert sites[0].callee_name == "helper"
        assert sites[0].call_type == "function"

    def test_method_call_on_self(self) -> None:
        source = (
            "def process(self):\n"
            "    self.validate()\n"
            "    self.data.save()\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "MyClass.process", "test.py")
        assert len(sites) == 2
        assert sites[0].callee_name == "self.validate"
        assert sites[0].call_type == "method"
        assert sites[1].callee_name == "self.data.save"
        assert sites[1].call_type == "method"

    def test_method_call_on_object(self) -> None:
        source = (
            "def run(self):\n"
            "    parser = Parser()\n"
            "    result = parser.parse(text)\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "run", "test.py")
        call_names = [s.callee_name for s in sites]
        assert "parser.parse" in call_names
        assert "Parser" in call_names

    def test_class_constructor(self) -> None:
        source = (
            "def create():\n"
            "    service = MyService()\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "create", "test.py")
        assert any(s.callee_name == "MyService" for s in sites)

    def test_super_call(self) -> None:
        source = (
            "def __init__(self, x):\n"
            "    super().__init__(x)\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "MyClass.__init__", "test.py")
        assert any(s.call_type == "super_call" for s in sites)

    def test_no_calls(self) -> None:
        source = (
            "def empty():\n"
            "    x = 1\n"
            "    return x\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "empty", "test.py")
        assert len(sites) == 0

    def test_chained_calls(self) -> None:
        source = (
            "def run(self):\n"
            "    self.db.query().filter().first()\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "run", "test.py")
        assert len(sites) >= 1

    def test_skips_print_and_builtins(self) -> None:
        source = (
            "def run():\n"
            "    print('hello')\n"
            "    len([1, 2, 3])\n"
            "    custom_func()\n"
        )
        sites = PythonCallExtractor.extract_calls(source, "run", "test.py")
        assert len(sites) >= 1
        assert any(s.callee_name == "custom_func" for s in sites)

    def test_with_line_numbers(self) -> None:
        source = "def f():\n    g()\n"
        sites = PythonCallExtractor.extract_calls(source, "f", "test.py")
        assert sites[0].line_number == 2
