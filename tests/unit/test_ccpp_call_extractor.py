"""Tests for C/C++ call extractor using tree-sitter-cpp."""

from __future__ import annotations

from ai_code2doc.analyzer.c_cpp_calls import CCppCallExtractor
from ai_code2doc.models.graph import CallSite


class TestCCppCallExtractor:
    """Tests for CCppCallExtractor.extract_calls."""

    def test_simple_function_call(self) -> None:
        """A bare function call like compute(x, y) is extracted."""
        source = (
            "int calculate() {\n"
            "    return compute(x, y);\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "calculate", "math.cpp")
        assert len(sites) >= 1
        assert any(s.callee_name == "compute" for s in sites)

    def test_pointer_method_call(self) -> None:
        """A pointer method call like data->validate() is extracted."""
        source = (
            "void process(Data* data) {\n"
            "    data->validate();\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "process", "main.cpp")
        assert len(sites) >= 1
        # field_expression: callee_name should be "data->validate"
        assert any("validate" in s.callee_name for s in sites)
        validate_site = next(s for s in sites if "validate" in s.callee_name)
        assert validate_site.call_type == "method"

    def test_dot_method_call(self) -> None:
        """A dot method call like obj.process() is extracted."""
        source = (
            "void handle(Counter& obj) {\n"
            "    obj.process();\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "handle", "counter.cpp")
        assert any("process" in s.callee_name for s in sites)

    def test_qualified_call(self) -> None:
        """A namespace-qualified call like std::sort(...) is extracted."""
        source = (
            "void sort_data(int* arr, int n) {\n"
            "    std::sort(arr, arr + n);\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "sort_data", "util.cpp")
        names = [s.callee_name for s in sites]
        assert any("sort" in n for n in names)

    def test_skip_stdlib(self) -> None:
        """Standard C library calls (printf, malloc, free) are filtered out."""
        source = (
            "void process() {\n"
            "    printf(\"hello\");\n"
            "    malloc(100);\n"
            "    free(ptr);\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "process", "proc.cpp")
        names = [s.callee_name for s in sites]
        assert "printf" not in names
        assert "malloc" not in names
        assert "free" not in names

    def test_no_calls(self) -> None:
        """A function body with no call expressions returns an empty list."""
        source = (
            "int get_value() {\n"
            "    return 42;\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "get_value", "value.cpp")
        assert len(sites) == 0

    def test_nested_call(self) -> None:
        """Calls nested inside other calls are extracted."""
        source = (
            "int compute() {\n"
            "    return parse(evaluate(expr));\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "compute", "expr.cpp")
        names = [s.callee_name for s in sites]
        assert "parse" in names
        assert "evaluate" in names

    def test_chained_method_call(self) -> None:
        """Chained method calls like builder->setX()->setY() are extracted."""
        source = (
            "void configure(Builder* builder) {\n"
            "    builder->setX(1)->setY(2);\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "configure", "builder.cpp")
        names = [s.callee_name for s in sites]
        assert any("setX" in n for n in names)
        assert any("setY" in n for n in names)

    def test_call_site_attributes(self) -> None:
        """Extracted CallSite has correct file_path, line_number, caller_fqn."""
        source = (
            "void example() {\n"
            "    helper(1, 2);\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "MyClass.example", "test.cpp")
        assert len(sites) == 1
        site = sites[0]
        assert site.callee_name == "helper"
        assert site.caller_fqn == "MyClass.example"
        assert site.file_path == "test.cpp"
        assert site.line_number == 2
        assert site.call_type == "function"
        assert site.confidence == 1.0

    def test_constructor_call(self) -> None:
        """A constructor-style call like MyClass() is extracted."""
        source = (
            "void create() {\n"
            "    MyClass obj;\n"
            "    auto ptr = new MyClass(42);\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "create", "factory.cpp")
        names = [s.callee_name for s in sites]
        # new MyClass(42) should be a call_expression
        assert any("MyClass" in n for n in names)

    def test_deduplication(self) -> None:
        """Duplicate call sites at the same location are deduplicated."""
        source = (
            "void run() {\n"
            "    foo();\n"
            "    foo();\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(source, "run", "run.cpp")
        # Two calls to foo on different lines should both appear
        assert len(sites) == 2

    def test_skip_known_macros(self) -> None:
        """Known function-like macros like CV_Assert(expr) are filtered out."""
        source = (
            "void process(Data* data) {\n"
            "    CV_Assert(data != nullptr);\n"
            "    CV_Error(0, \"error\");\n"
            "}\n"
        )
        sites = CCppCallExtractor.extract_calls(
            source, "process", "proc.cpp",
            known_macros={"CV_Assert", "CV_Error"},
        )
        names = [s.callee_name for s in sites]
        assert "CV_Assert" not in names
        assert "CV_Error" not in names

    def test_macro_collection(self) -> None:
        """collect_macro_names extracts function-like macro definitions."""
        from ai_code2doc.analyzer.c_cpp_calls import collect_macro_names
        source = (
            "#define CV_Assert(expr) do { if(!(expr)) ... } while(0)\n"
            "#define MIN(a,b) ((a)<(b)?(a):(b))\n"
            "void f() {}\n"
        )
        macros = collect_macro_names(source.encode("utf-8"))
        assert "CV_Assert" in macros
        assert "MIN" in macros
        assert "f" not in macros
