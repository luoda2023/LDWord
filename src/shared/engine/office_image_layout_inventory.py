"""OOXML image inventory and saved-package invariant verification."""

from __future__ import annotations

import json
import posixpath
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Mapping, Sequence

from lxml import etree

from src.shared.engine.office_image_layout_contracts import (
    OfficeImageJobReceipt,
    OfficeImageLayoutJob,
    OOXMLImageIdentity,
    job_owned_shape_id,
)
from src.shared.io.safe_docx_package import (
    DocxPackageError,
    DocxPackageLimits,
    SafeDocxPackage,
)

PREEXISTING_WP_EXTENT_TOLERANCE_EMU = 1000
OFFICE_DOCX_PACKAGE_LIMITS = DocxPackageLimits()

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_V_NS = "urn:schemas-microsoft-com:vml"
_W_BOOKMARK_START = f"{{{_W_NS}}}bookmarkStart"
_W_NAME = f"{{{_W_NS}}}name"
_W_P = f"{{{_W_NS}}}p"
_W_TC = f"{{{_W_NS}}}tc"
_W_R = f"{{{_W_NS}}}r"
_W_RPR = f"{{{_W_NS}}}rPr"
_W_T = f"{{{_W_NS}}}t"
_W_VAL = f"{{{_W_NS}}}val"
_W_VANISH = f"{{{_W_NS}}}vanish"
_W_WEB_HIDDEN = f"{{{_W_NS}}}webHidden"
_W_SPEC_VANISH = f"{{{_W_NS}}}specVanish"
_WP_ANCHOR = f"{{{_WP_NS}}}anchor"
_WP_INLINE = f"{{{_WP_NS}}}inline"
_WP_DOCPR = f"{{{_WP_NS}}}docPr"
_WP_EXTENT = f"{{{_WP_NS}}}extent"
_A_BLIP = f"{{{_A_NS}}}blip"
_V_IMAGE_DATA = f"{{{_V_NS}}}imagedata"
_V_SHAPE = f"{{{_V_NS}}}shape"
_R_EMBED = f"{{{_R_NS}}}embed"
_R_LINK = f"{{{_R_NS}}}link"
_R_ID_ATTR = f"{{{_R_NS}}}id"
_R_HREF = f"{{{_R_NS}}}href"
_REL_ID = "Id"
_REL_TARGET = "Target"
_REL_TARGET_MODE = "TargetMode"
_REL_TYPE = "Type"
_IMAGE_REL_SUFFIX = "/image"

# Public schema tags used by parent preflight and the Office child.  The OOXML
# namespace construction remains owned here so callers do not duplicate it.
W_NAMESPACE = _W_NS
W_PARAGRAPH_TAG = _W_P
W_TABLE_CELL_TAG = _W_TC
W_BOOKMARK_START_TAG = _W_BOOKMARK_START
W_BOOKMARK_NAME_ATTRIBUTE = _W_NAME
WP_ANCHOR_TAG = _WP_ANCHOR

@dataclass(frozen=True, slots=True)
class _ImageInventoryVerification:
    preexisting_unchanged: bool
    inserted_images_job_owned: bool
    inserted_images_visible: bool
    matched_preexisting: tuple[OOXMLImageIdentity, ...]
    inserted: tuple[OOXMLImageIdentity, ...]

def inventory_ooxml_images(
    path: str | Path,
    *,
    limits: DocxPackageLimits | None = None,
) -> tuple[OOXMLImageIdentity, ...]:
    """Return a deterministic inventory of image references in all Word parts.

    OOXML package metadata is intentionally ignored.  An internal relationship
    is bound to the SHA-256 of its actual ZIP member, while an external link is
    bound to its relationship id/type/target without fetching remote content.
    """

    try:
        package = SafeDocxPackage.open_path(
            path,
            limits=limits or OFFICE_DOCX_PACKAGE_LIMITS,
        )
        return _inventory_ooxml_images_from_package(package)
    except DocxPackageError as exc:
        raise ValueError(
            f"invalid DOCX image inventory [{exc.code}]: {exc}"
        ) from exc

