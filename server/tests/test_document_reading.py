from app.utils.document_reading import build_read_sections


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
