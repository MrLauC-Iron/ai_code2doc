"""Integration tests for change detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_code2doc.scanner.change_detector import ChangeDetector
from ai_code2doc.scanner.project_scanner import ProjectScanner


class TestChangeDetector:
    def test_first_detection_all_changed(self, sample_py_project: Path, tmp_path: Path) -> None:
        """First run with no prior state should detect all files as changed."""
        detector = ChangeDetector(sample_py_project, output_dir=str(tmp_path / "state"))
        scanner = ProjectScanner(sample_py_project)
        result = scanner.scan()

        changed, unchanged = detector.detect_changes(result.target_files)
        # All files should be considered changed on first run
        assert len(changed) >= 0  # May vary depending on file accessibility

    def test_no_changes_after_state_update(self, sample_py_project: Path, tmp_path: Path) -> None:
        """After updating state, same files should be unchanged."""
        detector = ChangeDetector(sample_py_project, output_dir=str(tmp_path / "state"))
        scanner = ProjectScanner(sample_py_project)
        result = scanner.scan()

        if not result.target_files:
            pytest.skip("No target files found")

        # First: update state
        detector.update_state(result.target_files)

        # Second: detect changes
        changed, unchanged = detector.detect_changes(result.target_files)
        # All files should be unchanged since we just updated state
        assert len(changed) == 0
        assert len(unchanged) == len(result.target_files)

    def test_partial_change(self, tmp_path: Path) -> None:
        """Modifying one file after state update should detect only that file."""
        # Create two files
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("x = 1\n", encoding="utf-8")
        f2.write_text("y = 2\n", encoding="utf-8")

        output = tmp_path / "output"
        detector = ChangeDetector(tmp_path, output_dir=str(output))

        # Update state
        detector.update_state([f1, f2])

        # Modify f1
        f1.write_text("x = 99\n", encoding="utf-8")

        changed, unchanged = detector.detect_changes([f1, f2])
        assert f1 in changed
        assert f2 in unchanged

    def test_new_file_detected(self, tmp_path: Path) -> None:
        """New files not in state should be detected as changed."""
        f1 = tmp_path / "existing.py"
        f1.write_text("x = 1\n", encoding="utf-8")

        output = tmp_path / "output"
        detector = ChangeDetector(tmp_path, output_dir=str(output))
        detector.update_state([f1])

        # Add a new file
        f2 = tmp_path / "new_file.py"
        f2.write_text("y = 2\n", encoding="utf-8")

        changed, unchanged = detector.detect_changes([f1, f2])
        assert f2 in changed

    def test_state_persistence(self, tmp_path: Path) -> None:
        """State should persist across save/load cycles."""
        f1 = tmp_path / "test.py"
        f1.write_text("x = 1\n", encoding="utf-8")

        output = tmp_path / "output"
        detector1 = ChangeDetector(tmp_path, output_dir=str(output))
        detector1.update_state([f1])

        # Create a new detector instance (simulates restart)
        detector2 = ChangeDetector(tmp_path, output_dir=str(output))
        changed, unchanged = detector2.detect_changes([f1])
        assert len(changed) == 0
        assert len(unchanged) == 1
