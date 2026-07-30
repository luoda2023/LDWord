import pytest

from src.config.content_materials import (
    HeadingBlock,
    ImageBlock,
    InlineKind,
    ListBlock,
    ParagraphBlock,
    TableBlock,
)
from src.services.material_content.markdown_importer import (
    MarkdownImportError,
    discover_markdown_resource_paths,
    parse_markdown_content,
    parse_markdown_content_with_events,
)


def test_commonmark_success_maps_supported_blocks_and_inlines() -> None:
    markdown = (
        """# H1
## H2
### H3
#### H4
##### H5
###### H6

普通 **粗体** *斜体* {{@text:COMPANY}}"""
        "  \n"
        """硬换行
软换行继续 [官网](https://example.com) [邮箱](mailto:test@example.com)

- A
- B

1. One
2. Two

| 名称 | 值 |
| --- | --- |
| 公司 | {{@text:COMPANY}} |
"""
    )
    fragment = parse_markdown_content(markdown)
    headings = [block for block in fragment.blocks if isinstance(block, HeadingBlock)]
    assert [block.level for block in headings] == [1, 2, 3, 4, 5, 6]
    paragraph = next(block for block in fragment.blocks if isinstance(block, ParagraphBlock))
    assert any(item.bold and item.text == "粗体" for item in paragraph.inlines)
    assert any(item.italic and item.text == "斜体" for item in paragraph.inlines)
    assert any(
        item.kind is InlineKind.FIELD_TOKEN and item.field_key == "@text:COMPANY"
        for item in paragraph.inlines
    )
    assert {
        item.href for item in paragraph.inlines if item.kind is InlineKind.HYPERLINK
    } == {"https://example.com", "mailto:test@example.com"}
    lists = [block for block in fragment.blocks if isinstance(block, ListBlock)]
    assert [(block.ordered, block.start, block.nesting) for block in lists] == [
        (False, 1, 0), (True, 1, 0)
    ]
    table = next(block for block in fragment.blocks if isinstance(block, TableBlock))
    assert len(table.rows) == 2
    assert all(len(row.cells) == 2 for row in table.rows)


def test_field_token_is_recognized_across_inline_runs() -> None:
    fragment = parse_markdown_content("前缀 {{@text:FI**EL**D}} 后缀")
    paragraph = fragment.blocks[0]
    assert isinstance(paragraph, ParagraphBlock)
    assert [
        item.field_key for item in paragraph.inlines if item.kind is InlineKind.FIELD_TOKEN
    ] == ["@text:FIELD"]


def test_nested_lists_support_three_levels_and_reject_fourth() -> None:
    fragment = parse_markdown_content("- 一级\n  - 二级\n    1. 三级\n")
    lists = [block for block in fragment.blocks if isinstance(block, ListBlock)]
    assert [block.nesting for block in lists] == [0, 1, 2]
    with pytest.raises(MarkdownImportError) as raised:
        parse_markdown_content("- 一级\n  - 二级\n    - 三级\n      - 四级\n")
    assert raised.value.code == "list_nesting_exceeded"
    assert parse_markdown_content("2. 从二开始\n").blocks[0].start == 2


@pytest.mark.parametrize(
    "markdown",
    [
        "[FTP](ftp://example.com/file)",
        "[文件](file:///tmp/a)",
        "[数据](data:text/plain,a)",
    ],
)
def test_link_whitelist_blocks_non_external_protocols(markdown: str) -> None:
    with pytest.raises(MarkdownImportError) as raised:
        parse_markdown_content(markdown, source_path="route.md")
    assert raised.value.code == "link_scheme_not_allowed"
    assert raised.value.path == "route.md"


def test_raw_html_remains_a_typed_blocker() -> None:
    with pytest.raises(MarkdownImportError) as raised:
        parse_markdown_content("<b>HTML</b>")
    assert raised.value.code == "raw_html_unsupported"


def test_common_structures_are_deterministically_normalized() -> None:
    fragment = parse_markdown_content(
        "> 引用\n\n```python\nprint('x')\n```\n\n"
        "正文 `inline`\n\n---\n\n- [ ] 待办\n- [x] 完成\n\n"
        "[相对文档](guide.md)"
    )
    text = "\n".join(
        _plain_block_text(block) for block in fragment.blocks
    )
    assert "│ 引用" in text
    assert "print('x')" in text
    assert "正文 inline" in text
    assert "────────" in text
    assert "☐ 待办" in text
    assert "☑ 完成" in text
    assert "相对文档" in text


