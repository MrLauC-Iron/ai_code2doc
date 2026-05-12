from __future__ import annotations

# Characters that have special meaning in Markdown and need escaping.
_MD_SPECIAL: str = r"\`*_{}[]()#+-.!|~>"


def escape_markdown(text: str) -> str:
    """Escape characters that have special meaning in Markdown.

    Parameters
    ----------
    text:
        Raw text that may contain Markdown metacharacters.

    Returns
    -------
    str
        The text with special characters escaped so it renders literally.
    """
    escaped: list[str] = []
    for ch in text:
        if ch in _MD_SPECIAL:
            escaped.append(f"\\{ch}")
        else:
            escaped.append(ch)
    return "".join(escaped)


def format_code_block(code: str, language: str = "python") -> str:
    """Wrap *code* in a fenced Markdown code block.

    Parameters
    ----------
    code:
        The source code to wrap.
    language:
        The info string for syntax highlighting (default ``"python"``).

    Returns
    -------
    str
        A fenced code block string.
    """
    return f"```{language}\n{code}\n```\n"


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a Markdown table from *headers* and *rows*.

    Parameters
    ----------
    headers:
        Column header labels.
    rows:
        A list of rows, where each row is a list of cell values with the same
        length as *headers*.

    Returns
    -------
    str
        A Markdown table as a single string (lines joined with ``\\n``).
    """
    # Build header line.
    header_line = "| " + " | ".join(headers) + " |"
    # Separator line: at least three dashes per column.
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    # Data lines.
    data_lines: list[str] = []
    for row in rows:
        # Pad row to header length if necessary.
        cells = list(row) + [""] * (len(headers) - len(row))
        data_lines.append("| " + " | ".join(cells[: len(headers)]) + " |")

    parts = [header_line, sep_line, *data_lines]
    return "\n".join(parts) + "\n"


def format_toc(items: list[tuple[str, str]]) -> str:
    """Format a Markdown table of contents.

    Parameters
    ----------
    items:
        A list of ``(title, anchor)`` tuples. The *anchor* should be the
        slug-style fragment identifier (e.g. ``"my-section"``).

    Returns
    -------
    str
        A bullet-list table of contents with Markdown links.
    """
    lines: list[str] = []
    for title, anchor in items:
        lines.append(f"- [{title}](#{anchor})")
    return "\n".join(lines) + "\n"
