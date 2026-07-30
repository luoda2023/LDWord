"""Import/export helpers for official-document material packages."""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from src.config.entity import (
    ENTITY_PACKAGE_VERSION,
    EntityArchive,
    EntityProfile,
    load_entity_archive,
    save_entity_archive,
)
from src.config.material_batch import MaterialBatchSelection
from src.config.material_context import MaterialExecutionContext
from src.config.material_package_library import (
    MaterialPackageLibraryEntry,
    create_material_package_in_library,
    list_material_package_entries,
    load_material_package_entry,
)
from src.config.material_mappings import load_material_mapping
from src.config.material_schema_registry import get_material_schema
from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
    get_official_document_profile,
)


PACKAGE_VERSION = ENTITY_PACKAGE_VERSION
OFFICIAL_MATERIAL_TABLE_SUFFIXES = (".csv", ".xlsx", ".xlsm")

_OFFICIAL_TABLE_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "title": ("title", "document title", "标题", "公文标题"),
    "body": ("body", "document body", "正文", "正文内容"),
    "organization": ("organization", "发文机关", "机关"),
    "document_no": ("document_no", "document number", "文号", "发文字号"),
    "issue_date": ("issue_date", "issue date", "成文日期", "发文日期"),
    "recipient": ("recipient", "主送机关", "收文单位"),
    "attachment_note": ("attachment_note", "attachment note", "附件说明"),
    "issuer": ("issuer", "签发机关"),
    "copy_scope": ("copy_scope", "copy scope", "抄送范围", "抄送机关"),
    "printing_org": ("printing_org", "printing organization", "印发机关"),
    "printing_date": ("printing_date", "printing date", "印发日期"),
    "meeting_date": ("meeting_date", "meeting date", "会议时间", "会议日期"),
    "participants": ("participants", "参会人员", "出席人员"),
    "document_type": (
        "document_type",
        "document type",
        "profile_id",
        "official_profile_id",
        "文种",
        "公文类型",
    ),
}

_OFFICIAL_TABLE_FIELD_ALIAS_INDEX = {
    alias.casefold(): field_id
    for field_id, aliases in _OFFICIAL_TABLE_FIELD_ALIASES.items()
    for alias in aliases
}
_OFFICIAL_TABLE_PROFILE_NAME_ALIASES = {"profile_name", "文种名称"}
_OFFICIAL_TABLE_RECORD_ID_ALIASES = {
    "id",
    "record_id",
    "task_id",
    "资料编号",
    "任务编号",
}
_OFFICIAL_TABLE_RECORD_NAME_ALIASES = {
    "record_name",
    "task_name",
    "资料名称",
    "任务名称",
}


@dataclass(frozen=True, slots=True)
class OfficialDocumentMaterialPackageSample:
    """Official semantic projection of one generic library entry."""

    sample_id: str
    label: str
    profile_id: str
    source_type: str
    path: Path
    material_schema_ids: tuple[str, ...] = ()
    load_error: str = ""

    @property
    def qualified_id(self) -> str:
        return f"{self.source_type}/{self.sample_id}"

    @property
    def is_available(self) -> bool:
        return not self.load_error


@dataclass(frozen=True, slots=True)
class OfficialDocumentMaterialPackageResult:
    """Loaded or saved official-document material package evidence."""

    status: str
    profile_id: str
    material_schema_ids: tuple[str, ...]
    context: MaterialExecutionContext
    package_path: Path | None = None
    missing_required_fields: tuple[str, ...] = ()
    unknown_fields: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "profile_id": self.profile_id,
            "material_schema_ids": list(self.material_schema_ids),
            "package_path": str(self.package_path or ""),
            "context_profile_id": self.context.profile_id,
            "context_profile_name": self.context.profile_name,
            "entity_data": dict(self.context.entity_data),
            "field_scopes": dict(self.context.field_scopes),
            "field_functions": dict(self.context.field_functions),
            "missing_required_fields": list(self.missing_required_fields),
            "unknown_fields": list(self.unknown_fields),
            "issues": list(self.issues),
        }


@dataclass(frozen=True, slots=True)
class OfficialDocumentMaterialBatchItem:
    """One source-table row with a task identity separate from its document type."""

    row_number: int
    item_id: str
    label: str
    material: OfficialDocumentMaterialPackageResult


