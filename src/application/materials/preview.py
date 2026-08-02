"""Read-only preview projection from one canonical package snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from src.domain.materials import MaterialContract, MaterialPackage, MaterialResolver

RUNTIME_IMAGE_WATERMARK_KEY = "__image_watermark_text__"


@dataclass(frozen=True, slots=True)
class MaterialRuntimeFieldPreview:
    key: str
    label: str
    value: str = ""
    editor_kind: str = "single_line"
    timeline: bool = False
    image_watermark: bool = False


@dataclass(frozen=True, slots=True)
class MaterialPreviewSnapshot:
    package_id: str
    package_revision: str
    package_name: str
    source_type: str
    current_record_id: str = ""
    current_record_name: str = ""
    record_count: int = 0
    field_count: int = 0
    required_field_count: int = 0
    filled_required_field_count: int = 0
    resource_count: int = 0
    issue_codes: tuple[str, ...] = ()
    runtime_fields: tuple[MaterialRuntimeFieldPreview, ...] = ()


def project_material_preview(
    package: MaterialPackage,
    *,
    revision: str,
    source_type: str,
    contract: MaterialContract,
    current_record_id: str = "",
) -> MaterialPreviewSnapshot:
    record = (
        package.get_record(current_record_id)
        if current_record_id
        else (package.records[0] if package.records else None)
    )
    if record is None:
        return MaterialPreviewSnapshot(
            package_id=package.package_id,
            package_revision=revision,
            package_name=package.display_name,
            source_type=source_type,
            record_count=len(package.records),
        )
    resolution = MaterialResolver(package, contract).resolve_record(
        record.record_id
    )
    resolved = resolution.record
    values = dict(resolved.field_values) if resolved is not None else {}
    resources = dict(resolved.resources) if resolved is not None else {}
    required = tuple(item for item in contract.fields if item.required)
    runtime_fields = _runtime_field_previews(
        package,
        record.record_id,
        contract=contract,
        values=values,
    )
    return MaterialPreviewSnapshot(
        package_id=package.package_id,
        package_revision=revision,
        package_name=package.display_name,
        source_type=source_type,
        current_record_id=record.record_id,
        current_record_name=record.display_name,
        record_count=len(package.records),
        field_count=len(values),
        required_field_count=len(required),
        filled_required_field_count=sum(
            bool(values.get(item.key, "")) for item in required
        ),
        resource_count=sum(len(items) for items in resources.values()),
        issue_codes=tuple(item.code for item in resolution.issues),
        runtime_fields=runtime_fields,
    )


def _runtime_field_previews(
    package: MaterialPackage,
    record_id: str,
    *,
    contract: MaterialContract,
    values: dict[str, str],
) -> tuple[MaterialRuntimeFieldPreview, ...]:
    record = package.get_record(record_id)
    if record is None:
        return ()
    effective_values = dict(package.shared_scope.fields)
    scopes = [package.shared_scope]
    if record.group_id:
        group = package.get_group(record.group_id)
        if group is not None:
            effective_values.update(group.scope.fields)
            scopes.append(group.scope)
    effective_values.update(record.scope.fields)
    effective_values.update(values)
    scopes.append(record.scope)

    timeline_keys: list[str] = []
    for scope in scopes:
        for specification in scope.timelines.values():
            if specification.parameters.get("input_scope") != "floating":
                continue
            for key in (
                specification.anchor_field,
                specification.parameters.get("end_field", ""),
            ):
                if key and key not in timeline_keys:
                    timeline_keys.append(key)

    candidates = list(timeline_keys)
    for item in contract.fields:
        if (
            item.required
            and item.allow_run_override
            and not effective_values.get(item.key, "")
            and item.key not in candidates
        ):
            candidates.append(item.key)

    previews: list[MaterialRuntimeFieldPreview] = []
    for key in candidates:
        field = contract.get_field(key)
        if field is None or not field.allow_run_override:
            continue
        previews.append(
            MaterialRuntimeFieldPreview(
                key=key,
                label=field.label,
                value=effective_values.get(key, ""),
                editor_kind="date" if key in timeline_keys else "single_line",
                timeline=key in timeline_keys,
            )
        )

    extensions = package.metadata.get("material_contract_extensions", {})
    policy = (
        extensions.get("image_policy", {})
        if isinstance(extensions, Mapping)
        else {}
    )
    if (
        isinstance(policy, Mapping)
        and bool(policy.get("watermark_enabled", False))
        and str(policy.get("watermark_source", "fixed")) == "free"
    ):
        previews.append(
            MaterialRuntimeFieldPreview(
                key=RUNTIME_IMAGE_WATERMARK_KEY,
                label="图片水印文字",
                image_watermark=True,
            )
        )
    return tuple(previews)


__all__ = [
    "RUNTIME_IMAGE_WATERMARK_KEY",
    "MaterialPreviewSnapshot",
    "MaterialRuntimeFieldPreview",
    "project_material_preview",
]