def _inventory_ooxml_images_from_package(
    package: SafeDocxPackage,
) -> tuple[OOXMLImageIdentity, ...]:
    identities: list[OOXMLImageIdentity] = []
    name_set = set(package.part_names)
    for part_name in sorted(
        name
        for name in name_set
        if name.startswith("word/") and name.endswith(".xml")
    ):
        root = package.parse_xml(part_name)
        relationships = _image_relationships_for_part(
            package,
            name_set,
            part_name,
        )
        for element in root.iter():
            if element.tag in {_WP_INLINE, _WP_ANCHOR}:
                drawing_kind = "inline" if element.tag == _WP_INLINE else "anchor"
                doc_pr = next(element.iter(_WP_DOCPR), None)
                doc_pr_values = {
                    "id": "" if doc_pr is None else str(doc_pr.get("id", "")),
                    "name": "" if doc_pr is None else str(doc_pr.get("name", "")),
                    "descr": "" if doc_pr is None else str(doc_pr.get("descr", "")),
                    "title": "" if doc_pr is None else str(doc_pr.get("title", "")),
                }
                drawing_semantic_sha256 = _drawing_semantic_sha256(
                    element,
                    relationships,
                )
                extent = next(element.iter(_WP_EXTENT), None)
                extent_cx = 0 if extent is None else int(str(extent.get("cx", "0")))
                extent_cy = 0 if extent is None else int(str(extent.get("cy", "0")))
                if extent_cx < 0 or extent_cy < 0:
                    raise ValueError(f"{part_name} drawing has a negative wp:extent")
                refs: list[tuple[str, str]] = []
                for descendant in element.iter():
                    for reference, attribute in (
                        ("embed", _R_EMBED),
                        ("link", _R_LINK),
                    ):
                        relationship_id = str(descendant.get(attribute, ""))
                        if relationship_id:
                            refs.append((reference, relationship_id))
                for reference, relationship_id in refs:
                    relationship = relationships.get(relationship_id)
                    if relationship is None:
                        raise ValueError(
                            f"{part_name} image references missing relationship "
                            f"{relationship_id}"
                        )
                    if not relationship[0].endswith(_IMAGE_REL_SUFFIX):
                        continue
                    identities.append(
                        _ooxml_image_identity(
                            package,
                            name_set,
                            part_name=part_name,
                            drawing_kind=drawing_kind,
                            doc_pr_id=doc_pr_values["id"],
                            doc_pr_name=doc_pr_values["name"],
                            alternative_text=doc_pr_values["descr"],
                            title=doc_pr_values["title"],
                            run_visibility=_drawing_run_visibility(element),
                            layout_extent_cx_emu=extent_cx,
                            layout_extent_cy_emu=extent_cy,
                            drawing_semantic_sha256=drawing_semantic_sha256,
                            relationship_reference=reference,
                            relationship_id=relationship_id,
                            relationship=relationship,
                        )
                    )
            elif element.tag == _V_IMAGE_DATA:
                shape = xml_ancestor(element, _V_SHAPE)
                doc_pr_id = "" if shape is None else str(shape.get("id", ""))
                doc_pr_name = "" if shape is None else str(shape.get("title", ""))
                drawing_semantic_sha256 = _drawing_semantic_sha256(
                    element if shape is None else shape,
                    relationships,
                )
                for reference, attribute in (
                    ("id", _R_ID_ATTR),
                    ("href", _R_HREF),
                ):
                    relationship_id = str(element.get(attribute, ""))
                    if not relationship_id:
                        continue
                    relationship = relationships.get(relationship_id)
                    if relationship is None:
                        raise ValueError(
                            f"{part_name} VML image references missing relationship "
                            f"{relationship_id}"
                        )
                    if not relationship[0].endswith(_IMAGE_REL_SUFFIX):
                        continue
                    identities.append(
                        _ooxml_image_identity(
                            package,
                            name_set,
                            part_name=part_name,
                            drawing_kind="vml",
                            doc_pr_id=doc_pr_id,
                            doc_pr_name=doc_pr_name,
                            alternative_text=(
                                "" if shape is None else str(shape.get("alt", ""))
                            ),
                            title=(
                                "" if shape is None else str(shape.get("title", ""))
                            ),
                            run_visibility=_drawing_run_visibility(element),
                            layout_extent_cx_emu=0,
                            layout_extent_cy_emu=0,
                            drawing_semantic_sha256=drawing_semantic_sha256,
                            relationship_reference=reference,
                            relationship_id=relationship_id,
                            relationship=relationship,
                        )
                    )
    return tuple(sorted(identities, key=lambda item: item.sort_key))

