"""Fast, explainable server-side chapter detection for readable documents."""

import re
from dataclasses import dataclass


DEFAULT_PARAGRAPHS_PER_SECTION = 60
MAX_TITLE_LENGTH = 80
_CHINESE_NUMBER = "〇零一二三四五六七八九十百千万两壹贰叁肆伍陆柒捌玖拾佰仟"
_SENTENCE_END = re.compile(r"[。！？!?；;]$", re.UNICODE)


@dataclass(frozen=True)
class ReadSection:
    title: str
    content: str
    source_line: int
    level: int = 1
    detected_by: str = "paragraph_fallback"


@dataclass(frozen=True)
class _HeadingCandidate:
    line: int
    title: str
    level: int
    family: str
    priority: int


def build_read_sections(source: str, document_format: str) -> list[ReadSection]:
    """Return bounded reading units without ML or sequential-number requirements."""

    if not source:
        return [ReadSection(title="正文", content="", source_line=0)]
    sections = (
        _split_markdown_chapters(source)
        if document_format == "markdown"
        else _split_html_chapters(source)
        if document_format == "html"
        else _split_plain_text_chapters(source)
    )
    return sections if len(sections) > 1 else _split_paragraphs(source)


def _split_markdown_chapters(source: str) -> list[ReadSection]:
    lines = source.splitlines()
    headings: list[_HeadingCandidate] = []
    in_fence = False
    for index, line in enumerate(lines):
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            continue
        match = None if in_fence else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if match:
            headings.append(_HeadingCandidate(index, _strip_markdown(match.group(2)), len(match.group(1)), "markdown", 100))
    if len(headings) < 2:
        return []
    top_level = min(heading.level for heading in headings)
    return _sections_from_line_headings(source, [heading for heading in headings if heading.level == top_level], "markdown")


def _split_html_chapters(source: str) -> list[ReadSection]:
    matches = list(re.finditer(r"<h([1-6])(?:\s[^>]*)?>([\s\S]*?)</h\1>", source, re.IGNORECASE))
    if len(matches) < 2:
        return []
    level = min(int(match.group(1)) for match in matches)
    chapters = [match for match in matches if int(match.group(1)) == level]
    if len(chapters) < 2:
        return []
    return [
        ReadSection(
            _strip_html(chapter.group(2)) or f"第 {index + 1} 节",
            source[chapter.start() : chapters[index + 1].start() if index + 1 < len(chapters) else None],
            source[: chapter.start()].count("\n"),
            level,
            "html",
        )
        for index, chapter in enumerate(chapters)
    ]


def _split_plain_text_chapters(source: str) -> list[ReadSection]:
    lines = source.splitlines()
    candidates = [candidate for index in range(len(lines)) if (candidate := _detect_plain_text_heading(lines, index))]
    if not candidates:
        return []
    families: dict[str, list[_HeadingCandidate]] = {}
    for candidate in candidates:
        families.setdefault(candidate.family, []).append(candidate)
    # Repetition proves the line pattern is structural. Numbering gaps are valid.
    eligible = [items for items in families.values() if len(items) >= 2]
    if not eligible:
        return []
    selected = max(eligible, key=lambda items: (items[0].priority, len(items)))
    top_level = min(item.level for item in selected)
    return _sections_from_line_headings(source, [item for item in selected if item.level == top_level], "pattern")


def _detect_plain_text_heading(lines: list[str], index: int) -> _HeadingCandidate | None:
    line = lines[index].strip()
    if not line or len(line) > MAX_TITLE_LENGTH or _SENTENCE_END.search(line):
        return None
    if not (index == 0 or not lines[index - 1].strip() or index == len(lines) - 1 or not lines[index + 1].strip()):
        return None

    match = re.match(rf"^第\s*([{_CHINESE_NUMBER}0-9]+)\s*([章节卷部篇回])\s*[:：、.．-]?\s*(.*)$", line)
    if match:
        return _HeadingCandidate(index, line, 1, "chapter", 95)
    match = re.match(rf"^([{_CHINESE_NUMBER}]+)\s*[、.．]\s*(.+)$", line)
    if match:
        return _HeadingCandidate(index, line, 1, "cn_enumeration", 80)
    match = re.match(r"^(\d+(?:\.\d+){0,4})\s*[、.．)]\s*(.+)$", line)
    if match:
        return _HeadingCandidate(index, line, match.group(1).count(".") + 1, "arabic_enumeration", 75)
    match = re.match(rf"^[（(]\s*([{_CHINESE_NUMBER}0-9]+)\s*[）)]\s*(.+)$", line)
    if match:
        return _HeadingCandidate(index, line, 2, "parenthesized", 55)
    match = re.match(r"^([①②③④⑤⑥⑦⑧⑨⑩])\s*(.+)$", line)
    if match:
        return _HeadingCandidate(index, line, 2, "circled", 50)
    return None


def _sections_from_line_headings(source: str, headings: list[_HeadingCandidate], detected_by: str) -> list[ReadSection]:
    if len(headings) < 2:
        return []
    lines = source.splitlines()
    sections: list[ReadSection] = []
    if any(line.strip() for line in lines[: headings[0].line]):
        sections.append(ReadSection("前言", "\n".join(lines[: headings[0].line]), 0, detected_by=detected_by))
    for index, heading in enumerate(headings):
        end = headings[index + 1].line if index + 1 < len(headings) else None
        sections.append(ReadSection(heading.title, "\n".join(lines[heading.line : end]), heading.line, heading.level, detected_by))
    return sections


def _split_paragraphs(source: str) -> list[ReadSection]:
    paragraphs = [paragraph for paragraph in re.split(r"(?:\r?\n){2,}", source) if paragraph.strip()]
    if not paragraphs:
        return [ReadSection(title="正文", content=source, source_line=0)]
    sections: list[ReadSection] = []
    for index in range(0, len(paragraphs), DEFAULT_PARAGRAPHS_PER_SECTION):
        content = "\n\n".join(paragraphs[index : index + DEFAULT_PARAGRAPHS_PER_SECTION])
        prefix = "\n\n".join(paragraphs[:index])
        sections.append(ReadSection(f"第 {len(sections) + 1} 段", content, prefix.count("\n") + (1 if prefix else 0)))
    return sections


def _strip_markdown(value: str) -> str:
    return re.sub(r"[`*_~]", "", re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", value)).strip()


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value).replace("&nbsp;", " ").strip()
