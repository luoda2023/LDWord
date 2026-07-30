from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from lxml import etree
from PIL import Image
import pytest

from src.config.content_materials import (
    HeadingBlock,
    ImageBlock,
    InlineVerticalAlignment,
    InlineKind,
    ListBlock,
    ListNumberFormat,
    PageBreakBlock,
    ParagraphBlock,
    TableBlock,
)
from src.services.material_content.docx_importer import (
    DocxContentImportError,
    DocxImportDiagnosticCode,
    import_docx_package,
)
from src.shared.io.safe_docx_package import SafeDocxPackage


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
V_NS = "urn:schemas-microsoft-com:vml"


def _import_docx(source: Path):
    package = SafeDocxPackage.open(source.read_bytes())
    return import_docx_package(package).fragment


def _diagnostics(source: Path):
    try:
        _import_docx(source)
    except DocxContentImportError as exc:
        return exc.diagnostics
    return ()


def _image_file(path: Path, size: tuple[int, int] = (32, 18)) -> bytes:
    image = Image.new("RGB", size, (20, 80, 160))
    image.save(path, format="PNG")
    return path.read_bytes()


def _add_external_hyperlink(paragraph, href: str, text: str = "link") -> None:
    relationship_id = paragraph.part.relate_to(href, RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship_id)
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    bold = OxmlElement("w:b")
    properties.append(bold)
    text_node = OxmlElement("w:t")
    text_node.text = text
    run.extend((properties, text_node))
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def _rewrite_package(
    path: Path,
    *,
    replacements: dict[str, bytes] | None = None,
    additions: dict[str, bytes] | None = None,
    removals: set[str] | None = None,
) -> None:
    replacements = replacements or {}
    additions = additions or {}
    removals = removals or set()
    with ZipFile(path, "r") as archive:
        parts = {
            info.filename: archive.read(info)
            for info in archive.infolist()
            if not info.is_dir() and info.filename not in removals
        }
    parts.update(replacements)
    parts.update(additions)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for name, payload in parts.items():
            archive.writestr(name, payload)
    path.write_bytes(buffer.getvalue())


def _mutate_xml_part(path: Path, part: str, mutate) -> None:
    with ZipFile(path, "r") as archive:
        root = etree.fromstring(archive.read(part))
    mutate(root)
    _rewrite_package(
        path,
        replacements={
            part: etree.tostring(root, xml_declaration=True, encoding="UTF-8")
        },
    )


def _codes(error: DocxContentImportError) -> set[DocxImportDiagnosticCode]:
    return {item.code for item in error.diagnostics}


def _append_break(run, local_name: str, break_type: str = "") -> None:
    node = OxmlElement(f"w:{local_name}")
    if break_type:
        node.set(qn("w:type"), break_type)
    run._r.append(node)


def test_imports_tab_strikethrough_and_vertical_alignment(tmp_path: Path) -> None:
    source = tmp_path / "inline-formatting.docx"
    document = Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("before").add_tab()
    strike = paragraph.add_run("strike")
    strike.font.strike = True
    superscript = paragraph.add_run("super")
    superscript.font.superscript = True
    subscript = paragraph.add_run("sub")
    subscript.font.subscript = True
    document.save(source)

    imported = import_docx_package(SafeDocxPackage.open(source.read_bytes()))
    fragment = imported.fragment

    block = fragment.blocks[0]
    assert isinstance(block, ParagraphBlock)
    assert [inline.kind for inline in block.inlines] == [
        InlineKind.TEXT,
        InlineKind.TAB,
        InlineKind.TEXT,
        InlineKind.TEXT,
        InlineKind.TEXT,
    ]
    assert block.inlines[2].strikethrough is True
    assert (
        block.inlines[3].vertical_alignment
        is InlineVerticalAlignment.SUPERSCRIPT
    )
    assert (
        block.inlines[4].vertical_alignment
        is InlineVerticalAlignment.SUBSCRIPT
    )


