"""Bind canonical package data into a frozen, single-authority run snapshot."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import MappingProxyType

from src.domain.materials import (
    MaterialContract,
    MaterialIssue,
    MaterialObjectRef,
    MaterialPackage,
    MaterialPackageRef,
    MaterialResolver,
    MaterialRunSelection,
)

_IMAGE_ROLE_LABEL_PREFIX = "role_label:"
_IMAGE_ROLE_CARDINALITY_PREFIX = "role_cardinality:"


def image_policy_role_label(
    image_policy: Mapping[str, object],
    role: str,
) -> str:
    """Return the frozen editor-facing name for one image role."""

    normalized_role = str(role or "").strip()
    return str(
        image_policy.get(
            f"{_IMAGE_ROLE_LABEL_PREFIX}{normalized_role}",
            normalized_role,
        )
        or normalized_role
    ).strip()


def image_policy_role_cardinality(
    image_policy: Mapping[str, object],
    role: str,
    *,
    resource_count: int,
) -> str:
    """Return the frozen single/multiple role kind with a legacy fallback."""

    value = str(
        image_policy.get(
            f"{_IMAGE_ROLE_CARDINALITY_PREFIX}{str(role or '').strip()}",
            "",
        )
        or ""
    ).strip()
    if value in {"single", "multiple"}:
        return value
    return "single" if resource_count == 1 else "multiple"


@dataclass(frozen=True, slots=True)
class ExecutionResource:
    object_ref: MaterialObjectRef
    source_path: str

    def __post_init__(self) -> None:
        source = Path(self.source_path)
        if not source.is_absolute() or not source.is_file():
            raise ValueError(
                f"execution_material_object_unavailable:{self.source_path}"
            )


@dataclass(frozen=True, slots=True)
class ExecutionMaterialRecord:
    record_id: str
    display_name: str
    group_id: str
    field_values: Mapping[str, str]
    field_owners: Mapping[str, str]
    resources: Mapping[str, tuple[ExecutionResource, ...]]
    resource_owners: Mapping[str, tuple[str, ...]]
    timeline_field_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionMaterialGroup:
    group_id: str
    display_name: str
    field_values: Mapping[str, str]
    field_owners: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ExecutionMaterialSnapshot:
    snapshot_id: str
    run_id: str
    package_ref: MaterialPackageRef
    work_mode_id: str
    material_contract_id: str
    recipe_id: str
    scene_id: str
    document_type: str
    package_display_name: str
    package_field_values: Mapping[str, str]
    package_field_owners: Mapping[str, str]
    groups: tuple[ExecutionMaterialGroup, ...]
    records: tuple[ExecutionMaterialRecord, ...]
    schema_version: int = 3
    resource_domains: Mapping[str, str] = field(default_factory=dict)
    content_policy: Mapping[str, object] = field(default_factory=dict)
    image_policy: Mapping[str, object] = field(default_factory=dict)
    contract_version: int = 1
    template_id: str = ""
    template_revision: str = ""
    master_id: str = ""
    master_revision: str = ""
    recipe_version: int = 1
    output_root: str = ""
    output_paths: tuple[str, ...] = ()
    preflight_receipt: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version not in {1, 2, 3}:
            raise ValueError("execution_material_snapshot_schema_unsupported")
        if (
            type(self.snapshot_id) is not str
            or (
                self.snapshot_id
                and not re.fullmatch(r"sha256:[0-9a-f]{64}", self.snapshot_id)
            )
        ):
            raise ValueError("execution_material_snapshot_id_invalid")
        if type(self.groups) is not tuple or any(
            not isinstance(item, ExecutionMaterialGroup)
            for item in self.groups
        ):
            raise TypeError("execution_material_groups_invalid")
        if type(self.records) is not tuple or any(
            not isinstance(item, ExecutionMaterialRecord)
            for item in self.records
        ):
            raise TypeError("execution_material_records_invalid")
        if not isinstance(self.resource_domains, Mapping) or any(
            type(key) is not str
            or type(value) is not str
            or value not in {"content", "image", "attachment"}
            for key, value in self.resource_domains.items()
        ):
            raise TypeError("execution_material_resource_domains_invalid")
        if not isinstance(self.image_policy, Mapping) or any(
            type(key) is not str or type(value) not in {bool, str}
            for key, value in self.image_policy.items()
        ):
            raise TypeError("execution_material_image_policy_invalid")
        if not isinstance(self.content_policy, Mapping) or any(
            type(key) is not str or type(value) not in {bool, str}
            for key, value in self.content_policy.items()
        ):
            raise TypeError("execution_material_content_policy_invalid")
        if type(self.output_paths) is not tuple or any(
            type(item) is not str for item in self.output_paths
        ):
            raise TypeError("execution_material_output_paths_invalid")
        if not isinstance(self.preflight_receipt, Mapping) or any(
            type(key) is not str or type(value) is not str
            for key, value in self.preflight_receipt.items()
        ):
            raise TypeError("execution_material_preflight_receipt_invalid")
        object.__setattr__(
            self,
            "preflight_receipt",
            MappingProxyType(dict(self.preflight_receipt)),
        )
        object.__setattr__(
            self,
            "resource_domains",
            MappingProxyType(dict(self.resource_domains)),
        )
        object.__setattr__(
            self,
            "content_policy",
            MappingProxyType(dict(self.content_policy)),
        )
        object.__setattr__(
            self,
            "image_policy",
            MappingProxyType(dict(self.image_policy)),
        )

    def to_payload(self) -> dict[str, object]:
        return execution_material_snapshot_to_payload(self)

    @property
    def execution_ready(self) -> bool:
        return (
            self.contract_version >= 1
            and bool(self.template_id)
            and bool(self.template_revision)
            and bool(self.master_id)
            and bool(self.master_revision)
            and self.recipe_version >= 1
            and bool(self.output_root)
            and bool(self.output_paths)
            and self.preflight_receipt.get("status") == "passed"
        )


@dataclass(frozen=True, slots=True)
class ExecutionMaterialFinalizeRequest:
    snapshot: ExecutionMaterialSnapshot
    template_id: str
    template_revision: str
    master_id: str
    master_revision: str
    recipe_version: int
    output_root: str
    output_paths: tuple[str, ...]
    supported_field_keys: tuple[str, ...] = ()
    supported_resource_roles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MaterialRunBindRequest:
    package: MaterialPackage
    package_revision: str
    source_type: str
    selection: MaterialRunSelection
    contract: MaterialContract
    recipe_id: str
    scene_id: str
    work_mode_id: str
    document_type: str = ""


@dataclass(frozen=True, slots=True)
class MaterialRunBindResult:
    snapshot: ExecutionMaterialSnapshot | None = None
    issues: tuple[MaterialIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return self.snapshot is not None and not any(
            item.severity == "error" for item in self.issues
        )


def bind_material_run(
    request: MaterialRunBindRequest,
    *,
    object_path: Callable[[MaterialObjectRef], str | Path],
) -> MaterialRunBindResult:
    issues: list[MaterialIssue] = []
    package = request.package
    selection = request.selection
    if request.work_mode_id != package.work_mode_id:
        issues.append(
            _issue(
                "material.bind.mode_mismatch",
                "work_mode_id",
                "任务工作模式与资料包不一致。",
            )
        )
    if request.contract.contract_id != package.material_contract_id:
        issues.append(
            _issue(
                "material.bind.contract_mismatch",
                "material_contract_id",
                "任务资料契约与资料包不一致。",
            )
        )
    if request.recipe_id not in request.contract.supported_recipes:
        issues.append(
            _issue(
                "material.bind.recipe_not_supported",
                "recipe_id",
                f"资料契约不支持执行配方：{request.recipe_id}",
            )
        )
    if selection.package_ref.package_id != package.package_id:
        issues.append(
            _issue(
                "material.bind.package_mismatch",
                "selection.package_ref.package_id",
                "运行选择不属于当前资料包。",
            )
        )
    if (
        selection.package_ref.revision != request.package_revision
        or not request.package_revision
    ):
        issues.append(
            _issue(
                "material.bind.revision_mismatch",
                "selection.package_ref.revision",
                "运行选择引用的资料包版本已变化。",
            )
        )
    if not selection.selected_record_ids:
        issues.append(
            _issue(
                "material.bind.selection_empty",
                "selection.selected_record_ids",
                "本次运行没有显式选择资料记录。",
            )
        )
    if issues:
        return MaterialRunBindResult(issues=tuple(issues))

    resolver = MaterialResolver(package, request.contract)
    records: list[ExecutionMaterialRecord] = []
    for record_id in selection.selected_record_ids:
        source_record = package.get_record(record_id)
        if source_record is None:
            issues.append(
                _issue(
                    "material.record.unknown",
                    "selection.selected_record_ids",
                    f"资料记录不存在：{record_id}",
                )
            )
            continue
        if source_record.lifecycle != "active":
            issues.append(
                _issue(
                    "material.record.not_active",
                    f"records.{record_id}.lifecycle",
                    f"资料记录不可执行：{source_record.lifecycle}",
                )
            )
            continue
        resolution = resolver.resolve_record(
            record_id,
            selection=selection,
        )
        issues.extend(resolution.issues)
        if not resolution.ok or resolution.record is None:
            continue
        if request.document_type:
            declared_type = resolution.record.field_values.get(
                "document_type",
                "",
            )
            if declared_type and declared_type != request.document_type:
                issues.append(
                    _issue(
                        "material.bind.document_type_mismatch",
                        f"records.{record_id}.fields.document_type",
                        (
                            f"任务文种 {request.document_type} 与资料声明 "
                            f"{declared_type} 不一致。"
                        ),
                    )
                )
                continue
        resolved_resources: dict[str, tuple[ExecutionResource, ...]] = {}
        for role, items in resolution.record.resources.items():
            resources: list[ExecutionResource] = []
            for item in items:
                try:
                    path = Path(object_path(item)).resolve(strict=True)
                    resources.append(
                        ExecutionResource(
                            object_ref=item,
                            source_path=str(path),
                        )
                    )
                except Exception as exc:
                    issues.append(
                        _issue(
                            "material.resource.object_unavailable",
                            f"records.{record_id}.resources.{role}",
                            f"{type(exc).__name__}: {exc}",
                        )
                    )
            resolved_resources[role] = tuple(resources)
        records.append(
            ExecutionMaterialRecord(
                record_id=resolution.record.record_id,
                display_name=resolution.record.display_name,
                group_id=source_record.group_id,
                field_values=MappingProxyType(
                    dict(resolution.record.field_values)
                ),
                field_owners=MappingProxyType(
                    dict(resolution.record.field_owners)
                ),
                resources=MappingProxyType(resolved_resources),
                resource_owners=MappingProxyType(
                    dict(resolution.record.resource_owners)
                ),
                timeline_field_keys=_record_timeline_field_keys(
                    package,
                    source_record,
                ),
            )
        )
    if issues:
        return MaterialRunBindResult(issues=tuple(issues))
    package_values = dict(package.shared_scope.fields)
    package_owners = {key: "shared" for key in package_values}
    selected_group_ids = {
        item.group_id
        for item in package.records
        if item.record_id in selection.selected_record_ids and item.group_id
    }
    groups = tuple(
        ExecutionMaterialGroup(
            group_id=group.group_id,
            display_name=group.display_name,
            field_values=MappingProxyType(
                {
                    **package_values,
                    **dict(group.scope.fields),
                }
            ),
            field_owners=MappingProxyType(
                {
                    **package_owners,
                    **{key: "group" for key in group.scope.fields},
                }
            ),
        )
        for group in package.groups
        if group.group_id in selected_group_ids
    )
    run_id = f"run_{uuid.uuid4().hex}"
    snapshot = ExecutionMaterialSnapshot(
            snapshot_id="",
            run_id=run_id,
            package_ref=selection.package_ref,
            work_mode_id=request.work_mode_id,
            material_contract_id=request.contract.contract_id,
            recipe_id=request.recipe_id,
            scene_id=request.scene_id,
            document_type=request.document_type,
            package_display_name=package.display_name,
            package_field_values=MappingProxyType(package_values),
            package_field_owners=MappingProxyType(package_owners),
            groups=groups,
            records=tuple(records),
            resource_domains=MappingProxyType(
                {
                    item.role: item.domain
                    for item in request.contract.resource_roles
                }
            ),
            content_policy=MappingProxyType(_package_content_policy(package)),
            image_policy=MappingProxyType(
                _package_image_policy(
                    package,
                    selection=selection,
                    contract=request.contract,
                )
            ),
        )
    snapshot = replace(snapshot, snapshot_id=_snapshot_content_id(snapshot))
    return MaterialRunBindResult(
        snapshot=snapshot
    )


def finalize_execution_material_snapshot(
    request: ExecutionMaterialFinalizeRequest,
) -> MaterialRunBindResult:
    """Freeze template/master identity, output plan, and preflight evidence."""

    if not isinstance(request.snapshot, ExecutionMaterialSnapshot):
        raise TypeError("execution_material_snapshot_required")
    issues: list[MaterialIssue] = []
    for label, value in (
        ("template_id", request.template_id),
        ("master_id", request.master_id),
    ):
        if type(value) is not str or not value or value != value.strip():
            issues.append(
                _issue(
                    f"material.bind.{label}_invalid",
                    label,
                    f"{label} 必须是显式且稳定的执行身份。",
                )
            )
    for label, value in (
        ("template_revision", request.template_revision),
        ("master_revision", request.master_revision),
    ):
        if (
            type(value) is not str
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", value)
        ):
            issues.append(
                _issue(
                    f"material.bind.{label}_invalid",
                    label,
                    f"{label} 必须是 SHA-256 revision。",
                )
            )
    if type(request.recipe_version) is not int or request.recipe_version < 1:
        issues.append(
            _issue(
                "material.bind.recipe_version_invalid",
                "recipe_version",
                "执行配方版本无效。",
            )
        )
    output_root = Path(request.output_root)
    if not output_root.is_absolute():
        issues.append(
            _issue(
                "material.bind.output_root_invalid",
                "output_root",
                "输出根目录必须是绝对路径。",
            )
        )
        resolved_root = output_root
    else:
        resolved_root = output_root.resolve()
    if type(request.output_paths) is not tuple or not request.output_paths:
        issues.append(
            _issue(
                "material.bind.output_plan_empty",
                "output_paths",
                "执行输出计划不能为空。",
            )
        )
    normalized_paths: list[str] = []
    seen_paths: set[str] = set()
    for index, raw_path in enumerate(request.output_paths):
        if type(raw_path) is not str or not raw_path:
            issues.append(
                _issue(
                    "material.bind.output_path_invalid",
                    f"output_paths.{index}",
                    "输出路径必须是非空字符串。",
                )
            )
            continue
        target = Path(raw_path)
        if not target.is_absolute():
            issues.append(
                _issue(
                    "material.bind.output_path_invalid",
                    f"output_paths.{index}",
                    "输出路径必须是绝对路径。",
                )
            )
            continue
        target = target.resolve()
        try:
            target.relative_to(resolved_root)
        except ValueError:
            issues.append(
                _issue(
                    "material.bind.output_path_outside_root",
                    f"output_paths.{index}",
                    f"输出路径越过根目录：{target}",
                )
            )
            continue
        collision_key = str(target).casefold()
        if collision_key in seen_paths:
            issues.append(
                _issue(
                    "material.bind.output_path_collision",
                    f"output_paths.{index}",
                    f"输出路径发生大小写无关碰撞：{target}",
                )
            )
            continue
        seen_paths.add(collision_key)
        if target.exists():
            issues.append(
                _issue(
                    "material.bind.output_path_exists",
                    f"output_paths.{index}",
                    f"输出路径已存在，默认不覆盖：{target}",
                )
            )
        normalized_paths.append(str(target))

    supported_fields = set(request.supported_field_keys)
    if supported_fields:
        unresolved_fields = sorted(
            {
                key
                for record in request.snapshot.records
                for key in record.field_values
            }
            - supported_fields
        )
        if unresolved_fields:
            issues.append(
                _issue(
                    "material.bind.template_fields_unsupported",
                    "supported_field_keys",
                    "模板/母版不支持字段：" + "、".join(unresolved_fields),
                )
            )
    supported_roles = set(request.supported_resource_roles)
    present_roles = {
        role
        for record in request.snapshot.records
        for role, resources in record.resources.items()
        if resources
    }
    if present_roles - supported_roles:
        issues.append(
            _issue(
                "material.bind.template_resources_unsupported",
                "supported_resource_roles",
                "模板/母版不支持资源角色："
                + "、".join(sorted(present_roles - supported_roles)),
            )
        )
    if issues:
        return MaterialRunBindResult(issues=tuple(issues))

    receipt_payload = {
        "material_snapshot_id": request.snapshot.snapshot_id,
        "template_id": request.template_id,
        "template_revision": request.template_revision,
        "master_id": request.master_id,
        "master_revision": request.master_revision,
        "recipe_id": request.snapshot.recipe_id,
        "recipe_version": request.recipe_version,
        "output_root": str(resolved_root),
        "output_paths": normalized_paths,
        "checks": [
            "mode",
            "contract",
            "document_type",
            "records",
            "fields",
            "resources",
            "calculations",
            "template_master",
            "output_containment",
            "output_collision",
        ],
    }
    receipt_digest = "sha256:" + hashlib.sha256(
        json.dumps(
            receipt_payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    receipt = MappingProxyType(
        {
            "status": "passed",
            "receipt_digest": receipt_digest,
            "material_snapshot_id": request.snapshot.snapshot_id,
        }
    )
    finalized = replace(
        request.snapshot,
        template_id=request.template_id,
        template_revision=request.template_revision,
        master_id=request.master_id,
        master_revision=request.master_revision,
        recipe_version=request.recipe_version,
        output_root=str(resolved_root),
        output_paths=tuple(normalized_paths),
        preflight_receipt=receipt,
    )
    finalized = replace(
        finalized,
        snapshot_id=_snapshot_content_id(finalized),
    )
    return MaterialRunBindResult(snapshot=finalized)


def project_execution_material_record_snapshot(
    snapshot: ExecutionMaterialSnapshot,
    record_id: str,
) -> ExecutionMaterialSnapshot:
    """Return an unfinalized, integrity-bound snapshot for one record.

    Production execution is intentionally single-record.  Batch callers must
    project each selected record before planning its own output paths instead
    of passing a multi-record snapshot into the single-document runner.
    """

    if not isinstance(snapshot, ExecutionMaterialSnapshot):
        raise TypeError("execution_material_snapshot_required")
    normalized = str(record_id or "").strip()
    matches = tuple(
        record for record in snapshot.records if record.record_id == normalized
    )
    if len(matches) != 1:
        raise ValueError(f"execution_material_record_unknown:{normalized}")
    record = matches[0]
    groups = tuple(
        group
        for group in snapshot.groups
        if record.group_id and group.group_id == record.group_id
    )
    projected = replace(
        snapshot,
        snapshot_id="",
        groups=groups,
        records=(record,),
        template_id="",
        template_revision="",
        master_id="",
        master_revision="",
        recipe_version=1,
        output_root="",
        output_paths=(),
        preflight_receipt={},
    )
    return replace(
        projected,
        snapshot_id=_snapshot_content_id(projected),
    )


def _record_timeline_field_keys(package, record) -> tuple[str, ...]:
    """Project effective timeline identities into the frozen run record."""

    scopes = [package.shared_scope]
    if record.group_id:
        group = package.get_group(record.group_id)
        if group is not None:
            scopes.append(group.scope)
    scopes.append(record.scope)
    keys: list[str] = []
    for scope in scopes:
        for output, specification in scope.timelines.items():
            candidates = [
                output,
                specification.output_field,
                specification.anchor_field,
            ]
            end_field = specification.parameters.get("end_field", "")
            if end_field:
                candidates.append(end_field)
            for key in candidates:
                if key and key not in keys:
                    keys.append(key)
    return tuple(keys)


def _package_image_policy(
    package: MaterialPackage,
    *,
    selection: MaterialRunSelection,
    contract: MaterialContract,
) -> dict[str, object]:
    defaults: dict[str, object] = {
        "adaptive": True,
        "watermark_enabled": False,
        "watermark_source": "fixed",
        "watermark_text": "",
        "watermark_font": "宋体",
        "show_single_image_name": False,
        "show_multi_image_name": False,
        "page_break_after_images": False,
    }
    extensions = package.metadata.get("material_contract_extensions", {})
    if not isinstance(extensions, Mapping):
        return defaults
    raw = extensions.get("image_policy", {})
    if not isinstance(raw, Mapping):
        return defaults
    legacy_show_image_name = bool(raw.get("show_image_name", False))
    defaults.update(
        {
            "adaptive": bool(raw.get("adaptive", True)),
            "watermark_enabled": bool(raw.get("watermark_enabled", False)),
            "watermark_source": str(raw.get("watermark_source", "fixed")),
            "watermark_text": str(raw.get("watermark_text", "")),
            "watermark_font": str(raw.get("watermark_font", "宋体") or "宋体"),
            "show_single_image_name": bool(
                raw.get("show_single_image_name", legacy_show_image_name)
            ),
            "show_multi_image_name": bool(
                raw.get("show_multi_image_name", legacy_show_image_name)
            ),
            "page_break_after_images": bool(
                raw.get("page_break_after_images", False)
            ),
        }
    )
    for item in contract.resource_roles:
        if item.domain != "image":
            continue
        defaults[f"{_IMAGE_ROLE_LABEL_PREFIX}{item.role}"] = item.label
        defaults[f"{_IMAGE_ROLE_CARDINALITY_PREFIX}{item.role}"] = (
            "single" if item.max_items == 1 else "multiple"
        )
    if defaults["watermark_source"] == "free":
        defaults["runtime_watermark_text"] = (
            selection.runtime_image_watermark_text
        )
    return defaults


def _package_content_policy(package: MaterialPackage) -> dict[str, object]:
    defaults: dict[str, object] = {
        "format_mode": "target_document",
        "page_break_policy": "drop",
    }
    extensions = package.metadata.get("material_contract_extensions", {})
    if not isinstance(extensions, Mapping):
        return defaults
    raw = extensions.get("content_policy", {})
    if not isinstance(raw, Mapping):
        return defaults
    format_mode = str(raw.get("format_mode", "target_document"))
    if format_mode in {"target_document", "plain_text"}:
        defaults["format_mode"] = format_mode
    page_break_policy = str(raw.get("page_break_policy", "drop"))
    if page_break_policy in {"drop", "preserve_explicit"}:
        defaults["page_break_policy"] = page_break_policy
    return defaults


def _issue(code: str, path: str, message: str) -> MaterialIssue:
    return MaterialIssue(code=code, path=path, message=message)


def _snapshot_content_id(snapshot: ExecutionMaterialSnapshot) -> str:
    payload = execution_material_snapshot_to_payload(snapshot)
    payload["snapshot_id"] = ""
    return "sha256:" + hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def execution_material_snapshot_to_payload(
    snapshot: ExecutionMaterialSnapshot,
) -> dict[str, object]:
    if not isinstance(snapshot, ExecutionMaterialSnapshot):
        raise TypeError("execution_material_snapshot_type_invalid")
    payload: dict[str, object] = {
        "schema_version": snapshot.schema_version,
        "snapshot_id": snapshot.snapshot_id,
        "run_id": snapshot.run_id,
        "package_ref": {
            "package_id": snapshot.package_ref.package_id,
            "revision": snapshot.package_ref.revision,
        },
        "work_mode_id": snapshot.work_mode_id,
        "material_contract_id": snapshot.material_contract_id,
        "recipe_id": snapshot.recipe_id,
        "scene_id": snapshot.scene_id,
        "document_type": snapshot.document_type,
        "contract_version": snapshot.contract_version,
        "template_id": snapshot.template_id,
        "template_revision": snapshot.template_revision,
        "master_id": snapshot.master_id,
        "master_revision": snapshot.master_revision,
        "recipe_version": snapshot.recipe_version,
        "output_root": snapshot.output_root,
        "output_paths": list(snapshot.output_paths),
        "preflight_receipt": dict(snapshot.preflight_receipt),
        "package_display_name": snapshot.package_display_name,
        "package_field_values": dict(snapshot.package_field_values),
        "package_field_owners": dict(snapshot.package_field_owners),
        "groups": [
            {
                "group_id": item.group_id,
                "display_name": item.display_name,
                "field_values": dict(item.field_values),
                "field_owners": dict(item.field_owners),
            }
            for item in snapshot.groups
        ],
        "records": [
            {
                "record_id": item.record_id,
                "display_name": item.display_name,
                "group_id": item.group_id,
                "field_values": dict(item.field_values),
                "field_owners": dict(item.field_owners),
                "resources": {
                    role: [
                        {
                            "object_ref": {
                                "object_id": resource.object_ref.object_id,
                                "media_type": resource.object_ref.media_type,
                                "original_name": resource.object_ref.original_name,
                                "size": resource.object_ref.size,
                            },
                            "source_path": resource.source_path,
                        }
                        for resource in resources
                    ]
                    for role, resources in item.resources.items()
                },
                "resource_owners": {
                    role: list(owners)
                    for role, owners in item.resource_owners.items()
                },
            }
            for item in snapshot.records
        ],
    }
    if snapshot.schema_version >= 2:
        payload["resource_domains"] = dict(snapshot.resource_domains)
        payload["image_policy"] = dict(snapshot.image_policy)
        for record_payload, record in zip(payload["records"], snapshot.records):
            record_payload["timeline_field_keys"] = list(
                record.timeline_field_keys
            )
    if snapshot.schema_version >= 3:
        payload["content_policy"] = dict(snapshot.content_policy)
    return payload


def execution_material_snapshot_from_payload(
    payload: Mapping[str, object],
) -> ExecutionMaterialSnapshot:
    if not isinstance(payload, Mapping) or payload.get("schema_version") not in {1, 2, 3}:
        raise ValueError("execution_material_snapshot_schema_unsupported")
    schema_version = _payload_int(payload, "schema_version")
    expected_keys = {
        "schema_version",
        "snapshot_id",
        "run_id",
        "package_ref",
        "work_mode_id",
        "material_contract_id",
        "recipe_id",
        "scene_id",
        "document_type",
        "contract_version",
        "template_id",
        "template_revision",
        "master_id",
        "master_revision",
        "recipe_version",
        "output_root",
        "output_paths",
        "preflight_receipt",
        "package_display_name",
        "package_field_values",
        "package_field_owners",
        "groups",
        "records",
    }
    if schema_version >= 2:
        expected_keys.update({"resource_domains", "image_policy"})
    if schema_version >= 3:
        expected_keys.add("content_policy")
    if set(payload) != expected_keys:
        raise ValueError("execution_material_snapshot_payload_keys_invalid")
    package_ref_payload = _payload_mapping(payload.get("package_ref"))
    groups_payload = _payload_list(payload.get("groups"))
    records_payload = _payload_list(payload.get("records"))
    groups = tuple(
        ExecutionMaterialGroup(
            group_id=_payload_text(item, "group_id"),
            display_name=_payload_text(item, "display_name"),
            field_values=MappingProxyType(
                _payload_text_mapping(item.get("field_values"))
            ),
            field_owners=MappingProxyType(
                _payload_text_mapping(item.get("field_owners"))
            ),
        )
        for raw in groups_payload
        for item in (_payload_mapping(raw),)
    )
    records: list[ExecutionMaterialRecord] = []
    for raw in records_payload:
        item = _payload_mapping(raw)
        resources_payload = _payload_mapping(item.get("resources"))
        resources: dict[str, tuple[ExecutionResource, ...]] = {}
        for role, raw_resources in resources_payload.items():
            resources[str(role)] = tuple(
                ExecutionResource(
                    object_ref=MaterialObjectRef(
                        object_id=_payload_text(ref, "object_id"),
                        media_type=_payload_text(ref, "media_type"),
                        original_name=_payload_text(ref, "original_name"),
                        size=_payload_int(ref, "size"),
                    ),
                    source_path=_payload_text(resource, "source_path"),
                )
                for raw_resource in _payload_list(raw_resources)
                for resource in (_payload_mapping(raw_resource),)
                for ref in (
                    _payload_mapping(resource.get("object_ref")),
                )
            )
        resource_owners = {
            str(role): tuple(str(value) for value in _payload_list(values))
            for role, values in _payload_mapping(
                item.get("resource_owners")
            ).items()
        }
        records.append(
            ExecutionMaterialRecord(
                record_id=_payload_text(item, "record_id"),
                display_name=_payload_text(item, "display_name"),
                group_id=_payload_text(item, "group_id", allow_empty=True),
                field_values=MappingProxyType(
                    _payload_text_mapping(item.get("field_values"))
                ),
                field_owners=MappingProxyType(
                    _payload_text_mapping(item.get("field_owners"))
                ),
                resources=MappingProxyType(resources),
                resource_owners=MappingProxyType(resource_owners),
                timeline_field_keys=(
                    _payload_text_list(item.get("timeline_field_keys"))
                    if schema_version >= 2
                    else ()
                ),
            )
        )
    snapshot = ExecutionMaterialSnapshot(
        snapshot_id=_payload_text(payload, "snapshot_id"),
        run_id=_payload_text(payload, "run_id"),
        package_ref=MaterialPackageRef(
            package_id=_payload_text(package_ref_payload, "package_id"),
            revision=_payload_text(package_ref_payload, "revision"),
        ),
        work_mode_id=_payload_text(payload, "work_mode_id"),
        material_contract_id=_payload_text(payload, "material_contract_id"),
        recipe_id=_payload_text(payload, "recipe_id"),
        scene_id=_payload_text(payload, "scene_id", allow_empty=True),
        document_type=_payload_text(
            payload,
            "document_type",
            allow_empty=True,
        ),
        contract_version=_payload_int(payload, "contract_version"),
        template_id=_payload_text(payload, "template_id", allow_empty=True),
        template_revision=_payload_text(
            payload,
            "template_revision",
            allow_empty=True,
        ),
        master_id=_payload_text(payload, "master_id", allow_empty=True),
        master_revision=_payload_text(
            payload,
            "master_revision",
            allow_empty=True,
        ),
        recipe_version=_payload_int(payload, "recipe_version"),
        output_root=_payload_text(payload, "output_root", allow_empty=True),
        output_paths=_payload_text_list(payload.get("output_paths")),
        preflight_receipt=MappingProxyType(
            _payload_text_mapping(payload.get("preflight_receipt"))
        ),
        package_display_name=_payload_text(payload, "package_display_name"),
        package_field_values=MappingProxyType(
            _payload_text_mapping(payload.get("package_field_values"))
        ),
        package_field_owners=MappingProxyType(
            _payload_text_mapping(payload.get("package_field_owners"))
        ),
        groups=groups,
        records=tuple(records),
        schema_version=schema_version,
        resource_domains=MappingProxyType(
            _payload_text_mapping(payload.get("resource_domains"))
            if schema_version >= 2
            else {}
        ),
        content_policy=MappingProxyType(
            _payload_scalar_mapping(payload.get("content_policy"))
            if schema_version >= 3
            else {}
        ),
        image_policy=MappingProxyType(
            _payload_scalar_mapping(payload.get("image_policy"))
            if schema_version >= 2
            else {}
        ),
    )
    if snapshot.snapshot_id != _snapshot_content_id(snapshot):
        raise ValueError("execution_material_snapshot_digest_mismatch")
    return snapshot


def _payload_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("execution_material_snapshot_payload_mapping_required")
    return value


def _payload_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("execution_material_snapshot_payload_list_required")
    return value


def _payload_text(
    payload: Mapping[str, object],
    key: str,
    *,
    allow_empty: bool = False,
) -> str:
    value = payload.get(key)
    if type(value) is not str or (not allow_empty and not value):
        raise ValueError(f"execution_material_snapshot_text_invalid:{key}")
    return value


def _payload_int(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if type(value) is not int:
        raise ValueError(f"execution_material_snapshot_int_invalid:{key}")
    return value


def _payload_text_mapping(value: object) -> dict[str, str]:
    payload = _payload_mapping(value)
    if any(type(key) is not str or type(item) is not str for key, item in payload.items()):
        raise ValueError("execution_material_snapshot_text_mapping_invalid")
    return dict(payload)


def _payload_scalar_mapping(value: object) -> dict[str, object]:
    payload = _payload_mapping(value)
    if any(
        type(key) is not str or type(item) not in {bool, str}
        for key, item in payload.items()
    ):
        raise ValueError("execution_material_snapshot_scalar_mapping_invalid")
    return dict(payload)


def _payload_text_list(value: object) -> tuple[str, ...]:
    payload = _payload_list(value)
    if any(type(item) is not str for item in payload):
        raise ValueError("execution_material_snapshot_text_list_invalid")
    return tuple(payload)


__all__ = [
    "ExecutionMaterialFinalizeRequest",
    "ExecutionMaterialGroup",
    "ExecutionMaterialRecord",
    "ExecutionMaterialSnapshot",
    "ExecutionResource",
    "MaterialRunBindRequest",
    "MaterialRunBindResult",
    "bind_material_run",
    "execution_material_snapshot_from_payload",
    "execution_material_snapshot_to_payload",
    "finalize_execution_material_snapshot",
]
