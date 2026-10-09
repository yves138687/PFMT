"""Bounded server-side sections for document reading responses."""

import re
from dataclasses import dataclass


DEFAULT_PARAGRAPHS_PER_SECTION = 60


@dataclass(frozen=True)
class ReadSection:
    title: str
    content: str
    source_line: int


def build_read_sections(source: str, document_format: str) -> list[ReadSection]:
    if not source:
        return [ReadSection(title="正文", content="", source_line=0)]
    sections = (
        _split_markdown_chapters(source)
        if document_format == "markdown"
        else _split_html_chapters(source)
        if document_format == "html"
        else []
    )
    return sections if len(sections) > 1 else _split_paragraphs(source)


def _split_markdown_chapters(source: str) -> list[ReadSection]:
    lines = source.splitlines()
    headings: list[tuple[int, int, str]] = []
    in_fence = False
    for index, line in enumerate(lines):
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            continue
        match = None if in_fence else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if match:
            headings.append((index, len(match.group(1)), _strip_markdown(match.group(2))))
    if len(headings) < 2:
        return []
    chapter_level = min(level for _, level, _ in headings)
    chapters = [heading for heading in headings if heading[1] == chapter_level]
    if len(chapters) < 2:
        return []
    return [
        ReadSection(title=title or f"第 {index + 1} 节", content="\n".join(lines[line : chapters[index + 1][0] if index + 1 < len(chapters) else None]), source_line=line)
        for index, (line, _level, title) in enumerate(chapters)
    ]


def _split_html_chapters(source: str) -> list[ReadSection]:
    headings = list(re.finditer(r"<h([1-6])(?:\s[^>]*)?>([\s\S]*?)</h\1>", source, re.IGNORECASE))
    if len(headings) < 2:
        return []
    chapter_level = min(int(heading.group(1)) for heading in headings)
    chapters = [heading for heading in headings if int(heading.group(1)) == chapter_level]
    if len(chapters) < 2:
        return []
    return [
        ReadSection(
            title=_strip_html(chapter.group(2)) or f"第 {index + 1} 节",
            content=source[chapter.start() : chapters[index + 1].start() if index + 1 < len(chapters) else None],
            source_line=source[: chapter.start()].count("\n"),
        )
        for index, chapter in enumerate(chapters)
    ]


def _split_paragraphs(source: str) -> list[ReadSection]:
    paragraphs = [paragraph for paragraph in re.split(r"(?:\r?\n){2,}", source) if paragraph.strip()]
    if not paragraphs:
        return [ReadSection(title="正文", content=source, source_line=0)]
    sections: list[ReadSection] = []
    for index in range(0, len(paragraphs), DEFAULT_PARAGRAPHS_PER_SECTION):
        content = "\n\n".join(paragraphs[index : index + DEFAULT_PARAGRAPHS_PER_SECTION])
        prefix = "\n\n".join(paragraphs[:index])
        sections.append(ReadSection(title=f"第 {len(sections) + 1} 段", content=content, source_line=prefix.count("\n") + (1 if prefix else 0)))
    return sections


def _strip_markdown(value: str) -> str:
    return re.sub(r"[`*_~]", "", re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", value)).strip()


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value).replace("&nbsp;", " ").strip()
