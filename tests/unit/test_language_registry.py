"""Tests for ai_code2doc language registry."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_code2doc.parser.language_registry import LanguageAdapter, LanguageRegistry


class TestLanguageRegistry:
    def test_builtin_languages_registered(self) -> None:
        """Importing languages should auto-register Python and C/C++."""
        # Force import to trigger registration
        import ai_code2doc.parser.languages  # noqa: F401

        adapters = LanguageRegistry.all_adapters()
        ids = {a.language_id for a in adapters}
        assert "python" in ids
        assert "c_cpp" in ids

    def test_get_by_extension_py(self) -> None:
        import ai_code2doc.parser.languages  # noqa: F401

        adapter = LanguageRegistry.get_by_extension(".py")
        assert adapter is not None
        assert adapter.language_id == "python"

    def test_get_by_extension_c(self) -> None:
        import ai_code2doc.parser.languages  # noqa: F401

        adapter = LanguageRegistry.get_by_extension(".c")
        assert adapter is not None
        assert adapter.language_id == "c_cpp"

    def test_get_by_extension_cpp(self) -> None:
        import ai_code2doc.parser.languages  # noqa: F401

        adapter = LanguageRegistry.get_by_extension(".cpp")
        assert adapter is not None
        assert adapter.language_id == "c_cpp"

    def test_get_by_extension_unknown(self) -> None:
        adapter = LanguageRegistry.get_by_extension(".zzz")
        assert adapter is None

    def test_get_by_id_python(self) -> None:
        import ai_code2doc.parser.languages  # noqa: F401

        adapter = LanguageRegistry.get_by_id("python")
        assert adapter is not None
        assert ".py" in adapter.extensions

    def test_get_by_id_unknown(self) -> None:
        adapter = LanguageRegistry.get_by_id("fortran")
        assert adapter is None

    def test_all_extensions(self) -> None:
        import ai_code2doc.parser.languages  # noqa: F401

        exts = LanguageRegistry.all_extensions()
        assert ".py" in exts
        assert ".c" in exts
        assert ".cpp" in exts
        assert ".h" in exts

    def test_all_adapters_count(self) -> None:
        import ai_code2doc.parser.languages  # noqa: F401

        adapters = LanguageRegistry.all_adapters()
        assert len(adapters) >= 2  # python + c_cpp

    def test_case_insensitive_extension(self) -> None:
        import ai_code2doc.parser.languages  # noqa: F401

        adapter = LanguageRegistry.get_by_extension(".PY")
        assert adapter is not None
        assert adapter.language_id == "python"
