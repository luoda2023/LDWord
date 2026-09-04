"""DOCX XML/media relationship recovery helpers for material assets."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile

SUPPORTED_DOCX_IMAGE_SUFFIXES = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}


def normalize_docx_relationship_target(
    target: str,
    *,
    source_part_path: str = "word/document.xml",
) -> str:
    cleaned = str(target or "").strip().replace("\\", "/")
    if not cleaned:
        return ""
    cleaned = cleaned.split("#", 1)[0].split("?", 1)[0]
    if cleaned.startswith("/"):
        normalized = posixpath.normpath(cleaned.lstrip("/"))
    else:
        base_dir = posixpath.dirname(str(source_part_path or "word/document.xml"))
        normalized = posixpath.normpath(posixpath.join(base_dir or "word", cleaned))
    return "" if normalized == "." else normalized


def docx_part_relationships_path(
    part_name: str,
) -> str:
    normalized = str(part_name or "").strip().replace("\\", "/")
    if not normalized or "/" not in normalized:
        return ""
    return (
        f"{posixpath.dirname(normalized)}/_rels/"
        f"{posixpath.basename(normalized)}.rels"
    )


def docx_image_part_kind(
    part_name: str,
) -> str:
    basename = posixpath.basename(str(part_name or ""))
    if basename == "document.xml":
        return "document"
    if re.match(r"^header\d+\.xml$", basename):
        return "header"
    if re.match(r"^footer\d+\.xml$", basename):
        return "footer"
    return "other"


def docx_image_part_names(
    names: set[str],
) -> list[str]:
    candidates = [
        name
        for name in names
        if re.match(r"^word/(document|header\d+|footer\d+)\.xml$", name)
    ]
    if "word/document.xml" not in candidates:
        candidates.insert(0, "word/document.xml")
    return sorted(
        dict.fromkeys(candidates),
        key=lambda item: (
            0 if item == "word/document.xml" else 1,
            docx_image_part_kind(item),
            item,
        ),
    )


def scan_docx_xml_media(
    docx_path: Path,
) -> dict[str, object]:
    path = Path(docx_path)
    result: dict[str, object] = {
        "path": str(path),
        "status": "pending",
        "document_xml_present": False,
        "relationships_present": False,
        "document_image_reference_ids": [],
        "header_footer_image_reference_ids": [],
        "image_relationship_ids": [],
        "header_footer_image_relationship_ids": [],
        "relationship_media_paths": [],
        "header_footer_relationship_media_paths": [],
        "media_paths": [],
        "missing_relationship_ids": [],
        "unreferenced_relationship_ids": [],
        "missing_media_paths": [],
        "orphan_media_paths": [],
        "word_image_part_rows": [],
        "scanned_part_count": 0,
        "header_footer_part_count": 0,
        "header_footer_relationship_status": "not_scanned",
        "header_footer_media_status": "not_scanned",
        "relationship_status": "not_scanned",
        "media_status": "not_scanned",
    }
    if not path.is_file() or path.suffix.lower() != ".docx":
        result.update(
            {
                "status": "missing_docx",
                "relationship_status": "missing_docx",
                "media_status": "missing_docx",
            }
        )
        return result
    if not zipfile.is_zipfile(path):
        result.update(
            {
                "status": "invalid_docx",
                "relationship_status": "invalid_docx",
                "media_status": "invalid_docx",
            }
        )
        return result
    relationship_namespace = (
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    )
    package_relationship_type_image = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
    )
    try:
        with zipfile.ZipFile(path) as archive:
            names = {
                name
                for name in archive.namelist()
                if name and not name.endswith("/")
            }
            media_paths = sorted(name for name in names if name.startswith("word/media/"))
            result["media_paths"] = media_paths
            all_part_rows: list[dict[str, object]] = []
            document_rel_ids: set[str] = set()
            header_footer_rel_ids: set[str] = set()
            image_relationship_ids: set[str] = set()
            header_footer_image_relationship_ids: set[str] = set()
            relationship_media_paths: set[str] = set()
            header_footer_relationship_media_paths: set[str] = set()
            missing_relationship_ids: set[str] = set()
            unreferenced_relationship_ids: set[str] = set()
            missing_media_paths: set[str] = set()
            document_xml_present = "word/document.xml" in names
            relationships_present = "word/_rels/document.xml.rels" in names
            result["document_xml_present"] = document_xml_present
            result["relationships_present"] = relationships_present
            for part_name in docx_image_part_names(
                names
            ):
                part_kind = docx_image_part_kind(
                    part_name
                )
                rels_name = docx_part_relationships_path(
                    part_name
                )
                part_xml_present = part_name in names
                part_relationships_present = rels_name in names
                part_document_rel_ids: set[str] = set()
                part_image_relationship_ids: set[str] = set()
                part_all_relationship_ids: set[str] = set()
                part_relationship_media_paths: set[str] = set()
                part_status = "not_scanned"
                part_relationship_status = "not_scanned"
                part_media_status = "not_scanned"
                if part_xml_present:
                    part_xml = archive.read(part_name)
                    try:
                        part_root = ET.fromstring(part_xml)
                        for element in part_root.iter():
                            for attr_key, attr_value in element.attrib.items():
                                if attr_key in {
                                    f"{relationship_namespace}embed",
                                    f"{relationship_namespace}link",
                                } and str(attr_value or "").strip():
                                    part_document_rel_ids.add(str(attr_value).strip())
                    except ET.ParseError:
                        result.update(
                            {
                                "status": f"{part_kind}_xml_parse_failed",
                                "relationship_status": f"{part_kind}_xml_parse_failed",
                                "media_status": "not_scanned",
                                "word_image_part_rows": all_part_rows,
                            }
                        )
                        return result
                elif part_name == "word/document.xml":
                    part_relationship_status = "xml_relationship_missing"
                    part_media_status = "media_not_scanned"
                    part_status = "xml_relationship_missing"
                if part_relationships_present:
                    relationships_xml = archive.read(rels_name)
                    try:
                        relationships_root = ET.fromstring(relationships_xml)
                        for relationship in relationships_root:
                            rel_id = str(relationship.attrib.get("Id") or "").strip()
                            rel_type = str(relationship.attrib.get("Type") or "").strip()
                            target = str(relationship.attrib.get("Target") or "").strip()
                            target_mode = str(
                                relationship.attrib.get("TargetMode") or ""
                            ).strip()
                            if rel_id:
                                part_all_relationship_ids.add(rel_id)
                            if rel_id and rel_type == package_relationship_type_image:
                                part_image_relationship_ids.add(rel_id)
                                if target_mode.lower() != "external":
                                    normalized_target = normalize_docx_relationship_target(
                                        target,
                                        source_part_path=part_name,
                                    )
                                    if normalized_target:
                                        part_relationship_media_paths.add(
                                            normalized_target
                                        )
                    except ET.ParseError:
                        result.update(
                            {
                                "status": f"{part_kind}_relationships_parse_failed",
                                "relationship_status": f"{part_kind}_relationships_parse_failed",
                                "media_status": "not_scanned",
                                "word_image_part_rows": all_part_rows,
                            }
                        )
                        return result
                part_missing_relationship_ids = sorted(
                    part_document_rel_ids.difference(part_all_relationship_ids)
                )
                part_unreferenced_relationship_ids = sorted(
                    part_image_relationship_ids.difference(part_document_rel_ids)
                )
                part_missing_media_paths = sorted(
                    part_relationship_media_paths.difference(set(media_paths))
                )
                if part_status == "not_scanned":
                    if not part_xml_present:
                        part_relationship_status = "xml_relationship_missing"
                        part_media_status = "media_not_scanned"
                        part_status = "xml_relationship_missing"
                    elif part_document_rel_ids and not part_relationships_present:
                        part_relationship_status = "xml_relationship_missing"
                        part_media_status = "media_not_scanned"
                        part_status = "xml_relationship_missing"
                    elif (
                        part_missing_relationship_ids
                        or part_unreferenced_relationship_ids
                    ):
                        part_relationship_status = "relationship_repair_required"
                        part_media_status = (
                            "media_repair_required"
                            if part_missing_media_paths
                            else "media_consistent"
                        )
                        part_status = "xml_media_repair_required"
                    elif part_missing_media_paths:
                        part_relationship_status = "relationship_consistent"
                        part_media_status = "media_repair_required"
                        part_status = "xml_media_repair_required"
                    else:
                        part_relationship_status = "relationship_consistent"
                        part_media_status = "media_consistent"
                        part_status = "xml_media_consistent"
                row = {
                    "part_name": part_name,
                    "part_kind": part_kind,
                    "relationships_name": rels_name,
                    "xml_present": part_xml_present,
                    "relationships_present": part_relationships_present,
                    "image_reference_ids": sorted(part_document_rel_ids),
                    "image_relationship_ids": sorted(part_image_relationship_ids),
                    "relationship_media_paths": sorted(part_relationship_media_paths),
                    "missing_relationship_ids": part_missing_relationship_ids,
                    "unreferenced_relationship_ids": part_unreferenced_relationship_ids,
                    "missing_media_paths": part_missing_media_paths,
                    "relationship_status": part_relationship_status,
                    "media_status": part_media_status,
                    "status": part_status,
                }
                all_part_rows.append(row)
                if part_kind == "document":
                    document_rel_ids.update(part_document_rel_ids)
                elif part_kind in {"header", "footer"}:
                    header_footer_rel_ids.update(part_document_rel_ids)
                    header_footer_image_relationship_ids.update(
                        part_image_relationship_ids
                    )
                    header_footer_relationship_media_paths.update(
                        part_relationship_media_paths
                    )
                image_relationship_ids.update(part_image_relationship_ids)
                relationship_media_paths.update(part_relationship_media_paths)
                missing_relationship_ids.update(part_missing_relationship_ids)
                unreferenced_relationship_ids.update(part_unreferenced_relationship_ids)
                missing_media_paths.update(part_missing_media_paths)
            orphan_media_paths = sorted(set(media_paths).difference(relationship_media_paths))
            for row in all_part_rows:
                row["orphan_media_paths"] = orphan_media_paths
            orphan_media_paths = sorted(
                set(media_paths).difference(relationship_media_paths)
            )
            if any(
                str(row.get("relationship_status") or "")
                in {
                    "document_xml_parse_failed",
                    "relationships_parse_failed",
                    "header_xml_parse_failed",
                    "header_relationships_parse_failed",
                    "footer_xml_parse_failed",
                    "footer_relationships_parse_failed",
                }
                for row in all_part_rows
            ):
                relationship_status = "relationship_scan_failed"
            elif any(
                str(row.get("relationship_status") or "") == "xml_relationship_missing"
                for row in all_part_rows
            ):
                relationship_status = "xml_relationship_missing"
            elif missing_relationship_ids or unreferenced_relationship_ids:
                relationship_status = "relationship_repair_required"
            else:
                relationship_status = "relationship_consistent"
            if relationship_status == "relationship_scan_failed":
                media_status = "not_scanned"
            elif any(
                str(row.get("media_status") or "") == "media_not_scanned"
                for row in all_part_rows
            ):
                media_status = "media_not_scanned"
            elif missing_media_paths or orphan_media_paths:
                media_status = "media_repair_required"
            else:
                media_status = "media_consistent"
            header_footer_rows = [
                row
                for row in all_part_rows
                if str(row.get("part_kind") or "") in {"header", "footer"}
            ]
            if not header_footer_rows:
                header_footer_relationship_status = "not_present"
                header_footer_media_status = "not_present"
            elif all(
                str(row.get("relationship_status") or "") == "relationship_consistent"
                for row in header_footer_rows
            ):
                header_footer_relationship_status = "relationship_consistent"
            elif any(
                str(row.get("relationship_status") or "")
                == "relationship_repair_required"
                for row in header_footer_rows
            ):
                header_footer_relationship_status = "relationship_repair_required"
            else:
                header_footer_relationship_status = "xml_relationship_missing"
            if not header_footer_rows:
                header_footer_media_status = "not_present"
            elif all(
                str(row.get("media_status") or "") == "media_consistent"
                for row in header_footer_rows
            ):
                header_footer_media_status = "media_consistent"
            elif any(
                str(row.get("media_status") or "") == "media_repair_required"
                for row in header_footer_rows
            ):
                header_footer_media_status = "media_repair_required"
            else:
                header_footer_media_status = "media_not_scanned"
            if relationship_status == "relationship_consistent" and (
                media_status == "media_consistent"
            ):
                status = "xml_media_consistent"
            elif relationship_status == "xml_relationship_missing":
                status = "xml_relationship_missing"
            else:
                status = "xml_media_repair_required"
            result.update(
                {
                    "status": status,
                    "relationship_status": relationship_status,
                    "media_status": media_status,
                    "document_image_reference_ids": sorted(document_rel_ids),
                    "header_footer_image_reference_ids": sorted(header_footer_rel_ids),
                    "image_relationship_ids": sorted(image_relationship_ids),
                    "header_footer_image_relationship_ids": sorted(
                        header_footer_image_relationship_ids
                    ),
                    "relationship_media_paths": sorted(relationship_media_paths),
                    "header_footer_relationship_media_paths": sorted(
                        header_footer_relationship_media_paths
                    ),
                    "missing_relationship_ids": sorted(missing_relationship_ids),
                    "unreferenced_relationship_ids": sorted(
                        unreferenced_relationship_ids
                    ),
                    "missing_media_paths": sorted(missing_media_paths),
                    "orphan_media_paths": orphan_media_paths,
                    "word_image_part_rows": all_part_rows,
                    "scanned_part_count": len(all_part_rows),
                    "header_footer_part_count": len(header_footer_rows),
                    "header_footer_relationship_status": header_footer_relationship_status,
                    "header_footer_media_status": header_footer_media_status,
                }
            )
            return result
    except (OSError, zipfile.BadZipFile):
        result.update(
            {
                "status": "docx_scan_failed",
                "relationship_status": "docx_scan_failed",
                "media_status": "docx_scan_failed",
            }
        )
        return result




def docx_image_content_type(
    extension: str,
) -> str:
    normalized = str(extension or "").strip().lower().lstrip(".")
    return {
        "bmp": "image/bmp",
        "gif": "image/gif",
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "png": "image/png",
        "tif": "image/tiff",
        "tiff": "image/tiff",
        "webp": "image/webp",
    }.get(normalized, "application/octet-stream")


def update_docx_content_types(
    content_types_xml: bytes | None,
    extensions: Sequence[str],
) -> bytes:
    package_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
    ET.register_namespace("", package_ns)
    if content_types_xml:
        try:
            root = ET.fromstring(content_types_xml)
        except ET.ParseError:
            root = ET.Element(f"{{{package_ns}}}Types")
    else:
        root = ET.Element(f"{{{package_ns}}}Types")
    root_ns = package_ns
    if root.tag.startswith("{") and "}" in root.tag:
        root_ns = root.tag[1:].split("}", 1)[0]
    default_tag = f"{{{root_ns}}}Default"
    existing = {
        str(child.attrib.get("Extension") or "").strip().lower()
        for child in root
        if child.tag.endswith("Default")
    }
    for extension in extensions:
        normalized = str(extension or "").strip().lower().lstrip(".")
        if not normalized or normalized in existing:
            continue
        ET.SubElement(
            root,
            default_tag,
            {
                "Extension": normalized,
                "ContentType": docx_image_content_type(normalized),
            },
        )
        existing.add(normalized)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def available_asset_image_paths(
    asset_rows: Sequence[Mapping[str, object]],
) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for row in asset_rows:
        image_path = str(row.get("image_path") or "").strip()
        if not image_path:
            continue
        path = Path(image_path).expanduser()
        if path.suffix.lower() not in SUPPORTED_DOCX_IMAGE_SUFFIXES:
            continue
        if not path.is_file():
            continue
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
    return paths


def deep_repair_docx_xml_media(
    input_docx_path: Path,
    output_docx_path: Path,
    asset_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    input_path = Path(input_docx_path)
    output_path = Path(output_docx_path)
    pre_scan = scan_docx_xml_media(
        input_path
    )
    result: dict[str, object] = {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "rollback_source_path": str(input_path),
        "status": "deep_repair_not_started",
        "relationship_repair_status": "not_started",
        "media_repair_status": "not_started",
        "rollback_connector_status": "rollback_not_available",
        "pre_scan": dict(pre_scan),
        "post_scan": {},
        "added_relationship_ids": [],
        "removed_relationship_ids": [],
        "added_media_paths": [],
        "removed_media_paths": [],
        "missing_relationship_repaired_count": 0,
        "unreferenced_relationship_removed_count": 0,
        "missing_media_repaired_count": 0,
        "orphan_media_removed_count": 0,
    }
    if str(pre_scan.get("status") or "") in {"missing_docx", "invalid_docx"}:
        result.update(
            {
                "status": "deep_repair_blocked_invalid_docx",
                "relationship_repair_status": str(
                    pre_scan.get("relationship_status") or "invalid_docx"
                ),
                "media_repair_status": str(
                    pre_scan.get("media_status") or "invalid_docx"
                ),
            }
        )
        return result
    if not zipfile.is_zipfile(input_path):
        result.update(
            {
                "status": "deep_repair_blocked_invalid_docx",
                "relationship_repair_status": "invalid_docx",
                "media_repair_status": "invalid_docx",
            }
        )
        return result

    available_images = available_asset_image_paths(
        asset_rows
    )
    primary_image = available_images[0] if available_images else None
    relationship_package_ns = (
        "http://schemas.openxmlformats.org/package/2006/relationships"
    )
    image_relationship_type = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
    )
    ET.register_namespace("", relationship_package_ns)
    part_rows = [
        dict(row)
        for row in pre_scan.get("word_image_part_rows", []) or []
        if isinstance(row, Mapping)
    ]
    if not part_rows:
        part_rows = [
            {
                "part_name": "word/document.xml",
                "part_kind": "document",
                "relationships_name": "word/_rels/document.xml.rels",
                "missing_relationship_ids": list(
                    pre_scan.get("missing_relationship_ids") or []
                ),
                "unreferenced_relationship_ids": list(
                    pre_scan.get("unreferenced_relationship_ids") or []
                ),
                "missing_media_paths": list(pre_scan.get("missing_media_paths") or []),
            }
        ]
    all_missing_media_paths = {
        str(item).strip()
        for row in part_rows
        for item in row.get("missing_media_paths", []) or []
        if str(item or "").strip()
    }
    orphan_media_paths = {
        str(item).strip()
        for item in pre_scan.get("orphan_media_paths") or []
        if str(item or "").strip()
    }
    add_media_files: dict[str, Path] = {}
    add_relationship_rows: list[tuple[str, str, str]] = []
    remove_relationship_ids: set[str] = set()
    remove_media_paths: set[str] = set(orphan_media_paths)
    modified_relationships_xml_by_path: dict[str, bytes] = {}
    modified_content_types_xml: bytes | None = None

    try:
        with zipfile.ZipFile(input_path) as source:
            names = {
                name
                for name in source.namelist()
                if name and not name.endswith("/")
            }
            for part_row in part_rows:
                part_name = str(part_row.get("part_name") or "").strip()
                if not part_name or part_name not in names:
                    continue
                rels_name = str(part_row.get("relationships_name") or "").strip()
                if not rels_name:
                    rels_name = docx_part_relationships_path(
                        part_name
                    )
                if not rels_name:
                    continue
                relationship_xml = source.read(rels_name) if rels_name in names else b""
                if relationship_xml:
                    try:
                        relationships_root = ET.fromstring(relationship_xml)
                    except ET.ParseError:
                        relationships_root = ET.Element(
                            f"{{{relationship_package_ns}}}Relationships"
                        )
                else:
                    relationships_root = ET.Element(
                        f"{{{relationship_package_ns}}}Relationships"
                    )
                root_ns = relationship_package_ns
                if relationships_root.tag.startswith("{") and "}" in relationships_root.tag:
                    root_ns = relationships_root.tag[1:].split("}", 1)[0]
                relationship_tag = f"{{{root_ns}}}Relationship"
                missing_relationship_ids = [
                    str(item).strip()
                    for item in part_row.get("missing_relationship_ids", []) or []
                    if str(item or "").strip()
                ]
                unreferenced_relationship_ids = {
                    str(item).strip()
                    for item in part_row.get("unreferenced_relationship_ids", []) or []
                    if str(item or "").strip()
                }
                missing_media_paths = {
                    str(item).strip()
                    for item in part_row.get("missing_media_paths", []) or []
                    if str(item or "").strip()
                }
                changed_relationships = False
                for relationship in list(relationships_root):
                    rel_id = str(relationship.attrib.get("Id") or "").strip()
                    if rel_id not in unreferenced_relationship_ids:
                        continue
                    rel_type = str(relationship.attrib.get("Type") or "").strip()
                    target_text = str(relationship.attrib.get("Target") or "").strip()
                    if rel_type == image_relationship_type:
                        normalized_target = normalize_docx_relationship_target(
                            target_text,
                            source_part_path=part_name,
                        )
                        if normalized_target:
                            remove_media_paths.add(normalized_target)
                    relationships_root.remove(relationship)
                    remove_relationship_ids.add(f"{part_name}:{rel_id}")
                    changed_relationships = True
                if primary_image is not None:
                    for media_path in sorted(missing_media_paths):
                        add_media_files[media_path] = primary_image
                    image_suffix = primary_image.suffix.lower() or ".png"
                    part_slug = re.sub(
                        r"[^A-Za-z0-9_.-]+",
                        "_",
                        Path(part_name).stem,
                    ).strip("_")
                    for rel_id in missing_relationship_ids:
                        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", rel_id).strip("_")
                        media_name = (
                            f"deep-repair-{part_slug or 'part'}-"
                            f"{safe_id or 'image'}{image_suffix}"
                        )
                        media_path = f"word/media/{media_name}"
                        target_text = posixpath.relpath(
                            media_path,
                            posixpath.dirname(part_name) or "word",
                        )
                        ET.SubElement(
                            relationships_root,
                            relationship_tag,
                            {
                                "Id": rel_id,
                                "Type": image_relationship_type,
                                "Target": target_text,
                            },
                        )
                        add_relationship_rows.append((part_name, rel_id, media_path))
                        add_media_files[media_path] = primary_image
                        changed_relationships = True
                if changed_relationships or (
                    missing_relationship_ids and not relationship_xml
                ):
                    modified_relationships_xml_by_path[rels_name] = ET.tostring(
                        relationships_root,
                        encoding="utf-8",
                        xml_declaration=True,
                    )
            new_extensions = [
                Path(media_path).suffix.lstrip(".")
                for media_path in add_media_files
                if Path(media_path).suffix
            ]
            content_types_xml = (
                source.read("[Content_Types].xml")
                if "[Content_Types].xml" in names
                else None
            )
            if new_extensions:
                modified_content_types_xml = update_docx_content_types(
                    content_types_xml,
                    new_extensions,
                )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            written_names: set[str] = set()
            with zipfile.ZipFile(
                output_path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as target:
                for zip_info in source.infolist():
                    if zip_info.filename in written_names:
                        continue
                    if zip_info.filename in modified_relationships_xml_by_path:
                        continue
                    if zip_info.filename == "[Content_Types].xml":
                        continue
                    if zip_info.filename in remove_media_paths:
                        continue
                    if zip_info.is_dir():
                        target.writestr(zip_info, b"")
                    else:
                        target.writestr(zip_info, source.read(zip_info.filename))
                    written_names.add(zip_info.filename)
                if modified_content_types_xml is not None:
                    target.writestr("[Content_Types].xml", modified_content_types_xml)
                    written_names.add("[Content_Types].xml")
                elif "[Content_Types].xml" in names:
                    target.writestr(
                        "[Content_Types].xml",
                        source.read("[Content_Types].xml"),
                    )
                    written_names.add("[Content_Types].xml")
                for rels_name, relationships_xml in sorted(
                    modified_relationships_xml_by_path.items()
                ):
                    if rels_name in written_names:
                        continue
                    target.writestr(rels_name, relationships_xml)
                    written_names.add(rels_name)
                for media_path, asset_path in add_media_files.items():
                    if media_path in written_names:
                        continue
                    target.writestr(media_path, asset_path.read_bytes())
                    written_names.add(media_path)
    except (OSError, zipfile.BadZipFile, ValueError):
        result.update(
            {
                "status": "deep_repair_write_failed",
                "relationship_repair_status": "write_failed",
                "media_repair_status": "write_failed",
            }
        )
        return result

    post_scan = scan_docx_xml_media(
        output_path
    )
    relationship_verified = (
        str(post_scan.get("relationship_status") or "") == "relationship_consistent"
    )
    media_verified = str(post_scan.get("media_status") or "") == "media_consistent"
    missing_media_repaired = len(set(add_media_files).intersection(all_missing_media_paths))
    result.update(
        {
            "post_scan": dict(post_scan),
            "added_relationship_ids": [
                f"{part_name}:{rel_id}" for part_name, rel_id, _ in add_relationship_rows
            ],
            "removed_relationship_ids": sorted(remove_relationship_ids),
            "added_media_paths": sorted(add_media_files),
            "removed_media_paths": sorted(remove_media_paths),
            "missing_relationship_repaired_count": len(add_relationship_rows),
            "unreferenced_relationship_removed_count": len(remove_relationship_ids),
            "missing_media_repaired_count": missing_media_repaired,
            "orphan_media_removed_count": len(remove_media_paths),
            "relationship_repair_status": (
                "relationship_deep_repair_verified"
                if relationship_verified
                else "relationship_deep_repair_attention_required"
            ),
            "media_repair_status": (
                "media_deep_repair_verified"
                if media_verified
                else "media_deep_repair_attention_required"
            ),
            "rollback_connector_status": "rollback_snapshot_written",
            "status": (
                "deep_repair_completed"
                if str(post_scan.get("status") or "") == "xml_media_consistent"
                else "deep_repair_attention_required"
            ),
        }
    )
    return result

__all__ = [
    "docx_image_part_kind",
    "docx_image_part_names",
    "docx_image_content_type",
    "available_asset_image_paths",
    "deep_repair_docx_xml_media",
    "docx_part_relationships_path",
    "normalize_docx_relationship_target",
    "scan_docx_xml_media",
    "update_docx_content_types",
]
