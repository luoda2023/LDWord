"""Pure projection for template/material-package Token existence checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.config.execution_target import ExecutionTarget
from src.config.master_library import MasterSpec, get_master
from src.config.master_placeholder_index import (
    placeholder_identifier,
    scan_master_placeholder_index,
)
from src.config.master_preflight import check_master_preflight
from src.config.material_context import MaterialExecutionContext
from src.config.material_schema_registry import (
    get_material_schema,
    resolve_material_schema_ids,
)
from src.shared.engine.material_timeline import (
    timeline_output_field_keys,
    timeline_owned_field_keys,
)
from src.shared.engine.material_token_contract import (
    MaterialTokenNamespace,
    material_token,
    try_parse_material_token,
)
from src.ui.panels.scene_product_summary_projection import (
    material_asset_role_display_name,
    material_field_display_name,
)


_TYPE_LABELS = {
    "text": "文字",
    "time": "时间",
    "file": "文件",
    "img": "图片",
    "attach": "附件",
    "structure": "结构",
    "invalid": "未知",
}


@dataclass(frozen=True, slots=True)
class TokenAuditMapping:
    token: str
    identifier: str
    namespace: str
    target_key: str
    target_label: str
    source_label: str
    required: bool = False
    occurrence_policy: str = "all"
    repair_type: str = ""
    content_text: str = "未填写"


@dataclass(frozen=True, slots=True)
class SceneTokenAuditRow:
    row_id: str
    token: str
    identifier: str
    namespace: str
    type_label: str
    occurrence_count: int
    locations: tuple[str, ...]
    location_evidence: tuple[str, ...]
    mapping_target: str
    mapping_source: str
    package_present: bool
    status: str
    status_label: str
    detail: str
    content_text: str = "—"
    repair_type: str = ""
    repair_key: str = ""
    repair_namespace: str = ""
    issue_code: str = ""
    document_order: int = 1_000_000

    @property
    def template_present(self) -> bool:
        return self.occurrence_count > 0

    @property
    def has_issue(self) -> bool:
        return self.status != "ok"

    @property
    def searchable_text(self) -> str:
        return " ".join(
            (
                self.token,
                self.identifier,
                self.type_label,
                self.status_label,
                self.content_text,
                self.detail,
            )
        ).casefold()

    @property
    def repair_owner(self) -> str:
        if not self.has_issue:
            return "none"
        if self.issue_code == "mapping_missing":
            return "material"
        if self.issue_code == "type_conflict":
            return "choice"
        if self.issue_code in {"invalid_token", "duplicate_occurrence"}:
            return "source"
        if self.issue_code == "required_token_missing":
            return "contract"
        return "none"


@dataclass(frozen=True, slots=True)
class SceneTokenAuditProjection:
    source_label: str
    source_path: str
    source_kind: str
    rows: tuple[SceneTokenAuditRow, ...] = ()
    scan_status: str = "ready"
    scan_message: str = ""
    source_sha256: str = ""
    reference_page_excluded: bool = False
    global_issues: tuple[str, ...] = ()
    mapping_count: int = 0

    @property
    def token_count(self) -> int:
        return sum(1 for row in self.rows if row.occurrence_count > 0)

    @property
    def occurrence_count(self) -> int:
        return sum(max(0, row.occurrence_count) for row in self.rows)

    @property
    def ok_count(self) -> int:
        return sum(
            1
            for row in self.rows
            if row.occurrence_count > 0 and row.status == "ok"
        )

    @property
    def error_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "warning")

    @property
    def conclusion(self) -> str:
        if self.scan_status == "not_applicable":
            return "当前装配方式不使用模板 Token"
        if self.scan_status != "ready":
            return "尚未校验"
        if self.error_count:
            return f"存在 {self.error_count} 个不一致项"
        if self.warning_count:
            return f"存在 {self.warning_count} 个不一致项"
        if self.token_count == 0:
            return "模板中未发现 Token"
        return "模板与资料包一致"

    @property
    def source_kind_label(self) -> str:
        return {
            "document": "当前任务文档",
            "master": "方案母版",
            "structured": "结构化装配",
            "unresolved_master": "方案母版",
            "none": "校验来源",
        }.get(self.source_kind, "校验来源")


@dataclass(slots=True)
class _MappingCatalog:
    mappings: dict[str, TokenAuditMapping]
    by_identifier: dict[str, list[TokenAuditMapping]]

    def add(self, mapping: TokenAuditMapping, *, replace: bool = False) -> None:
        if replace or mapping.token not in self.mappings:
            self.mappings[mapping.token] = mapping
        values = self.by_identifier.setdefault(mapping.identifier, [])
        if mapping not in values:
            values.append(mapping)


def build_scene_token_audit_projection(
    scene,
    execution_target: ExecutionTarget | None,
    material_context: MaterialExecutionContext | None = None,
    *,
    master: MasterSpec | None = None,
) -> SceneTokenAuditProjection:
    """Compare material Tokens in the active template with the material package."""

    target = execution_target or ExecutionTarget()
    context = (
        material_context
        if isinstance(material_context, MaterialExecutionContext)
        else MaterialExecutionContext()
    )
    source_path = str(target.placeholder_source_path or target.master_path or "").strip()
    source_label = str(
        target.placeholder_source_label
        or target.master_id
        or (Path(source_path).name if source_path else "")
        or "未选择校验来源"
    ).strip()
    if not source_path:
        message = (
            "当前方案采用结构化装配，没有可扫描的模板文件。"
            if target.is_structured_assembly
            else "当前方案尚未选择可扫描的 DOCX 文档。"
        )
        return SceneTokenAuditProjection(
            source_label=source_label,
            source_path="",
            source_kind=str(target.placeholder_source_kind or "none"),
            scan_status=("not_applicable" if target.is_structured_assembly else "missing_source"),
            scan_message=message,
            global_issues=tuple(str(item) for item in target.issues),
        )

    path = Path(source_path)
    if not path.is_file():
        return SceneTokenAuditProjection(
            source_label=source_label,
            source_path=str(path),
            source_kind=str(target.placeholder_source_kind or "none"),
            scan_status="missing_source",
            scan_message="来源文档不存在或已被移动。",
            global_issues=tuple(str(item) for item in target.issues),
        )

    try:
        index = scan_master_placeholder_index(path, use_cache=True)
    except (OSError, ValueError) as exc:
        return SceneTokenAuditProjection(
            source_label=source_label,
            source_path=str(path),
            source_kind=str(target.placeholder_source_kind or "none"),
            scan_status="scan_failed",
            scan_message=f"无法读取来源文档 Token：{exc}",
            global_issues=tuple(str(item) for item in target.issues),
        )

    resolved_master = master or _resolve_target_master(scene, target)
    contract_required: set[str] = set()
    contract_optional: set[str] = set()
    preflight_issues: list[str] = []
    if resolved_master is not None:
        contract_required.update(
            str(item or "").strip()
            for item in resolved_master.placeholder_contract.required
            if str(item or "").strip()
        )
        contract_optional.update(
            str(item or "").strip()
            for item in resolved_master.placeholder_contract.optional
            if str(item or "").strip()
        )
        try:
            preflight = check_master_preflight(resolved_master)
        except Exception as exc:  # Manifest corruption is itself audit evidence.
            preflight_issues.append(f"母版登记信息不可读：{exc}")
        else:
            if preflight.placeholder_index_status == "stale":
                preflight_issues.append("模板文件已变化，登记的 Token 索引需要更新。")
            if preflight.unexpected_placeholders:
                preflight_issues.append(
                    f"发现 {len(preflight.unexpected_placeholders)} 个契约外 Token。"
                )

    catalog = _build_mapping_catalog(scene, target, context)
    surface_map = dict(index.placeholder_surfaces)
    rows: list[SceneTokenAuditRow] = []
    scanned_tokens: set[str] = set()
    present_identifiers: set[str] = set()
    replaceable_counts = index.replaceable_counts

    for document_order, raw_key in enumerate(index.replaceable_placeholder_ids):
        raw_key = str(raw_key or "").strip()
        # Visibility/content block markers are control directives, not variables.
        if not raw_key or raw_key.startswith(("#", "/")):
            continue
        occurrence_count = int(replaceable_counts.get(raw_key, 0))
        evidence = tuple(surface_map.get(raw_key, ()))
        locations = _location_labels(evidence, occurrence_count)
        ref = try_parse_material_token(raw_key)
        identifier = placeholder_identifier(raw_key)
        present_identifiers.add(identifier)
        if ref is None:
            token = "{{" + raw_key + "}}"
            if identifier in contract_required or identifier in contract_optional:
                # Structural assembly placeholders are not material-package Tokens.
                continue
            else:
                rows.append(
                    SceneTokenAuditRow(
                        row_id=f"token:{raw_key}",
                        token=token,
                        identifier=identifier,
                        namespace="invalid",
                        type_label=_TYPE_LABELS["invalid"],
                        occurrence_count=occurrence_count,
                        locations=locations,
                        location_evidence=evidence,
                        mapping_target="未识别",
                        mapping_source="无",
                        package_present=False,
                        status="error",
                        status_label="格式无效",
                        detail="资料 Token 必须使用 @text、@time、@file、@img 或 @attach 命名空间。",
                        issue_code="invalid_token",
                        document_order=document_order,
                    )
                )
            continue

        token = ref.token
        scanned_tokens.add(token)
        mapping = catalog.mappings.get(token)
        if mapping is None:
            conflicts = [
                item
                for item in catalog.by_identifier.get(ref.identifier, ())
                if item.namespace != ref.namespace.value
            ]
            if conflicts:
                conflict = conflicts[0]
                rows.append(
                    _mapped_row(
                        raw_key=raw_key,
                        token=token,
                        identifier=ref.identifier,
                        namespace=ref.namespace.value,
                        occurrence_count=occurrence_count,
                        locations=locations,
                        evidence=evidence,
                        mapping=conflict,
                        status="error",
                        status_label="Token 不一致",
                        detail=(
                            f"资料包中不存在完全相同的 Token；同名项使用了"
                            f"{_TYPE_LABELS.get(conflict.namespace, conflict.namespace)}类型。"
                        ),
                        issue_code="type_conflict",
                        document_order=document_order,
                        package_present=False,
                    )
                )
            else:
                repair_type = _repair_type_for_namespace(ref.namespace.value)
                rows.append(
                    SceneTokenAuditRow(
                        row_id=f"token:{token}",
                        token=token,
                        identifier=ref.identifier,
                        namespace=ref.namespace.value,
                        type_label=_TYPE_LABELS[ref.namespace.value],
                        occurrence_count=occurrence_count,
                        locations=locations,
                        location_evidence=evidence,
                        mapping_target="未映射",
                        mapping_source="无",
                        package_present=False,
                        status="error",
                        status_label="资料包缺少",
                        detail=_missing_mapping_detail(ref.namespace.value),
                        repair_type=repair_type,
                        repair_key=ref.identifier,
                        repair_namespace=ref.namespace.value,
                        issue_code="mapping_missing",
                        document_order=document_order,
                    )
                )
            continue

        rows.append(
            _mapped_row(
                raw_key=raw_key,
                token=token,
                identifier=ref.identifier,
                namespace=ref.namespace.value,
                occurrence_count=occurrence_count,
                locations=locations,
                evidence=evidence,
                mapping=mapping,
                status="ok",
                status_label="一致",
                detail="模板与资料包中均存在该 Token。",
                issue_code="",
                document_order=document_order,
            )
        )

    missing_required = contract_required - present_identifiers
    for identifier in sorted(missing_required):
        mapping = _mapping_for_identifier(catalog, identifier)
        if mapping is None:
            continue
        token = mapping.token
        rows.append(
            SceneTokenAuditRow(
                row_id=f"missing:{identifier}",
                token=token,
                identifier=identifier,
                namespace=mapping.namespace,
                type_label=_TYPE_LABELS.get(mapping.namespace, mapping.namespace),
                occurrence_count=0,
                locations=("模板中未出现",),
                location_evidence=(),
                mapping_target=_mapping_target_text(mapping),
                mapping_source=mapping.source_label,
                package_present=True,
                status="error",
                status_label="模板缺少",
                detail="资料包中存在该 Token，但当前模板中没有找到。",
                content_text=mapping.content_text,
                issue_code="required_token_missing",
            )
        )

    existing_row_tokens = {row.token for row in rows}
    for mapping in sorted(catalog.mappings.values(), key=lambda item: item.token):
        if (
            not mapping.required
            or mapping.token in scanned_tokens
            or mapping.token in existing_row_tokens
        ):
            continue
        rows.append(
            SceneTokenAuditRow(
                row_id=f"unused:{mapping.token}",
                token=mapping.token,
                identifier=mapping.identifier,
                namespace=mapping.namespace,
                type_label=_TYPE_LABELS.get(mapping.namespace, mapping.namespace),
                occurrence_count=0,
                locations=("模板中未使用",),
                location_evidence=(),
                mapping_target=_mapping_target_text(mapping),
                mapping_source=mapping.source_label,
                package_present=True,
                status="error",
                status_label="模板缺少",
                detail="资料包要求该 Token，但模板中没有对应项。",
                content_text=mapping.content_text,
                repair_type=mapping.repair_type,
                repair_key=mapping.target_key,
                repair_namespace=mapping.namespace,
                issue_code="required_token_missing",
            )
        )

    rows.sort(key=_row_sort_key)
    global_issues = [*map(str, target.issues), *preflight_issues]
    scan_message = (
        f"已扫描 {len([row for row in rows if row.occurrence_count > 0])} 个 Token，"
        f"共 {sum(row.occurrence_count for row in rows)} 处。"
    )
    if index.reference_page_excluded:
        scan_message += " 已排除母版占位符说明页。"
    return SceneTokenAuditProjection(
        source_label=source_label,
        source_path=str(path),
        source_kind=str(target.placeholder_source_kind or "none"),
        rows=tuple(rows),
        scan_status="ready",
        scan_message=scan_message,
        source_sha256=index.sha256,
        reference_page_excluded=index.reference_page_excluded,
        global_issues=tuple(dict.fromkeys(item for item in global_issues if item)),
        mapping_count=len(catalog.mappings),
    )


def _build_mapping_catalog(
    scene,
    target: ExecutionTarget,
    context: MaterialExecutionContext,
) -> _MappingCatalog:
    catalog = _MappingCatalog(mappings={}, by_identifier={})
    values = {
        **dict(context.entity_data or {}),
        **dict(context.frozen_field_values or {}),
    }

    schema_ids = resolve_material_schema_ids(
        getattr(getattr(scene, "input_source_profile", None), "material_schema_id", ""),
        (
            *tuple(
                getattr(
                    getattr(scene, "input_source_profile", None),
                    "material_schema_ids",
                    (),
                )
                or ()
            ),
            *tuple(context.material_schema_ids or ()),
        ),
    )
    field_labels: dict[str, str] = {}
    image_labels: dict[str, str] = {}
    attachment_labels: dict[str, str] = {}
    for schema_id in schema_ids:
        try:
            schema = get_material_schema(schema_id)
        except KeyError:
            continue
        for field in schema.fields:
            field_labels.setdefault(field.key, material_field_display_name(field.key))
        for role in schema.asset_roles:
            labels = attachment_labels if role.is_attachment else image_labels
            labels.setdefault(role.role, material_asset_role_display_name(role.role))

    profile = getattr(scene, "input_source_profile", None)
    for field_key in tuple(getattr(profile, "required_material_fields", ()) or ()):
        key = str(field_key or "").strip()
        if key:
            field_labels.setdefault(key, material_field_display_name(key))

    for binding in target.placeholder_bindings:
        placeholder_key = str(binding.placeholder_key or "").strip()
        field_key = str(binding.field_key or "").strip()
        if not placeholder_key or not field_key:
            continue
        token = material_token(MaterialTokenNamespace.TEXT, placeholder_key)
        catalog.add(
            TokenAuditMapping(
                token=token,
                identifier=placeholder_key,
                namespace="text",
                target_key=field_key,
                target_label=field_labels.get(field_key, material_field_display_name(field_key)),
                source_label="装配字段契约",
                required=bool(binding.required),
                occurrence_policy="all",
                repair_type="field",
                content_text=_field_content_text(values, field_key),
            ),
            replace=True,
        )

    direct_field_keys = set(field_labels)
    direct_field_keys.update(str(key) for key in values if str(key).strip())
    direct_field_keys.update(str(key) for key in context.field_functions if str(key).strip())
    direct_field_keys.update(str(key) for key in context.field_scopes if str(key).strip())
    for field_key in sorted(direct_field_keys):
        token = material_token(MaterialTokenNamespace.TEXT, field_key)
        catalog.add(
            TokenAuditMapping(
                token=token,
                identifier=field_key,
                namespace="text",
                target_key=field_key,
                target_label=field_labels.get(field_key, material_field_display_name(field_key)),
                source_label="资料字段",
                repair_type="field",
                content_text=_field_content_text(values, field_key),
            )
        )

    for alias, target_key in dict(context.field_aliases or {}).items():
        alias_key = str(alias or "").strip()
        canonical = str(target_key or "").strip()
        if not alias_key or not canonical:
            continue
        parsed = try_parse_material_token(alias_key)
        token = (
            parsed.token
            if parsed is not None
            else material_token(MaterialTokenNamespace.TEXT, alias_key)
        )
        catalog.add(
            TokenAuditMapping(
                token=token,
                identifier=(parsed.identifier if parsed is not None else alias_key),
                namespace=(parsed.namespace.value if parsed is not None else "text"),
                target_key=canonical,
                target_label=field_labels.get(canonical, material_field_display_name(canonical)),
                source_label="字段别名",
                repair_type="field",
                content_text=_field_content_text(values, canonical),
            ),
            replace=True,
        )

    timeline_keys = set(timeline_owned_field_keys(context.timeline_plans, include_inactive=True))
    timeline_keys.update(timeline_output_field_keys(context.timeline_plans))
    for field_key in sorted(timeline_keys):
        catalog.add(
            TokenAuditMapping(
                token=material_token(MaterialTokenNamespace.TIME, field_key),
                identifier=field_key,
                namespace="time",
                target_key=field_key,
                target_label=material_field_display_name(field_key),
                source_label="时间计划",
                repair_type="field",
                content_text=_field_content_text(
                    values,
                    field_key,
                    fallback="自动生成",
                ),
            )
        )

    for rule in tuple(context.content_rules or ()):
        token = str(getattr(rule, "anchor_token", "") or "").strip()
        parsed = try_parse_material_token(token)
        if parsed is None or parsed.namespace is not MaterialTokenNamespace.FILE:
            continue
        content_id = str(getattr(rule, "content_id", "") or "").strip()
        binding = dict(context.content_bindings or {}).get(content_id)
        label = str(getattr(binding, "label", "") or content_id).strip() or content_id
        catalog.add(
            TokenAuditMapping(
                token=parsed.token,
                identifier=parsed.identifier,
                namespace="file",
                target_key=content_id,
                target_label=label,
                source_label="文件资料规则",
                required=bool(getattr(rule, "required", True)),
                occurrence_policy=str(
                    getattr(getattr(rule, "occurrence_policy", "all"), "value", "")
                    or getattr(rule, "occurrence_policy", "all")
                ),
                repair_type="content",
                content_text=(
                    str(getattr(binding, "label", "") or content_id).strip()
                    if binding is not None
                    else "未填写"
                ),
            ),
            replace=True,
        )

    image_content_by_role = _asset_content_by_role(context.asset_items)
    for rule in dict(context.image_material_rules or {}).values():
        token = str(getattr(rule, "anchor_token", "") or "").strip()
        parsed = try_parse_material_token(token)
        if parsed is None or parsed.namespace is not MaterialTokenNamespace.IMAGE:
            continue
        role = str(getattr(rule, "source_role", "") or "").strip()
        catalog.add(
            TokenAuditMapping(
                token=parsed.token,
                identifier=parsed.identifier,
                namespace="img",
                target_key=role,
                target_label=image_labels.get(role, material_asset_role_display_name(role)),
                source_label="图片映射规则",
                required=bool(getattr(rule, "required", True)),
                occurrence_policy=str(
                    getattr(getattr(rule, "occurrence_policy", "all"), "value", "")
                    or getattr(rule, "occurrence_policy", "all")
                ),
                repair_type="asset",
                content_text=image_content_by_role.get(role, "未填写"),
            ),
            replace=True,
        )

    for role, binding in dict(context.attachment_bindings or {}).items():
        role_key = str(role or getattr(binding, "role", "") or "").strip()
        if not role_key:
            continue
        items = tuple(getattr(binding, "items", ()) or ())
        catalog.add(
            TokenAuditMapping(
                token=material_token(MaterialTokenNamespace.ATTACHMENT, role_key),
                identifier=role_key,
                namespace="attach",
                target_key=role_key,
                target_label=attachment_labels.get(
                    role_key,
                    str(getattr(binding, "label", "") or "").strip()
                    or material_asset_role_display_name(role_key),
                ),
                source_label="附件绑定",
                required=bool(getattr(binding, "token_required", False)),
                occurrence_policy=str(
                    getattr(getattr(binding, "occurrence_policy", "all"), "value", "")
                    or getattr(binding, "occurrence_policy", "all")
                ),
                repair_type="asset",
                content_text=_attachment_content_text(binding, items),
            ),
            replace=True,
        )

    return catalog


def _resolve_target_master(scene, target: ExecutionTarget) -> MasterSpec | None:
    master_id = str(target.master_id or getattr(scene, "master_id", "") or "").strip()
    mode_id = str(target.mode_id or getattr(scene, "mode_id", "") or "").strip()
    if not master_id or not mode_id:
        return None
    try:
        return get_master(
            master_id,
            mode_id,
            exam_config=getattr(scene, "exam_paper", None),
        )
    except Exception:
        return None


def _mapped_row(
    *,
    raw_key: str,
    token: str,
    identifier: str,
    namespace: str,
    occurrence_count: int,
    locations: tuple[str, ...],
    evidence: tuple[str, ...],
    mapping: TokenAuditMapping,
    status: str,
    status_label: str,
    detail: str,
    issue_code: str,
    document_order: int,
    package_present: bool = True,
) -> SceneTokenAuditRow:
    return SceneTokenAuditRow(
        row_id=f"token:{raw_key}",
        token=token,
        identifier=identifier,
        namespace=namespace,
        type_label=_TYPE_LABELS.get(namespace, namespace),
        occurrence_count=occurrence_count,
        locations=locations,
        location_evidence=evidence,
        mapping_target=_mapping_target_text(mapping),
        mapping_source=mapping.source_label,
        package_present=package_present,
        status=status,
        status_label=status_label,
        detail=detail,
        content_text=mapping.content_text,
        repair_type=mapping.repair_type,
        repair_key=mapping.target_key,
        repair_namespace=mapping.namespace,
        issue_code=issue_code,
        document_order=document_order,
    )


def _mapping_target_text(mapping: TokenAuditMapping) -> str:
    label = str(mapping.target_label or "").strip()
    key = str(mapping.target_key or "").strip()
    if label and key and label.casefold() != key.casefold():
        return f"{label}（{key}）"
    return label or key or "已映射"


def _mapping_for_identifier(
    catalog: _MappingCatalog,
    identifier: str,
) -> TokenAuditMapping | None:
    values = catalog.by_identifier.get(str(identifier or "").strip(), ())
    return values[0] if values else None


def _location_labels(evidence: Iterable[str], occurrence_count: int) -> tuple[str, ...]:
    labels: list[str] = []
    for surface in evidence:
        value = str(surface or "")
        lowered = value.casefold()
        if "header" in lowered:
            label = "页眉"
        elif "footer" in lowered:
            label = "页脚"
        elif "document.xml" in lowered and "tbl" in lowered:
            label = "正文表格"
        elif "document.xml" in lowered:
            label = "正文"
        else:
            label = "其他文档区域"
        if label not in labels:
            labels.append(label)
    if not labels:
        labels.append("位置未记录")
    if occurrence_count > 1:
        labels[0] = f"{labels[0]}等 {occurrence_count} 处"
    return tuple(labels)


def _field_content_text(
    values: dict[str, object],
    field_key: str,
    *,
    fallback: str = "未填写",
) -> str:
    if field_key not in values:
        return fallback
    return _compact_content_text(values.get(field_key), fallback=fallback)


def _compact_content_text(value: object, *, fallback: str = "未填写") -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return fallback
    return text if len(text) <= 160 else text[:157] + "…"


def _asset_content_by_role(items: Iterable[object]) -> dict[str, str]:
    names_by_role: dict[str, list[str]] = {}
    for item in tuple(items or ()):
        role = str(getattr(item, "role", "") or "").strip()
        path = str(getattr(item, "path", "") or "").strip()
        if not role or not path:
            continue
        name = str(getattr(item, "label", "") or "").strip() or Path(path).name
        names_by_role.setdefault(role, []).append(name)
    return {
        role: (
            names[0] if len(names) == 1 else f"{names[0]} 等 {len(names)} 张"
        )
        for role, names in names_by_role.items()
    }


def _attachment_content_text(binding: object, items: Iterable[object]) -> str:
    names: list[str] = []
    for item in tuple(items or ()):
        name = str(
            getattr(item, "label", "")
            or getattr(item, "relative_path", "")
            or getattr(getattr(item, "file_ref", None), "original_name", "")
            or ""
        ).strip()
        if name:
            names.append(name)
    if names:
        return names[0] if len(names) == 1 else f"{names[0]} 等 {len(names)} 个"
    source_path = str(getattr(binding, "source_path", "") or "").strip()
    return Path(source_path).name if source_path else "未填写"


def _repair_type_for_namespace(namespace: str) -> str:
    return {
        "text": "field",
        "time": "field",
        "file": "content",
        "img": "asset",
        "attach": "asset",
    }.get(namespace, "")


def _missing_mapping_detail(namespace: str) -> str:
    return {
        "text": "模板中存在该文字 Token，但资料包中不存在同名 Token。",
        "time": "模板中存在该时间 Token，但资料包中不存在同名 Token。",
        "file": "模板中存在该文件 Token，但资料包中不存在同名 Token。",
        "img": "模板中存在该图片 Token，但资料包中不存在同名 Token。",
        "attach": "模板中存在该附件 Token，但资料包中不存在同名 Token。",
    }.get(namespace, "模板中的 Token 在资料包中不存在。")


def _row_sort_key(row: SceneTokenAuditRow) -> tuple[int, int, str]:
    status_order = {"error": 0, "warning": 1, "ok": 2}
    return (
        status_order.get(row.status, 3),
        row.document_order,
        row.token.casefold(),
    )


__all__ = [
    "SceneTokenAuditProjection",
    "SceneTokenAuditRow",
    "TokenAuditMapping",
    "build_scene_token_audit_projection",
]
