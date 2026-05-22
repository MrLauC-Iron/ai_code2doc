"""rescan tool: trigger incremental re-analysis of files."""

from __future__ import annotations

import asyncio
from pathlib import Path

from ai_code2doc.agent.models import ToolCall, ToolDefinition, ToolParameter, ToolResult


tool_definition = ToolDefinition(
    name="rescan",
    description="Trigger an incremental re-scan of the project.",
    parameters=[
        ToolParameter(name="target", type="string", description="Specific file or directory to rescan (empty = full rescan)", required=False),
    ],
)


def execute(call: ToolCall, context) -> ToolResult:
    target = call.arguments.get("target", "")

    try:
        from ai_code2doc.scanner.project_scanner import ProjectScanner
        from ai_code2doc.scanner.change_detector import ChangeDetector

        if target:
            target_path = context.project_root / target
            if not target_path.exists():
                return ToolResult(tool_call_id=call.id, content=f"Target not found: {target_path}", is_error=True)
            if target_path.is_file():
                files = [target_path]
            else:
                scanner = ProjectScanner(target_path, max_file_size_kb=context.settings.max_file_size_kb)
                scan = scanner.scan()
                files = scan.target_files
        else:
            scanner = ProjectScanner(context.project_root, max_file_size_kb=context.settings.max_file_size_kb)
            scan = scanner.scan()
            files = scan.target_files

        detector = ChangeDetector(context.project_root, context.settings.output_dir)
        changed, unchanged = detector.detect_changes(files)
        detector.update_state(files)

        parsed_count = 0
        if changed:
            from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser
            from ai_code2doc.utils.parse_cache import ParseCache
            parser = TreeSitterParser()
            cache = ParseCache(context.output_dir / "file_infos")
            for f in changed:
                try:
                    fi = parser.parse_file(f, context.project_root)
                    cache.put(fi)
                    parsed_count += 1
                except Exception:
                    continue

        if context.analysis_result is not None:
            context.analysis_result.target_files = files

        parts = [f"Rescan complete: {len(files)} files scanned", f"  Changed/new: {len(changed)}", f"  Unchanged: {len(unchanged)}"]
        if parsed_count:
            parts.append(f"  Re-parsed: {parsed_count}")
        return ToolResult(tool_call_id=call.id, content="\n".join(parts))

    except Exception as exc:
        return ToolResult(tool_call_id=call.id, content=f"Rescan failed: {exc}", is_error=True)