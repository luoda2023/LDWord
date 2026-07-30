"""Material requirement controls and preview helpers for the scene panel."""

from __future__ import annotations

import re

from src.config.material_schema_registry import (
    get_material_schema,
    list_material_schemas,
    missing_material_schema_ids,
    recommend_material_schema_replacement,
    resolve_material_schema_ids,
)
from src.config.scene import SceneWorkspace
from src.qt_api import QHBoxLayout, QLineEdit, QPushButton, QWidget, Qt, Signal
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.summary_grid import SummaryGrid, SummaryGridItem
from src.shared.ui.template_form_layout import template_form_row
from src.shared.ui.text_area import TextArea
from src.ui.panels.scene_detail_support import (
    _apply_template_button_contract,
    _apply_template_line_edit_contract,
)
from src.ui.panels.scene_product_summary_projection import (
    COVERAGE_PACK_DISPLAY_LABELS,
    FAMILY_DISPLAY_LABELS,
    material_asset_role_display_name,
    material_field_display_name,
    material_schema_display_name,
)

def _format_list_text(values) -> str:
    return "\n".join(
        str(value or "").strip()
        for value in list(values or [])
        if str(value or "").strip()
    )


def _parse_list_text(text: str) -> list[str]:
    values: list[str] = []
    for raw_value in re.split(r"[\n,，;；\t]+", str(text or "")):
        normalized = raw_value.strip()
        if normalized and normalized not in values:
            values.append(normalized)
    return values


def _populate_material_schema_combo(combo: StyledComboBox) -> None:
    combo.clear()
    combo.addItem("选择资料规则", "")
    for schema in list_material_schemas():
        combo.addItem(material_schema_display_name(schema.schema_id), schema.schema_id)
        combo.setItemData(
            combo.count() - 1,
            (
                f"资料规则 ID：{schema.schema_id}\n"
                f"英文名称：{schema.label}\n"
                f"适用方案族：{_schema_family_display_name(schema.family)}"
            ),
            Qt.ToolTipRole,
        )


def _profile_material_schema_ids(profile) -> tuple[str, ...]:
    return resolve_material_schema_ids(
        getattr(profile, "material_schema_id", ""),
        getattr(profile, "material_schema_ids", ()),
    )


def _schema_preview_count(required_count: int, total_count: int) -> str:
    if not total_count:
        return "无"
    return f"{required_count} 必填 / {total_count} 全部"


def _material_role_is_attachment(role_spec: object) -> bool:
    return (
        str(getattr(role_spec, "material_domain", "") or "")
        .strip()
        .casefold()
        == "attachment"
    )


def _schema_family_display_name(family_id: object) -> str:
    normalized = str(family_id or "").strip()
    if not normalized:
        return ""
    fallback_labels = {
        "bidding": "标书/资质包",
        "official": "公文/会议材料",
        "technical": "技术长文档",
    }
    return FAMILY_DISPLAY_LABELS.get(
        normalized,
        COVERAGE_PACK_DISPLAY_LABELS.get(
            normalized,
            fallback_labels.get(normalized, normalized.replace("_", " ")),
        ),
    )


def _accepted_type_display(value: object) -> str:
    normalized = str(value or "").strip().lower()
    labels = {
        "image": "图片",
        "pdf": "PDF",
        "xlsx": "Excel",
    }
    return labels.get(normalized, normalized.upper() if normalized else "")


def _schema_count_value(required_count: int, total_count: int) -> str:
    if not total_count:
        return "无"
    if required_count == total_count:
        return f"{total_count} 个必填项"
    return f"{required_count} 必填 / {total_count} 全部"


def _readable_preview_lines(lines: list[str], *, empty: str, limit: int = 5) -> str:
    if not lines:
        return empty
    if len(lines) <= limit:
        return _format_list_text(lines)
    return _format_list_text([*lines[:limit], f"还有 {len(lines) - limit} 项"])


SCENE_MATERIAL_REQUIREMENT_SOURCE_LABEL = "本方案补充要求"