def image_inventory_sha256(inventory: Sequence[OOXMLImageIdentity]) -> str:
    ordered = sorted(tuple(inventory or ()), key=lambda item: item.sort_key)
    encoded = json.dumps(
        [item.to_dict() for item in ordered],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()

def image_preservation_sha256(inventory: Sequence[OOXMLImageIdentity]) -> str:
    keys = sorted(item.preservation_key for item in tuple(inventory or ()))
    encoded = json.dumps(
        keys,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()

def marker_text_run_visibility(
    path: str | Path,
    marker_names: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    requested = {str(item) for item in marker_names if str(item)}
    result: dict[str, list[str]] = {name: [] for name in requested}
    if not requested:
        return {}
    try:
        package = SafeDocxPackage.open_path(
            path,
            limits=OFFICE_DOCX_PACKAGE_LIMITS,
        )
        root = package.parse_xml("word/document.xml")
    except DocxPackageError as exc:
        raise ValueError(f"cannot inspect image sentinel visibility: {exc}") from exc
    for text_element in root.iter(_W_T):
        value = str(text_element.text or "")
        if value in result:
            result[value].append(_drawing_run_visibility(text_element))
    return {name: tuple(values) for name, values in result.items()}

def _image_relationships_for_part(
    package: SafeDocxPackage,
    names: set[str],
    part_name: str,
) -> dict[str, tuple[str, str, str]]:
    directory, filename = posixpath.split(part_name)
    relationships_name = posixpath.join(directory, "_rels", filename + ".rels")
    if relationships_name not in names:
        return {}
    root = package.parse_xml(relationships_name)
    result: dict[str, tuple[str, str, str]] = {}
    for element in root:
        if element.tag != f"{{{_REL_NS}}}Relationship":
            continue
        relationship_id = str(element.get(_REL_ID, ""))
        if not relationship_id:
            raise ValueError(f"{relationships_name} contains a relationship without Id")
        if relationship_id in result:
            raise ValueError(
                f"{relationships_name} contains duplicate relationship {relationship_id}"
            )
        result[relationship_id] = (
            str(element.get(_REL_TYPE, "")),
            str(element.get(_REL_TARGET, "")),
            str(element.get(_REL_TARGET_MODE, "")),
        )
    return result

def _ooxml_on(element: etree._Element) -> bool:
    return str(element.get(_W_VAL, "true")).strip().casefold() not in {
        "0",
        "false",
        "off",
        "no",
    }

def _drawing_run_visibility(element: etree._Element) -> str:
    run = xml_ancestor(element, _W_R)
    if run is None:
        return "outside_run"
    rpr = next((child for child in run if child.tag == _W_RPR), None)
    if rpr is None:
        return "visible"
    hidden_tags = (
        (_W_VANISH, "vanish"),
        (_W_WEB_HIDDEN, "web_hidden"),
        (_W_SPEC_VANISH, "spec_vanish"),
    )
    markers = sorted(
        label
        for tag, label in hidden_tags
        for child in rpr
        if child.tag == tag and _ooxml_on(child)
    )
    return "+".join(markers) if markers else "visible"

def _drawing_semantic_sha256(
    element: etree._Element,
    relationships: Mapping[str, tuple[str, str, str]],
) -> str:
    """Hash drawing semantics without provider-local ids or XML presentation.

    The structural JSON ignores namespace prefixes/indentation, replaces local
    relationship ids by their targets, and removes provider-normalized editing
    metadata.  Inline distance defaults, derived effect extents, non-visual
    picture metadata, and editing locks are not appearance/placement ownership.
    ``wp:extent`` is recorded raw and checked separately with the evidenced WPS
    quantization tolerance; DrawingML ``a:xfrm/a:ext`` stays exact.  Anchor/
    wrap, crop, transform, effects, geometry, docPr name/alt/title,
    relationship target, and media bytes remain covered.
    """

    def structural(node: etree._Element) -> object | None:
        tag = etree.QName(node.tag)
        if node.tag == _WP_EXTENT:
            return None
        if tag.namespace == _WP_NS and tag.localname in {
            "effectExtent",
            "cNvGraphicFramePr",
        }:
            return None
        if tag.namespace == _PIC_NS and tag.localname in {"cNvPr", "cNvPicPr"}:
            return None
        if (
            tag.namespace == _A_NS
            and tag.localname == "avLst"
            and not node.attrib
            and not len(node)
            and not str(node.text or "").strip()
        ):
            return None
        attributes: list[tuple[str, str]] = []
        for raw_name, raw_value in node.attrib.items():
            attribute = etree.QName(raw_name)
            if node.tag == _WP_DOCPR and attribute.localname == "id":
                continue
            if node.tag == _V_SHAPE and attribute.localname == "id":
                continue
            if attribute.localname in {"anchorId", "editId"}:
                continue
            value = str(raw_value)
            # Inline distance attributes are ignored by WordprocessingML's
            # in-flow layout and are provider defaults (WPS writes 9pt left/
            # right on save).  Anchor distances remain covered because they do
            # affect floating wrapping.
            if node.tag == _WP_INLINE:
                continue
            if attribute.namespace == _R_NS and attribute.localname in {
                "embed",
                "link",
                "id",
                "href",
            }:
                relationship = relationships.get(value)
                if relationship is not None:
                    value = "|".join(
                        (
                            relationship[0],
                            relationship[1],
                            relationship[2].casefold() or "internal",
                        )
                    )
            attributes.append((str(raw_name), value))
        children = []
        for child in node:
            if not isinstance(child.tag, str):
                continue
            child_value = structural(child)
            if child_value is not None:
                children.append(child_value)
        text = str(node.text or "")
        if not text.strip():
            text = ""
        return (
            (str(tag.namespace or ""), tag.localname),
            tuple(sorted(attributes)),
            text,
            tuple(children),
        )

    encoded = json.dumps(
        structural(element),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()

def _ooxml_image_identity(
    package: SafeDocxPackage,
    names: set[str],
    *,
    part_name: str,
    drawing_kind: str,
    doc_pr_id: str,
    doc_pr_name: str,
    alternative_text: str,
    title: str,
    run_visibility: str,
    layout_extent_cx_emu: int,
    layout_extent_cy_emu: int,
    drawing_semantic_sha256: str,
    relationship_reference: str,
    relationship_id: str,
    relationship: tuple[str, str, str],
) -> OOXMLImageIdentity:
    relationship_type, relationship_target, target_mode_raw = relationship
    if not relationship_target:
        raise ValueError(f"{part_name} relationship {relationship_id} has no Target")
    external = target_mode_raw.casefold() == "external"
    media_part_name = ""
    media_sha256 = ""
    if not external:
        if relationship_target.startswith("/"):
            media_part_name = posixpath.normpath(relationship_target.lstrip("/"))
        else:
            media_part_name = posixpath.normpath(
                posixpath.join(posixpath.dirname(part_name), relationship_target)
            )
        if media_part_name.startswith("../") or media_part_name not in names:
            raise ValueError(
                f"{part_name} relationship {relationship_id} targets missing package "
                f"member {media_part_name!r}"
            )
        media_sha256 = sha256(package.read_part(media_part_name)).hexdigest()
    return OOXMLImageIdentity(
        part_name=part_name,
        drawing_kind=drawing_kind,
        doc_pr_id=doc_pr_id,
        doc_pr_name=doc_pr_name,
        alternative_text=alternative_text,
        title=title,
        run_visibility=run_visibility,
        layout_extent_cx_emu=layout_extent_cx_emu,
        layout_extent_cy_emu=layout_extent_cy_emu,
        drawing_semantic_sha256=drawing_semantic_sha256,
        relationship_reference=relationship_reference,
        relationship_id=relationship_id,
        relationship_type=relationship_type,
        relationship_target=relationship_target,
        target_mode="external" if external else "internal",
        media_part_name=media_part_name,
        media_sha256=media_sha256,
    )

def verify_ooxml_image_invariants(
    before: Sequence[OOXMLImageIdentity],
    after: Sequence[OOXMLImageIdentity],
    request_jobs: Sequence[OfficeImageLayoutJob],
    job_receipts: Sequence[OfficeImageJobReceipt],
) -> _ImageInventoryVerification:
    remaining = list(sorted(tuple(after or ()), key=lambda item: item.sort_key))
    matched_preexisting: list[OOXMLImageIdentity] = []
    preexisting_unchanged = True
    for existing in sorted(tuple(before or ()), key=lambda item: item.sort_key):
        candidates = [
            (index, candidate)
            for index, candidate in enumerate(remaining)
            if candidate.preservation_key == existing.preservation_key
        ]
        if not candidates:
            preexisting_unchanged = False
            continue
        matched_index, matched = min(
            candidates,
            key=lambda item: (
                max(
                    abs(
                        item[1].layout_extent_cx_emu
                        - existing.layout_extent_cx_emu
                    ),
                    abs(
                        item[1].layout_extent_cy_emu
                        - existing.layout_extent_cy_emu
                    ),
                ),
                item[1].sort_key,
            ),
        )
        if (
            abs(matched.layout_extent_cx_emu - existing.layout_extent_cx_emu)
            > PREEXISTING_WP_EXTENT_TOLERANCE_EMU
            or abs(matched.layout_extent_cy_emu - existing.layout_extent_cy_emu)
            > PREEXISTING_WP_EXTENT_TOLERANCE_EMU
        ):
            preexisting_unchanged = False
        matched_preexisting.append(remaining.pop(matched_index))
    inserted = tuple(remaining)
    expected = Counter(
        (
            job_owned_shape_id(job.job_id),
            job.job_id,
            job.prepared_image.output_sha256,
        )
        for job in request_jobs
    )
    receipted = Counter(
        (item.shape_id, item.job_id, item.prepared_image_sha256)
        for item in job_receipts
    )
    actual = Counter(
        (item.alternative_text, item.title, item.media_sha256)
        for item in inserted
    )
    inserted_images_job_owned = (
        preexisting_unchanged
        and receipted == expected
        and actual == expected
        and all(
            item.drawing_kind == "inline"
            and item.relationship_reference == "embed"
            and item.target_mode == "internal"
            and item.relationship_type.endswith(_IMAGE_REL_SUFFIX)
            for item in inserted
        )
    )
    inserted_images_visible = inserted_images_job_owned and all(
        item.run_visibility == "visible" for item in inserted
    )
    return _ImageInventoryVerification(
        preexisting_unchanged=preexisting_unchanged,
        inserted_images_job_owned=inserted_images_job_owned,
        inserted_images_visible=inserted_images_visible,
        matched_preexisting=tuple(matched_preexisting),
        inserted=inserted,
    )

def xml_ancestor(element: etree._Element, tag: str) -> etree._Element | None:
    current = element.getparent()
    while current is not None:
        if current.tag == tag:
            return current
        current = current.getparent()
    return None

__all__ = [
    "OFFICE_DOCX_PACKAGE_LIMITS",
    "PREEXISTING_WP_EXTENT_TOLERANCE_EMU",
    "W_BOOKMARK_NAME_ATTRIBUTE",
    "W_BOOKMARK_START_TAG",
    "W_NAMESPACE",
    "W_PARAGRAPH_TAG",
    "W_TABLE_CELL_TAG",
    "WP_ANCHOR_TAG",
    "image_inventory_sha256",
    "image_preservation_sha256",
    "inventory_ooxml_images",
    "marker_text_run_visibility",
    "verify_ooxml_image_invariants",
    "xml_ancestor",
]
