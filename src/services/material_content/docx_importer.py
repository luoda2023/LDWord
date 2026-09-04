"""Strict, source-neutral DOCX semantic importer.

The importer reads an OOXML package into the shared content-material IR.  It
never opens or mutates a target document and never copies source XML, style
ids, numbering ids, or relationship ids into the returned fragment.

Version one intentionally has a narrow allow-list.  Package preflight walks
all XML parts and relationships before a fragment may be returned; unsupported
objects are reported as typed diagnostics rather than silently discarded.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from enum import Enum
from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath
import posixpath
import re
import warnings
from typing import Any, Iterable, Sequence
from urllib.parse import urlsplit

from lxml import etree
from PIL import Image, UnidentifiedImageError

from src.config.content_materials import (
    DocumentFragment,
    HeadingBlock,
    ImageBlock,
    InlineContent,
    InlineKind,
    InlineVerticalAlignment,
    ListBlock,
    ListItem,
    ListNumberFormat,
    PageBreakBlock,
    ParagraphBlock,
    TableBlock,
    TableCell,
    TableRow,
)
from src.shared.io.safe_docx_package import (
    DocxPackageError,
    SafeDocxPackage,
)
from src.services.material_content.metafile_converter import (
    MetafileConversionError,
    convert_metafile_to_png,
)
from src.shared.engine.material_token_contract import (
    MaterialTokenKind,
    parse_material_token,
)


DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
_MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_V_NS = "urn:schemas-microsoft-com:vml"
_O_NS = "urn:schemas-microsoft-com:office:office"

_NS = {
    "w": _W_NS,
    "r": _R_NS,
    "wp": _WP_NS,
    "a": _A_NS,
    "pic": _PIC_NS,
    "mc": _MC_NS,
    "m": _M_NS,
    "v": _V_NS,
    "o": _O_NS,
}

_DOCUMENT_PART = "word/document.xml"
_DOCUMENT_RELS_PART = "word/_rels/document.xml.rels"
_STYLES_PART = "word/styles.xml"
_NUMBERING_PART = "word/numbering.xml"
_CONTENT_TYPES_PART = "[Content_Types].xml"

_FIELD_TOKEN_PATTERN = re.compile(r"\{\{([^{}\r\n]+)\}\}")
_ALLOWED_HYPERLINK_SCHEMES = frozenset({"http", "https", "mailto"})

_MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/webp": ".webp",
}
_PIL_MEDIA_TYPES = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "BMP": "image/bmp",
    "TIFF": "image/tiff",
    "WEBP": "image/webp",
}
_METAFILE_MEDIA_TYPES = {
    "image/wmf",
    "image/x-wmf",
    "image/emf",
    "image/x-emf",
}
_MAX_IMAGE_PIXELS = 40_000_000


class DocxImportDiagnosticCode(str, Enum):
    INVALID_PACKAGE = "invalid_package"
    INVALID_PACKAGE_PATH = "invalid_package_path"
    DUPLICATE_PACKAGE_PART = "duplicate_package_part"
    MISSING_PART = "missing_part"
    MALFORMED_XML = "malformed_xml"
    DANGLING_RELATIONSHIP = "dangling_relationship"
    ORPHAN_RELATIONSHIP = "orphan_relationship"
    ORPHAN_RESOURCE = "orphan_resource"
    DISALLOWED_EXTERNAL_RELATIONSHIP = "disallowed_external_relationship"
    EXTERNAL_IMAGE = "external_image"
    HEADER_FOOTER_CONTENT = "header_footer_content"
    COMPLEX_SECTION = "complex_section"
    FLOATING_IMAGE = "floating_image"
    TEXT_BOX = "text_box"
    SHAPE = "shape"
    SMART_ART = "smart_art"
    CHART = "chart"
    OLE_OBJECT = "ole_object"
    MACRO = "macro"
    ACTIVE_X = "active_x"
    REVISION = "revision"
    COMMENT = "comment"
    HIDDEN_TEXT = "hidden_text"
    CONTENT_CONTROL = "content_control"
    WORD_FIELD = "word_field"
    FOOTNOTE_ENDNOTE = "footnote_endnote"
    INTERNAL_BOOKMARK_LINK = "internal_bookmark_link"
    OMML = "omml"
    ALT_CHUNK = "alt_chunk"
    VML = "vml"
    ALTERNATE_CONTENT = "alternate_content"
    SUBDOCUMENT = "subdocument"
    UNSUPPORTED_BODY_OBJECT = "unsupported_body_object"
    UNSUPPORTED_INLINE = "unsupported_inline"
    UNSUPPORTED_BREAK = "unsupported_break"
    UNSUPPORTED_CONTENT_TOKEN = "unsupported_content_token"
    UNSUPPORTED_LIST_FORMAT = "unsupported_list_format"
    LIST_NESTING_TOO_DEEP = "list_nesting_too_deep"
    ORDERED_LIST_START = "ordered_list_start"
    COMPLEX_NUMBERING = "complex_numbering"
    MIXED_IMAGE_PARAGRAPH = "mixed_image_paragraph"
    MULTIPLE_INLINE_IMAGES = "multiple_inline_images"
    INVALID_IMAGE = "invalid_image"
    UNSUPPORTED_IMAGE_TYPE = "unsupported_image_type"
    IMAGE_MEDIA_TYPE_MISMATCH = "image_media_type_mismatch"
    NESTED_TABLE = "nested_table"
    MERGED_TABLE_CELL = "merged_table_cell"
    NON_RECTANGULAR_TABLE = "non_rectangular_table"
    UNSUPPORTED_TABLE_CELL = "unsupported_table_cell"


@dataclass(frozen=True, slots=True)
class DocxImportDiagnostic:
    code: DocxImportDiagnosticCode
    message: str
    part: str
    path: str


class DocxContentImportError(ValueError):
    """Raised when a DOCX cannot be represented by the v1 semantic IR."""

    def __init__(self, diagnostics: Sequence[DocxImportDiagnostic]):
        self.diagnostics = tuple(diagnostics)
        summary = "; ".join(
            f"{item.code.value} [{item.part}{item.path}]: {item.message}"
            for item in self.diagnostics[:8]
        )
        if len(self.diagnostics) > 8:
            summary += f"; ... and {len(self.diagnostics) - 8} more"
        super().__init__(summary or "DOCX semantic import failed")

    @property
    def codes(self) -> tuple[DocxImportDiagnosticCode, ...]:
        return tuple(item.code for item in self.diagnostics)


class _ImageInspectionError(ValueError):
    def __init__(self, code: DocxImportDiagnosticCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class ImportedDocxResource:
    resource_id: str
    media_type: str
    payload: bytes


@dataclass(frozen=True, slots=True)
class ImportedDocxContent:
    fragment: DocumentFragment
    resources: tuple[ImportedDocxResource, ...]
    normalized_counts: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class _Relationship:
    relationship_id: str
    relationship_type: str
    target: str
    target_mode: str
    source_part: str
    rels_part: str
    resolved_part: str | None

    @property
    def external(self) -> bool:
        return self.target_mode.casefold() == "external"

    @property
    def kind(self) -> str:
        return self.relationship_type.rstrip("/").rsplit("/", 1)[-1]


@dataclass(frozen=True, slots=True)
class _TextFormat:
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    vertical_alignment: InlineVerticalAlignment = InlineVerticalAlignment.BASELINE


@dataclass(frozen=True, slots=True)
class _InlineAtom:
    kind: str
    text: str = ""
    formatting: _TextFormat = _TextFormat()
    href: str = ""
    image: ImageBlock | None = None


@dataclass(slots=True)
class _TableCellDraft:
    blocks: list[Any]
    rowspan: int = 1
    colspan: int = 1

    def freeze(self) -> TableCell:
        return TableCell(
            blocks=tuple(self.blocks),
            rowspan=self.rowspan,
            colspan=self.colspan,
        )


@dataclass(frozen=True, slots=True)
class _ListSemantics:
    ordered: bool
    nesting: int
    source_num_id: str
    start: int
    number_format: ListNumberFormat
    marker_template: str


@dataclass(frozen=True, slots=True)
class _StyleInfo:
    style_id: str
    based_on: str
    style_type: str
    element: etree._Element


class _DiagnosticCollector:
    def __init__(self) -> None:
        self._items: list[DocxImportDiagnostic] = []
        self._keys: set[tuple[DocxImportDiagnosticCode, str, str, str]] = set()

    def add(
        self,
        code: DocxImportDiagnosticCode,
        message: str,
        part: str,
        path: str,
    ) -> None:
        normalized_part = part or "package"
        normalized_path = path or "/"
        key = (code, normalized_part, normalized_path, message)
        if key in self._keys:
            return
        self._keys.add(key)
        self._items.append(
            DocxImportDiagnostic(
                code=code,
                message=message,
                part=normalized_part,
                path=normalized_path,
            )
        )

    @property
    def items(self) -> tuple[DocxImportDiagnostic, ...]:
        return tuple(self._items)


class _Package:
    def __init__(
        self,
        source: bytes | SafeDocxPackage,
        diagnostics: _DiagnosticCollector,
    ):
        self.diagnostics = diagnostics
        self.parts: dict[str, bytes] = {}
        self.xml: dict[str, etree._Element] = {}
        self.relationships_by_source: dict[str, dict[str, _Relationship]] = {}
        self.default_content_types: dict[str, str] = {}
        self.override_content_types: dict[str, str] = {}
        self.safe_package: SafeDocxPackage | None = None
        self._read_zip(source)
        self._parse_xml_parts()
        self._read_content_types()
        self._read_relationships()

    def _read_zip(self, source: bytes | SafeDocxPackage) -> None:
        try:
            package = (
                source
                if isinstance(source, SafeDocxPackage)
                else SafeDocxPackage.open(source)
            )
            self.safe_package = package
            self.parts.update(package.parts)
        except DocxPackageError as exc:
            code = {
                "zip_unsafe_member_path": DocxImportDiagnosticCode.INVALID_PACKAGE_PATH,
                "zip_duplicate_member": DocxImportDiagnosticCode.DUPLICATE_PACKAGE_PART,
            }.get(exc.code, DocxImportDiagnosticCode.INVALID_PACKAGE)
            self.diagnostics.add(
                code,
                str(exc),
                exc.part or "package",
                "/",
            )

        for required in (_CONTENT_TYPES_PART, _DOCUMENT_PART):
            if required not in self.parts:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.MISSING_PART,
                    f"required OOXML part is missing: {required}",
                    "package",
                    f"/{required}",
                )

    def _parse_xml_parts(self) -> None:
        for part, payload in self.parts.items():
            if not (part.endswith(".xml") or part.endswith(".rels")):
                continue
            try:
                if self.safe_package is None:
                    raise DocxPackageError(
                        "zip_invalid",
                        "DOCX package is unavailable",
                        part=part,
                    )
                self.xml[part] = self.safe_package.parse_xml(part)
            except DocxPackageError as exc:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.MALFORMED_XML,
                    str(exc),
                    part,
                    "/",
                )

    def _read_content_types(self) -> None:
        root = self.xml.get(_CONTENT_TYPES_PART)
        if root is None:
            return
        for child in root:
            local = _local_name(child)
            if local == "Default":
                extension = str(child.get("Extension", "")).casefold()
                media_type = str(child.get("ContentType", ""))
                if extension and media_type:
                    self.default_content_types[extension] = media_type
            elif local == "Override":
                part_name = str(child.get("PartName", "")).lstrip("/")
                media_type = str(child.get("ContentType", ""))
                if part_name and media_type:
                    self.override_content_types[part_name] = media_type

    def _read_relationships(self) -> None:
        for rels_part, root in self.xml.items():
            if not rels_part.endswith(".rels"):
                continue
            source_part = _source_part_for_rels(rels_part)
            relationships: dict[str, _Relationship] = {}
            for relationship in root:
                if _local_name(relationship) != "Relationship":
                    continue
                relationship_id = str(relationship.get("Id", ""))
                relationship_type = str(relationship.get("Type", ""))
                target = str(relationship.get("Target", ""))
                target_mode = str(relationship.get("TargetMode", ""))
                path = _element_path(relationship)
                if not relationship_id or relationship_id in relationships:
                    self.diagnostics.add(
                        DocxImportDiagnosticCode.DANGLING_RELATIONSHIP,
                        "relationship id is missing or duplicated",
                        rels_part,
                        path,
                    )
                    continue
                resolved_part: str | None = None
                if target_mode.casefold() != "external":
                    resolved_part = _resolve_relationship_target(source_part, target)
                    if resolved_part is None:
                        self.diagnostics.add(
                            DocxImportDiagnosticCode.INVALID_PACKAGE_PATH,
                            f"relationship target escapes the package: {target!r}",
                            rels_part,
                            path,
                        )
                    elif resolved_part not in self.parts:
                        self.diagnostics.add(
                            DocxImportDiagnosticCode.DANGLING_RELATIONSHIP,
                            f"relationship target is missing: {resolved_part}",
                            rels_part,
                            path,
                        )
                item = _Relationship(
                    relationship_id=relationship_id,
                    relationship_type=relationship_type,
                    target=target,
                    target_mode=target_mode,
                    source_part=source_part,
                    rels_part=rels_part,
                    resolved_part=resolved_part,
                )
                relationships[relationship_id] = item
                self._validate_external_relationship(item, path)
            self.relationships_by_source[source_part] = relationships

    def _validate_external_relationship(
        self,
        relationship: _Relationship,
        path: str,
    ) -> None:
        if not relationship.external:
            return
        if (
            relationship.source_part == "word/settings.xml"
            and relationship.kind == "attachedTemplate"
        ):
            return
        if relationship.kind == "image":
            self.diagnostics.add(
                DocxImportDiagnosticCode.EXTERNAL_IMAGE,
                "linked local or remote images are not importable",
                relationship.rels_part,
                path,
            )
            return
        if relationship.kind != "hyperlink" or not _allowed_hyperlink(
            relationship.target
        ):
            self.diagnostics.add(
                DocxImportDiagnosticCode.DISALLOWED_EXTERNAL_RELATIONSHIP,
                f"external relationship is not an allowed http/https/mailto link: "
                f"{relationship.target!r}",
                relationship.rels_part,
                path,
            )

    def media_type(self, part: str) -> str:
        override = self.override_content_types.get(part)
        if override:
            return override
        extension = PurePosixPath(part).suffix.lstrip(".").casefold()
        return self.default_content_types.get(extension, "")


class _StyleCatalog:
    def __init__(self, root: etree._Element | None):
        self.root = root
        self.styles: dict[str, _StyleInfo] = {}
        if root is not None:
            for style in root.findall("w:style", namespaces=_NS):
                style_id = _w_attr(style, "styleId")
                if not style_id:
                    continue
                based_on_node = style.find("w:basedOn", namespaces=_NS)
                self.styles[style_id] = _StyleInfo(
                    style_id=style_id,
                    based_on=_w_attr(based_on_node, "val") if based_on_node is not None else "",
                    style_type=_w_attr(style, "type"),
                    element=style,
                )

    def paragraph_style_id(self, paragraph: etree._Element) -> str:
        node = paragraph.find("w:pPr/w:pStyle", namespaces=_NS)
        return _w_attr(node, "val") if node is not None else ""

    def heading_level(self, paragraph: etree._Element) -> int | None:
        direct = paragraph.find("w:pPr/w:outlineLvl", namespaces=_NS)
        if direct is not None:
            value = _int_attr(direct, "val")
            return value + 1 if value is not None and 0 <= value <= 8 else None
        for style in reversed(self._style_chain(self.paragraph_style_id(paragraph))):
            node = style.element.find("w:pPr/w:outlineLvl", namespaces=_NS)
            if node is not None:
                value = _int_attr(node, "val")
                return value + 1 if value is not None and 0 <= value <= 8 else None
        return None

    def num_properties(self, paragraph: etree._Element) -> tuple[str, int] | None:
        num_id = ""
        level: int | None = None
        for style in self._style_chain(self.paragraph_style_id(paragraph)):
            node = style.element.find("w:pPr/w:numPr", namespaces=_NS)
            if node is not None:
                num_id, level = _merge_num_properties(node, num_id, level)
        direct = paragraph.find("w:pPr/w:numPr", namespaces=_NS)
        if direct is not None:
            num_id, level = _merge_num_properties(direct, num_id, level)
        if not num_id or num_id == "0":
            return None
        return num_id, 0 if level is None else level

    def run_format(
        self,
        paragraph: etree._Element,
        run: etree._Element,
    ) -> _TextFormat:
        # Document defaults and paragraph-style appearance belong to the
        # target template. Only character-style and direct run formatting are
        # semantic inline facts in Content IR.
        formatting = _TextFormat()
        r_style_node = run.find("w:rPr/w:rStyle", namespaces=_NS)
        r_style_id = _w_attr(r_style_node, "val") if r_style_node is not None else ""
        for style in self._style_chain(r_style_id):
            formatting = _apply_rpr(
                formatting,
                style.element.find("w:rPr", namespaces=_NS),
            )
        return _apply_rpr(formatting, run.find("w:rPr", namespaces=_NS))

    def _style_chain(self, style_id: str) -> tuple[_StyleInfo, ...]:
        chain: list[_StyleInfo] = []
        seen: set[str] = set()
        current = style_id
        while current and current not in seen:
            seen.add(current)
            info = self.styles.get(current)
            if info is None:
                break
            chain.append(info)
            current = info.based_on
        chain.reverse()
        return tuple(chain)


class _NumberingCatalog:
    def __init__(
        self,
        root: etree._Element | None,
        diagnostics: _DiagnosticCollector,
    ):
        self.root = root
        self.diagnostics = diagnostics
        self.abstracts: dict[str, etree._Element] = {}
        self.instances: dict[str, etree._Element] = {}
        if root is None:
            return
        for abstract in root.findall("w:abstractNum", namespaces=_NS):
            abstract_id = _w_attr(abstract, "abstractNumId")
            if abstract_id:
                self.abstracts[abstract_id] = abstract
        for instance in root.findall("w:num", namespaces=_NS):
            num_id = _w_attr(instance, "numId")
            if num_id:
                self.instances[num_id] = instance

    def semantics(
        self,
        num_id: str,
        level: int,
        element: etree._Element,
    ) -> _ListSemantics | None:
        path = _element_path(element)
        if level > 8:
            self.diagnostics.add(
                DocxImportDiagnosticCode.LIST_NESTING_TOO_DEEP,
                f"list level {level + 1} exceeds the nine-level Word limit",
                _DOCUMENT_PART,
                path,
            )
            return None
        instance = self.instances.get(num_id)
        if instance is None:
            self.diagnostics.add(
                DocxImportDiagnosticCode.DANGLING_RELATIONSHIP,
                f"paragraph references missing numId {num_id}",
                _NUMBERING_PART,
                f"/w:numbering/w:num[@w:numId='{num_id}']",
            )
            return None
        abstract_ref = instance.find("w:abstractNumId", namespaces=_NS)
        abstract_id = _w_attr(abstract_ref, "val") if abstract_ref is not None else ""
        abstract = self.abstracts.get(abstract_id)
        if abstract is None:
            self.diagnostics.add(
                DocxImportDiagnosticCode.DANGLING_RELATIONSHIP,
                f"numId {num_id} references missing abstractNumId {abstract_id}",
                _NUMBERING_PART,
                _element_path(instance),
            )
            return None
        if abstract.find("w:numStyleLink", namespaces=_NS) is not None or abstract.find(
            "w:styleLink", namespaces=_NS
        ) is not None:
            self.diagnostics.add(
                DocxImportDiagnosticCode.COMPLEX_NUMBERING,
                "style-linked numbering is outside the v1 list contract",
                _NUMBERING_PART,
                _element_path(abstract),
            )
            return None
        if abstract.find(".//w:lvlPicBulletId", namespaces=_NS) is not None or (
            self.root is not None
            and self.root.find("w:numPicBullet", namespaces=_NS) is not None
        ):
            self.diagnostics.add(
                DocxImportDiagnosticCode.COMPLEX_NUMBERING,
                "picture bullets are outside the v1 list contract",
                _NUMBERING_PART,
                _element_path(abstract),
            )
            return None
        level_node = abstract.find(f"w:lvl[@w:ilvl='{level}']", namespaces=_NS)
        override = instance.find(f"w:lvlOverride[@w:ilvl='{level}']", namespaces=_NS)
        if override is not None:
            override_level = override.find("w:lvl", namespaces=_NS)
            if override_level is not None:
                level_node = override_level
        if level_node is None:
            self.diagnostics.add(
                DocxImportDiagnosticCode.UNSUPPORTED_LIST_FORMAT,
                f"numbering definition has no level {level}",
                _NUMBERING_PART,
                _element_path(abstract),
            )
            return None
        format_node = level_node.find("w:numFmt", namespaces=_NS)
        format_name = _w_attr(format_node, "val") if format_node is not None else ""
        supported_formats = {
            item.value: item
            for item in ListNumberFormat
        }
        number_format = supported_formats.get(format_name)
        if number_format is None:
            self.diagnostics.add(
                DocxImportDiagnosticCode.UNSUPPORTED_LIST_FORMAT,
                f"unsupported numbering format {format_name!r}",
                _NUMBERING_PART,
                _element_path(level_node),
            )
            return None
        start = 1
        start_node = level_node.find("w:start", namespaces=_NS)
        if start_node is not None and _int_attr(start_node, "val") is not None:
            start = int(_int_attr(start_node, "val") or 0)
        if override is not None:
            start_override = override.find("w:startOverride", namespaces=_NS)
            if start_override is not None and _int_attr(start_override, "val") is not None:
                start = int(_int_attr(start_override, "val") or 0)
        if start < 1:
            self.diagnostics.add(
                DocxImportDiagnosticCode.ORDERED_LIST_START,
                f"list start must be positive, got {start}",
                _NUMBERING_PART,
                _element_path(override if override is not None else level_node),
            )
            return None
        level_text = level_node.find("w:lvlText", namespaces=_NS)
        level_pattern = _w_attr(level_text, "val") if level_text is not None else ""
        if number_format is not ListNumberFormat.BULLET and f"%{level + 1}" not in level_pattern:
            self.diagnostics.add(
                DocxImportDiagnosticCode.UNSUPPORTED_LIST_FORMAT,
                "numbered list level text must contain its level placeholder",
                _NUMBERING_PART,
                _element_path(level_node),
            )
            return None
        return _ListSemantics(
            ordered=number_format is not ListNumberFormat.BULLET,
            nesting=level,
            source_num_id=num_id,
            start=start,
            number_format=number_format,
            marker_template=level_pattern,
        )


class _DocxSemanticImporter:
    def __init__(self, source: bytes | SafeDocxPackage):
        self.diagnostics = _DiagnosticCollector()
        self.package = _Package(source, self.diagnostics)
        self.document = self.package.xml.get(_DOCUMENT_PART)
        self.styles = _StyleCatalog(self.package.xml.get(_STYLES_PART))
        self.numbering = _NumberingCatalog(
            self.package.xml.get(_NUMBERING_PART), self.diagnostics
        )
        self.document_relationships = self.package.relationships_by_source.get(
            _DOCUMENT_PART, {}
        )
        self.used_hyperlink_relationships: set[str] = set()
        self.used_image_relationships: set[str] = set()
        self.used_image_parts: set[str] = set()
        self.resources: dict[str, ImportedDocxResource] = {}
        self.normalized_counts: Counter[str] = Counter()

    def import_fragment(
        self,
    ) -> DocumentFragment:
        self._normalize_visible_content()
        self._validate_package_features()
        blocks = self._parse_body() if self.document is not None else []
        self._validate_relationship_usage(blocks)
        if self.diagnostics.items:
            raise DocxContentImportError(self.diagnostics.items)
        return DocumentFragment(blocks=tuple(blocks))

    def _normalize_visible_content(self) -> None:
        if self.document is None:
            return
        alternate_nodes = list(
            self.document.findall(".//mc:AlternateContent", namespaces=_NS)
        )
        for alternate in reversed(alternate_nodes):
            if alternate.getparent() is None:
                continue
            selected = alternate.find("mc:Choice", namespaces=_NS)
            if selected is None:
                selected = alternate.find("mc:Fallback", namespaces=_NS)
            if selected is None:
                continue
            _unwrap_element(alternate, tuple(selected))
            self.normalized_counts["alternate_content_resolved"] += 1
        deleted_tags = ("del", "moveFrom")
        for local in deleted_tags:
            removed = 0
            for element in list(
                self.document.findall(f".//w:{local}", namespaces=_NS)
            ):
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)
                    removed += 1
            if removed:
                self.normalized_counts["revision_final_view"] += removed

        for local in ("ins", "moveTo"):
            unwrapped = 0
            elements = list(
                self.document.findall(f".//w:{local}", namespaces=_NS)
            )
            for element in reversed(elements):
                if element.getparent() is not None:
                    _unwrap_element(element, tuple(element))
                    unwrapped += 1
            if unwrapped:
                self.normalized_counts["revision_final_view"] += unwrapped

        revision_metadata = {
            "moveFromRangeStart",
            "moveFromRangeEnd",
            "moveToRangeStart",
            "moveToRangeEnd",
            "cellIns",
            "cellDel",
            "cellMerge",
            "numberingChange",
            "pPrChange",
            "rPrChange",
            "tblPrChange",
            "tblGridChange",
            "trPrChange",
            "tcPrChange",
            "sectPrChange",
        }
        removed_metadata = 0
        for element in list(self.document.iter()):
            if _namespace(element) == _W_NS and _local_name(element) in revision_metadata:
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)
                    removed_metadata += 1
        if removed_metadata:
            self.normalized_counts["revision_metadata_removed"] += removed_metadata

        controls = list(self.document.findall(".//w:sdt", namespaces=_NS))
        for control in reversed(controls):
            if control.getparent() is None:
                continue
            content = control.find("w:sdtContent", namespaces=_NS)
            if content is None:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.CONTENT_CONTROL,
                    "content control has no deterministic visible content",
                    _DOCUMENT_PART,
                    _element_path(control),
                )
                continue
            _unwrap_element(control, tuple(content))
            self.normalized_counts["content_control_unwrapped"] += 1

        fields = list(self.document.findall(".//w:fldSimple", namespaces=_NS))
        for field in reversed(fields):
            if field.getparent() is None:
                continue
            children = tuple(field)
            if not children:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.WORD_FIELD,
                    "Word field has no cached visible result",
                    _DOCUMENT_PART,
                    _element_path(field),
                )
                continue
            _unwrap_element(field, children)
            self.normalized_counts["field_cached_result"] += 1

        for parent in self.document.xpath(".//w:p | .//w:hyperlink", namespaces=_NS):
            self._normalize_complex_fields(parent)

    def _normalize_complex_fields(self, parent: etree._Element) -> None:
        children = list(parent)
        events: list[tuple[int, str]] = []
        state = ""
        result_visible = False
        field_count = 0
        valid = True
        for index, child in enumerate(children):
            if _local_name(child) != "r":
                if state:
                    valid = False
                continue
            controls = child.findall("w:fldChar", namespaces=_NS)
            if len(controls) > 1:
                valid = False
                continue
            field_type = _w_attr(controls[0], "fldCharType") if controls else ""
            if field_type:
                events.append((index, field_type))
                if field_type == "begin":
                    if state:
                        valid = False
                    state = "instruction"
                    field_count += 1
                    result_visible = False
                elif field_type == "separate":
                    if state != "instruction":
                        valid = False
                    state = "result"
                elif field_type == "end":
                    if state != "result" or not result_visible:
                        valid = False
                    state = ""
                else:
                    valid = False
                continue
            if state == "result" and _run_has_visible_content(child):
                result_visible = True
        if not events:
            return
        if state or not valid:
            self.diagnostics.add(
                DocxImportDiagnosticCode.WORD_FIELD,
                "complex Word field has no deterministic cached result",
                _DOCUMENT_PART,
                _element_path(parent),
            )
            return

        state = ""
        for child in list(parent):
            if _local_name(child) != "r":
                continue
            control = child.find("w:fldChar", namespaces=_NS)
            field_type = _w_attr(control, "fldCharType") if control is not None else ""
            if field_type == "begin":
                state = "instruction"
            elif field_type == "separate":
                state = "result"
            elif field_type == "end":
                state = ""
            keep = state == "result" and not field_type
            if control is not None:
                child.remove(control)
            if not keep:
                parent.remove(child)
        self.normalized_counts["field_cached_result"] += field_count

    def _validate_package_features(self) -> None:
        self._validate_part_kinds()
        if self.document is not None:
            self._scan_unsupported_xml(_DOCUMENT_PART, self.document)
        self._validate_sections()

    def _validate_part_kinds(self) -> None:
        for part, payload in self.package.parts.items():
            lowered = part.casefold()
            media_type = self.package.media_type(part).casefold()
            if "vbaproject" in lowered or "macroenabled" in media_type or "vba" in media_type:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.MACRO,
                    "macro-enabled content is not importable",
                    part,
                    "/",
                )
            if "/activex/" in f"/{lowered}" or "activex" in media_type:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.ACTIVE_X,
                    "ActiveX content is not importable",
                    part,
                    "/",
                )
            if lowered.startswith("word/charts/") or "drawingml.chart" in media_type:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.CHART,
                    "chart parts are not importable",
                    part,
                    "/",
                )
            if lowered.startswith("word/diagrams/"):
                self.diagnostics.add(
                    DocxImportDiagnosticCode.SMART_ART,
                    "SmartArt/diagram parts are not importable",
                    part,
                    "/",
                )
            if lowered.startswith("word/embeddings/"):
                self.diagnostics.add(
                    DocxImportDiagnosticCode.OLE_OBJECT,
                    "embedded OLE/package parts are not importable",
                    part,
                    "/",
                )
            if lowered in {"word/footnotes.xml", "word/endnotes.xml"}:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.FOOTNOTE_ENDNOTE,
                    "footnotes and endnotes are not importable",
                    part,
                    "/",
                )

        unsupported_relationship_codes = {
            "chart": DocxImportDiagnosticCode.CHART,
            "diagramData": DocxImportDiagnosticCode.SMART_ART,
            "diagramLayout": DocxImportDiagnosticCode.SMART_ART,
            "diagramColors": DocxImportDiagnosticCode.SMART_ART,
            "diagramQuickStyle": DocxImportDiagnosticCode.SMART_ART,
            "oleObject": DocxImportDiagnosticCode.OLE_OBJECT,
            "package": DocxImportDiagnosticCode.OLE_OBJECT,
            "control": DocxImportDiagnosticCode.ACTIVE_X,
            "vbaProject": DocxImportDiagnosticCode.MACRO,
            "footnotes": DocxImportDiagnosticCode.FOOTNOTE_ENDNOTE,
            "endnotes": DocxImportDiagnosticCode.FOOTNOTE_ENDNOTE,
        }
        for relationships in self.package.relationships_by_source.values():
            for relationship in relationships.values():
                code = unsupported_relationship_codes.get(relationship.kind)
                if code is not None:
                    self.diagnostics.add(
                        code,
                        f"unsupported {relationship.kind} relationship",
                        relationship.rels_part,
                        f"/Relationships/Relationship[@Id='{relationship.relationship_id}']",
                    )

    def _scan_unsupported_xml(self, part: str, root: etree._Element) -> None:
        tag_codes = {
            f"{{{_W_NS}}}ins": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}del": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}moveFrom": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}moveTo": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}moveFromRangeStart": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}moveFromRangeEnd": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}moveToRangeStart": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}moveToRangeEnd": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}delText": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}cellIns": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}cellDel": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}cellMerge": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}numberingChange": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}pPrChange": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}rPrChange": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}tblPrChange": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}tblGridChange": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}trPrChange": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}tcPrChange": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}sectPrChange": DocxImportDiagnosticCode.REVISION,
            f"{{{_W_NS}}}sdt": DocxImportDiagnosticCode.CONTENT_CONTROL,
            f"{{{_W_NS}}}fldSimple": DocxImportDiagnosticCode.WORD_FIELD,
            f"{{{_W_NS}}}fldChar": DocxImportDiagnosticCode.WORD_FIELD,
            f"{{{_W_NS}}}instrText": DocxImportDiagnosticCode.WORD_FIELD,
            f"{{{_W_NS}}}footnoteReference": DocxImportDiagnosticCode.FOOTNOTE_ENDNOTE,
            f"{{{_W_NS}}}endnoteReference": DocxImportDiagnosticCode.FOOTNOTE_ENDNOTE,
            f"{{{_W_NS}}}altChunk": DocxImportDiagnosticCode.ALT_CHUNK,
            f"{{{_W_NS}}}subDoc": DocxImportDiagnosticCode.SUBDOCUMENT,
            f"{{{_W_NS}}}txbxContent": DocxImportDiagnosticCode.TEXT_BOX,
            f"{{{_W_NS}}}object": DocxImportDiagnosticCode.OLE_OBJECT,
            f"{{{_MC_NS}}}AlternateContent": DocxImportDiagnosticCode.ALTERNATE_CONTENT,
            f"{{{_M_NS}}}oMath": DocxImportDiagnosticCode.OMML,
            f"{{{_M_NS}}}oMathPara": DocxImportDiagnosticCode.OMML,
        }
        messages = {
            DocxImportDiagnosticCode.REVISION: "tracked revisions are not importable",
            DocxImportDiagnosticCode.COMMENT: "comments are not importable",
            DocxImportDiagnosticCode.CONTENT_CONTROL: "content controls are not importable",
            DocxImportDiagnosticCode.WORD_FIELD: "Word/TOC fields are not importable",
            DocxImportDiagnosticCode.FOOTNOTE_ENDNOTE: "footnotes/endnotes are not importable",
            DocxImportDiagnosticCode.ALT_CHUNK: "altChunk content is not importable",
            DocxImportDiagnosticCode.SUBDOCUMENT: "subdocuments are not importable",
            DocxImportDiagnosticCode.TEXT_BOX: "text boxes are not importable",
            DocxImportDiagnosticCode.OLE_OBJECT: "OLE objects are not importable",
            DocxImportDiagnosticCode.VML: "VML content is not importable",
            DocxImportDiagnosticCode.FLOATING_IMAGE: "floating images are not importable",
            DocxImportDiagnosticCode.ALTERNATE_CONTENT: "AlternateContent is not importable",
            DocxImportDiagnosticCode.OMML: "OMML equations are not importable",
        }
        for element in root.iter():
            code = tag_codes.get(element.tag)
            namespace = _namespace(element)
            if namespace in {
                "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
                "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
            }:
                code = DocxImportDiagnosticCode.SHAPE
            elif namespace.startswith(
                "http://schemas.openxmlformats.org/drawingml/2006/diagram"
            ):
                code = DocxImportDiagnosticCode.SMART_ART
            elif namespace == "http://schemas.openxmlformats.org/drawingml/2006/chart":
                code = DocxImportDiagnosticCode.CHART
            if code is not None:
                self.diagnostics.add(
                    code,
                    messages.get(code, f"unsupported {code.value} object"),
                    part,
                    _element_path(element),
                )
            if element.tag in {f"{{{_W_NS}}}vanish", f"{{{_W_NS}}}webHidden"}:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.HIDDEN_TEXT,
                    "hidden text is not importable",
                    part,
                    _element_path(element),
                )
            if element.tag == f"{{{_W_NS}}}hyperlink" and _w_attr(element, "anchor"):
                self.diagnostics.add(
                    DocxImportDiagnosticCode.INTERNAL_BOOKMARK_LINK,
                    "internal bookmark hyperlinks are not importable",
                    part,
                    _element_path(element),
                )
            if element.tag == f"{{{_A_NS}}}graphicData":
                uri = str(element.get("uri", ""))
                if uri and uri != _PIC_NS:
                    code = (
                        DocxImportDiagnosticCode.CHART
                        if "chart" in uri.casefold()
                        else DocxImportDiagnosticCode.SMART_ART
                        if "diagram" in uri.casefold()
                        else DocxImportDiagnosticCode.SHAPE
                    )
                    self.diagnostics.add(
                        code,
                        f"unsupported DrawingML graphicData URI: {uri}",
                        part,
                        _element_path(element),
                    )

    def _validate_sections(self) -> None:
        if self.document is None:
            return
        section_properties = self.document.findall(".//w:sectPr", namespaces=_NS)
        for section in section_properties:
            cols = section.find("w:cols", namespaces=_NS)
            if cols is None:
                continue
            count = _int_attr(cols, "num")
            raw_separator = _w_attr(cols, "sep")
            separator = bool(raw_separator) and raw_separator.casefold() not in {
                "0",
                "false",
                "off",
                "none",
            }
            if (count is not None and count != 1) or separator or len(cols):
                self.diagnostics.add(
                    DocxImportDiagnosticCode.COMPLEX_SECTION,
                    "multi-column or custom column sections are not importable",
                    _DOCUMENT_PART,
                    _element_path(cols),
                )

    def _parse_body(self) -> list[Any]:
        assert self.document is not None
        body = self.document.find("w:body", namespaces=_NS)
        if body is None:
            self.diagnostics.add(
                DocxImportDiagnosticCode.MISSING_PART,
                "word/document.xml has no body",
                _DOCUMENT_PART,
                "/w:document",
            )
            return []

        blocks: list[Any] = []
        pending_list: tuple[
            tuple[bool, int, str, int, ListNumberFormat, str],
            list[ListItem],
        ] | None = None

        def flush_list() -> None:
            nonlocal pending_list
            if pending_list is None:
                return
            (
                ordered,
                nesting,
                _source_num_id,
                start,
                number_format,
                marker_template,
            ), items = pending_list
            blocks.append(
                ListBlock(
                    ordered=ordered,
                    start=start,
                    nesting=nesting,
                    items=tuple(items),
                    number_format=number_format,
                    marker_template=marker_template,
                )
            )
            pending_list = None

        for child in body:
            local = _local_name(child)
            if local == "sectPr":
                continue
            if local == "tbl":
                flush_list()
                table = self._parse_table(child)
                if table is not None:
                    blocks.append(table)
                continue
            if local != "p":
                flush_list()
                self.diagnostics.add(
                    DocxImportDiagnosticCode.UNSUPPORTED_BODY_OBJECT,
                    f"unsupported body child {local}",
                    _DOCUMENT_PART,
                    _element_path(child),
                )
                continue

            page_break_before = child.find("w:pPr/w:pageBreakBefore", namespaces=_NS)
            if page_break_before is not None and _on_off_attr(page_break_before):
                flush_list()
                blocks.append(PageBreakBlock())

            atoms = self._parse_paragraph_atoms(child)
            segments = self._atoms_to_segments(atoms, child)
            heading_level = self.styles.heading_level(child)
            raw_num = self.styles.num_properties(child)
            list_semantics = (
                self.numbering.semantics(raw_num[0], raw_num[1], child)
                if raw_num is not None
                else None
            )
            if any(atom.image is not None for atom in atoms):
                flush_list()
                if heading_level is not None or raw_num is not None:
                    self.diagnostics.add(
                        DocxImportDiagnosticCode.MIXED_IMAGE_PARAGRAPH,
                        "images in headings or list items cannot preserve ordering",
                        _DOCUMENT_PART,
                        _element_path(child),
                    )
                    continue
                blocks.extend(self._atoms_to_content_blocks(atoms, child))
                continue
            if heading_level is not None and raw_num is not None:
                flush_list()
                self.diagnostics.add(
                    DocxImportDiagnosticCode.UNSUPPORTED_LIST_FORMAT,
                    "a paragraph cannot be both a heading and a v1 list item",
                    _DOCUMENT_PART,
                    _element_path(child),
                )
                continue
            if raw_num is not None:
                if list_semantics is None:
                    flush_list()
                    continue
                if any(marker for marker, _inlines in segments):
                    flush_list()
                    self.diagnostics.add(
                        DocxImportDiagnosticCode.UNSUPPORTED_BREAK,
                        "page breaks inside list items are not importable",
                        _DOCUMENT_PART,
                        _element_path(child),
                    )
                    continue
                inlines = segments[0][1] if segments else ()
                key = (
                    list_semantics.ordered,
                    list_semantics.nesting,
                    list_semantics.source_num_id,
                    list_semantics.start,
                    list_semantics.number_format,
                    list_semantics.marker_template,
                )
                if pending_list is None or pending_list[0] != key:
                    flush_list()
                    pending_list = (key, [])
                pending_list[1].append(ListItem(inlines=tuple(inlines)))
                continue

            flush_list()
            for is_page_break, inlines in segments:
                if is_page_break:
                    blocks.append(PageBreakBlock())
                elif heading_level is not None:
                    blocks.append(
                        HeadingBlock(level=heading_level, inlines=tuple(inlines))
                    )
                else:
                    blocks.append(ParagraphBlock(inlines=tuple(inlines)))
        flush_list()
        return blocks

    def _parse_drawing_images(self, drawing: etree._Element) -> list[ImageBlock]:
        containers = drawing.findall(".//wp:inline", namespaces=_NS)
        anchored = drawing.findall(".//wp:anchor", namespaces=_NS)
        containers.extend(anchored)
        if len(containers) != 1:
            self.diagnostics.add(
                DocxImportDiagnosticCode.INVALID_IMAGE,
                "DrawingML image must have one inline or anchor container",
                _DOCUMENT_PART,
                _element_path(drawing),
            )
            return []
        container = containers[0]
        blips = container.findall(".//a:blip", namespaces=_NS)
        if len(blips) != 1:
            self.diagnostics.add(
                DocxImportDiagnosticCode.INVALID_IMAGE,
                "DrawingML image must have one embedded blip",
                _DOCUMENT_PART,
                _element_path(container),
            )
            return []
        blip = blips[0]
        if blip.get(f"{{{_R_NS}}}link", ""):
            self.diagnostics.add(
                DocxImportDiagnosticCode.EXTERNAL_IMAGE,
                "linked images are not importable",
                _DOCUMENT_PART,
                _element_path(blip),
            )
            return []
        extent = container.find("wp:extent", namespaces=_NS)
        display_size = _drawing_extent_px(extent)
        properties = container.find("wp:docPr", namespaces=_NS)
        alt_text = ""
        if properties is not None:
            alt_text = str(
                properties.get("descr")
                or properties.get("title")
                or properties.get("name")
                or ""
            )
        image = self._extract_image_relationship(
            blip.get(f"{{{_R_NS}}}embed", ""),
            source_element=blip,
            alt_text=alt_text,
            display_size=display_size,
        )
        if image is not None and anchored:
            self.normalized_counts["floating_image_inlined"] += 1
        return [image] if image is not None else []

    def _parse_vml_images(self, pict: etree._Element) -> list[ImageBlock]:
        image_nodes = pict.findall(".//v:imagedata", namespaces=_NS)
        if not image_nodes:
            self.diagnostics.add(
                DocxImportDiagnosticCode.SHAPE,
                "VML object has no importable image payload",
                _DOCUMENT_PART,
                _element_path(pict),
            )
            return []
        output: list[ImageBlock] = []
        for image_node in image_nodes:
            shape = image_node.getparent()
            while shape is not None and _local_name(shape) != "shape":
                shape = shape.getparent()
            display_size = _vml_shape_size_px(shape)
            alt_text = str(
                image_node.get(f"{{{_O_NS}}}title")
                or (shape.get("alt") if shape is not None else "")
                or ""
            )
            image = self._extract_image_relationship(
                image_node.get(f"{{{_R_NS}}}id", ""),
                source_element=image_node,
                alt_text=alt_text,
                display_size=display_size,
            )
            if image is not None:
                output.append(image)
                self.normalized_counts["vml_image_normalized"] += 1
        return output

    def _extract_image_relationship(
        self,
        relationship_id: str,
        *,
        source_element: etree._Element,
        alt_text: str,
        display_size: tuple[int, int] | None,
    ) -> ImageBlock | None:
        relationship = self.document_relationships.get(relationship_id)
        if relationship is None or relationship.kind != "image" or relationship.external:
            self.diagnostics.add(
                DocxImportDiagnosticCode.DANGLING_RELATIONSHIP,
                f"image relationship {relationship_id!r} is missing or invalid",
                _DOCUMENT_PART,
                _element_path(source_element),
            )
            return None
        part = relationship.resolved_part
        if part is None or part not in self.package.parts:
            self.diagnostics.add(
                DocxImportDiagnosticCode.DANGLING_RELATIONSHIP,
                "image target is missing",
                relationship.rels_part,
                f"/Relationships/Relationship[@Id='{relationship_id}']",
            )
            return None
        declared_media_type = self.package.media_type(part).casefold()
        payload = self.package.parts[part]
        try:
            inspected = _inspect_or_convert_image(
                payload,
                declared_media_type=declared_media_type,
            )
        except _ImageInspectionError as exc:
            self.diagnostics.add(
                exc.code,
                f"unsupported or invalid image payload {declared_media_type!r}",
                part,
                "/",
            )
            return None
        normalized_payload, media_type, intrinsic_size = inspected
        if declared_media_type in _METAFILE_MEDIA_TYPES:
            self.normalized_counts["metafile_rasterized"] += 1
        width_px, height_px = display_size or intrinsic_size
        if width_px < 1 or height_px < 1:
            self.diagnostics.add(
                DocxImportDiagnosticCode.INVALID_IMAGE,
                "image dimensions must be positive",
                part,
                "/",
            )
            return None
        extension = _MIME_EXTENSIONS[media_type]
        digest = sha256(normalized_payload).hexdigest()
        resource_id = f"sha256/{digest}{extension}"
        resource = ImportedDocxResource(
            resource_id=resource_id,
            media_type=media_type,
            payload=normalized_payload,
        )
        existing = self.resources.get(resource_id)
        if existing is not None and existing != resource:
            self.diagnostics.add(
                DocxImportDiagnosticCode.ORPHAN_RESOURCE,
                "content-addressed image resource collision",
                part,
                "/",
            )
            return None
        self.resources[resource_id] = resource
        self.used_image_relationships.add(relationship_id)
        self.used_image_parts.add(part)
        return ImageBlock(
            resource_id=resource_id,
            alt_text=alt_text,
            width_px=int(width_px),
            height_px=int(height_px),
        )

    def _parse_paragraph_atoms(self, paragraph: etree._Element) -> list[_InlineAtom]:
        atoms: list[_InlineAtom] = []
        for child in paragraph:
            local = _local_name(child)
            if local == "pPr":
                continue
            if local == "r":
                atoms.extend(self._parse_run(paragraph, child))
            elif local == "hyperlink":
                atoms.extend(self._parse_hyperlink(paragraph, child))
            elif local in {
                "bookmarkStart",
                "bookmarkEnd",
                "commentRangeStart",
                "commentRangeEnd",
                "proofErr",
                "permStart",
                "permEnd",
            }:
                continue
            else:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.UNSUPPORTED_INLINE,
                    f"unsupported paragraph inline {local}",
                    _DOCUMENT_PART,
                    _element_path(child),
                )
        return atoms

    def _parse_run(
        self,
        paragraph: etree._Element,
        run: etree._Element,
    ) -> list[_InlineAtom]:
        formatting = self.styles.run_format(paragraph, run)
        atoms: list[_InlineAtom] = []
        for child in run:
            local = _local_name(child)
            if local in {
                "rPr",
                "lastRenderedPageBreak",
                "commentReference",
                "annotationRef",
            }:
                continue
            if local == "t":
                atoms.append(
                    _InlineAtom("text", text=child.text or "", formatting=formatting)
                )
            elif local == "noBreakHyphen":
                atoms.append(_InlineAtom("text", text="‑", formatting=formatting))
            elif local == "softHyphen":
                atoms.append(_InlineAtom("text", text="\u00ad", formatting=formatting))
            elif local == "tab":
                atoms.append(_InlineAtom("tab", formatting=formatting))
            elif local == "drawing":
                for image in self._parse_drawing_images(child):
                    atoms.append(_InlineAtom("image", image=image))
            elif local == "pict":
                for image in self._parse_vml_images(child):
                    atoms.append(_InlineAtom("image", image=image))
            elif local == "cr":
                atoms.append(_InlineAtom("soft_break", formatting=formatting))
            elif local == "br":
                break_type = _w_attr(child, "type") or "textWrapping"
                if break_type == "page":
                    atoms.append(_InlineAtom("page_break"))
                elif break_type == "textWrapping":
                    atoms.append(_InlineAtom("hard_break", formatting=formatting))
                else:
                    self.diagnostics.add(
                        DocxImportDiagnosticCode.UNSUPPORTED_BREAK,
                        f"unsupported Word break type {break_type!r}",
                        _DOCUMENT_PART,
                        _element_path(child),
                    )
            else:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.UNSUPPORTED_INLINE,
                    f"unsupported run child {local}",
                    _DOCUMENT_PART,
                    _element_path(child),
                )
        return atoms

    def _parse_hyperlink(
        self,
        paragraph: etree._Element,
        hyperlink: etree._Element,
    ) -> list[_InlineAtom]:
        relationship_id = hyperlink.get(f"{{{_R_NS}}}id", "")
        relationship = self.document_relationships.get(relationship_id)
        if (
            relationship is None
            or relationship.kind != "hyperlink"
            or not relationship.external
            or not _allowed_hyperlink(relationship.target)
        ):
            self.diagnostics.add(
                DocxImportDiagnosticCode.DANGLING_RELATIONSHIP,
                f"hyperlink relationship {relationship_id!r} is missing or invalid",
                _DOCUMENT_PART,
                _element_path(hyperlink),
            )
            return []
        self.used_hyperlink_relationships.add(relationship_id)
        atoms: list[_InlineAtom] = []
        for child in hyperlink:
            if _local_name(child) != "r":
                self.diagnostics.add(
                    DocxImportDiagnosticCode.UNSUPPORTED_INLINE,
                    "a hyperlink may contain only text runs",
                    _DOCUMENT_PART,
                    _element_path(child),
                )
                continue
            for atom in self._parse_run(paragraph, child):
                if atom.kind != "text":
                    self.diagnostics.add(
                        DocxImportDiagnosticCode.UNSUPPORTED_INLINE,
                        "line/page breaks inside hyperlinks are not importable",
                        _DOCUMENT_PART,
                        _element_path(child),
                    )
                    continue
                atoms.append(
                    _InlineAtom(
                        "hyperlink",
                        text=atom.text,
                        formatting=atom.formatting,
                        href=relationship.target,
                    )
                )
        if _FIELD_TOKEN_PATTERN.search("".join(atom.text for atom in atoms)):
            self.diagnostics.add(
                DocxImportDiagnosticCode.UNSUPPORTED_INLINE,
                "field/content tokens cannot be hyperlink text in the v1 IR",
                _DOCUMENT_PART,
                _element_path(hyperlink),
            )
        return atoms

    def _atoms_to_segments(
        self,
        atoms: Sequence[_InlineAtom],
        paragraph: etree._Element,
    ) -> list[tuple[bool, tuple[InlineContent, ...]]]:
        segments: list[tuple[bool, tuple[InlineContent, ...]]] = []
        current: list[InlineContent] = []
        plain_atoms: list[_InlineAtom] = []

        def flush_plain() -> None:
            if plain_atoms:
                current.extend(self._tokenize_plain_atoms(plain_atoms, paragraph))
                plain_atoms.clear()

        for atom in atoms:
            if atom.kind == "text":
                plain_atoms.append(atom)
                continue
            flush_plain()
            if atom.kind == "page_break":
                if current:
                    segments.append((False, tuple(_merge_inlines(current))))
                    current.clear()
                segments.append((True, ()))
            elif atom.kind == "hyperlink":
                current.append(
                    InlineContent(
                        kind=InlineKind.HYPERLINK,
                        text=atom.text,
                        bold=atom.formatting.bold,
                        italic=atom.formatting.italic,
                        underline=atom.formatting.underline,
                        strikethrough=atom.formatting.strikethrough,
                        vertical_alignment=atom.formatting.vertical_alignment,
                        href=atom.href,
                    )
                )
            elif atom.kind == "tab":
                current.append(
                    InlineContent(
                        kind=InlineKind.TAB,
                        bold=atom.formatting.bold,
                        italic=atom.formatting.italic,
                        underline=atom.formatting.underline,
                        strikethrough=atom.formatting.strikethrough,
                        vertical_alignment=atom.formatting.vertical_alignment,
                    )
                )
            elif atom.kind in {"soft_break", "hard_break"}:
                current.append(
                    InlineContent(
                        kind=(
                            InlineKind.SOFT_BREAK
                            if atom.kind == "soft_break"
                            else InlineKind.HARD_BREAK
                        ),
                        bold=atom.formatting.bold,
                        italic=atom.formatting.italic,
                        underline=atom.formatting.underline,
                        strikethrough=atom.formatting.strikethrough,
                        vertical_alignment=atom.formatting.vertical_alignment,
                    )
                )
        flush_plain()
        if current or not segments:
            segments.append((False, tuple(_merge_inlines(current))))
        return segments

    def _atoms_to_content_blocks(
        self,
        atoms: Sequence[_InlineAtom],
        paragraph: etree._Element,
    ) -> list[ParagraphBlock | ImageBlock | PageBreakBlock]:
        output: list[ParagraphBlock | ImageBlock | PageBreakBlock] = []
        pending: list[_InlineAtom] = []

        def flush() -> None:
            if not pending:
                return
            for is_page_break, inlines in self._atoms_to_segments(
                tuple(pending),
                paragraph,
            ):
                if is_page_break:
                    output.append(PageBreakBlock())
                elif inlines:
                    output.append(ParagraphBlock(tuple(inlines)))
            pending.clear()

        for atom in atoms:
            if atom.image is None:
                pending.append(atom)
                continue
            flush()
            output.append(atom.image)
        flush()
        return output

    def _tokenize_plain_atoms(
        self,
        atoms: Sequence[_InlineAtom],
        paragraph: etree._Element,
    ) -> list[InlineContent]:
        combined = "".join(atom.text for atom in atoms)
        if not combined:
            return []
        result: list[InlineContent] = []
        cursor = 0
        for match in _FIELD_TOKEN_PATTERN.finditer(combined):
            raw_key = match.group(1)
            key = raw_key.strip()
            if not key or raw_key != key:
                continue
            result.extend(_text_slice_to_inlines(atoms, cursor, match.start()))
            formatting = _format_at(atoms, match.start())
            try:
                token_ref = parse_material_token(match.group(0))
            except (TypeError, ValueError):
                token_ref = None
            if token_ref is None or token_ref.kind is not MaterialTokenKind.FIELD:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.UNSUPPORTED_CONTENT_TOKEN,
                    "reusable content may contain only @text: or @time: inline tokens",
                    _DOCUMENT_PART,
                    _element_path(paragraph),
                )
                result.extend(_text_slice_to_inlines(atoms, match.start(), match.end()))
            else:
                result.append(
                    InlineContent(
                        kind=InlineKind.FIELD_TOKEN,
                        field_key=token_ref.key,
                        bold=formatting.bold,
                        italic=formatting.italic,
                        underline=formatting.underline,
                        strikethrough=formatting.strikethrough,
                        vertical_alignment=formatting.vertical_alignment,
                    )
                )
            cursor = match.end()
        result.extend(_text_slice_to_inlines(atoms, cursor, len(combined)))
        return result

    def _parse_table(self, table: etree._Element) -> TableBlock | None:
        path = _element_path(table)
        nested = table.findall(".//w:tc//w:tbl", namespaces=_NS)
        for item in nested:
            self.diagnostics.add(
                DocxImportDiagnosticCode.NESTED_TABLE,
                "nested tables are not importable",
                _DOCUMENT_PART,
                _element_path(item),
            )
        draft_rows: list[list[_TableCellDraft]] = []
        expected_columns: int | None = None
        active_vertical: dict[int, _TableCellDraft] = {}
        grid = table.find("w:tblGrid", namespaces=_NS)
        grid_columns = (
            len(grid.findall("w:gridCol", namespaces=_NS))
            if grid is not None
            else 0
        )
        row_elements = table.findall("w:tr", namespaces=_NS)
        if not row_elements:
            self.diagnostics.add(
                DocxImportDiagnosticCode.NON_RECTANGULAR_TABLE,
                "a simple table must contain at least one row",
                _DOCUMENT_PART,
                path,
            )
        for row_element in row_elements:
            if row_element.find("w:trPr/w:gridBefore", namespaces=_NS) is not None or row_element.find(
                "w:trPr/w:gridAfter", namespaces=_NS
            ) is not None:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.NON_RECTANGULAR_TABLE,
                    "gridBefore/gridAfter rows are not a simple rectangle",
                    _DOCUMENT_PART,
                _element_path(row_element),
            )
            drafts: list[_TableCellDraft] = []
            column = 0
            horizontal_origin: _TableCellDraft | None = None
            for cell_element in row_element.findall("w:tc", namespaces=_NS):
                grid_span = cell_element.find("w:tcPr/w:gridSpan", namespaces=_NS)
                colspan = _int_attr(grid_span, "val") if grid_span is not None else 1
                if colspan is None or colspan < 1:
                    self.diagnostics.add(
                        DocxImportDiagnosticCode.NON_RECTANGULAR_TABLE,
                        "table cell has an invalid grid span",
                        _DOCUMENT_PART,
                        _element_path(cell_element),
                    )
                    colspan = 1

                horizontal = cell_element.find("w:tcPr/w:hMerge", namespaces=_NS)
                horizontal_value = (
                    (_w_attr(horizontal, "val") or "continue").casefold()
                    if horizontal is not None
                    else ""
                )
                vertical = cell_element.find("w:tcPr/w:vMerge", namespaces=_NS)
                vertical_value = (
                    (_w_attr(vertical, "val") or "continue").casefold()
                    if vertical is not None
                    else ""
                )

                if horizontal_value == "continue":
                    if horizontal_origin is None or vertical_value:
                        self.diagnostics.add(
                            DocxImportDiagnosticCode.NON_RECTANGULAR_TABLE,
                            "legacy horizontal merge has no valid restart cell",
                            _DOCUMENT_PART,
                            _element_path(cell_element),
                        )
                    else:
                        horizontal_origin.colspan += colspan
                        continuation_blocks = self._parse_table_cell_blocks(cell_element)
                        if _cell_blocks_have_visible_content(continuation_blocks):
                            horizontal_origin.blocks.extend(continuation_blocks)
                        self.normalized_counts["table_merge_normalized"] += 1
                    column += colspan
                    continue

                if vertical_value == "continue":
                    origin_values = [
                        active_vertical.get(current)
                        for current in range(column, column + colspan)
                    ]
                    origins = {
                        id(origin): origin
                        for origin in origin_values
                        if origin is not None
                    }
                    if len(origins) != 1:
                        self.diagnostics.add(
                            DocxImportDiagnosticCode.NON_RECTANGULAR_TABLE,
                            "vertical merge continuation has no unique origin",
                            _DOCUMENT_PART,
                            _element_path(cell_element),
                        )
                    else:
                        origin = next(iter(origins.values()))
                        if origin.colspan != colspan:
                            self.diagnostics.add(
                                DocxImportDiagnosticCode.NON_RECTANGULAR_TABLE,
                                "vertical merge continuation changes column span",
                                _DOCUMENT_PART,
                                _element_path(cell_element),
                            )
                        else:
                            origin.rowspan += 1
                            self.normalized_counts["table_merge_normalized"] += 1
                    column += colspan
                    horizontal_origin = None
                    continue

                blocks = self._parse_table_cell_blocks(cell_element)
                draft = _TableCellDraft(blocks=blocks, colspan=colspan)
                drafts.append(draft)
                for current in range(column, column + colspan):
                    active_vertical.pop(current, None)
                if vertical_value == "restart":
                    for current in range(column, column + colspan):
                        active_vertical[current] = draft
                elif vertical_value:
                    self.diagnostics.add(
                        DocxImportDiagnosticCode.NON_RECTANGULAR_TABLE,
                        f"unsupported vertical merge value {vertical_value!r}",
                        _DOCUMENT_PART,
                        _element_path(cell_element),
                    )
                horizontal_origin = draft if horizontal_value == "restart" else None
                column += colspan
            if expected_columns is None:
                expected_columns = column
            if column != expected_columns:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.NON_RECTANGULAR_TABLE,
                    "table rows cover different logical column counts",
                    _DOCUMENT_PART,
                    _element_path(row_element),
                )
            draft_rows.append(drafts)
        if grid_columns and expected_columns is not None and grid_columns != expected_columns:
            self.diagnostics.add(
                DocxImportDiagnosticCode.NON_RECTANGULAR_TABLE,
                "table grid and row cell count disagree",
                _DOCUMENT_PART,
                path,
            )
        if nested or not draft_rows:
            return None
        try:
            return TableBlock(
                rows=tuple(
                    TableRow(tuple(cell.freeze() for cell in row))
                    for row in draft_rows
                )
            )
        except (TypeError, ValueError) as exc:
            self.diagnostics.add(
                DocxImportDiagnosticCode.NON_RECTANGULAR_TABLE,
                str(exc),
                _DOCUMENT_PART,
                path,
            )
            return None

    def _parse_table_cell_blocks(
        self,
        cell: etree._Element,
    ) -> list[ParagraphBlock | ListBlock | ImageBlock]:
        unexpected = [
            child
            for child in cell
            if _local_name(child) not in {"tcPr", "p", "tbl"}
        ]
        nested = cell.findall("w:tbl", namespaces=_NS)
        if unexpected or nested:
            self.diagnostics.add(
                DocxImportDiagnosticCode.UNSUPPORTED_TABLE_CELL,
                "table cell contains an unsupported block object",
                _DOCUMENT_PART,
                _element_path(cell),
            )
        blocks: list[ParagraphBlock | ListBlock | ImageBlock] = []
        pending: tuple[
            tuple[bool, int, str, int, ListNumberFormat, str],
            list[ListItem],
        ] | None = None

        def flush() -> None:
            nonlocal pending
            if pending is None:
                return
            (
                ordered,
                nesting,
                _source_num_id,
                start,
                number_format,
                marker_template,
            ), items = pending
            blocks.append(
                ListBlock(
                    ordered=ordered,
                    start=start,
                    nesting=nesting,
                    items=tuple(items),
                    number_format=number_format,
                    marker_template=marker_template,
                )
            )
            pending = None

        for paragraph in cell.findall("w:p", namespaces=_NS):
            if paragraph.find("w:pPr/w:pageBreakBefore", namespaces=_NS) is not None:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.UNSUPPORTED_TABLE_CELL,
                    "page breaks inside table cells are not importable",
                    _DOCUMENT_PART,
                    _element_path(paragraph),
                )
            atoms = self._parse_paragraph_atoms(paragraph)
            if any(atom.image is not None for atom in atoms):
                flush()
                content_blocks = self._atoms_to_content_blocks(atoms, paragraph)
                for content_block in content_blocks:
                    if isinstance(content_block, PageBreakBlock):
                        self.diagnostics.add(
                            DocxImportDiagnosticCode.UNSUPPORTED_TABLE_CELL,
                            "page breaks inside table cells are not importable",
                            _DOCUMENT_PART,
                            _element_path(paragraph),
                        )
                    else:
                        blocks.append(content_block)
                continue
            segments = self._atoms_to_segments(atoms, paragraph)
            if any(is_break for is_break, _inlines in segments):
                self.diagnostics.add(
                    DocxImportDiagnosticCode.UNSUPPORTED_TABLE_CELL,
                    "page breaks inside table cells are not importable",
                    _DOCUMENT_PART,
                    _element_path(paragraph),
                )
                continue
            inlines = segments[0][1] if segments else ()
            raw_num = self.styles.num_properties(paragraph)
            semantics = (
                self.numbering.semantics(raw_num[0], raw_num[1], paragraph)
                if raw_num is not None
                else None
            )
            if raw_num is not None and semantics is not None:
                key = (
                    semantics.ordered,
                    semantics.nesting,
                    semantics.source_num_id,
                    semantics.start,
                    semantics.number_format,
                    semantics.marker_template,
                )
                if pending is None or pending[0] != key:
                    flush()
                    pending = (key, [])
                pending[1].append(ListItem(tuple(inlines)))
            elif raw_num is None:
                flush()
                blocks.append(ParagraphBlock(tuple(inlines)))
            else:
                flush()
        flush()
        return blocks or [ParagraphBlock(())]

    def _validate_relationship_usage(self, blocks: Sequence[Any]) -> None:
        if self.document is None:
            return
        referenced_ids = {
            value
            for element in self.document.iter()
            for attribute, value in element.attrib.items()
            if attribute
            in {
                f"{{{_R_NS}}}id",
                f"{{{_R_NS}}}embed",
                f"{{{_R_NS}}}link",
            }
            and value
        }
        for relationship_id in referenced_ids:
            if relationship_id not in self.document_relationships:
                self.diagnostics.add(
                    DocxImportDiagnosticCode.DANGLING_RELATIONSHIP,
                    f"document references missing relationship {relationship_id}",
                    _DOCUMENT_PART,
                    f"//*[@r:id='{relationship_id}' or @r:embed='{relationship_id}' "
                    f"or @r:link='{relationship_id}']",
                )
        for relationship_id, relationship in self.document_relationships.items():
            if (
                relationship.kind == "hyperlink"
                and relationship_id not in self.used_hyperlink_relationships
                and relationship_id not in referenced_ids
            ):
                self.diagnostics.add(
                    DocxImportDiagnosticCode.ORPHAN_RELATIONSHIP,
                    f"unused hyperlink relationship {relationship_id}",
                    relationship.rels_part,
                    f"/Relationships/Relationship[@Id='{relationship_id}']",
                )
            if (
                relationship.kind == "image"
                and relationship_id not in self.used_image_relationships
                and relationship_id not in referenced_ids
            ):
                self.diagnostics.add(
                    DocxImportDiagnosticCode.ORPHAN_RELATIONSHIP,
                    f"unused or unsupported image relationship {relationship_id}",
                    relationship.rels_part,
                    f"/Relationships/Relationship[@Id='{relationship_id}']",
                )
        for source_part, relationships in self.package.relationships_by_source.items():
            if source_part == _DOCUMENT_PART:
                continue
            for relationship_id, relationship in relationships.items():
                if relationship.kind == "hyperlink":
                    self.diagnostics.add(
                        DocxImportDiagnosticCode.ORPHAN_RELATIONSHIP,
                        "hyperlinks outside the main document body are not represented",
                        relationship.rels_part,
                        f"/Relationships/Relationship[@Id='{relationship_id}']",
                    )
        media_parts = {
            part for part in self.package.parts if part.casefold().startswith("word/media/")
        }
        referenced_image_parts = {
            relationship.resolved_part
            for relationship_id, relationship in self.document_relationships.items()
            if relationship_id in referenced_ids
            and relationship.kind == "image"
            and relationship.resolved_part is not None
        }
        for part in sorted(
            media_parts - self.used_image_parts - referenced_image_parts
        ):
            self.diagnostics.add(
                DocxImportDiagnosticCode.ORPHAN_RESOURCE,
                "media part is not represented by an ImageBlock",
                part,
                "/",
            )
        resource_ids = set(self.resources)
        image_resource_ids = set(_image_resource_ids(blocks))
        for resource_id in sorted(image_resource_ids - resource_ids):
            self.diagnostics.add(
                DocxImportDiagnosticCode.ORPHAN_RESOURCE,
                f"ImageBlock references missing resource {resource_id}",
                _DOCUMENT_PART,
                "/w:document/w:body",
            )
        for resource_id in sorted(resource_ids - image_resource_ids):
            self.diagnostics.add(
                DocxImportDiagnosticCode.ORPHAN_RESOURCE,
                f"captured resource has no ImageBlock {resource_id}",
                _DOCUMENT_PART,
                "/w:document/w:body",
            )


def import_docx_package(
    package: SafeDocxPackage,
) -> ImportedDocxContent:
    """Normalize one already bounded in-memory OOXML package."""

    if not isinstance(package, SafeDocxPackage):
        raise TypeError("package must be a SafeDocxPackage")
    importer = _DocxSemanticImporter(package)
    fragment = importer.import_fragment()
    resources = tuple(importer.resources.values())
    return ImportedDocxContent(
        fragment=fragment,
        resources=resources,
        normalized_counts=tuple(sorted(importer.normalized_counts.items())),
    )


def _unwrap_element(
    element: etree._Element,
    children: Sequence[etree._Element],
) -> None:
    parent = element.getparent()
    if parent is None:
        return
    index = parent.index(element)
    parent.remove(element)
    for offset, child in enumerate(children):
        parent.insert(index + offset, child)


def _run_has_visible_content(run: etree._Element) -> bool:
    return any(
        (
            child.tag == f"{{{_W_NS}}}t"
            and bool(child.text)
        )
        or child.tag
        in {
            f"{{{_W_NS}}}tab",
            f"{{{_W_NS}}}br",
            f"{{{_W_NS}}}cr",
            f"{{{_W_NS}}}drawing",
            f"{{{_W_NS}}}pict",
        }
        for child in run
    )


def _cell_blocks_have_visible_content(
    blocks: Sequence[ParagraphBlock | ListBlock | ImageBlock],
) -> bool:
    for block in blocks:
        if isinstance(block, ImageBlock):
            return True
        if isinstance(block, ParagraphBlock) and any(
            inline.text or inline.field_key for inline in block.inlines
        ):
            return True
        if isinstance(block, ListBlock) and any(
            inline.text or inline.field_key
            for item in block.items
            for inline in item.inlines
        ):
            return True
    return False


def _image_resource_ids(blocks: Sequence[Any]) -> tuple[str, ...]:
    result: list[str] = []
    for block in blocks:
        if isinstance(block, ImageBlock):
            result.append(block.resource_id)
        elif isinstance(block, TableBlock):
            for row in block.rows:
                for cell in row.cells:
                    result.extend(_image_resource_ids(cell.blocks))
    return tuple(result)


def _drawing_extent_px(
    extent: etree._Element | None,
) -> tuple[int, int] | None:
    if extent is None:
        return None
    try:
        width = max(1, round(int(extent.get("cx", "0")) / 9525))
        height = max(1, round(int(extent.get("cy", "0")) / 9525))
    except (TypeError, ValueError):
        return None
    if width * height > _MAX_IMAGE_PIXELS:
        return None
    return width, height


def _vml_shape_size_px(
    shape: etree._Element | None,
) -> tuple[int, int] | None:
    if shape is None:
        return None
    style = str(shape.get("style", "") or "")
    values = {
        key.strip().casefold(): value.strip()
        for item in style.split(";")
        if ":" in item
        for key, value in (item.split(":", 1),)
    }
    width = _css_length_px(values.get("width", ""))
    height = _css_length_px(values.get("height", ""))
    if width is None or height is None or width * height > _MAX_IMAGE_PIXELS:
        return None
    return width, height


def _css_length_px(value: str) -> int | None:
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)(pt|px|in|cm|mm)?\s*", value)
    if match is None:
        return None
    amount = float(match.group(1))
    unit = match.group(2) or "px"
    factor = {
        "px": 1.0,
        "pt": 96.0 / 72.0,
        "in": 96.0,
        "cm": 96.0 / 2.54,
        "mm": 96.0 / 25.4,
    }[unit]
    return max(1, round(amount * factor))


def _inspect_or_convert_image(
    payload: bytes,
    *,
    declared_media_type: str,
) -> tuple[bytes, str, tuple[int, int]]:
    if declared_media_type in _METAFILE_MEDIA_TYPES:
        try:
            normalized, width, height = convert_metafile_to_png(payload)
        except MetafileConversionError as exc:
            raise _ImageInspectionError(
                DocxImportDiagnosticCode.UNSUPPORTED_IMAGE_TYPE
            ) from exc
        return normalized, "image/png", (width, height)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as image:
                detected_format = str(image.format or "").upper()
                width, height = image.size
                if width < 1 or height < 1 or width * height > _MAX_IMAGE_PIXELS:
                    raise _ImageInspectionError(DocxImportDiagnosticCode.INVALID_IMAGE)
                image.verify()
    except _ImageInspectionError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning) as exc:
        raise _ImageInspectionError(DocxImportDiagnosticCode.INVALID_IMAGE) from exc
    if detected_format in {"WMF", "EMF"}:
        try:
            normalized, width, height = convert_metafile_to_png(payload)
        except MetafileConversionError as exc:
            raise _ImageInspectionError(
                DocxImportDiagnosticCode.UNSUPPORTED_IMAGE_TYPE
            ) from exc
        return normalized, "image/png", (width, height)
    detected_media_type = _PIL_MEDIA_TYPES.get(detected_format)
    if detected_media_type is None:
        raise _ImageInspectionError(DocxImportDiagnosticCode.UNSUPPORTED_IMAGE_TYPE)
    normalized_declared = (
        "image/jpeg"
        if declared_media_type in {"image/jpeg", "image/jpg"}
        else declared_media_type
    )
    if normalized_declared != detected_media_type:
        raise _ImageInspectionError(DocxImportDiagnosticCode.IMAGE_MEDIA_TYPE_MISMATCH)
    return payload, detected_media_type, (width, height)


def _safe_package_part(name: str) -> bool:
    if not name or name.startswith("/") or "\\" in name:
        return False
    parts = PurePosixPath(name).parts
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def _source_part_for_rels(rels_part: str) -> str:
    path = PurePosixPath(rels_part)
    if rels_part == "_rels/.rels":
        return ""
    if path.parent.name != "_rels" or not path.name.endswith(".rels"):
        return ""
    return (path.parent.parent / path.name[: -len(".rels")]).as_posix()


def _resolve_relationship_target(source_part: str, target: str) -> str | None:
    if not target or target.startswith("/"):
        return None
    base = PurePosixPath(source_part).parent.as_posix() if source_part else ""
    normalized = posixpath.normpath(posixpath.join(base, target.replace("\\", "/")))
    if normalized == ".." or normalized.startswith("../") or normalized.startswith("/"):
        return None
    return PurePosixPath(normalized).as_posix()


def _allowed_hyperlink(target: str) -> bool:
    try:
        parsed = urlsplit(target)
    except ValueError:
        return False
    scheme = parsed.scheme.casefold()
    if scheme not in _ALLOWED_HYPERLINK_SCHEMES:
        return False
    if scheme in {"http", "https"}:
        return bool(parsed.netloc)
    return bool(parsed.path)


def _namespace(element: etree._Element) -> str:
    try:
        return etree.QName(element).namespace or ""
    except ValueError:
        return ""


def _local_name(element: etree._Element) -> str:
    try:
        return etree.QName(element).localname
    except ValueError:
        return str(element.tag)


def _element_path(element: etree._Element) -> str:
    try:
        return element.getroottree().getpath(element)
    except Exception:
        return "/"


def _w_attr(element: etree._Element | None, local: str) -> str:
    if element is None:
        return ""
    return str(element.get(f"{{{_W_NS}}}{local}", ""))


def _int_attr(element: etree._Element | None, local: str) -> int | None:
    raw = _w_attr(element, local)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _on_off_attr(element: etree._Element | None, local: str = "val") -> bool:
    if element is None:
        return False
    raw = _w_attr(element, local)
    if not raw:
        return True
    return raw.casefold() not in {"0", "false", "off", "none"}


def _merge_num_properties(
    num_pr: etree._Element,
    current_num_id: str,
    current_level: int | None,
) -> tuple[str, int | None]:
    num_id_node = num_pr.find("w:numId", namespaces=_NS)
    level_node = num_pr.find("w:ilvl", namespaces=_NS)
    num_id = _w_attr(num_id_node, "val") if num_id_node is not None else current_num_id
    level = _int_attr(level_node, "val") if level_node is not None else current_level
    return num_id, level


def _apply_rpr(
    formatting: _TextFormat,
    rpr: etree._Element | None,
) -> _TextFormat:
    if rpr is None:
        return formatting
    bold = formatting.bold
    italic = formatting.italic
    underline = formatting.underline
    strikethrough = formatting.strikethrough
    vertical_alignment = formatting.vertical_alignment
    bold_node = rpr.find("w:b", namespaces=_NS)
    if bold_node is None:
        bold_node = rpr.find("w:bCs", namespaces=_NS)
    if bold_node is not None:
        bold = _on_off_attr(bold_node)
    italic_node = rpr.find("w:i", namespaces=_NS)
    if italic_node is None:
        italic_node = rpr.find("w:iCs", namespaces=_NS)
    if italic_node is not None:
        italic = _on_off_attr(italic_node)
    underline_node = rpr.find("w:u", namespaces=_NS)
    if underline_node is not None:
        underline = _on_off_attr(underline_node)
    strike_node = rpr.find("w:strike", namespaces=_NS)
    if strike_node is None:
        strike_node = rpr.find("w:dstrike", namespaces=_NS)
    if strike_node is not None:
        strikethrough = _on_off_attr(strike_node)
    vertical_node = rpr.find("w:vertAlign", namespaces=_NS)
    if vertical_node is not None:
        raw_alignment = (_w_attr(vertical_node, "val") or "baseline").casefold()
        vertical_alignment = {
            "superscript": InlineVerticalAlignment.SUPERSCRIPT,
            "subscript": InlineVerticalAlignment.SUBSCRIPT,
            "baseline": InlineVerticalAlignment.BASELINE,
        }.get(raw_alignment, InlineVerticalAlignment.BASELINE)
    return _TextFormat(
        bold=bold,
        italic=italic,
        underline=underline,
        strikethrough=strikethrough,
        vertical_alignment=vertical_alignment,
    )


def _text_slice_to_inlines(
    atoms: Sequence[_InlineAtom],
    start: int,
    end: int,
) -> list[InlineContent]:
    if end <= start:
        return []
    result: list[InlineContent] = []
    cursor = 0
    for atom in atoms:
        atom_end = cursor + len(atom.text)
        overlap_start = max(start, cursor)
        overlap_end = min(end, atom_end)
        if overlap_end > overlap_start:
            text = atom.text[overlap_start - cursor : overlap_end - cursor]
            result.append(
                InlineContent(
                    text=text,
                    bold=atom.formatting.bold,
                    italic=atom.formatting.italic,
                    underline=atom.formatting.underline,
                    strikethrough=atom.formatting.strikethrough,
                    vertical_alignment=atom.formatting.vertical_alignment,
                )
            )
        cursor = atom_end
    return result


def _format_at(atoms: Sequence[_InlineAtom], position: int) -> _TextFormat:
    cursor = 0
    for atom in atoms:
        end = cursor + len(atom.text)
        if position < end:
            return atom.formatting
        cursor = end
    return atoms[-1].formatting if atoms else _TextFormat()


def _merge_inlines(inlines: Iterable[InlineContent]) -> list[InlineContent]:
    result: list[InlineContent] = []
    for inline in inlines:
        if (
            result
            and inline.kind is InlineKind.TEXT
            and result[-1].kind is InlineKind.TEXT
            and inline.bold == result[-1].bold
            and inline.italic == result[-1].italic
            and inline.underline == result[-1].underline
            and inline.strikethrough == result[-1].strikethrough
            and inline.vertical_alignment == result[-1].vertical_alignment
        ):
            previous = result[-1]
            result[-1] = InlineContent(
                text=previous.text + inline.text,
                bold=inline.bold,
                italic=inline.italic,
                underline=inline.underline,
                strikethrough=inline.strikethrough,
                vertical_alignment=inline.vertical_alignment,
            )
        else:
            result.append(inline)
    return result


__all__ = [
    "DOCX_MEDIA_TYPE",
    "DocxContentImportError",
    "DocxImportDiagnostic",
    "DocxImportDiagnosticCode",
    "ImportedDocxContent",
    "ImportedDocxResource",
    "import_docx_package",
]