def _schema_field_preview(known_schemas, profile) -> tuple[str, str, str]:
    fields: dict[str, dict[str, object]] = {}
    for schema in known_schemas:
        for field in getattr(schema, "fields", ()):
            key = str(getattr(field, "key", "") or "").strip()
            if not key:
                continue
            entry = fields.setdefault(
                key,
                {
                    "label": str(getattr(field, "label", "") or key),
                    "required": False,
                    "sources": [],
                },
            )
            entry["required"] = bool(entry["required"]) or bool(getattr(field, "required", True))
            sources = entry["sources"]
            if isinstance(sources, list) and schema.schema_id not in sources:
                sources.append(schema.schema_id)
    for key in _parse_list_text(_format_list_text(getattr(profile, "required_material_fields", ()))):
        entry = fields.setdefault(
            key,
            {"label": key, "required": True, "sources": []},
        )
        entry["required"] = True
        sources = entry["sources"]
        if isinstance(sources, list) and SCENE_MATERIAL_REQUIREMENT_SOURCE_LABEL not in sources:
            sources.append(SCENE_MATERIAL_REQUIREMENT_SOURCE_LABEL)

    required_count = sum(1 for item in fields.values() if bool(item["required"]))
    visible_lines = [
        f"{material_field_display_name(key)}（{'必填' if bool(item['required']) else '可选'}）"
        for key, item in fields.items()
    ]
    evidence_lines = [
        (
            f"{key} · {item['label']} · "
            f"{'必填' if bool(item['required']) else '可选'} · "
            f"{', '.join(item['sources']) if isinstance(item['sources'], list) else ''}"
        )
        for key, item in fields.items()
    ]
    return (
        _schema_count_value(required_count, len(fields)),
        _readable_preview_lines(visible_lines, empty="无字段"),
        _format_list_text(evidence_lines) or "无字段",
    )


def _schema_role_preview(known_schemas, profile, *, attachments: bool) -> tuple[str, str, str]:
    roles: dict[str, dict[str, object]] = {}
    for schema in known_schemas:
        for role_spec in getattr(schema, "asset_roles", ()):
            accepted_types = tuple(getattr(role_spec, "accepted_types", ("image",)) or ("image",))
            if _material_role_is_attachment(role_spec) != attachments:
                continue
            role = str(getattr(role_spec, "role", "") or "").strip()
            if not role:
                continue
            entry = roles.setdefault(
                role,
                {
                    "label": str(getattr(role_spec, "label", "") or role),
                    "required": False,
                    "accepted_types": accepted_types,
                    "archive_dir": str(getattr(role_spec, "archive_dir", "") or ""),
                    "sources": [],
                },
            )
            entry["required"] = bool(entry["required"]) or bool(getattr(role_spec, "required", True))
            if not str(entry.get("archive_dir") or "").strip():
                entry["archive_dir"] = str(getattr(role_spec, "archive_dir", "") or "")
            sources = entry["sources"]
            if isinstance(sources, list) and schema.schema_id not in sources:
                sources.append(schema.schema_id)
    if not attachments:
        for role in _parse_list_text(_format_list_text(getattr(profile, "required_image_roles", ()))):
            entry = roles.setdefault(
                role,
                {
                    "label": role,
                    "required": True,
                    "accepted_types": ("image",),
                    "archive_dir": "",
                    "sources": [],
                },
            )
            entry["required"] = True
            sources = entry["sources"]
            if isinstance(sources, list) and SCENE_MATERIAL_REQUIREMENT_SOURCE_LABEL not in sources:
                sources.append(SCENE_MATERIAL_REQUIREMENT_SOURCE_LABEL)

    required_count = sum(1 for item in roles.values() if bool(item["required"]))
    visible_lines = []
    evidence_lines = []
    for role, item in roles.items():
        accepted_types = item["accepted_types"]
        accepted_label = "/".join(accepted_types) if isinstance(accepted_types, tuple) else str(accepted_types)
        accepted_display = (
            " / ".join(_accepted_type_display(value) for value in accepted_types)
            if isinstance(accepted_types, tuple)
            else _accepted_type_display(accepted_types)
        )
        sources = item["sources"]
        archive_dir = str(item.get("archive_dir") or "").strip()
        archive_label = f" | assets/{archive_dir}" if archive_dir else ""
        visible_lines.append(
            f"{material_asset_role_display_name(role)}"
            f"（{'必填' if bool(item['required']) else '可选'}"
            f"{'，' + accepted_display if attachments and accepted_display else ''}）"
        )
        evidence_lines.append(
            f"{role} · {item['label']} · "
            f"{'必填' if bool(item['required']) else '可选'} · "
            f"{accepted_label}{archive_label} · "
            f"{', '.join(sources) if isinstance(sources, list) else ''}"
        )
    empty_detail = "无附件角色" if attachments else "无图片或签章角色"
    return (
        _schema_count_value(required_count, len(roles)),
        _readable_preview_lines(visible_lines, empty=empty_detail),
        _format_list_text(evidence_lines) or empty_detail,
    )