@dataclass(frozen=True, slots=True)
class OfficialDocumentMaterialBatchResult:
    """Validated official-document batch plus its transient execution selection."""

    status: str
    source_path: Path
    items: tuple[OfficialDocumentMaterialBatchItem, ...]
    selection: MaterialBatchSelection
    issues: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return self.status in {"ready", "ready_with_issues"}

    @property
    def invalid_count(self) -> int:
        return sum(1 for item in self.items if not item.material.ok)


def list_official_document_material_package_samples(
    *,
    source_type: str | None = None,
) -> tuple[OfficialDocumentMaterialPackageSample, ...]:
    """Project official samples from the generic library's sole scanner."""

    requested_source = str(source_type or "").strip()
    return tuple(
        _sample_from_entry(entry)
        for entry in list_material_package_entries(mode_id="official")
        if not requested_source or entry.source_type == requested_source
    )


def get_official_document_material_package_sample(
    sample_id: str,
    *,
    source_type: str | None = None,
) -> OfficialDocumentMaterialPackageSample | None:
    matches = _matching_official_document_material_package_samples(
        sample_id,
        source_type=source_type,
    )
    return matches[0] if len(matches) == 1 else None


def load_official_document_material_package_sample(
    sample_id: str,
    *,
    source_type: str | None = None,
) -> OfficialDocumentMaterialPackageResult:
    matches = _matching_official_document_material_package_samples(
        sample_id,
        source_type=source_type,
    )
    if len(matches) != 1:
        context = MaterialExecutionContext()
        target = str(sample_id or "").strip()
        if len(matches) > 1:
            qualified_matches = ",".join(
                sorted(sample.qualified_id for sample in matches)
            )
            return OfficialDocumentMaterialPackageResult(
                status="sample_ambiguous",
                profile_id=target,
                material_schema_ids=(),
                context=context,
                issues=(
                    f"official_material_package_sample_ambiguous: {target}; "
                    f"matches={qualified_matches}",
                ),
            )
        return OfficialDocumentMaterialPackageResult(
            status="sample_not_found",
            profile_id=target,
            material_schema_ids=(),
            context=context,
            issues=(f"official_material_package_sample_not_found: {sample_id}",),
        )
    sample = matches[0]
    if not sample.is_available:
        return OfficialDocumentMaterialPackageResult(
            status="invalid_package",
            profile_id="",
            material_schema_ids=(),
            context=MaterialExecutionContext(),
            package_path=sample.path,
            issues=(sample.load_error,),
        )
    entry = MaterialPackageLibraryEntry(
        package_id=sample.sample_id,
        name=sample.label,
        path=sample.path,
        mode_id="official",
        source_type=sample.source_type,
    )
    try:
        archive = load_material_package_entry(entry)
        return _official_document_result_from_archive(
            archive,
            package_path=entry.path,
        )
    except (OSError, ValueError, TypeError) as exc:
        return _invalid_official_package_result(entry.path, exc)


def _matching_official_document_material_package_samples(
    sample_id: str,
    *,
    source_type: str | None = None,
) -> tuple[OfficialDocumentMaterialPackageSample, ...]:
    target = str(sample_id or "").strip()
    if not target:
        return ()
    samples = list_official_document_material_package_samples(source_type=source_type)
    if "/" in target:
        return tuple(sample for sample in samples if sample.qualified_id == target)
    return tuple(sample for sample in samples if sample.sample_id == target)


def export_official_document_material_package(
    context: MaterialExecutionContext,
    path: Path | str,
    *,
    profile_id: str | None = None,
    sample_id: str | None = None,
    sample_label: str | None = None,
) -> OfficialDocumentMaterialPackageResult:
    """Write the generic EntityArchive wire format for one official profile."""

    target = Path(path)
    result, archive = _build_official_document_material_archive(
        context,
        profile_id=profile_id,
        package_id=sample_id or context.package_id or target.stem,
        package_label=sample_label,
    )
    if archive is None:
        return result
    save_entity_archive(archive, target)
    return replace(result, package_path=target)


