"""Preflight inspection for fragile objects inside DOCX packages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from zipfile import BadZipFile, ZipFile, is_zipfile

from src.config.scene import ObjectPreflightPolicy


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

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)

    @property
    def blocking_findings(self) -> list[ObjectPreflightFinding]:
        return [finding for finding in self.findings if finding.severity == "error"]


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


def inspect_docx_package(
    docx_path: str | Path,
    policy: ObjectPreflightPolicy | None = None,
) -> ObjectPreflightResult:
    """Inspect DOCX package parts that python-docx can otherwise hide."""

    path = Path(docx_path)
    result = ObjectPreflightResult(source_path=str(path))
    if not path.exists() or not is_zipfile(path):
        return result

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
        with ZipFile(path) as package:
            names = package.namelist()
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
    except (BadZipFile, OSError):
        return result

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


def _inspect_relationships(package: ZipFile, name: str, add) -> None:
    try:
        data = package.read(name).lower()
    except (KeyError, OSError):
        return

    if b"oleobject" in data:
        add("ole_objects", name, "OLE object relationship is present.")
    if b"package" in data and b"embeddings/" in data:
        add("embedded_packages", name, "Embedded package relationship is present.")
    if b"vba" in data or b"vbaproject" in data:
        add("macros", name, "Macro relationship is present.")


def _inspect_xml_part(package: ZipFile, name: str, add) -> None:
    try:
        data = package.read(name)
    except (KeyError, OSError):
        return

    lower = data.lower()
    if b"visio" in lower:
        add("visio_drawings", name, "Visio content type or markup is present.")
    if b"macroenabled" in lower or b"vnd.ms-word.document.macroenabled" in lower:
        add("macros", name, "Macro-enabled document content type is present.")

    for kind, patterns, message in _XML_SCAN_PATTERNS:
        if any(pattern.lower() in lower for pattern in patterns):
            add(kind, name, message)
