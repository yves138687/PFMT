"""Markdown heading detection, including numbered titles missing a space."""

import re
from collections.abc import Iterator


def iter_markdown_headings(source: str) -> Iterator[tuple[int, int, str]]:
    """Yield source line, level and title without rewriting stored content."""
    fence: tuple[str, int] | None = None
    for index, line in enumerate(source.splitlines()):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
            continue
        if marker and (marker[1][0] != "`" or "`" not in marker[2]):
            fence = (marker[1][0], len(marker[1]))
            continue
        normalized = re.sub(r"^( {0,3}#{1,6})(?=[0-9]+(?:\.[0-9]+)*[ \t]+\S)", r"\1 ", line)
        match = re.match(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*#*\s*$", normalized)
        if match:
            yield index, len(match[1]), match[2]