def _build_material_schema_validation_items(scene: SceneWorkspace) -> tuple[SummaryGridItem, ...]:
    profile = scene.input_source_profile
    schema_ids = _profile_material_schema_ids(profile)
    missing_ids = missing_material_schema_ids(schema_ids)
    known_schemas = []
    for schema_id in schema_ids:
        try:
            known_schemas.append(get_material_schema(schema_id))
        except KeyError:
            continue
    families = []
    for schema in known_schemas:
        if schema.family and schema.family not in families:
            families.append(schema.family)
    schema_names = [material_schema_display_name(schema.schema_id) for schema in known_schemas]
    schema_evidence = [f"{schema.schema_id} · {schema.label}" for schema in known_schemas]
    family_names = [_schema_family_display_name(family) for family in families]
    field_value, field_detail, field_tooltip = _schema_field_preview(known_schemas, profile)
    image_value, image_detail, image_tooltip = _schema_role_preview(
        known_schemas,
        profile,
        attachments=False,
    )
    attachment_value, attachment_detail, attachment_tooltip = _schema_role_preview(
        known_schemas,
        profile,
        attachments=True,
    )

    if not schema_ids:
        status_value = "未配置"
        status_detail = "未绑定资料规则"
        status_tooltip = status_detail
        status_variant = "neutral"
    elif missing_ids:
        status_value = f"未识别 {len(missing_ids)} 个"
        status_detail = f"{len(missing_ids)} 个资料规则未登记，可从列表替换"
        status_tooltip = "未登记资料规则 ID：\n" + _format_list_text(missing_ids)
        status_variant = "warning"
    else:
        status_value = "通过"
        status_detail = f"{len(schema_ids)} 个资料规则已登记"
        status_tooltip = "资料规则 ID：\n" + _format_list_text(schema_ids)
        status_variant = "success"

    preview_detail = (
        f"字段：{field_value}；图片/签章：{image_value}；附件：{attachment_value}"
    )
    if not schema_ids:
        overview_value = "未配置资料规则"
        overview_detail = "选择资料规则后可预览字段、图片和附件要求"
        overview_variant = "neutral"
    elif missing_ids:
        overview_value = (
            f"已识别 {len(known_schemas)} 个，未识别 {len(missing_ids)} 个"
            if known_schemas
            else f"未识别 {len(missing_ids)} 个资料规则"
        )
        overview_detail = preview_detail
        overview_variant = "warning"
    else:
        overview_value = f"已识别 {len(known_schemas)} 个资料规则"
        overview_detail = preview_detail
        overview_variant = "success"
    overview_tooltip = _format_list_text(
        [
            status_tooltip,
            _format_list_text(schema_evidence),
            field_tooltip,
            image_tooltip,
            attachment_tooltip,
        ]
    )

    return (
        SummaryGridItem(
            key="schema_rule_overview",
            label="规则概览",
            value=overview_value,
            detail=overview_detail,
            variant=overview_variant,
            column_span=3,
            tooltip=overview_tooltip,
        ),
        SummaryGridItem(
            key="schema_registry_status",
            label="资料规则校验",
            value=status_value,
            detail=status_detail,
            variant=status_variant,
            tooltip=status_tooltip,
        ),
        SummaryGridItem(
            key="schema_labels",
            label="资料规则",
            value=f"{len(known_schemas)} 个资料规则" if known_schemas else "无",
            detail=_format_list_text(schema_names) or "无可用名称",
            variant="info" if known_schemas else "neutral",
            tooltip=_format_list_text(schema_evidence) or "无可用名称",
        ),
        SummaryGridItem(
            key="schema_families",
            label="适用方案族",
            value=f"{len(families)} 个方案族" if families else "无",
            detail=_format_list_text(family_names) or "无方案族",
            variant="info" if families else "neutral",
            tooltip=_format_list_text(families) or "无方案族",
        ),
        SummaryGridItem(
            key="schema_fields",
            label="字段预览",
            value=field_value,
            detail=field_detail,
            variant="info" if field_value != "无" else "neutral",
            tooltip=field_tooltip,
        ),
        SummaryGridItem(
            key="schema_image_roles",
            label="图片/签章",
            value=image_value,
            detail=image_detail,
            variant="info" if image_value != "无" else "neutral",
            tooltip=image_tooltip,
        ),
        SummaryGridItem(
            key="schema_attachment_roles",
            label="附件清单",
            value=attachment_value,
            detail=attachment_detail,
            variant="info" if attachment_value != "无" else "neutral",
            tooltip=attachment_tooltip,
        ),
    )