def export_official_document_material_package_to_user_library(
    context: MaterialExecutionContext,
    *,
    package_id: str | None = None,
    label: str | None = None,
    profile_id: str | None = None,
) -> OfficialDocumentMaterialPackageResult:
    """Publish one official profile through the generic package library."""

    requested_profile_id = _canonical_official_profile_id(profile_id)
    package_label = str(
        label
        or context.entity_data.get("title", "")
        or (
            f"{_profile_label(requested_profile_id)}资料包"
            if requested_profile_id
            else "公文资料包"
        )
    ).strip()
    base_id = _safe_material_package_sample_id(
        package_id
        or package_label
        or f"{requested_profile_id}_material_package"
    )
    result, archive = _build_official_document_material_archive(
        context,
        profile_id=requested_profile_id,
        package_id=base_id,
        package_label=package_label,
    )
    if archive is None:
        return result
    entry = create_material_package_in_library(
        archive,
        mode_id="official",
        requested_id=base_id,
    )
    projected_context = result.context.clone()
    projected_context.package_id = entry.package_id
    return replace(
        result,
        context=projected_context,
        package_path=entry.path,
    )


def load_official_document_material_package(
    path: Path | str,
) -> OfficialDocumentMaterialPackageResult:
    """Strictly load one generic EntityArchive and project official semantics."""

    source = Path(path)
    try:
        archive = load_entity_archive(source)
        return _official_document_result_from_archive(archive, package_path=source)
    except (OSError, ValueError, TypeError) as exc:
        return _invalid_official_package_result(source, exc)


def load_official_document_material_table(
    path: Path | str,
    *,
    profile_id: str | None = None,
) -> OfficialDocumentMaterialPackageResult:
    """Load one official-document record from CSV or Excel.

    Supported table shapes are a horizontal first data row or vertical
    ``key,value`` rows. Field ids, English schema labels, and the Chinese UI
    labels are accepted. Multi-row batch execution remains a separate flow.
    """

    source = Path(path)
    if source.suffix.lower() not in OFFICIAL_MATERIAL_TABLE_SUFFIXES:
        raise ValueError(f"Unsupported official material table: {source}")

    mapping = load_material_mapping(source)
    if mapping.table_shape == "records" and mapping.record_count > 1:
        return OfficialDocumentMaterialPackageResult(
            status="multiple_records",
            profile_id=_canonical_official_profile_id(profile_id),
            material_schema_ids=(),
            context=MaterialExecutionContext(),
            package_path=source,
            issues=(
                f"official_material_table_multiple_records: {mapping.record_count}",
            ),
        )
    raw_entity_data = dict(mapping.entity_data)
    if not raw_entity_data:
        return OfficialDocumentMaterialPackageResult(
            status="invalid_table",
            profile_id=_canonical_official_profile_id(profile_id),
            material_schema_ids=(),
            context=MaterialExecutionContext(),
            package_path=source,
            issues=("official_material_table_entity_data_empty",),
        )

    profile_name = ""
    entity_data: dict[str, str] = {}
    for raw_key, raw_value in raw_entity_data.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        if key.casefold() in _OFFICIAL_TABLE_PROFILE_NAME_ALIASES:
            profile_name = str(raw_value or "").strip()
            continue
        field_id = _OFFICIAL_TABLE_FIELD_ALIAS_INDEX.get(key.casefold(), key)
        value = str(raw_value or "").strip()
        if value or field_id == "document_type":
            entity_data[field_id] = value

    resolved_profile_id, identity_status, identity_issue = (
        _resolve_table_profile_identity(
            entity_data.get("document_type", ""),
            selected_profile_id=profile_id,
        )
    )
    if identity_status:
        return _invalid_table_profile_result(
            source,
            entity_data,
            profile_name=profile_name,
            profile_id=resolved_profile_id,
            status=identity_status,
            issue=identity_issue,
        )

    contract = get_official_document_assembly_contract(resolved_profile_id)
    normalized_entity_data = dict(entity_data)
    if not str(normalized_entity_data.get("document_type", "") or "").strip():
        normalized_entity_data["document_type"] = resolved_profile_id

    context = MaterialExecutionContext(
        mode_id="official",
        package_id=source.stem,
        archive_name=source.stem,
        material_schema_ids=tuple(contract.material_schema_ids),
        compatible_profile_ids=(resolved_profile_id,),
        compatible_master_families=("official",),
        profile_id=_context_profile_id(resolved_profile_id),
        profile_name=profile_name or _profile_label(resolved_profile_id),
        entity_data=normalized_entity_data,
    )
    missing = _missing_required_fields(
        contract,
        context.entity_data,
        removed_field_keys=_removed_field_keys(context),
    )
    unknown = _unknown_fields(contract.material_schema_ids, context.entity_data)
    return OfficialDocumentMaterialPackageResult(
        status="ok" if not missing else "missing_required_fields",
        profile_id=resolved_profile_id,
        material_schema_ids=contract.material_schema_ids,
        context=context,
        package_path=source,
        missing_required_fields=missing,
        unknown_fields=unknown,
        issues=tuple(f"missing_required_field: {field}" for field in missing),
    )