def test_golden_semantic_ir_is_source_neutral_and_resource_closed(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "diagram.png"
    image_bytes = _image_file(image_path)
    image_digest = sha256(image_bytes).hexdigest()
    source = tmp_path / "technical-route.docx"

    doc = Document()
    doc.add_heading("技术路线", level=2)
    paragraph = doc.add_paragraph()
    paragraph.add_run("正文 ")
    bold = paragraph.add_run("粗体")
    bold.bold = True
    italic = paragraph.add_run("斜体")
    italic.italic = True
    underlined = paragraph.add_run("下划线")
    underlined.underline = True
    paragraph.add_run(" {{@text:com")
    paragraph.add_run("pany_name}}")
    breaks = doc.add_paragraph("第一行")
    _append_break(breaks.add_run(), "cr")
    breaks.add_run("第二行")
    _append_break(breaks.add_run(), "br")
    breaks.add_run("第三行")
    hyperlink_paragraph = doc.add_paragraph("参考：")
    _add_external_hyperlink(hyperlink_paragraph, "https://example.com/spec", "规范")
    doc.add_paragraph("条目甲", style="List Bullet")
    doc.add_paragraph("条目乙", style="List Bullet")
    doc.add_paragraph("步骤一", style="List Number")
    doc.add_paragraph("步骤二", style="List Number")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "A"
    table.cell(0, 1).text = "B"
    table.cell(1, 0).text = "C"
    table.cell(1, 1).text = ""
    _add_external_hyperlink(table.cell(1, 1).paragraphs[0], "mailto:qa@example.com", "邮件")
    doc.add_picture(str(image_path))
    doc.add_page_break()
    doc.save(source)
    source_before = sha256(source.read_bytes()).hexdigest()

    imported = import_docx_package(SafeDocxPackage.open(source.read_bytes()))
    fragment = imported.fragment

    assert sha256(source.read_bytes()).hexdigest() == source_before
    assert len(fragment.digest) == 64
    assert [type(block) for block in fragment.blocks] == [
        HeadingBlock,
        ParagraphBlock,
        ParagraphBlock,
        ParagraphBlock,
        ListBlock,
        ListBlock,
        TableBlock,
        ImageBlock,
        PageBreakBlock,
    ]
    heading = fragment.blocks[0]
    assert isinstance(heading, HeadingBlock)
    assert heading.level == 2
    assert heading.inlines[0].text == "技术路线"

    body = fragment.blocks[1]
    assert isinstance(body, ParagraphBlock)
    assert [(item.text, item.bold, item.italic, item.underline) for item in body.inlines[:4]] == [
        ("正文 ", False, False, False),
        ("粗体", True, False, False),
        ("斜体", False, True, False),
        ("下划线", False, False, True),
    ]
    assert body.inlines[-1].kind is InlineKind.FIELD_TOKEN
    assert body.inlines[-1].field_key == "@text:company_name"

    line_breaks = fragment.blocks[2]
    assert isinstance(line_breaks, ParagraphBlock)
    assert [item.kind for item in line_breaks.inlines] == [
        InlineKind.TEXT,
        InlineKind.SOFT_BREAK,
        InlineKind.TEXT,
        InlineKind.HARD_BREAK,
        InlineKind.TEXT,
    ]
    link_block = fragment.blocks[3]
    assert isinstance(link_block, ParagraphBlock)
    assert link_block.inlines[-1].kind is InlineKind.HYPERLINK
    assert link_block.inlines[-1].href == "https://example.com/spec"
    assert link_block.inlines[-1].bold is True

    unordered, ordered = fragment.blocks[4:6]
    assert isinstance(unordered, ListBlock) and not unordered.ordered
    assert [item.inlines[0].text for item in unordered.items] == ["条目甲", "条目乙"]
    assert isinstance(ordered, ListBlock) and ordered.ordered
    assert ordered.start == 1
    assert [item.inlines[0].text for item in ordered.items] == ["步骤一", "步骤二"]

    table_block = fragment.blocks[6]
    assert isinstance(table_block, TableBlock)
    assert [
        [cell.blocks[0].inlines[0].text for cell in row.cells]
        for row in table_block.rows
    ] == [
        ["A", "B"],
        ["C", "邮件"],
    ]
    assert (
        table_block.rows[1].cells[1].blocks[0].inlines[0].href
        == "mailto:qa@example.com"
    )

    image = fragment.blocks[7]
    assert isinstance(image, ImageBlock)
    expected_resource_id = f"sha256/{image_digest}.png"
    assert image.resource_id == expected_resource_id
    assert (image.width_px, image.height_px) == (43, 24)
    assert len(imported.resources) == 1
    resource = imported.resources[0]
    assert resource.resource_id == image.resource_id
    assert sha256(resource.payload).hexdigest() == image_digest
    assert len(resource.payload) == len(image_bytes)
    assert resource.media_type == "image/png"

    serialized = json.dumps(fragment.to_dict(), ensure_ascii=False, sort_keys=True)
    assert "rId" not in serialized
    assert "numId" not in serialized
    assert "styleId" not in serialized
    assert "word/media" not in serialized
    assert {
        block.resource_id
        for block in fragment.blocks
        if isinstance(block, ImageBlock)
    } == {item.resource_id for item in imported.resources}


@pytest.mark.parametrize("scheme", ["http", "https", "mailto"])
def test_external_hyperlink_protocol_allowlist_accepts_only_declared_schemes(
    tmp_path: Path,
    scheme: str,
) -> None:
    target = f"{scheme}://example.com/path" if scheme != "mailto" else "mailto:qa@example.com"
    source = tmp_path / f"allowed-{scheme}.docx"
    doc = Document()
    paragraph = doc.add_paragraph()
    _add_external_hyperlink(paragraph, target)
    doc.save(source)

    fragment = _import_docx(source)

    block = fragment.blocks[0]
    assert isinstance(block, ParagraphBlock)
    assert block.inlines[0].href == target


@pytest.mark.parametrize("target", ["file:///C:/secret.txt", "ftp://example.com/a", "javascript:x"])
def test_external_relationship_protocol_allowlist_blocks_other_schemes(
    tmp_path: Path,
    target: str,
) -> None:
    source = tmp_path / "denied-link.docx"
    doc = Document()
    paragraph = doc.add_paragraph()
    _add_external_hyperlink(paragraph, target)
    doc.save(source)

    with pytest.raises(DocxContentImportError) as raised:
        _import_docx(source)

    assert DocxImportDiagnosticCode.DISALLOWED_EXTERNAL_RELATIONSHIP in _codes(
        raised.value
    )
    assert all(item.part and item.path for item in raised.value.diagnostics)


def test_package_preflight_aggregates_complex_object_diagnostics(tmp_path: Path) -> None:
    source = tmp_path / "unsupported-objects.docx"
    doc = Document()
    doc.add_paragraph("safe")
    doc.save(source)

    def mutate(root: etree._Element) -> None:
        paragraph = root.find(f".//{{{W_NS}}}p")
        assert paragraph is not None
        for tag in (
            f"{{{W_NS}}}ins",
            f"{{{W_NS}}}sdt",
            f"{{{W_NS}}}fldSimple",
            f"{{{W_NS}}}altChunk",
            f"{{{W_NS}}}subDoc",
            f"{{{W_NS}}}commentRangeStart",
            f"{{{W_NS}}}footnoteReference",
            f"{{{W_NS}}}txbxContent",
            f"{{{W_NS}}}object",
            f"{{{M_NS}}}oMath",
            f"{{{MC_NS}}}AlternateContent",
            f"{{{WP_NS}}}anchor",
        ):
            paragraph.append(etree.Element(tag))
        run = etree.SubElement(paragraph, f"{{{W_NS}}}r")
        rpr = etree.SubElement(run, f"{{{W_NS}}}rPr")
        etree.SubElement(rpr, f"{{{W_NS}}}vanish")
        pict = etree.SubElement(paragraph, f"{{{W_NS}}}pict")
        etree.SubElement(pict, f"{{{V_NS}}}shape")
        graphic_data = etree.SubElement(paragraph, f"{{{A_NS}}}graphicData")
        graphic_data.set("uri", "http://schemas.openxmlformats.org/drawingml/2006/chart")

    _mutate_xml_part(source, "word/document.xml", mutate)

    with pytest.raises(DocxContentImportError) as raised:
        _import_docx(source)

    codes = _codes(raised.value)
    assert {
        DocxImportDiagnosticCode.CONTENT_CONTROL,
        DocxImportDiagnosticCode.WORD_FIELD,
        DocxImportDiagnosticCode.HIDDEN_TEXT,
        DocxImportDiagnosticCode.OMML,
        DocxImportDiagnosticCode.ALT_CHUNK,
        DocxImportDiagnosticCode.ALTERNATE_CONTENT,
        DocxImportDiagnosticCode.SUBDOCUMENT,
        DocxImportDiagnosticCode.FOOTNOTE_ENDNOTE,
        DocxImportDiagnosticCode.TEXT_BOX,
        DocxImportDiagnosticCode.OLE_OBJECT,
        DocxImportDiagnosticCode.CHART,
    } <= codes
    assert DocxImportDiagnosticCode.REVISION not in codes
    assert len(raised.value.diagnostics) >= 13
    assert all(item.part and item.path for item in raised.value.diagnostics)


def test_package_parts_block_active_content_and_notes_but_ignore_comment_metadata(
    tmp_path: Path,
) -> None:
    source = tmp_path / "unsupported-parts.docx"
    doc = Document()
    doc.add_paragraph("safe")
    doc.save(source)
    additions = {
        "word/vbaProject.bin": b"macro",
        "word/activeX/activeX1.bin": b"activex",
        "word/charts/chart1.xml": b"<chart/>",
        "word/diagrams/data1.xml": b"<diagram/>",
        "word/embeddings/object1.bin": b"ole",
        "word/comments.xml": f'<w:comments xmlns:w="{W_NS}"/>'.encode(),
        "word/footnotes.xml": f'<w:footnotes xmlns:w="{W_NS}"/>'.encode(),
        "word/endnotes.xml": f'<w:endnotes xmlns:w="{W_NS}"/>'.encode(),
    }
    _rewrite_package(source, additions=additions)

    diagnostics = _diagnostics(source)
    codes = {item.code for item in diagnostics}

    assert {
        DocxImportDiagnosticCode.MACRO,
        DocxImportDiagnosticCode.ACTIVE_X,
        DocxImportDiagnosticCode.CHART,
        DocxImportDiagnosticCode.SMART_ART,
        DocxImportDiagnosticCode.OLE_OBJECT,
        DocxImportDiagnosticCode.FOOTNOTE_ENDNOTE,
    } <= codes
    assert DocxImportDiagnosticCode.COMMENT not in codes


def _add_custom_numbering(
    doc: Document,
    levels: list[tuple[str, int]],
) -> int:
    numbering = doc.part.numbering_part.element
    abstract_ids = [
        int(node.get(qn("w:abstractNumId")))
        for node in numbering.findall(qn("w:abstractNum"))
    ]
    num_ids = [
        int(node.get(qn("w:numId"))) for node in numbering.findall(qn("w:num"))
    ]
    abstract_id = max(abstract_ids, default=0) + 1
    num_id = max(num_ids, default=0) + 1
    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(abstract_id))
    for level, (format_name, start) in enumerate(levels):
        level_node = OxmlElement("w:lvl")
        level_node.set(qn("w:ilvl"), str(level))
        start_node = OxmlElement("w:start")
        start_node.set(qn("w:val"), str(start))
        format_node = OxmlElement("w:numFmt")
        format_node.set(qn("w:val"), format_name)
        level_text = OxmlElement("w:lvlText")
        level_text.set(qn("w:val"), "•" if format_name == "bullet" else f"%{level + 1}.")
        level_node.extend((start_node, format_node, level_text))
        abstract.append(level_node)
    instance = OxmlElement("w:num")
    instance.set(qn("w:numId"), str(num_id))
    abstract_ref = OxmlElement("w:abstractNumId")
    abstract_ref.set(qn("w:val"), str(abstract_id))
    instance.append(abstract_ref)
    numbering.append(abstract)
    numbering.append(instance)
    return num_id