class _MaterialRequirementBlock(QWidget):
    """Semantic block for material rules, overrides, preview, and repairs."""

    edited = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._is_syncing = False
        self._preview_summary = SummaryGrid(columns=3, parent=self)

        self._schema_registry_tools = QWidget(self)
        schema_registry_layout = QHBoxLayout(self._schema_registry_tools)
        schema_registry_layout.setContentsMargins(0, 0, 0, 0)
        schema_registry_layout.setSpacing(8)

        self._schema_registry_combo = StyledComboBox(self._schema_registry_tools)
        _populate_material_schema_combo(self._schema_registry_combo)

        self._set_primary_schema_btn = QPushButton("设为主规则", self._schema_registry_tools)
        self._append_schema_btn = QPushButton("加入列表", self._schema_registry_tools)
        self._replace_unknown_schema_btn = QPushButton("替换未识别", self._schema_registry_tools)
        self._remove_unknown_schema_btn = QPushButton("移除未识别", self._schema_registry_tools)

        self._schema_registry_combo.currentIndexChanged.connect(self.sync_actions)
        self._set_primary_schema_btn.clicked.connect(self.set_selected_schema_as_primary)
        self._append_schema_btn.clicked.connect(self.append_selected_schema)
        self._replace_unknown_schema_btn.clicked.connect(self.replace_unrecognized_schemas)
        self._replace_unknown_schema_btn.setEnabled(False)
        self._remove_unknown_schema_btn.clicked.connect(self.remove_unrecognized_schemas)
        self._remove_unknown_schema_btn.setEnabled(False)

        schema_registry_layout.addWidget(self._schema_registry_combo, 1)
        schema_registry_layout.addWidget(self._set_primary_schema_btn)
        schema_registry_layout.addWidget(self._append_schema_btn)
        schema_registry_layout.addWidget(self._replace_unknown_schema_btn)
        schema_registry_layout.addWidget(self._remove_unknown_schema_btn)

        self._material_schema_id = QLineEdit(self)
        self._material_schema_id.setPlaceholderText("从上方选择资料规则，或输入规则 ID")
        self._material_schema_id.textChanged.connect(self._emit_edited)

        self._material_schema_ids = TextArea(
            placeholder="每行一个资料规则；建议用上方“加入列表”",
            min_height=72,
            max_height=120,
            parent=self,
        )
        self._material_schema_ids.text_changed.connect(self._emit_edited)

        self._required_material_fields = TextArea(
            placeholder="留空则按资料规则执行；每行一个资料字段",
            min_height=72,
            max_height=120,
            parent=self,
        )
        self._required_material_fields.text_changed.connect(self._emit_edited)

        self._required_image_roles = TextArea(
            placeholder="留空则按资料规则执行；每行一个图片或签章要求",
            min_height=72,
            max_height=120,
            parent=self,
        )
        self._required_image_roles.text_changed.connect(self._emit_edited)

        self.apply_theme()
        self.sync_actions()

    @property
    def schema_registry_tools(self) -> QWidget:
        return self._schema_registry_tools

    @property
    def schema_registry_combo(self) -> StyledComboBox:
        return self._schema_registry_combo

    @property
    def set_primary_button(self) -> QPushButton:
        return self._set_primary_schema_btn

    @property
    def append_button(self) -> QPushButton:
        return self._append_schema_btn

    @property
    def replace_unrecognized_button(self) -> QPushButton:
        return self._replace_unknown_schema_btn

    @property
    def remove_unrecognized_button(self) -> QPushButton:
        return self._remove_unknown_schema_btn

    @property
    def primary_schema_editor(self) -> QLineEdit:
        return self._material_schema_id

    @property
    def schema_list_editor(self) -> TextArea:
        return self._material_schema_ids

    @property
    def required_material_fields_editor(self) -> TextArea:
        return self._required_material_fields

    @property
    def required_image_roles_editor(self) -> TextArea:
        return self._required_image_roles

    @property
    def preview_summary(self) -> SummaryGrid:
        return self._preview_summary

    def form_rows(self, *, parent) -> list[QWidget]:
        return [
            template_form_row("资料规则选择", self._schema_registry_tools, parent=parent),
            template_form_row("主资料规则", self._material_schema_id, parent=parent),
            template_form_row("资料规则列表", self._material_schema_ids, parent=parent),
            template_form_row("必填资料字段", self._required_material_fields, parent=parent),
            template_form_row("必需图片/签章", self._required_image_roles, parent=parent),
        ]

    def apply_theme(self) -> None:
        _apply_template_line_edit_contract(self._material_schema_id)
        _apply_template_button_contract(
            (self._set_primary_schema_btn, "secondary"),
            (self._append_schema_btn, "secondary"),
            (self._replace_unknown_schema_btn, "secondary"),
            (self._remove_unknown_schema_btn, "ghost-danger"),
        )

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        profile = scene.input_source_profile
        self._is_syncing = True
        try:
            self._material_schema_id.setText(profile.material_schema_id)
            self._material_schema_ids.set_text(_format_list_text(profile.material_schema_ids))
            self._required_material_fields.set_text(
                _format_list_text(profile.required_material_fields)
            )
            self._required_image_roles.set_text(_format_list_text(profile.required_image_roles))
        finally:
            self._is_syncing = False
        self.refresh_preview(scene)
        self.sync_actions()

    def refresh_preview(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._preview_summary.set_items(_build_material_schema_validation_items(scene))

    def apply_to_profile(self, profile) -> None:
        schema_id = self._material_schema_id.text().strip()
        schema_ids = _parse_list_text(self._material_schema_ids.get_text())
        profile.material_schema_id = schema_id
        profile.material_schema_ids = (
            _parse_list_text("\n".join([schema_id, *schema_ids]))
            if schema_ids
            else []
        )
        profile.required_material_fields = _parse_list_text(
            self._required_material_fields.get_text()
        )
        profile.required_image_roles = _parse_list_text(self._required_image_roles.get_text())

    def selected_schema_id(self) -> str:
        return str(self._schema_registry_combo.currentData() or "").strip()

    def schema_ids_from_inputs(self) -> tuple[str, ...]:
        return resolve_material_schema_ids(
            self._material_schema_id.text().strip(),
            _parse_list_text(self._material_schema_ids.get_text()),
        )

    def navigation_widget_for_field(self, field_id: str) -> QWidget | None:
        target = str(field_id or "").strip()
        aliases = {
            "schema": self._schema_registry_tools,
            "schema_id": self._material_schema_id,
            "material_schema": self._material_schema_id,
            "material_schema_id": self._material_schema_id,
            "input_source_profile.material_schema_id": self._material_schema_id,
            "material_schema_ids": self._material_schema_ids,
            "input_source_profile.material_schema_ids": self._material_schema_ids,
            "schema_registry": self._schema_registry_tools,
            "schema_registry_combo": self._schema_registry_combo,
            "required_material_fields": self._required_material_fields,
            "input_source_profile.required_material_fields": self._required_material_fields,
            "required_image_roles": self._required_image_roles,
            "input_source_profile.required_image_roles": self._required_image_roles,
        }
        widget = aliases.get(target)
        if widget is not None:
            return widget
        primary_id = self._material_schema_id.text().strip()
        schema_ids = _parse_list_text(self._material_schema_ids.get_text())
        if target == primary_id:
            return self._material_schema_id
        if target in schema_ids:
            return self._material_schema_ids
        if target in _parse_list_text(self._required_material_fields.get_text()):
            return self._required_material_fields
        if target in _parse_list_text(self._required_image_roles.get_text()):
            return self._required_image_roles
        return None

    def sync_actions(self, *_args) -> None:
        missing_ids = missing_material_schema_ids(self.schema_ids_from_inputs())
        replacement_id = self.selected_schema_id()
        suggested_id = self._suggest_unknown_schema_replacement(missing_ids)
        effective_replacement_id = replacement_id or suggested_id
        can_replace = bool(missing_ids and effective_replacement_id)
        self._replace_unknown_schema_btn.setEnabled(can_replace)
        self._replace_unknown_schema_btn.setToolTip(
            (
                "将未识别规则 "
                + ", ".join(missing_ids)
                + f" 替换为 {effective_replacement_id}"
                + ("（推荐）" if suggested_id and not replacement_id else "")
            )
            if can_replace
            else (
                "选择一个已登记的资料规则后可替换: " + ", ".join(missing_ids)
                if missing_ids
                else "当前资料规则均已识别"
            )
        )
        self._remove_unknown_schema_btn.setEnabled(bool(missing_ids))
        self._remove_unknown_schema_btn.setToolTip(
            "移除未识别规则: " + ", ".join(missing_ids)
            if missing_ids
            else "当前资料规则均已识别"
        )

    def set_selected_schema_as_primary(self) -> None:
        schema_id = self.selected_schema_id()
        if not schema_id:
            return
        existing_ids = _parse_list_text(self._material_schema_ids.get_text())
        next_ids = (
            _parse_list_text("\n".join([schema_id, *existing_ids]))
            if existing_ids
            else []
        )
        self._is_syncing = True
        try:
            self._material_schema_id.setText(schema_id)
            if existing_ids:
                self._material_schema_ids.set_text(_format_list_text(next_ids))
        finally:
            self._is_syncing = False
        self._emit_edited()

    def append_selected_schema(self) -> None:
        schema_id = self.selected_schema_id()
        if not schema_id:
            return
        primary_id = self._material_schema_id.text().strip() or schema_id
        existing_ids = _parse_list_text(self._material_schema_ids.get_text())
        next_ids = _parse_list_text("\n".join([primary_id, *existing_ids, schema_id]))
        self._is_syncing = True
        try:
            self._material_schema_id.setText(primary_id)
            self._material_schema_ids.set_text(_format_list_text(next_ids))
        finally:
            self._is_syncing = False
        self._emit_edited()

    def replace_unrecognized_schemas(self) -> None:
        schema_ids = self.schema_ids_from_inputs()
        missing_ids = set(missing_material_schema_ids(schema_ids))
        replacement_id = self.selected_schema_id() or self._suggest_unknown_schema_replacement(
            tuple(missing_ids)
        )
        if not replacement_id or not missing_ids:
            self.sync_actions()
            return
        next_ids: list[str] = []
        for schema_id in schema_ids:
            next_id = replacement_id if schema_id in missing_ids else schema_id
            if next_id and next_id not in next_ids:
                next_ids.append(next_id)
        current_primary = self._material_schema_id.text().strip()
        next_primary = replacement_id if current_primary in missing_ids else current_primary
        if not next_primary and next_ids:
            next_primary = next_ids[0]
        had_schema_list = bool(_parse_list_text(self._material_schema_ids.get_text()))
        next_list = next_ids if had_schema_list else []
        self._is_syncing = True
        try:
            self._material_schema_id.setText(next_primary)
            self._material_schema_ids.set_text(_format_list_text(next_list))
        finally:
            self._is_syncing = False
        self._emit_edited()

    def remove_unrecognized_schemas(self) -> None:
        schema_ids = self.schema_ids_from_inputs()
        missing_ids = set(missing_material_schema_ids(schema_ids))
        if not missing_ids:
            self.sync_actions()
            return
        valid_ids = [schema_id for schema_id in schema_ids if schema_id not in missing_ids]
        current_primary = self._material_schema_id.text().strip()
        next_primary = current_primary if current_primary not in missing_ids else ""
        if not next_primary and valid_ids:
            next_primary = valid_ids[0]
        had_schema_list = bool(_parse_list_text(self._material_schema_ids.get_text()))
        next_list = valid_ids if had_schema_list else []
        self._is_syncing = True
        try:
            self._material_schema_id.setText(next_primary)
            self._material_schema_ids.set_text(_format_list_text(next_list))
        finally:
            self._is_syncing = False
        self._emit_edited()

    def _suggest_unknown_schema_replacement(self, missing_ids: tuple[str, ...]) -> str:
        if self._current_scene is None or not missing_ids:
            return ""
        schema_ids = self.schema_ids_from_inputs()
        recommendation = recommend_material_schema_replacement(
            missing_ids,
            family_hints=(
                getattr(self._current_scene, "category", ""),
                getattr(self._current_scene, "scene_id", ""),
            ),
            existing_schema_ids=tuple(
                schema_id for schema_id in schema_ids if schema_id not in missing_ids
            ),
        )
        return recommendation.schema_id if recommendation is not None else ""

    def _emit_edited(self, *_args) -> None:
        if self._is_syncing:
            return
        self.sync_actions()
        self.edited.emit()