def load_official_document_material_batch(
    path: Path | str,
) -> OfficialDocumentMaterialBatchResult:
    """Load every horizontal CSV/Excel record as an isolated official task."""

    source = Path(path)
    if source.suffix.lower() not in OFFICIAL_MATERIAL_TABLE_SUFFIXES:
        raise ValueError(f"Unsupported official material batch table: {source}")

    mapping = load_material_mapping(source)
    if mapping.table_shape != "records" or not mapping.records:
        return OfficialDocumentMaterialBatchResult(
            status="invalid_table",
            source_path=source,
            items=(),
            selection=MaterialBatchSelection(
                source_kind="official_document_table",
                source_path=str(source),
            ),
            issues=("official_material_batch_requires_horizontal_records",),
        )

    items: list[OfficialDocumentMaterialBatchItem] = []
    profiles: list[EntityProfile] = []
    profile_ids: list[str] = []
    item_metadata: dict[str, dict[str, object]] = {}
    used_item_ids: set[str] = set()

    for row_number, raw_record in enumerate(mapping.records, start=1):
        record_id, record_name, profile_name, entity_data = (
            _normalize_official_table_record(raw_record)
        )
        material = _official_material_result_from_table_record(
            source,
            entity_data,
            profile_name=profile_name,
        )
        item_id = _unique_batch_item_id(
            record_id or f"row_{row_number:04d}",
            used_item_ids,
        )
        label = (
            record_name
            or material.context.entity_data.get("title", "")
            or f"{_profile_label(material.profile_id)} {row_number}"
        )
        label = str(label or item_id).strip() or item_id
        item = OfficialDocumentMaterialBatchItem(
            row_number=row_number,
            item_id=item_id,
            label=label,
            material=material,
        )
        items.append(item)
        profiles.append(
            EntityProfile(
                    profile_id=item_id,
                    profile_name=label,
                    fields=dict(material.context.entity_data),
                    field_sources={
                    key: "imported_official_table"
                    for key in material.context.entity_data
                },
            )
        )
        profile_ids.append(item_id)
        item_metadata[item_id] = {
            "row_number": row_number,
            "official_profile_id": material.profile_id,
            "import_status": material.status,
            "missing_required_fields": list(material.missing_required_fields),
            "unknown_fields": list(material.unknown_fields),
            "issues": list(material.issues),
        }

    archive = EntityArchive(
        archive_id=f"official_batch:{_safe_material_package_sample_id(source.stem)}",
        archive_name=f"{source.stem} 公文批次",
        profiles=profiles,
    )
    selection = MaterialBatchSelection(
        archive=archive,
        profile_ids=profile_ids,
        output_dir_template="{profile_id}_{entity_name}",
        source_kind="official_document_table",
        source_path=str(source),
        item_metadata=item_metadata,
    )
    status = (
        "ready"
        if all(item.material.ok for item in items)
        else "ready_with_issues"
    )
    return OfficialDocumentMaterialBatchResult(
        status=status,
        source_path=source,
        items=tuple(items),
        selection=selection,
    )


