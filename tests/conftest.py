"""Shared pytest fixtures for ai_code2doc tests."""

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

FIXTURES_DIR = Path(__file__).parent / "integration" / "fixtures"


@pytest.fixture
def sample_py_project() -> Path:
    """Return path to the sample Python project fixture."""
    return FIXTURES_DIR / "sample-py-project"


@pytest.fixture
def sample_c_project() -> Path:
    """Return path to the sample C project fixture."""
    return FIXTURES_DIR / "sample-c-project"


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Return a temporary output directory."""
    d = tmp_path / ".ai_code2doc"
    d.mkdir()
    return d
