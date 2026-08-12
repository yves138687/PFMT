import codecs
import html
import math
import re
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Literal

import jieba
import jieba.analyse

from app.models.file import FileTag


TagSuggestionSource = Literal["existing_tag_match", "keyword_weight"]

DEFAULT_SUGGESTION_LIMIT = 15
PROCESS_TEXT_CHARS = 16 * 1024
MIN_TAIL_CHARS = 128
DEFAULT_IDF = 5.0

URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
HTML_HEADING_PATTERN = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.IGNORECASE | re.DOTALL)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
MARKDOWN_HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
TOKEN_BOUNDARY_CHARS = "A-Za-z0-9_"

STOP_WORDS = {
    "一个",
    "一些",
    "一种",
    "以及",
    "已经",
    "因为",
    "所以",
    "如果",
    "但是",
    "然后",
    "可以",
    "进行",
    "通过",
    "这个",
    "这些",
    "那些",
    "我们",
    "你们",
    "他们",
    "它们",
    "是否",
    "不是",
    "没有",
    "需要",
    "相关",
    "内容",
    "文档",
    "文章",
    "文件",
    "标题",
    "摘要",
    "系统",
    "页面",
    "功能",
    "用户",
    "支持",
    "实现",
    "使用",
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "you",
    "your",
    "file",
    "document",
    "content",
}

FORMAT_WORDS = {
    "http",
    "https",
    "html",
    "markdown",
    "md",
    "txt",
    "json",
    "xml",
    "yaml",
    "csv",
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
}


@dataclass(frozen=True)
class TagSuggestion:
    tag_name: str
    score: float
    source: TagSuggestionSource
    existing_tag_id: str | None = None
    matched_count: int | None = None


@dataclass
class _TermStat:
    weight: float = 0.0
    count: int = 0
    first_position: int = 0
    heading_hits: int = 0


@dataclass(frozen=True)
class _ExistingTagMatcher:
    tag: FileTag
    pattern: re.Pattern[str] | None = None
    has_cjk: bool = False

    def count(self, text: str) -> int:
        tag_name = self.tag.tag_name
        if self.has_cjk:
            return text.lower().count(tag_name.lower())
        if self.pattern is None:
            return 0
        return len(self.pattern.findall(text))


@dataclass
class _StreamKeywordAnalyzer:
    document_format: str
    existing_tags: list[FileTag]
    text_buffer: str = ""
    position: int = 0
    term_stats: dict[str, _TermStat] = field(default_factory=dict)
    tag_counts: Counter[str] = field(default_factory=Counter)

    def __post_init__(self) -> None:
        self.matchers = [_build_existing_tag_matcher(tag) for tag in self.existing_tags if tag.tag_name.strip()]
        max_tag_length = max((len(tag.tag_name) for tag in self.existing_tags), default=0)
        self.tail_chars = max(MIN_TAIL_CHARS, max_tag_length - 1)
        self.idf_freq = _load_jieba_idf()

    def feed(self, text: str) -> None:
        self.text_buffer += text
        while len(self.text_buffer) > PROCESS_TEXT_CHARS + self.tail_chars:
            process_text = self.text_buffer[:-self.tail_chars]
            self.text_buffer = self.text_buffer[-self.tail_chars :]
            self._process(process_text)

    def finish(self) -> None:
        if self.text_buffer:
            self._process(self.text_buffer)
            self.text_buffer = ""

    def suggestions(self, limit: int) -> list[TagSuggestion]:
        existing_items = self._existing_tag_suggestions()
        existing_names = {item.tag_name.lower() for item in existing_items}
        keyword_items = self._keyword_suggestions(excluded_names=existing_names)
        return [*existing_items, *keyword_items][:limit]

    def _process(self, raw_text: str) -> None:
        if not raw_text:
            return
        normalized_text = _normalize_text(raw_text, self.document_format)
        self._count_existing_tags(normalized_text)
        heading_text = _extract_heading_text(raw_text, self.document_format)
        self._count_terms(normalized_text, weight=1.0, heading=False)
        if heading_text:
            self._count_terms(heading_text, weight=1.4, heading=True)

    def _count_existing_tags(self, text: str) -> None:
        if not text:
            return
        for matcher in self.matchers:
            matched_count = matcher.count(text)
            if matched_count:
                self.tag_counts[matcher.tag.tag_id] += matched_count

    def _count_terms(self, text: str, *, weight: float, heading: bool) -> None:
        cleaned = _prepare_for_tokenize(text)
        normalized_tokens: list[str] = []
        for token in jieba.cut(cleaned, cut_all=False):
            normalized = _normalize_token(token)
            if not _is_valid_keyword(normalized):
                continue
            normalized_tokens.append(normalized)
            self._add_term(normalized, weight=weight, heading=heading)
            if not heading:
                self.position += 1

        for first, second in zip(normalized_tokens, normalized_tokens[1:]):
            phrase = f"{first}{second}"
            if not _is_valid_phrase(first, second, phrase):
                continue
            self._add_term(phrase, weight=weight * 1.15, heading=heading)

    def _add_term(self, term: str, *, weight: float, heading: bool) -> None:
        stat = self.term_stats.get(term)
        if stat is None:
            stat = _TermStat(first_position=self.position)
            self.term_stats[term] = stat
        stat.weight += weight
        stat.count += 1
        if heading:
            stat.heading_hits += 1

    def _existing_tag_suggestions(self) -> list[TagSuggestion]:
        tag_by_id = {tag.tag_id: tag for tag in self.existing_tags}
        items: list[TagSuggestion] = []
        for tag_id, matched_count in self.tag_counts.items():
            tag = tag_by_id.get(tag_id)
            if tag is None:
                continue
            items.append(
                TagSuggestion(
                    tag_name=tag.tag_name,
                    score=round(1000.0 + math.log1p(matched_count), 4),
                    source="existing_tag_match",
                    existing_tag_id=tag.tag_id,
                    matched_count=matched_count,
                )
            )
        return sorted(items, key=lambda item: (-item.score, item.tag_name.lower()))

    def _keyword_suggestions(self, *, excluded_names: set[str]) -> list[TagSuggestion]:
        items: list[TagSuggestion] = []
        for tag_name, stat in self.term_stats.items():
            if tag_name.lower() in excluded_names:
                continue
            idf = self.idf_freq.get(tag_name, DEFAULT_IDF)
            tf = 1.0 + math.log(stat.weight)
            position_boost = 1.0 + max(0.0, 0.25 - min(stat.first_position, 500) / 2000)
            heading_boost = 1.0 + min(0.45, stat.heading_hits * 0.12)
            score = tf * idf * position_boost * heading_boost
            items.append(
                TagSuggestion(
                    tag_name=tag_name,
                    score=round(score, 4),
                    source="keyword_weight",
                    matched_count=stat.count,
                )
            )
        return sorted(items, key=lambda item: (-item.score, item.tag_name.lower()))