def _normalize_official_table_record(
    raw_record: Mapping[str, object],
) -> tuple[str, str, str, dict[str, str]]:
    record_id = ""
    record_name = ""
    profile_name = ""
    entity_data: dict[str, str] = {}
    for raw_key, raw_value in raw_record.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        folded = key.casefold()
        value = str(raw_value or "").strip()
        if folded in _OFFICIAL_TABLE_RECORD_ID_ALIASES:
            record_id = value
            continue
        if folded in _OFFICIAL_TABLE_RECORD_NAME_ALIASES:
            record_name = value
            continue
        if folded in _OFFICIAL_TABLE_PROFILE_NAME_ALIASES:
            profile_name = value
            continue
        field_id = _OFFICIAL_TABLE_FIELD_ALIAS_INDEX.get(folded, key)
        if value or field_id == "document_type":
            entity_data[field_id] = value
    return record_id, record_name, profile_name, entity_data


def _official_material_result_from_table_record(
    source: Path,
    entity_data: Mapping[str, object],
    *,
    profile_name: str,
) -> OfficialDocumentMaterialPackageResult:
    normalized_data = _text_mapping(entity_data)
    profile_id, identity_status, identity_issue = _resolve_table_profile_identity(
        normalized_data.get("document_type", ""),
    )
    if identity_status:
        return _invalid_table_profile_result(
            source,
            normalized_data,
            profile_name=profile_name,
            profile_id=profile_id,
            status=identity_status,
            issue=identity_issue,
        )

    contract = get_official_document_assembly_contract(profile_id)
    context = MaterialExecutionContext(
        mode_id="official",
        package_id=source.stem,
        archive_name=source.stem,
        material_schema_ids=tuple(contract.material_schema_ids),
        compatible_profile_ids=(profile_id,),
        compatible_master_families=("official",),
        profile_id=_context_profile_id(profile_id),
        profile_name=profile_name or _profile_label(profile_id),
        entity_data=normalized_data,
    )

    missing = _missing_required_fields(
        contract,
        context.entity_data,
        removed_field_keys=_removed_field_keys(context),
    )
    unknown = _unknown_fields(contract.material_schema_ids, context.entity_data)
    return OfficialDocumentMaterialPackageResult(
        status="ok" if not missing else "missing_required_fields",
        profile_id=profile_id,
        material_schema_ids=contract.material_schema_ids,
        context=context,
        package_path=source,
        missing_required_fields=missing,
        unknown_fields=unknown,
        issues=tuple(f"missing_required_field: {field}" for field in missing),
    )


def _unique_batch_item_id(value: object, used_ids: set[str]) -> str:
    base = _safe_material_package_sample_id(value)
    candidate = base
    suffix = 2
    while candidate in used_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used_ids.add(candidate)
    return candidate


def _sample_from_entry(
    entry: MaterialPackageLibraryEntry,
) -> OfficialDocumentMaterialPackageSample:
    load_error = str(entry.load_error or "")
    profile_id = ""
    schema_ids: tuple[str, ...] = ()
    if not load_error:
        try:
            archive = load_material_package_entry(entry)
            result = _official_document_result_from_archive(
                archive,
                package_path=entry.path,
            )
            profile_id = result.profile_id
            schema_ids = result.material_schema_ids
        except (OSError, ValueError, TypeError) as exc:
            load_error = str(exc) or type(exc).__name__
    return OfficialDocumentMaterialPackageSample(
        sample_id=entry.package_id,
        label=entry.name,
        profile_id=profile_id,
        source_type=entry.source_type,
        path=entry.path,
        material_schema_ids=schema_ids,
        load_error=load_error,
    )


