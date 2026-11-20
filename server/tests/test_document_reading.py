from app.utils.document_reading import build_read_sections
from app.utils.markdown_headings import iter_markdown_headings


def test_detects_non_contiguous_chapter_numbers() -> None:
    source = "第1章 开端\n\n正文一\n\n第3章 跳过的章节\n\n正文三\n\n第8章 结尾\n\n正文八"

    sections = build_read_sections(source, "plain_text")

    assert [section.title for section in sections] == ["第1章 开端", "第3章 跳过的章节", "第8章 结尾"]
    assert all(section.detected_by == "pattern" for section in sections)


def test_detects_chinese_and_parenthesized_heading_patterns() -> None:
    chinese = "一、范围\n\n说明\n\n三、定义\n\n说明\n\n五、流程\n\n说明"
    parenthesized = "（一）准备\n\n说明\n\n（二）执行\n\n说明\n\n（三）验收\n\n说明"

    chinese_sections = build_read_sections(chinese, "plain_text")
    parenthesized_sections = build_read_sections(parenthesized, "plain_text")

    assert [section.title for section in chinese_sections] == ["一、范围", "三、定义", "五、流程"]
    assert [section.title for section in parenthesized_sections] == ["（一）准备", "（二）执行", "（三）验收"]
    assert all(section.level == 2 for section in parenthesized_sections)


def test_does_not_treat_inline_enumeration_as_chapter_heading() -> None:
    source = "这是正文（一）不应拆分。\n下一行继续正文。\n\n这是另一个段落。"

    sections = build_read_sections(source, "plain_text")

    assert len(sections) == 1
    assert sections[0].detected_by == "paragraph_fallback"


def test_numbered_markdown_headings_keep_levels_source_lines_and_original_content() -> None:
    source = "#1 开始\n\n正文\n\n##2 小节\n\n###1.1 背景\n\n# 标准标题\n\n结尾"
    assert list(iter_markdown_headings(source)) == [
        (0, 1, "1 开始"), (4, 2, "2 小节"), (6, 3, "1.1 背景"), (8, 1, "标准标题")
    ]
    sections = build_read_sections(source, "markdown")
    assert [(s.title, s.source_line) for s in sections] == [("1 开始", 0), ("标准标题", 8)]
    assert sections[0].content.startswith("#1 开始")


def test_markdown_heading_compatibility_excludes_code_tags_and_escaped_hashes() -> None:
    source = "\n".join([
        "#标签", "#FFFFFF", "#1标题", "#1", r"\#1 转义", "正文 #1 内联", "",
        "    #1 缩进代码", "\t#2 制表符代码", "", "````md", "#3 围栏代码",
        "~~~", "#4 仍是代码", "```", "#5 仍是代码", "````", "",
        "~~~", "#6 另一围栏", "~~~", "   ######12.3 标题 ###", "#######7 超出层级"
    ])
    assert list(iter_markdown_headings(source)) == [(21, 6, "12.3 标题")]


def test_html_conversion_renders_compatible_heading_without_promoting_code() -> None:
    from app.services.file_service import FileService

    html = FileService._render_document_html("#1 标题\n\n```\n#2 代码\n```\n\\#3 转义", "markdown")
    assert "<h1>1 标题</h1>" in html
    assert "<h1>2 代码</h1>" not in html
    assert "<h1>3 转义</h1>" not in html