def _numbered_paragraph(doc: Document, text: str, num_id: int, level: int) -> None:
    paragraph = doc.add_paragraph(text)
    properties = paragraph._p.get_or_add_pPr()
    num_pr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), str(level))
    num_id_node = OxmlElement("w:numId")
    num_id_node.set(qn("w:val"), str(num_id))
    num_pr.extend((ilvl, num_id_node))
    properties.append(num_pr)


def test_lists_support_three_levels_and_restart_each_emitted_block(tmp_path: Path) -> None:
    source = tmp_path / "lists.docx"
    doc = Document()
    num_id = _add_custom_numbering(doc, [("decimal", 1), ("bullet", 1), ("decimal", 1)])
    _numbered_paragraph(doc, "L1-A", num_id, 0)
    _numbered_paragraph(doc, "L2", num_id, 1)
    _numbered_paragraph(doc, "L3", num_id, 2)
    _numbered_paragraph(doc, "L1-B", num_id, 0)
    doc.save(source)

    fragment = _import_docx(source)

    blocks = fragment.blocks
    assert all(isinstance(item, ListBlock) for item in blocks)
    assert [(item.ordered, item.nesting, item.start) for item in blocks] == [
        (True, 0, 1),
        (False, 1, 1),
        (True, 2, 1),
        (True, 0, 1),
    ]
    assert [item.items[0].inlines[0].text for item in blocks] == [
        "L1-A",
        "L2",
        "L3",
        "L1-B",
    ]