def _build_official_document_material_archive(
    context: MaterialExecutionContext,
    *,
    profile_id: str | None,
    package_id: str | None,
    package_label: str | None,
) -> tuple[OfficialDocumentMaterialPackageResult, EntityArchive | None]:
    normalized_profile_id, identity_status, identity_issue = (
        _resolve_export_profile_identity(context, selected_profile_id=profile_id)
    )
    if identity_status:
        return (
            OfficialDocumentMaterialPackageResult(
                status=identity_status,
                profile_id=normalized_profile_id,
                material_schema_ids=(),
                context=MaterialExecutionContext(),
                issues=(identity_issue,),
            ),
            None,
        )

    contract = get_official_document_assembly_contract(normalized_profile_id)
    if contract is None:  # Guard the registry invariant at the write boundary.
        return (
            OfficialDocumentMaterialPackageResult(
                status="unknown_profile",
                profile_id=normalized_profile_id,
                material_schema_ids=(),
                context=MaterialExecutionContext(),
                issues=(f"unknown_official_profile: {normalized_profile_id}",),
            ),
            None,
        )

    normalized_package_id = _safe_material_package_sample_id(package_id)
    normalized_context = _context_for_profile(context, normalized_profile_id)
    normalized_context.package_id = normalized_package_id
    missing = _missing_required_fields(
        contract,
        normalized_context.entity_data,
        removed_field_keys=_removed_field_keys(normalized_context),
    )
    unknown = _unknown_fields(contract.material_schema_ids, normalized_context.entity_data)
    result = OfficialDocumentMaterialPackageResult(
        status="ok" if not missing else "missing_required_fields",
        profile_id=normalized_profile_id,
        material_schema_ids=contract.material_schema_ids,
        context=normalized_context,
        missing_required_fields=missing,
        unknown_fields=unknown,
        issues=tuple(f"missing_required_field: {field}" for field in missing),
    )
    profile = EntityProfile(
        profile_id=_context_profile_id(normalized_profile_id),
        profile_name=normalized_context.profile_name,
        fields=dict(normalized_context.entity_data),
        assets_dir=normalized_context.entity_assets_dir,
        field_scopes=dict(normalized_context.field_scopes),
        field_functions=copy.deepcopy(normalized_context.field_functions),
        timeline_plans=copy.deepcopy(normalized_context.timeline_plans),
        declared_field_keys=list(normalized_context.entity_data),
        field_aliases=dict(normalized_context.field_aliases),
        image_material_rules=copy.deepcopy(normalized_context.image_material_rules),
        content_bindings=copy.deepcopy(normalized_context.content_bindings),
        content_rules=copy.deepcopy(normalized_context.content_rules),
        attachment_bindings=copy.deepcopy(normalized_context.attachment_bindings),
    )
    archive = EntityArchive(
        archive_id=normalized_package_id,
        archive_name=str(
            package_label
            or normalized_context.profile_name
            or normalized_context.entity_data.get("title", "")
            or f"{_profile_label(normalized_profile_id)}资料包"
        ).strip(),
        profiles=[profile],
        mode_id="official",
        package_id=normalized_package_id,
        material_schema_ids=list(contract.material_schema_ids),
    )
    return result, archive


def _official_document_result_from_archive(
    archive: EntityArchive,
    *,
    package_path: Path,
) -> OfficialDocumentMaterialPackageResult:
    if archive.mode_id != "official":
        raise ValueError(
            f"official_material_package_mode_invalid:{archive.mode_id}"
        )
    if len(archive.profiles) != 1:
        raise ValueError(
            f"official_material_package_profile_count_invalid:{len(archive.profiles)}"
        )
    profile = archive.profiles[0]
    stored_profile_id = str(profile.profile_id or "").strip()
    profile_id = _unqualified_official_profile_id(stored_profile_id)
    document_type = _canonical_official_profile_id(
        profile.fields.get("document_type", "")
    )
    if not profile_id or stored_profile_id != _context_profile_id(profile_id):
        raise ValueError(
            f"official_material_package_profile_identity_invalid:{stored_profile_id}"
        )
    if not document_type or document_type != profile_id:
        raise ValueError(
            "official_material_package_document_type_mismatch:"
            f"{profile_id}:{document_type}"
        )
    contract = get_official_document_assembly_contract(profile_id)
    if contract is None:
        raise ValueError(f"unknown_official_profile:{profile_id}")
    schema_ids = tuple(str(item) for item in archive.material_schema_ids)
    if schema_ids != tuple(contract.material_schema_ids):
        raise ValueError(
            "official_material_package_schema_mismatch:"
            f"{','.join(schema_ids)}:{','.join(contract.material_schema_ids)}"
        )
    context = MaterialExecutionContext(
        mode_id="official",
        package_id=archive.package_id,
        archive_name=archive.archive_name,
        material_schema_ids=schema_ids,
        compatible_profile_ids=(profile_id,),
        compatible_master_families=("official",),
        archive_id=archive.archive_id,
        profile_id=stored_profile_id,
        profile_name=profile.profile_name or _profile_label(profile_id),
        entity_data=dict(profile.fields),
        field_scopes=dict(profile.field_scopes),
        field_functions=copy.deepcopy(profile.field_functions),
        timeline_plans=copy.deepcopy(profile.timeline_plans),
        field_aliases=dict(profile.field_aliases),
        entity_assets_dir=profile.assets_dir,
        image_material_rules=copy.deepcopy(profile.image_material_rules),
        content_bindings=copy.deepcopy(profile.content_bindings),
        content_rules=copy.deepcopy(profile.content_rules),
        attachment_bindings=copy.deepcopy(profile.attachment_bindings),
        exact_material_placeholders=True,
    )
    missing = _missing_required_fields(
        contract,
        context.entity_data,
        removed_field_keys=_removed_field_keys(context),
    )
    unknown = _unknown_fields(contract.material_schema_ids, context.entity_data)
    return OfficialDocumentMaterialPackageResult(
        status="ok" if not missing else "missing_required_fields",
        profile_id=profile_id,
        material_schema_ids=schema_ids,
        context=context,
        package_path=package_path,
        missing_required_fields=missing,
        unknown_fields=unknown,
        issues=tuple(f"missing_required_field: {field}" for field in missing),
    )


