from __future__ import annotations

from pathlib import Path

from ai_code2doc.models.knowledge import KnowledgeDocument


class MarkdownWriter:
    def write_doc(self, file_path: Path, doc: KnowledgeDocument) -> Path:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        content = f"# {doc.title}\n\n"
        content += f"> Generated: {doc.created_at.isoformat()}\n"
        content += f"> Tags: {', '.join(doc.tags)}\n\n"
        content += doc.content
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def write_raw(self, file_path: Path, content: str) -> Path:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return file_path
