from __future__ import annotations

from ai_code2doc.analyzer.external_libs import is_external_call


class TestExternalLibs:
    def test_known_stdlib(self) -> None:
        assert is_external_call("print", "a.py") is True
        assert is_external_call("len", "a.py") is True
        assert is_external_call("range", "a.py") is True

    def test_project_internal(self) -> None:
        assert is_external_call("parse_file", "a.py") is False

    def test_common_test_mocks(self) -> None:
        assert is_external_call("MagicMock", "a.py") is True
        assert is_external_call("patch", "a.py") is True
        assert is_external_call("AsyncMock", "a.py") is True

    def test_common_stdlib_types(self) -> None:
        assert is_external_call("Path", "a.py") is True
        assert is_external_call("dict", "a.py") is True
        assert is_external_call("list", "a.py") is True
        assert is_external_call("set", "a.py") is True

    def test_dotted_names_not_filtered(self) -> None:
        # obj.method() should NOT be filtered even if 'obj' looks like a builtin
        assert is_external_call("result.append", "a.py") is False
        assert is_external_call("data.items", "a.py") is False

    def test_loguru_console(self) -> None:
        assert is_external_call("console", "a.py") is True
