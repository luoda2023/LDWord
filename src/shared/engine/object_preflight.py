"""Preflight inspection for fragile objects inside DOCX packages."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile, is_zipfile

from src.config.scene import ObjectPreflightPolicy
from src.shared.io.safe_docx_package import SafeDocxPackage


OBJECT_PREFLIGHT_SCAN_TARGETS: tuple[str, ...] = (
    "ole_objects",
    "embedded_workbooks",
    "embedded_packages",
    "visio_drawings",
    "macros",
    "tracked_changes",
    "comments",
    "hidden_text",
    "textboxes",
    "content_controls",
    "fields",
)

OOXML_TOUCHPOINT_TO_PREFLIGHT_TARGETS: dict[str, tuple[str, ...]] = {
    "field": ("fields",),
    "comment": ("comments",),
    "revision": ("tracked_changes",),
    "hidden_text": ("hidden_text",),
    "textbox": ("textboxes",),
    "shape": ("textboxes",),
    "content_control": ("content_controls",),
    "drawing": ("visio_drawings",),
    "relationship": (
        "ole_objects",
        "embedded_workbooks",
        "embedded_packages",
        "visio_drawings",
        "macros",
    ),
    "package_part": (
        "ole_objects",
        "embedded_workbooks",
        "embedded_packages",
        "macros",
    ),
    "embedded_workbook": ("embedded_workbooks",),
}


@dataclass(slots=True, frozen=True)
class ObjectPreflightFinding:
    kind: str
    location: str
    message: str
    severity: str = "warning"


@dataclass(slots=True)
class ObjectPreflightResult:
    source_path: str = ""
    findings: list[ObjectPreflightFinding] = field(default_factory=list)
    inspection_status: str = "ok"
    inspection_error: str = ""

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)

    @property
    def blocking_findings(self) -> list[ObjectPreflightFinding]:
        return [finding for finding in self.findings if finding.severity == "error"]

    @property
    def inspection_succeeded(self) -> bool:
        return self.inspection_status == "ok"


_XML_SCAN_PATTERNS: tuple[tuple[str, tuple[bytes, ...], str], ...] = (
    (
        "tracked_changes",
        (b"<w:ins", b"<w:del", b"<w:moveFrom", b"<w:moveTo"),
        "Tracked changes are present.",
    ),
    (
        "textboxes",
        (b"<w:txbxContent", b"<wps:txbx", b"<v:textbox"),
        "Text box content is present.",
    ),
    (
        "content_controls",
        (b"<w:sdt",),
        "Structured document tags/content controls are present.",
    ),
    (
        "fields",
        (b"<w:fldSimple", b"<w:instrText", b'w:fldCharType="begin"'),
        "Word field instructions are present.",
    ),
    (
        "hidden_text",
        (b"<w:vanish", b"<w:webHidden"),
        "Hidden text markup is present.",
    ),
    (
        "ole_objects",
        (b"<o:OLEObject", b"<w:object"),
        "OLE object markup is present.",
    ),
)

_VISIO_XML_MARKERS: tuple[bytes, ...] = (
    b"vnd.ms-visio",
    b"schemas.microsoft.com/visio",
    b"/visio/drawing",
    b"/visio/relationships",
)

_REQUIRED_DOCX_PARTS: frozenset[str] = frozenset(
    {
        "[content_types].xml",
        "_rels/.rels",
        "word/document.xml",
    }
)

_REQUIRED_XML_ROOTS: dict[str, str] = {
    "[content_types].xml": "Types",
    "_rels/.rels": "Relationships",
    "word/document.xml": "document",
}


def inspect_docx_package(
    docx_path: str | Path,
    policy: ObjectPreflightPolicy | None = None,
    *,
    safe_package: SafeDocxPackage | None = None,
) -> ObjectPreflightResult:
    """Inspect DOCX package parts that python-docx can otherwise hide."""

    path = Path(docx_path)
    result = ObjectPreflightResult(source_path=str(path))
    if safe_package is None:
        try:
            source_exists = path.is_file()
        except OSError:
            source_exists = False
        if not source_exists:
            return _inspection_failure_result(result, "source_unavailable")
        try:
            package_is_zip = is_zipfile(path)
        except OSError:
            return _inspection_failure_result(result, "source_unreadable")
        if not package_is_zip:
            return _inspection_failure_result(result, "invalid_docx_package")

    policy = policy or ObjectPreflightPolicy()
    allowed_targets = _allowed_scan_targets(policy)
    seen: set[tuple[str, str]] = set()

    def add(kind: str, location: str, message: str) -> None:
        if allowed_targets is not None and kind not in allowed_targets:
            return
        key = (kind, location)
        if key in seen:
            return
        seen.add(key)
        result.findings.append(
            ObjectPreflightFinding(
                kind=kind,
                location=location,
                message=message,
                severity=_severity_for(kind, policy),
            )
        )

    try:
        package_context = (
            nullcontext(safe_package)
            if safe_package is not None
            else ZipFile(path)
        )
        with package_context as package:
            names = _package_names(package)
            if not _REQUIRED_DOCX_PARTS.issubset(
                {name.lower() for name in names}
            ):
                return _inspection_failure_result(
                    result,
                    "invalid_docx_package",
                )
            for name in names:
                lower = name.lower()
                if lower.startswith("word/embeddings/"):
                    _inspect_embedding_part(name, add)
                if lower.endswith("vbaproject.bin"):
                    add("macros", name, "VBA macro project is present.")
                if lower in {"word/comments.xml", "word/commentsExtended.xml".lower()}:
                    add("comments", name, "Comments are present.")
                if lower.endswith(".rels"):
                    _inspect_relationships(package, name, add)
                if lower.endswith(".xml") and (
                    lower.startswith("word/")
                    or lower == "[content_types].xml"
                ):
                    _inspect_xml_part(package, name, add)
    except (BadZipFile, ElementTree.ParseError, KeyError, ValueError):
        return _inspection_failure_result(result, "invalid_docx_package")
    except OSError:
        return _inspection_failure_result(result, "source_unreadable")
    except (EOFError, NotImplementedError, RuntimeError):
        return _inspection_failure_result(result, "source_unreadable")

    return result


def _inspection_failure_result(
    result: ObjectPreflightResult,
    status: str,
) -> ObjectPreflightResult:
    result.inspection_status = status
    result.inspection_error = status
    result.findings = [
        ObjectPreflightFinding(
            kind="object_preflight_inspection_failed",
            location=result.source_path,
            message=(
                "Object preflight could not inspect a valid DOCX package "
                f"({status})."
            ),
            severity="error",
        )
    ]
    return result


def object_preflight_targets_for_touchpoints(
    touchpoints: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    """Map planning-level OOXML touchpoints to concrete preflight finding kinds."""

    targets: list[str] = []
    for touchpoint in touchpoints:
        normalized = str(touchpoint or "").strip()
        for target in OOXML_TOUCHPOINT_TO_PREFLIGHT_TARGETS.get(normalized, ()):
            if target not in targets:
                targets.append(target)
    return tuple(targets)


def object_preflight_module_skips(
    findings: list,
    policy: ObjectPreflightPolicy,
) -> dict[str, dict[str, object]]:
    """Build the module-skip map caused by object preflight findings."""

    if not bool(getattr(policy, "skip_high_risk_modules", True)):
        return {}

    mapping = getattr(policy, "skip_modules_by_finding", None) or {}
    if not isinstance(mapping, dict):
        return {}

    module_to_kinds: dict[str, set[str]] = {}
    for finding in findings:
        kind = str(getattr(finding, "kind", "") or "").strip()
        for module_name in mapping.get(kind, []) or []:
            normalized = str(module_name or "").strip()
            if not normalized:
                continue
            module_to_kinds.setdefault(normalized, set()).add(kind)

    skips: dict[str, dict[str, object]] = {}
    for module_name, kinds in module_to_kinds.items():
        finding_kinds = sorted(kinds)
        reason = (
            "Skipped because object preflight found "
            + ", ".join(finding_kinds)
            + "."
        )
        skips[module_name] = {
            "module_name": module_name,
            "finding_kinds": finding_kinds,
            "reason": reason,
        }
    return skips


def refine_section_format_module_skips(
    skips: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    """Remove section skips for embedded-part findings outside ``w:sectPr``.

    The section planner only writes direct section properties and proves any
    cleanup boundary free of protected/non-paragraph content.  Relationship-
    level OLE/workbook/package/Visio findings therefore remain warnings but do
    not disable the entire module.  Macro/revision/content-control risks remain
    degradation triggers.
    """

    refined = {name: dict(entry) for name, entry in skips.items()}
    entry = refined.get("section_format")
    if entry is None:
        return refined
    safe_findings = {
        "ole_objects",
        "embedded_workbooks",
        "embedded_packages",
        "visio_drawings",
    }
    remaining = [
        str(kind)
        for kind in list(entry.get("finding_kinds", []) or [])
        if str(kind) not in safe_findings
    ]
    if not remaining:
        refined.pop("section_format", None)
        return refined
    entry["finding_kinds"] = sorted(remaining)
    entry["reason"] = (
        "Skipped because object preflight found " + ", ".join(sorted(remaining)) + "."
    )
    return refined


def _severity_for(kind: str, policy: ObjectPreflightPolicy) -> str:
    block_on = {str(item) for item in getattr(policy, "block_on", []) or []}
    if str(getattr(policy, "preservation_mode", "") or "") == "strict" and kind in block_on:
        return "error"
    return "warning"


def _allowed_scan_targets(policy: ObjectPreflightPolicy) -> set[str] | None:
    raw_targets = getattr(policy, "scan_targets", None)
    if raw_targets is None:
        return None
    return {
        str(target or "").strip()
        for target in raw_targets
        if str(target or "").strip()
    }


def _inspect_embedding_part(name: str, add) -> None:
    lower = name.lower()
    if lower.endswith((".xlsx", ".xls", ".xlsm", ".xlsb")):
        add("embedded_workbooks", name, "Embedded Excel workbook is present.")
        return
    if lower.endswith((".vsdx", ".vsd", ".vsdm")):
        add("visio_drawings", name, "Embedded Visio drawing is present.")
        return
    add("ole_objects", name, "Embedded OLE object is present.")


def _package_names(package: ZipFile | SafeDocxPackage) -> list[str]:
    if isinstance(package, SafeDocxPackage):
        return list(package.part_names)
    return package.namelist()


def _package_read(package: ZipFile | SafeDocxPackage, name: str) -> bytes:
    if isinstance(package, SafeDocxPackage):
        return package.read_part(name)
    return package.read(name)


def _inspect_relationships(
    package: ZipFile | SafeDocxPackage,
    name: str,
    add,
) -> None:
    raw_data = _package_read(package, name)
    _validate_required_xml(name, raw_data)
    data = raw_data.lower()

    if b"oleobject" in data:
        add("ole_objects", name, "OLE object relationship is present.")
    if b"package" in data and b"embeddings/" in data:
        add("embedded_packages", name, "Embedded package relationship is present.")
    if b"vba" in data or b"vbaproject" in data:
        add("macros", name, "Macro relationship is present.")


def _inspect_xml_part(
    package: ZipFile | SafeDocxPackage,
    name: str,
    add,
) -> None:
    data = _package_read(package, name)
    _validate_required_xml(name, data)

    lower = data.lower()
    if any(marker in lower for marker in _VISIO_XML_MARKERS):
        add("visio_drawings", name, "Visio content type or markup is present.")
    if b"macroenabled" in lower or b"vnd.ms-word.document.macroenabled" in lower:
        add("macros", name, "Macro-enabled document content type is present.")

    for kind, patterns, message in _XML_SCAN_PATTERNS:
        if any(pattern.lower() in lower for pattern in patterns):
            add(kind, name, message)


def _validate_required_xml(name: str, data: bytes) -> None:
    expected_root = _REQUIRED_XML_ROOTS.get(name.lower())
    if not expected_root:
        return
    root = ElementTree.fromstring(data)
    local_name = str(root.tag).rsplit("}", 1)[-1]
    if local_name != expected_root:
        raise ValueError(f"invalid_docx_core_part:{name}")