def test_nine_level_chinese_numbering_and_non_one_start_are_preserved(
    tmp_path: Path,
) -> None:
    source = tmp_path / "nine-level-chinese.docx"
    doc = Document()
    levels = [("decimal", 1)] * 8 + [("chineseCounting", 5)]
    num_id = _add_custom_numbering(doc, levels)
    _numbered_paragraph(doc, "第九层", num_id, 8)
    doc.save(source)

    fragment = _import_docx(source)

    block = fragment.blocks[0]
    assert isinstance(block, ListBlock)
    assert block.nesting == 8
    assert block.start == 5
    assert block.number_format is ListNumberFormat.CHINESE_COUNTING
    assert block.marker_template == "%9."


def test_lists_allow_nine_levels_and_non_one_start_but_block_unknown_format(
    tmp_path: Path,
) -> None:
    source = tmp_path / "bad-lists.docx"
    doc = Document()
    deep = _add_custom_numbering(
        doc,
        [("decimal", 1), ("bullet", 1), ("decimal", 1), ("bullet", 1)],
    )
    roman = _add_custom_numbering(doc, [("upperRoman", 1)])
    late = _add_custom_numbering(doc, [("decimal", 5)])
    _numbered_paragraph(doc, "too deep", deep, 3)
    _numbered_paragraph(doc, "roman", roman, 0)
    _numbered_paragraph(doc, "starts five", late, 0)
    doc.save(source)

    with pytest.raises(DocxContentImportError) as raised:
        _import_docx(source)

    codes = _codes(raised.value)
    assert DocxImportDiagnosticCode.UNSUPPORTED_LIST_FORMAT in codes
    assert DocxImportDiagnosticCode.LIST_NESTING_TOO_DEEP not in codes
    assert DocxImportDiagnosticCode.ORDERED_LIST_START not in codes


