from __future__ import annotations

from src.config.content_materials import (
    DocumentFragment,
    HeadingBlock,
    ImageBlock,
    InlineContent,
    InlineKind,
    ListBlock,
    ListItem,
    PageBreakBlock,
    ParagraphBlock,
    TableBlock,
    TableCell,
    TableRow,
)
from src.services.material_content.semantic_inventory import (
    inventory_document_fragment,
)


def test_semantic_inventory_is_deterministic_and_counts_nested_content() -> None:
    fragment = DocumentFragment(
        (
            HeadingBlock(1, (InlineContent(text="标题"),)),
            ParagraphBlock(
                (
                    InlineContent(text="正文"),
                    InlineContent(kind=InlineKind.FIELD_TOKEN, field_key="@text:name"),
                )
            ),
            ListBlock(False, 1, 0, (ListItem((InlineContent(text="项目"),)),)),
            TableBlock(
                (
                    TableRow(
                        (
                            TableCell(
                                (ParagraphBlock((InlineContent(text="A"),)),)
                            ),
                            TableCell(
                                (ParagraphBlock((InlineContent(text="B"),)),)
                            ),
                        )
                    ),
                )
            ),
            ImageBlock("image.png", alt_text="图"),
            PageBreakBlock(),
        )
    )

    first = inventory_document_fragment(fragment)
    second = inventory_document_fragment(DocumentFragment.from_dict(fragment.to_dict()))

    assert first == second
    assert dict(first.block_counts) == {
        "heading": 1,
        "image": 1,
        "list": 1,
        "page_break": 1,
        "paragraph": 1,
        "table": 1,
    }
    assert first.heading_count == 1
    assert first.list_item_count == 1
    assert first.table_cell_count == 2
    assert first.image_count == 1
    assert first.field_token_count == 1
    assert first.page_break_count == 1


def test_anonymous_wps_fixture_contains_required_compatibility_surfaces(tmp_path) -> None:
    from zipfile import ZipFile

    from lxml import etree

    from tests.content_docx_fixture_factory import build_anonymous_wps_compat_docx

    source = build_anonymous_wps_compat_docx(tmp_path / "anonymous-wps.docx")
    with ZipFile(source) as archive:
        assert "word/_rels/settings.xml.rels" in archive.namelist()
        document = etree.fromstring(archive.read("word/document.xml"))
        settings = etree.fromstring(archive.read("word/settings.xml"))

    assert len(document.xpath('.//*[local-name()="tab"]')) >= 2
    assert len(document.xpath('.//*[local-name()="anchor"]')) == 1
    assert len(document.xpath('.//*[local-name()="pict"]')) == 3
    assert len(document.xpath('.//*[local-name()="gridSpan"]')) == 1
    assert len(settings.xpath('.//*[local-name()="AlternateContent"]')) == 1
    assert len(settings.xpath('.//*[namespace-uri()="urn:schemas-microsoft-com:vml"]')) == 2
