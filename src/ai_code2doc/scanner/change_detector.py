from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ai_code2doc.models.analysis_state import AnalysisState, FileState
from ai_code2doc.utils.hashing import compute_file_hash


class ChangeDetector:
    def __init__(self, project_root: Path, output_dir: str = ".ai_code2doc"):
        self.state_path = project_root / output_dir / "analysis_state.json"

    def load_state(self) -> AnalysisState:
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return AnalysisState(**data)
        return AnalysisState(project_root=str(self.state_path.parent.parent))

    def save_state(self, state: AnalysisState) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            state.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def detect_changes(self, files: list[Path]) -> tuple[list[Path], list[Path]]:
        """Returns (changed_files, unchanged_files)."""
        state = self.load_state()
        changed: list[Path] = []
        unchanged: list[Path] = []
        for f in files:
            try:
                h = compute_file_hash(f)
            except (OSError, PermissionError):
                changed.append(f)
                continue
            fs = state.file_states.get(str(f))
            if fs is None or fs.hash != h:
                changed.append(f)
            else:
                unchanged.append(f)
        return changed, unchanged

    def update_state(self, files: list[Path]) -> None:
        """Update state hashes for analyzed files."""
        state = self.load_state()
        now = datetime.now()
        for f in files:
            try:
                state.file_states[str(f)] = FileState(
                    path=str(f),
                    hash=compute_file_hash(f),
                    last_analyzed=now,
                )
            except (OSError, PermissionError):
                continue
        self.save_state(state)