def _invalid_official_package_result(
    source: Path,
    exc: BaseException,
) -> OfficialDocumentMaterialPackageResult:
    return OfficialDocumentMaterialPackageResult(
        status="invalid_package",
        profile_id="",
        material_schema_ids=(),
        context=MaterialExecutionContext(),
        package_path=source,
        issues=(str(exc) or type(exc).__name__,),
    )


def _safe_material_package_sample_id(value: object) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join(
        ch if ch not in forbidden and ord(ch) >= 32 else "_"
        for ch in str(value or "").strip()
    )
    cleaned = cleaned.strip(" ._")
    return cleaned or "official_material_package"


def _context_for_profile(
    context: MaterialExecutionContext,
    profile_id: str,
) -> MaterialExecutionContext:
    cloned = context.clone()
    cloned.mode_id = "official"
    contract = get_official_document_assembly_contract(profile_id)
    cloned.material_schema_ids = (
        tuple(contract.material_schema_ids) if contract is not None else ()
    )
    cloned.compatible_profile_ids = (profile_id,)
    cloned.compatible_master_families = ("official",)
    cloned.profile_id = _context_profile_id(profile_id)
    cloned.profile_name = cloned.profile_name or _profile_label(profile_id)
    entity_data = dict(cloned.entity_data)
    if not str(entity_data.get("document_type", "") or "").strip():
        entity_data["document_type"] = profile_id
    cloned.entity_data = entity_data
    return cloned


def _resolve_export_profile_identity(
    context: MaterialExecutionContext,
    *,
    selected_profile_id: object,
) -> tuple[str, str, str]:
    """Resolve one explicit export owner and validate every stored identity claim."""

    selected = _canonical_official_profile_id(selected_profile_id)
    if not selected:
        return "", "missing_profile", "official_profile_id_missing"
    if get_official_document_profile(selected) is None:
        return selected, "unknown_profile", f"unknown_official_profile: {selected}"

    raw_context_profile_id = str(context.profile_id or "").strip()
    if raw_context_profile_id:
        expected_context_profile_id = _context_profile_id(selected)
        if raw_context_profile_id != expected_context_profile_id:
            context_claim = _unqualified_official_profile_id(raw_context_profile_id)
            if context_claim and get_official_document_profile(context_claim) is None:
                return (
                    context_claim,
                    "unknown_profile",
                    f"unknown_official_profile: {context_claim}",
                )
            return (
                selected,
                "profile_conflict",
                "official_profile_identity_conflict:"
                f" selected={selected}; context_profile_id={raw_context_profile_id}",
            )

    document_type = _canonical_official_profile_id(
        context.entity_data.get("document_type", "")
    )
    if document_type:
        if get_official_document_profile(document_type) is None:
            return (
                document_type,
                "unknown_profile",
                f"unknown_official_profile: {document_type}",
            )
        if document_type != selected:
            return (
                selected,
                "profile_conflict",
                "official_profile_identity_conflict:"
                f" selected={selected}; document_type={document_type}",
            )
    return selected, "", ""