class TagSuggestionService:
    """Generate document tag suggestions from a decrypted text stream."""

    def suggest(
        self,
        *,
        content_chunks: Iterable[bytes],
        document_format: str,
        existing_tags: list[FileTag],
        limit: int = DEFAULT_SUGGESTION_LIMIT,
    ) -> list[TagSuggestion]:
        analyzer = _StreamKeywordAnalyzer(document_format=document_format, existing_tags=existing_tags)
        decoder = codecs.getincrementaldecoder("utf-8-sig")("replace")
        for chunk in content_chunks:
            analyzer.feed(decoder.decode(chunk, final=False))
        analyzer.feed(decoder.decode(b"", final=True))
        analyzer.finish()
        return analyzer.suggestions(limit=max(1, limit))


def _build_existing_tag_matcher(tag: FileTag) -> _ExistingTagMatcher:
    tag_name = tag.tag_name.strip()
    has_cjk = _has_cjk(tag_name)
    if has_cjk:
        return _ExistingTagMatcher(tag=tag, has_cjk=True)
    pattern = re.compile(rf"(?<![{TOKEN_BOUNDARY_CHARS}]){re.escape(tag_name)}(?![{TOKEN_BOUNDARY_CHARS}])", re.IGNORECASE)
    return _ExistingTagMatcher(tag=tag, pattern=pattern)


def _normalize_text(raw_text: str, document_format: str) -> str:
    text = URL_PATTERN.sub(" ", raw_text)
    if document_format == "html":
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = HTML_TAG_PATTERN.sub(" ", text)
        return html.unescape(text)
    if document_format == "markdown":
        text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
        text = re.sub(r"`[^`]*`", " ", text)
        text = re.sub(r"!\[[^\]]*]\([^)]*\)", " ", text)
        text = re.sub(r"\[[^\]]+]\([^)]*\)", " ", text)
    return text


def _extract_heading_text(raw_text: str, document_format: str) -> str:
    headings: list[str] = []
    if document_format == "html":
        headings.extend(HTML_TAG_PATTERN.sub(" ", match.group(1)) for match in HTML_HEADING_PATTERN.finditer(raw_text))
    elif document_format == "markdown":
        headings.extend(match.group(1) for match in MARKDOWN_HEADING_PATTERN.finditer(raw_text))
    return html.unescape("\n".join(headings))


def _prepare_for_tokenize(text: str) -> str:
    text = URL_PATTERN.sub(" ", text)
    return re.sub(r"[\\/_.,:;!?()[\]{}<>\"'`|*=+#@$%^&~-]+", " ", text)


def _normalize_token(token: str) -> str:
    token = token.strip().lower()
    return token


def _is_valid_keyword(token: str) -> bool:
    if not token:
        return False
    if len(token) < 2:
        return False
    if token in STOP_WORDS or token in FORMAT_WORDS:
        return False
    if token.isdigit():
        return False
    if re.fullmatch(r"\d+(\.\d+)?", token):
        return False
    if re.fullmatch(r"[a-z]{1,2}", token):
        return False
    if not re.search(r"[\w\u4e00-\u9fff]", token):
        return False
    return True


def _is_valid_phrase(first: str, second: str, phrase: str) -> bool:
    if len(phrase) < 4 or len(phrase) > 12:
        return False
    if not (_has_cjk(first) and _has_cjk(second)):
        return False
    if phrase in STOP_WORDS:
        return False
    return True


def _has_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def _load_jieba_idf() -> dict[str, float]:
    try:
        tfidf = jieba.analyse.TFIDF()
        return dict(tfidf.idf_freq)
    except Exception:
        return {}