def _plain_block_text(block) -> str:
    if isinstance(block, (ParagraphBlock, HeadingBlock)):
        return "".join(item.text or item.field_key for item in block.inlines)
    if isinstance(block, ListBlock):
        return "\n".join(
            "".join(item.text or item.field_key for item in list_item.inlines)
            for list_item in block.items
        )
    return ""


def test_nested_content_token_is_blocked() -> None:
    with pytest.raises(MarkdownImportError) as raised:
        parse_markdown_content("{{@file:another_block}}")
    assert raised.value.code == "recursive_content_token"


def test_images_use_captured_resource_ids_and_deterministic_anchors() -> None:
    markdown = "![第一张](images/route.png)\n\n![第二张](images/route.png)\n"
    manifest = {"images/route.png": "sha256/abc.png"}
    first = parse_markdown_content(markdown, resource_id_by_path=manifest)
    second = parse_markdown_content(markdown, resource_id_by_path=manifest)
    images = [block for block in first.blocks if isinstance(block, ImageBlock)]
    assert [item.resource_id for item in images] == ["sha256/abc.png"] * 2
    assert len({item.generated_anchor_id for item in images}) == 2
    assert [item.generated_anchor_id for item in images] == [
        item.generated_anchor_id
        for item in second.blocks
        if isinstance(item, ImageBlock)
    ]


@pytest.mark.parametrize(
    ("target", "code"),
    [
        ("https://example.com/a.png", "image_path_not_local_relative"),
        ("data:image/png;base64,AAAA", "image_path_not_local_relative"),
        ("file:///tmp/a.png", "image_path_not_local_relative"),
        ("../outside.png", "image_path_escape"),
        ("/absolute.png", "image_path_not_local_relative"),
        ("//server/share/a.png", "image_path_not_local_relative"),
        ("C:/absolute.png", "image_path_not_local_relative"),
    ],
)
def test_images_reject_remote_absolute_and_escape_paths(target: str, code: str) -> None:
    with pytest.raises(MarkdownImportError) as raised:
        parse_markdown_content(f"![x]({target})")
    assert raised.value.code == code


@pytest.mark.parametrize(
    ("markdown", "code"),
    [
        ("文字 ![x](images/a.png)", "image_mixed_content"),
        ("![a](images/a.png) ![b](images/b.png)", "image_multiple_in_paragraph"),
        ("[![x](images/a.png)](https://example.com)", "image_linked_unsupported"),
        ("- ![x](images/a.png)", "image_in_list_unsupported"),
        ("| 图 |\n| --- |\n| ![x](images/a.png) |", "image_in_table_unsupported"),
    ],
)
def test_images_must_be_exclusive_body_paragraphs(markdown: str, code: str) -> None:
    paths = discover_markdown_resource_paths(markdown)
    manifest = {path: f"sha256/{index}.png" for index, path in enumerate(paths)}
    with pytest.raises(MarkdownImportError) as raised:
        parse_markdown_content(markdown, resource_id_by_path=manifest)
    assert raised.value.code == code


def test_resource_manifest_must_match_references_exactly() -> None:
    with pytest.raises(MarkdownImportError) as raised:
        parse_markdown_content("![x](images/a.png)")
    assert raised.value.code == "resource_not_declared"
    with pytest.raises(MarkdownImportError) as raised:
        parse_markdown_content(
            "没有图片", resource_id_by_path={"images/a.png": "sha256/a.png"}
        )
    assert raised.value.code == "resource_manifest_mismatch"


def test_image_and_link_titles_are_ignored_without_losing_visible_content() -> None:
    fragment, events = parse_markdown_content_with_events(
        '![图](images/a.png "图片标题")\n\n[官网](https://example.com "链接标题")',
        resource_id_by_path={"images/a.png": "sha256/a.png"},
    )
    assert isinstance(fragment.blocks[0], ImageBlock)
    assert fragment.blocks[0].alt_text == "图"
    assert dict(events) == {
        "markdown_image_title_ignored": 1,
        "markdown_link_title_ignored": 1,
    }