def _resolve_table_profile_identity(
    source_profile_id: object,
    *,
    selected_profile_id: object = None,
) -> tuple[str, str, str]:
    """Use a row identity, or one explicit UI selection when the row omits it."""

    source = _canonical_official_profile_id(source_profile_id)
    selected = _canonical_official_profile_id(selected_profile_id)
    for candidate in (source, selected):
        if candidate and get_official_document_profile(candidate) is None:
            return candidate, "unknown_profile", f"unknown_official_profile: {candidate}"
    if source and selected and source != selected:
        return (
            selected,
            "profile_conflict",
            "official_profile_identity_conflict:"
            f" selected={selected}; document_type={source}",
        )
    resolved = source or selected
    if not resolved:
        return "", "missing_profile", "official_profile_id_missing"
    return resolved, "", ""


def _invalid_table_profile_result(
    source: Path,
    entity_data: Mapping[str, object],
    *,
    profile_name: str,
    profile_id: str,
    status: str,
    issue: str,
) -> OfficialDocumentMaterialPackageResult:
    return OfficialDocumentMaterialPackageResult(
        status=status,
        profile_id=profile_id,
        material_schema_ids=(),
        context=MaterialExecutionContext(
            mode_id="official",
            package_id=source.stem,
            archive_name=source.stem,
            profile_name=profile_name,
            entity_data=_text_mapping(entity_data),
        ),
        package_path=source,
        issues=(issue,),
    )


def _canonical_official_profile_id(value: object) -> str:
    return str(value or "").strip()


def _unqualified_official_profile_id(value: object) -> str:
    normalized = str(value or "").strip()
    if normalized.startswith("official:"):
        normalized = normalized.split(":", 1)[1]
    return normalized


def _context_profile_id(profile_id: str) -> str:
    return f"official:{_canonical_official_profile_id(profile_id)}"


def _profile_label(profile_id: str) -> str:
    profile = get_official_document_profile(profile_id)
    return str(getattr(profile, "label", "") or profile_id)


def _removed_field_keys(context: MaterialExecutionContext) -> set[str]:
    return {
        str(key)
        for key, scope in dict(getattr(context, "field_scopes", {}) or {}).items()
        if str(scope) == "removed"
    }


def _missing_required_fields(
    contract,
    entity_data: Mapping[str, object],
    *,
    removed_field_keys: set[str] | tuple[str, ...] | list[str] = (),
) -> tuple[str, ...]:
    removed = {str(key) for key in removed_field_keys}
    missing: list[str] = []
    for binding in contract.field_bindings:
        if not binding.required or binding.field_key in removed:
            continue
        if str(entity_data.get(binding.field_key, "") or "").strip():
            continue
        missing.append(binding.field_key)
    return tuple(dict.fromkeys(missing))


def _unknown_fields(
    schema_ids: tuple[str, ...],
    entity_data: Mapping[str, object],
) -> tuple[str, ...]:
    allowed = {"document_type"}
    for schema_id in schema_ids:
        try:
            schema = get_material_schema(schema_id)
        except KeyError:
            continue
        allowed.update(field.key for field in schema.fields)
    return tuple(
        sorted(
            key
            for key in (str(item or "").strip() for item in entity_data.keys())
            if key and key not in allowed
        )
    )


def _text_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): str(item)
        for key, item in value.items()
        if str(key or "").strip()
    }


__all__ = [
    "OFFICIAL_MATERIAL_TABLE_SUFFIXES",
    "PACKAGE_VERSION",
    "OfficialDocumentMaterialBatchItem",
    "OfficialDocumentMaterialBatchResult",
    "OfficialDocumentMaterialPackageSample",
    "OfficialDocumentMaterialPackageResult",
    "export_official_document_material_package",
    "export_official_document_material_package_to_user_library",
    "get_official_document_material_package_sample",
    "list_official_document_material_package_samples",
    "load_official_document_material_package",
    "load_official_document_material_package_sample",
    "load_official_document_material_batch",
    "load_official_document_material_table",
]