def test_inline_images_support_mixed_text_multiple_objects_and_resource_reuse(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "image.png"
    _image_file(image_path)
    source = tmp_path / "mixed-images.docx"
    doc = Document()
    mixed = doc.add_paragraph()
    mixed.add_run().add_picture(str(image_path))
    mixed.add_run("caption")
    multiple = doc.add_paragraph()
    multiple.add_run().add_picture(str(image_path))
    multiple.add_run().add_picture(str(image_path))
    doc.save(source)

    imported = import_docx_package(SafeDocxPackage.open(source.read_bytes()))
    fragment = imported.fragment

    assert [type(block) for block in fragment.blocks] == [
        ImageBlock,
        ParagraphBlock,
        ImageBlock,
        ImageBlock,
    ]
    assert fragment.blocks[1].inlines[0].text == "caption"
    resource_ids = {
        block.resource_id
        for block in fragment.blocks
        if isinstance(block, ImageBlock)
    }
    assert len(resource_ids) == 1
    assert len(imported.resources) == 1


def test_embedded_image_declared_media_type_must_match_its_bytes(tmp_path: Path) -> None:
    image_path = tmp_path / "image.png"
    _image_file(image_path)
    source = tmp_path / "media-mismatch.docx"
    doc = Document()
    doc.add_picture(str(image_path))
    doc.save(source)

    def lie_about_png(root: etree._Element) -> None:
        for default in root:
            if str(default.get("Extension", "")).casefold() == "png":
                default.set("ContentType", "image/jpeg")

    _mutate_xml_part(source, "[Content_Types].xml", lie_about_png)

    with pytest.raises(DocxContentImportError) as raised:
        _import_docx(source)
    assert DocxImportDiagnosticCode.IMAGE_MEDIA_TYPE_MISMATCH in _codes(raised.value)


def test_gif_is_blocked_before_it_can_reach_the_prepare_images_chain(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "animated.gif"
    Image.new("RGB", (12, 8), "white").save(image_path, format="GIF")
    source = tmp_path / "gif.docx"
    doc = Document()
    doc.add_picture(str(image_path))
    doc.save(source)

    with pytest.raises(DocxContentImportError) as raised:
        _import_docx(source)

    assert DocxImportDiagnosticCode.UNSUPPORTED_IMAGE_TYPE in _codes(raised.value)


@pytest.mark.parametrize(
    "external_target",
    ["https://example.com/image.png", "file:///C:/private/image.png"],
)
def test_linked_remote_and_local_images_are_both_blocked(
    tmp_path: Path,
    external_target: str,
) -> None:
    image_path = tmp_path / "image.png"
    _image_file(image_path)
    source = tmp_path / "linked-image.docx"
    doc = Document()
    doc.add_picture(str(image_path))
    doc.save(source)

    def mutate_relationships(root: etree._Element) -> None:
        for relationship in root:
            if str(relationship.get("Type", "")).endswith("/image"):
                relationship.set("Target", external_target)
                relationship.set("TargetMode", "External")

    def mutate_document(root: etree._Element) -> None:
        blip = root.find(f".//{{{A_NS}}}blip")
        assert blip is not None
        relationship_id = blip.attrib.pop(f"{{{R_NS}}}embed")
        blip.set(f"{{{R_NS}}}link", relationship_id)

    _mutate_xml_part(source, "word/_rels/document.xml.rels", mutate_relationships)
    _mutate_xml_part(source, "word/document.xml", mutate_document)

    with pytest.raises(DocxContentImportError) as raised:
        _import_docx(source)

    assert DocxImportDiagnosticCode.EXTERNAL_IMAGE in _codes(raised.value)


def test_orphan_image_relationship_and_media_are_never_silently_dropped(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "image.png"
    _image_file(image_path)
    source = tmp_path / "orphan-image.docx"
    doc = Document()
    doc.add_picture(str(image_path))
    doc.save(source)

    def remove_picture_paragraph(root: etree._Element) -> None:
        drawing = root.find(f".//{{{W_NS}}}drawing")
        assert drawing is not None
        paragraph = drawing
        while paragraph.getparent() is not None and paragraph.tag != f"{{{W_NS}}}p":
            paragraph = paragraph.getparent()
        paragraph.getparent().remove(paragraph)

    _mutate_xml_part(source, "word/document.xml", remove_picture_paragraph)

    diagnostics = _diagnostics(source)
    codes = {item.code for item in diagnostics}

    assert DocxImportDiagnosticCode.ORPHAN_RELATIONSHIP in codes
    assert DocxImportDiagnosticCode.ORPHAN_RESOURCE in codes


def test_tables_block_merges_and_nested_tables(tmp_path: Path) -> None:
    source = tmp_path / "bad-tables.docx"
    doc = Document()
    merged = doc.add_table(rows=2, cols=2)
    merged.cell(0, 0).merge(merged.cell(0, 1))
    nested_host = doc.add_table(rows=1, cols=1)
    nested_host.cell(0, 0).add_table(rows=1, cols=1)
    doc.save(source)

    with pytest.raises(DocxContentImportError) as raised:
        _import_docx(source)

    assert {
        DocxImportDiagnosticCode.NESTED_TABLE,
        DocxImportDiagnosticCode.UNSUPPORTED_TABLE_CELL,
    } <= _codes(raised.value)
    assert DocxImportDiagnosticCode.MERGED_TABLE_CELL not in _codes(raised.value)


def test_header_footer_internal_bookmark_and_complex_section_are_blocked(
    tmp_path: Path,
) -> None:
    source = tmp_path / "surface-blocks.docx"
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "secret header"
    paragraph = doc.add_paragraph()
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("w:anchor"), "inside")
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "jump"
    run.append(text)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)
    columns = doc.sections[0]._sectPr.find(qn("w:cols"))
    assert columns is not None
    columns.set(qn("w:num"), "2")
    doc.save(source)

    with pytest.raises(DocxContentImportError) as raised:
        _import_docx(source)

    assert {
        DocxImportDiagnosticCode.INTERNAL_BOOKMARK_LINK,
        DocxImportDiagnosticCode.COMPLEX_SECTION,
    } <= _codes(raised.value)
    assert DocxImportDiagnosticCode.HEADER_FOOTER_CONTENT not in _codes(raised.value)


def test_explicit_page_break_inside_text_preserves_block_order(tmp_path: Path) -> None:
    source = tmp_path / "page-break.docx"
    doc = Document()
    paragraph = doc.add_paragraph("before")
    paragraph.add_run().add_break(WD_BREAK.PAGE)
    paragraph.add_run("after")
    doc.save(source)

    fragment = _import_docx(source)

    assert [type(item) for item in fragment.blocks] == [
        ParagraphBlock,
        PageBreakBlock,
        ParagraphBlock,
    ]
    assert fragment.blocks[0].inlines[0].text == "before"
    assert fragment.blocks[2].inlines[0].text == "after"


def test_direct_page_break_before_is_preserved_and_content_anchor_is_blocked(
    tmp_path: Path,
) -> None:
    page_source = tmp_path / "page-break-before.docx"
    doc = Document()
    paragraph = doc.add_paragraph("new page")
    paragraph._p.get_or_add_pPr().append(OxmlElement("w:pageBreakBefore"))
    doc.save(page_source)

    fragment = _import_docx(page_source)

    assert [type(item) for item in fragment.blocks] == [
        PageBreakBlock,
        ParagraphBlock,
    ]

    token_source = tmp_path / "content-token.docx"
    token_doc = Document()
    token_doc.add_paragraph("{{@file:nested}}")
    token_doc.save(token_source)

    with pytest.raises(DocxContentImportError) as raised:
        _import_docx(token_source)
    assert DocxImportDiagnosticCode.UNSUPPORTED_CONTENT_TOKEN in _codes(raised.value)


def test_source_is_read_only_even_when_validation_fails(tmp_path: Path) -> None:
    source = tmp_path / "read-only-source.docx"
    doc = Document()
    run = doc.add_paragraph().add_run("hidden")
    run.font.hidden = True
    doc.save(source)
    before = source.read_bytes()

    diagnostics = _diagnostics(source)

    assert source.read_bytes() == before
    assert DocxImportDiagnosticCode.HIDDEN_TEXT in {item.code for item in diagnostics}
