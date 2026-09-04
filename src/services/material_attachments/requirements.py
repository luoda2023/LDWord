"""Discover and project material requirements consumed by attachment DOCX files.

The attachment panel must not own a second copy of field or image values.  This
module therefore keeps two concerns separate: scanning says what a bound file
consumes, while projection says whether the owning field/image material is
currently available.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re

from docx import Document

from src.config.attachment_materials import AttachmentBinding
from src.shared.io.safe_docx_package import (
    SafeDocxPackage,
    capture_bounded_file,
)
from src.shared.engine.docx_material_tokens import extract_docx_material_token_blocks
from src.shared.engine.material_token_contract import (
    MATERIAL_TOKEN_PATTERN,
    MaterialTokenKind,
    MaterialTokenNamespace,
    material_token,
    parse_material_token,
)


class AttachmentRequirementKind(str, Enum):
    FIELD = "field"
    IMAGE = "image"
    LEGACY = "legacy"
    UNSUPPORTED = "unsupported"


class AttachmentRequirementState(str, Enum):
    """One resolution state shared by the attachment UI and preflight summary."""

    RESOLVED = "resolved"
    PARTIAL = "partial"
    EMPTY = "empty"
    MISSING = "missing"
    UNCONFIGURED = "unconfigured"
    DISABLED = "disabled"
    ERROR = "error"


class AttachmentRequirementAction(str, Enum):
    """The single next action derived from a requirement resolution state."""

    NONE = "none"
    FILL_FIELD = "fill_field"
    CREATE_FIELD = "create_field"
    CONFIGURE_TIMELINE = "configure_timeline"
    SELECT_IMAGE = "select_image"
    CONFIGURE_IMAGE = "configure_image"
    ENABLE_SYNC = "enable_sync"
    EDIT_SOURCE = "edit_source"


class AttachmentRequirementOwner(str, Enum):
    """Canonical owner that supplies one attachment Token value."""

    FIELD = "field"
    TIMELINE = "timeline"
    IMAGE = "image"
    ISSUE = "issue"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class AttachmentTokenRequirement:
    token: str
    kind: AttachmentRequirementKind
    namespace: str
    identifier: str
    occurrence_count: int
    relative_paths: tuple[str, ...]
    suggested_token: str = ""
    issue_code: str = ""


@dataclass(frozen=True, slots=True)
class AttachmentRequirementReport:
    requirements: tuple[AttachmentTokenRequirement, ...] = ()
    docx_count: int = 0
    unreadable_paths: tuple[str, ...] = ()

    @property
    def strict_count(self) -> int:
        return sum(
            item.kind
            in {AttachmentRequirementKind.FIELD, AttachmentRequirementKind.IMAGE}
            for item in self.requirements
        )

    @property
    def legacy_count(self) -> int:
        return sum(
            item.kind is AttachmentRequirementKind.LEGACY
            for item in self.requirements
        )


@dataclass(frozen=True, slots=True)
class AttachmentRequirementProjection:
    """One typed requirement resolved against one material profile."""

    token: str
    kind: AttachmentRequirementKind
    namespace: str
    identifier: str
    resource_key: str
    owner: AttachmentRequirementOwner
    value: str
    source: str
    status: str
    state: AttachmentRequirementState
    action: AttachmentRequirementAction
    occurrence_count: int
    relative_paths: tuple[str, ...]
    suggested_token: str = ""
    issue_code: str = ""


def scan_attachment_token_requirements(
    binding: AttachmentBinding,
) -> AttachmentRequirementReport:
    """Aggregate strict and legacy Token usage for every DOCX in one binding."""

    if not isinstance(binding, AttachmentBinding):
        raise TypeError("binding must be an AttachmentBinding")
    order: list[str] = []
    aggregate: dict[str, dict[str, object]] = {}
    unreadable: list[str] = []
    docx_count = 0
    for item in binding.items:
        if Path(item.relative_path).suffix.casefold() != ".docx":
            continue
        docx_count += 1
        try:
            occurrences = _scan_docx_requirements(
                item.file_ref.source_path,
                item.file_ref.content_sha256,
            )
        except Exception:
            unreadable.append(item.relative_path)
            continue
        for occurrence in occurrences:
            token = occurrence.token
            if token not in aggregate:
                order.append(token)
                aggregate[token] = {
                    "requirement": occurrence,
                    "count": 0,
                    "paths": [],
                }
            row = aggregate[token]
            row["count"] = int(row["count"]) + occurrence.occurrence_count
            paths = row["paths"]
            if item.relative_path not in paths:
                paths.append(item.relative_path)

    requirements = tuple(
        AttachmentTokenRequirement(
            token=aggregate[token]["requirement"].token,
            kind=aggregate[token]["requirement"].kind,
            namespace=aggregate[token]["requirement"].namespace,
            identifier=aggregate[token]["requirement"].identifier,
            occurrence_count=int(aggregate[token]["count"]),
            relative_paths=tuple(aggregate[token]["paths"]),
            suggested_token=aggregate[token]["requirement"].suggested_token,
            issue_code=aggregate[token]["requirement"].issue_code,
        )
        for token in order
    )
    return AttachmentRequirementReport(
        requirements=requirements,
        docx_count=docx_count,
        unreadable_paths=tuple(unreadable),
    )


def project_attachment_token_requirements(
    report: AttachmentRequirementReport,
    *,
    field_values: Mapping[str, object] | None = None,
    field_aliases: Mapping[str, str] | None = None,
    available_field_keys: Iterable[str] = (),
    timeline_field_keys: Iterable[str] = (),
    image_token_bindings: Mapping[str, str] | None = None,
    image_values: Mapping[str, object] | None = None,
    available_image_roles: Iterable[str] = (),
    processing_enabled: bool = True,
) -> tuple[AttachmentRequirementProjection, ...]:
    """Resolve scanned dependencies against their canonical material owners."""

    if not isinstance(report, AttachmentRequirementReport):
        raise TypeError("report must be an AttachmentRequirementReport")
    fields = {
        str(key or "").strip(): str(value or "").strip()
        for key, value in dict(field_values or {}).items()
        if str(key or "").strip()
    }
    aliases = _normalized_lookup(field_aliases or {})
    timeline_fields = _normalized_keys(timeline_field_keys)
    available_fields = _normalized_keys(available_field_keys) | (
        set(fields) - timeline_fields
    )
    image_bindings = _normalized_lookup(image_token_bindings or {})
    resolved_image_values = {
        str(key or "").strip(): str(value or "").strip()
        for key, value in dict(image_values or {}).items()
        if str(key or "").strip()
    }
    available_roles = {
        str(role or "").strip()
        for role in available_image_roles
        if str(role or "").strip()
    }
    rows: list[AttachmentRequirementProjection] = []
    for requirement in report.requirements:
        source = ""
        value = ""
        owner = AttachmentRequirementOwner.ISSUE
        state = AttachmentRequirementState.ERROR
        action = AttachmentRequirementAction.EDIT_SOURCE
        resource_key = requirement.identifier
        if requirement.kind is AttachmentRequirementKind.FIELD:
            resource_key = _lookup_value(aliases, requirement) or requirement.identifier
            value = fields.get(resource_key, "")
            if requirement.namespace == MaterialTokenNamespace.TIME.value:
                # ``@time`` describes the value type, not its owner.  A date
                # can be imported directly (for example 项目开始日期) or be a
                # calculated timeline output.  Treating every time Token as a
                # timeline node made valid imported columns look unconfigured.
                if resource_key in timeline_fields:
                    source = "时间节点"
                    owner = AttachmentRequirementOwner.TIMELINE
                    if value:
                        state = AttachmentRequirementState.RESOLVED
                        action = AttachmentRequirementAction.NONE
                    else:
                        state = AttachmentRequirementState.UNCONFIGURED
                        action = AttachmentRequirementAction.CONFIGURE_TIMELINE
                elif value:
                    source = "时间字段"
                    owner = AttachmentRequirementOwner.FIELD
                    state = AttachmentRequirementState.RESOLVED
                    action = AttachmentRequirementAction.NONE
                elif resource_key in available_fields:
                    source = "时间字段"
                    owner = AttachmentRequirementOwner.FIELD
                    state = AttachmentRequirementState.EMPTY
                    action = AttachmentRequirementAction.FILL_FIELD
                elif _is_timeline_identifier(resource_key):
                    source = "时间节点"
                    owner = AttachmentRequirementOwner.TIMELINE
                    state = AttachmentRequirementState.UNCONFIGURED
                    action = AttachmentRequirementAction.CONFIGURE_TIMELINE
                else:
                    source = "时间字段"
                    owner = AttachmentRequirementOwner.FIELD
                    state = AttachmentRequirementState.MISSING
                    action = AttachmentRequirementAction.CREATE_FIELD
            else:
                source = "字段资料"
                if resource_key in timeline_fields and resource_key not in available_fields:
                    owner = AttachmentRequirementOwner.ISSUE
                    state = AttachmentRequirementState.ERROR
                    action = AttachmentRequirementAction.EDIT_SOURCE
                elif value:
                    owner = AttachmentRequirementOwner.FIELD
                    state = AttachmentRequirementState.RESOLVED
                    action = AttachmentRequirementAction.NONE
                elif resource_key in available_fields:
                    owner = AttachmentRequirementOwner.FIELD
                    state = AttachmentRequirementState.EMPTY
                    action = AttachmentRequirementAction.FILL_FIELD
                else:
                    owner = AttachmentRequirementOwner.FIELD
                    state = AttachmentRequirementState.MISSING
                    action = AttachmentRequirementAction.CREATE_FIELD
        elif requirement.kind is AttachmentRequirementKind.IMAGE:
            source = "图片资料"
            owner = AttachmentRequirementOwner.IMAGE
            resource_key = _lookup_value(image_bindings, requirement)
            if not resource_key:
                state = AttachmentRequirementState.MISSING
                action = AttachmentRequirementAction.CONFIGURE_IMAGE
            elif resource_key in available_roles:
                value = resolved_image_values.get(resource_key, resource_key)
                state = AttachmentRequirementState.RESOLVED
                action = AttachmentRequirementAction.NONE
            else:
                state = AttachmentRequirementState.EMPTY
                action = AttachmentRequirementAction.SELECT_IMAGE
        elif requirement.kind is AttachmentRequirementKind.LEGACY:
            source = "旧 Token"
            owner = AttachmentRequirementOwner.ISSUE
            state = AttachmentRequirementState.ERROR
            action = AttachmentRequirementAction.EDIT_SOURCE
        else:
            source = "附件内部"
            owner = AttachmentRequirementOwner.ISSUE
            state = AttachmentRequirementState.ERROR
            action = AttachmentRequirementAction.EDIT_SOURCE

        if (
            not processing_enabled
            and requirement.kind
            in {AttachmentRequirementKind.FIELD, AttachmentRequirementKind.IMAGE}
        ):
            state = AttachmentRequirementState.DISABLED
            action = AttachmentRequirementAction.ENABLE_SYNC
        status = _requirement_status(state, requirement.kind)
        rows.append(
            AttachmentRequirementProjection(
                token=requirement.token,
                kind=requirement.kind,
                namespace=requirement.namespace,
                identifier=requirement.identifier,
                resource_key=resource_key,
                owner=owner,
                value=value,
                source=source,
                status=status,
                state=state,
                action=action,
                occurrence_count=requirement.occurrence_count,
                relative_paths=requirement.relative_paths,
                suggested_token=requirement.suggested_token,
                issue_code=requirement.issue_code,
            )
        )
    return tuple(rows)


def _requirement_status(
    state: AttachmentRequirementState,
    kind: AttachmentRequirementKind,
) -> str:
    if state is AttachmentRequirementState.RESOLVED:
        return "已对应"
    if state is AttachmentRequirementState.DISABLED:
        return "未启用同步"
    if state is AttachmentRequirementState.UNCONFIGURED:
        return "待配置"
    if state is AttachmentRequirementState.MISSING:
        return "未配置图片 Token" if kind is AttachmentRequirementKind.IMAGE else "未创建"
    if state is AttachmentRequirementState.EMPTY:
        return "待选图片" if kind is AttachmentRequirementKind.IMAGE else "待填写"
    return "需修改源文件"


def _is_timeline_identifier(identifier: str) -> bool:
    text = str(identifier or "").strip()
    return bool(
        text.startswith("节点_")
        or re.fullmatch(r"时间节点\d+(?:[-_．.]\d+)+", text)
    )


@lru_cache(maxsize=256)
def _scan_docx_requirements(
    source_path: str,
    content_sha256: str,
) -> tuple[AttachmentTokenRequirement, ...]:
    payload = capture_bounded_file(Path(source_path))
    if sha256(payload).hexdigest() != content_sha256:
        raise ValueError("attachment_requirement_source_hash_mismatch")
    package = SafeDocxPackage.open(payload)
    package.parse_xml("word/document.xml")
    document = Document(BytesIO(payload))
    order: list[str] = []
    aggregate: dict[str, AttachmentTokenRequirement] = {}
    counts: dict[str, int] = {}
    for block in extract_docx_material_token_blocks(document).blocks:
        for match in MATERIAL_TOKEN_PATTERN.finditer(block.combined_text or ""):
            raw_token = match.group(0)
            requirement = _classify_token(raw_token)
            if raw_token not in aggregate:
                order.append(raw_token)
                aggregate[raw_token] = requirement
                counts[raw_token] = 0
            counts[raw_token] += 1
    return tuple(
        AttachmentTokenRequirement(
            token=aggregate[token].token,
            kind=aggregate[token].kind,
            namespace=aggregate[token].namespace,
            identifier=aggregate[token].identifier,
            occurrence_count=counts[token],
            relative_paths=(),
            suggested_token=aggregate[token].suggested_token,
            issue_code=aggregate[token].issue_code,
        )
        for token in order
    )


def _classify_token(raw_token: str) -> AttachmentTokenRequirement:
    try:
        ref = parse_material_token(raw_token)
    except (TypeError, ValueError):
        identifier = raw_token[2:-2].strip()
        if re.fullmatch(r"[^\s{}:@]+", identifier) and not identifier.startswith("@"):
            namespace = (
                MaterialTokenNamespace.TIME
                if identifier.startswith("节点_") or identifier.endswith("日期")
                else MaterialTokenNamespace.TEXT
            )
            return AttachmentTokenRequirement(
                token=raw_token,
                kind=AttachmentRequirementKind.LEGACY,
                namespace="legacy",
                identifier=identifier,
                occurrence_count=1,
                relative_paths=(),
                suggested_token=material_token(namespace, identifier),
                issue_code="legacy_material_token",
            )
        return AttachmentTokenRequirement(
            token=raw_token,
            kind=AttachmentRequirementKind.UNSUPPORTED,
            namespace="invalid",
            identifier=identifier,
            occurrence_count=1,
            relative_paths=(),
            issue_code="invalid_material_token",
        )
    if ref.kind is MaterialTokenKind.FIELD:
        kind = AttachmentRequirementKind.FIELD
        issue_code = ""
    elif ref.kind is MaterialTokenKind.IMAGE:
        kind = AttachmentRequirementKind.IMAGE
        issue_code = ""
    else:
        kind = AttachmentRequirementKind.UNSUPPORTED
        issue_code = "attachment_nested_token_unsupported"
    return AttachmentTokenRequirement(
        token=ref.token,
        kind=kind,
        namespace=ref.namespace.value,
        identifier=ref.identifier,
        occurrence_count=1,
        relative_paths=(),
        issue_code=issue_code,
    )


def _normalized_lookup(values: Mapping[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_key, raw_value in values.items():
        key = str(raw_key or "").strip()
        value = str(raw_value or "").strip()
        if not key or not value:
            continue
        normalized[key] = value
        try:
            ref = parse_material_token(key)
        except (TypeError, ValueError):
            if key.startswith("{{") and key.endswith("}}"):
                normalized[key[2:-2].strip()] = value
        else:
            normalized[ref.key] = value
            normalized[ref.token] = value
            normalized[ref.identifier] = value
    return normalized


def _normalized_keys(values: Iterable[str]) -> set[str]:
    return {
        str(value or "").strip()
        for value in values
        if str(value or "").strip()
    }


def _lookup_value(
    values: Mapping[str, str],
    requirement: AttachmentTokenRequirement,
) -> str:
    key = f"@{requirement.namespace}:{requirement.identifier}"
    for candidate in (requirement.token, key, requirement.identifier):
        value = str(values.get(candidate, "") or "").strip()
        if value:
            return value
    return ""


__all__ = [
    "AttachmentRequirementAction",
    "AttachmentRequirementKind",
    "AttachmentRequirementOwner",
    "AttachmentRequirementProjection",
    "AttachmentRequirementReport",
    "AttachmentRequirementState",
    "AttachmentTokenRequirement",
    "project_attachment_token_requirements",
    "scan_attachment_token_requirements",
]
