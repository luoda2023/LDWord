"""Content/material configuration detail for the scene panel."""

from __future__ import annotations

from pathlib import Path

from src.config.material_context import MaterialExecutionContext
from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
    list_common_official_document_profiles,
)
from src.config.official_material_form import (
    OFFICIAL_MATERIAL_FIELD_SPECS,
    build_official_material_form_projection,
    official_material_field_label,
)
from src.config.scene import SceneWorkspace
from src.qt_api import (
    QAbstractItemView,
    QBrush,
    QColor,
    QDesktopServices,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTimer,
    QUrl,
    QVBoxLayout,
    QWidget,
    Qt,
)
from src.shared.engine.official_document_material_package import (
    export_official_document_material_package,
    export_official_document_material_package_to_user_library,
    load_official_document_material_batch,
)
from src.shared.ui import apply_button_variant
from src.shared.ui.collapsible_section import CollapsibleSection
from src.shared.ui.segmented_control import SegmentedControl
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.summary_grid import SummaryGrid
from src.shared.ui.template_form_layout import TemplateFormStack, template_form_row
from src.shared.ui.text_area import TextArea
from src.shared.ui.theme import get_theme
from src.shared.ui.toast import Toast
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.panels.scene_detail_base import _SimpleFormDetail
from src.ui.panels.scene_detail_support import (
    _apply_template_button_contract,
    _apply_template_line_edit_contract,
    _load_official_material_source,
    _populate_combo,
    _set_combo_by_data,
)
from src.ui.panels.scene_material_requirement_block import _MaterialRequirementBlock
from src.ui.panels.scene_token_audit_projection import (
    SceneTokenAuditProjection,
    SceneTokenAuditRow,
    build_scene_token_audit_projection,
)
from src.ui.panels.scene_product_summary_projection import (
    FAILURE_POLICY_LABELS,
    LATEX_POLICY_LABELS,
    MARKDOWN_POLICY_LABELS,
    build_input_profile_summary_items,
)
from src.config.scene_surface_registry import (
    scene_uses_official_document_surface as _scene_uses_official_document_surface,
)


class _ContentDetail(_SimpleFormDetail):
    """Audit template tokens and keep legacy material settings available."""

    def __init__(self, bridge=None, parent=None):
        super().__init__(
            "模板 Token 校验",
            "scan",
            "核对模板 Token 是否也存在于当前资料包。",
            parent,
        )
        self._bridge = bridge
        self._current_scene: SceneWorkspace | None = None
        self._desc_label.setVisible(False)
        self._detail_summary.setVisible(False)
        self._token_audit_projection = SceneTokenAuditProjection(
            source_label="未选择校验来源",
            source_path="",
            source_kind="none",
            scan_status="missing_source",
            scan_message="当前方案尚未选择可扫描的 DOCX 文档。",
        )
        self._visible_token_audit_rows: list[SceneTokenAuditRow] = []
        self._token_view_initialized = False
        self._official_material_fields: dict[str, QWidget] = {}
        self._official_material_rows: dict[str, QWidget] = {}
        self._official_material_expanded_groups: set[str] = set()
        self._official_material_commit_timer = QTimer(self)
        self._official_material_commit_timer.setSingleShot(True)
        self._official_material_commit_timer.setInterval(250)
        self._official_material_commit_timer.timeout.connect(
            self._commit_official_material_edits
        )
        self._token_audit_refresh_timer = QTimer(self)
        self._token_audit_refresh_timer.setSingleShot(True)
        self._token_audit_refresh_timer.setInterval(180)
        self._token_audit_refresh_timer.timeout.connect(self._refresh_token_audit)

        self._build_token_audit_workbench()
        self._advanced_section = CollapsibleSection(
            "输入处理设置",
            expanded=False,
            parent=self._card,
        )
        self._card.add_widget(self._advanced_section)

        self._input_summary = SummaryGrid(columns=3, parent=self._advanced_section)
        self._advanced_section.add_widget(self._input_summary)

        self._material_requirement_block = _MaterialRequirementBlock(
            self._advanced_section
        )
        self._material_rule_selector = self._material_requirement_block
        self._material_rule_selector.edited.connect(self._on_edited)
        self._schema_validation_summary = self._material_rule_selector.preview_summary
        self._advanced_section.add_widget(self._schema_validation_summary)

        self._markdown_policy = StyledComboBox(self)
        _populate_combo(self._markdown_policy, MARKDOWN_POLICY_LABELS)
        self._markdown_policy.currentIndexChanged.connect(self._on_edited)
        rows = [template_form_row("Markdown", self._markdown_policy, parent=self._card)]

        self._latex_policy = StyledComboBox(self)
        _populate_combo(self._latex_policy, LATEX_POLICY_LABELS)
        self._latex_policy.currentIndexChanged.connect(self._on_edited)
        rows.append(template_form_row("LaTeX", self._latex_policy, parent=self._card))

        self._require_material = ToggleSwitch(self, checked=False)
        self._require_material.toggled_signal.connect(self._on_edited)
        rows.append(
            template_form_row("资料包必需", self._require_material, parent=self._card)
        )

        self._schema_registry_tools = self._material_rule_selector.schema_registry_tools
        self._schema_registry_combo = self._material_rule_selector.schema_registry_combo
        self._set_primary_schema_btn = self._material_rule_selector.set_primary_button
        self._append_schema_btn = self._material_rule_selector.append_button
        self._replace_unknown_schema_btn = (
            self._material_rule_selector.replace_unrecognized_button
        )
        self._remove_unknown_schema_btn = (
            self._material_rule_selector.remove_unrecognized_button
        )
        self._material_schema_id = self._material_rule_selector.primary_schema_editor
        self._material_schema_ids = self._material_rule_selector.schema_list_editor
        self._required_material_fields = (
            self._material_rule_selector.required_material_fields_editor
        )
        self._required_image_roles = (
            self._material_rule_selector.required_image_roles_editor
        )
        rows.extend(self._material_rule_selector.form_rows(parent=self._card))

        self._input_failure = StyledComboBox(self)
        _populate_combo(self._input_failure, FAILURE_POLICY_LABELS)
        self._input_failure.currentIndexChanged.connect(self._on_edited)
        rows.append(
            template_form_row("失败策略", self._input_failure, parent=self._card)
        )

        self._watermark_enabled = ToggleSwitch(self, checked=False)
        self._watermark_enabled.toggled_signal.connect(self._on_edited)
        rows.append(
            template_form_row("启用水印", self._watermark_enabled, parent=self._card)
        )

        self._watermark_text = QLineEdit(self)
        self._watermark_text.setPlaceholderText("例如 内部传阅")
        self._watermark_text.textChanged.connect(self._on_edited)
        rows.append(
            template_form_row("水印文本", self._watermark_text, parent=self._card)
        )
        self._advanced_section.add_widget(
            TemplateFormStack(rows, parent=self._advanced_section)
        )

        self._official_material_section = QWidget(self._advanced_section)
        self._official_material_section.setObjectName("scn_official_material_section")
        official_layout = QVBoxLayout(self._official_material_section)
        official_layout.setContentsMargins(0, 12, 0, 0)
        official_layout.setSpacing(8)

        self._official_material_status = QLabel("", self._official_material_section)
        self._official_material_status.setObjectName(
            "scn_official_material_fill_status"
        )
        self._official_material_status.setWordWrap(True)
        official_layout.addWidget(self._official_material_status)

        self._official_material_batch_status = QLabel(
            "",
            self._official_material_section,
        )
        self._official_material_batch_status.setObjectName(
            "scn_official_material_batch_status"
        )
        self._official_material_batch_status.setWordWrap(True)
        self._official_material_batch_status.setVisible(False)
        official_layout.addWidget(self._official_material_batch_status)

        self._official_batch_profile = StyledComboBox(self._official_material_section)
        self._official_batch_profile.setObjectName(
            "scn_official_material_batch_profile"
        )
        self._official_batch_profile.set_full_width_mode(True)
        self._official_batch_profile.currentIndexChanged.connect(
            self._on_official_batch_profile_changed
        )

        self._official_material_profile = StyledComboBox(
            self._official_material_section
        )
        self._official_material_profile.setObjectName("scn_official_material_profile")
        self._official_material_profile.set_full_width_mode(True)
        for profile in list_common_official_document_profiles():
            self._official_material_profile.addItem(
                f"{profile.label} / {profile.profile_id}",
                profile.profile_id,
            )
        self._official_material_profile.currentIndexChanged.connect(
            self._on_official_material_profile_changed
        )

        self._official_batch_profile_row = template_form_row(
            "批次任务",
            self._official_batch_profile,
            parent=self._official_material_section,
        )
        self._official_batch_profile_row.setVisible(False)
        official_rows = [
            self._official_batch_profile_row,
            template_form_row(
                "文种",
                self._official_material_profile,
                parent=self._official_material_section,
            ),
        ]
        self._official_optional_fields_toggle = QPushButton(
            "展开常用选填",
            self._official_material_section,
        )
        self._official_optional_fields_toggle.setCheckable(True)
        self._official_optional_fields_toggle.toggled.connect(
            lambda checked: self._on_official_material_group_toggled(
                "optional",
                checked,
            )
        )
        apply_button_variant(self._official_optional_fields_toggle, "secondary")
        self._official_advanced_fields_toggle = QPushButton(
            "展开版记与高级",
            self._official_material_section,
        )
        self._official_advanced_fields_toggle.setCheckable(True)
        self._official_advanced_fields_toggle.toggled.connect(
            lambda checked: self._on_official_material_group_toggled(
                "advanced",
                checked,
            )
        )
        apply_button_variant(self._official_advanced_fields_toggle, "secondary")

        for spec in OFFICIAL_MATERIAL_FIELD_SPECS:
            field_id = spec.field_key
            if spec.editor_kind == "multiline":
                editor = TextArea(
                    placeholder="填写公文正文，可先用短段落验证装配效果。",
                    min_height=96,
                    max_height=180,
                    parent=self._official_material_section,
                )
                editor.setObjectName("scn_official_material_body")
                editor._text_edit.setObjectName("scn_official_material_body_text")
                editor.text_changed.connect(self._schedule_official_material_commit)
            else:
                editor = QLineEdit(self._official_material_section)
                editor.setObjectName(f"scn_official_material_{field_id}")
                editor.setPlaceholderText(spec.label)
                editor.textChanged.connect(self._schedule_official_material_commit)
            self._official_material_fields[field_id] = editor
            row = template_form_row(
                spec.label,
                editor,
                parent=self._official_material_section,
            )
            self._official_material_rows[field_id] = row
            official_rows.append(row)

        official_rows.extend(
            [
                template_form_row(
                    "常用选填",
                    self._official_optional_fields_toggle,
                    parent=self._official_material_section,
                ),
                template_form_row(
                    "版记与高级",
                    self._official_advanced_fields_toggle,
                    parent=self._official_material_section,
                ),
            ]
        )

        self._official_material_contract = QLabel("", self._official_material_section)
        self._official_material_contract.setObjectName("scn_official_material_contract")
        self._official_material_contract.setWordWrap(True)
        self._official_material_contract_row = template_form_row(
            "占位符映射",
            self._official_material_contract,
            parent=self._official_material_section,
        )
        official_rows.append(self._official_material_contract_row)
        official_layout.addWidget(
            TemplateFormStack(official_rows, parent=self._official_material_section)
        )
        self._official_material_section.setVisible(False)
        self._advanced_section.add_widget(self._official_material_section)

        if self._bridge is not None and hasattr(
            self._bridge, "material_context_changed"
        ):
            self._bridge.material_context_changed.connect(
                self._on_material_context_changed
            )
        if self._bridge is not None and hasattr(
            self._bridge,
            "official_document_type_changed",
        ):
            self._bridge.official_document_type_changed.connect(
                self._on_official_document_type_changed
            )
        if self._bridge is not None and hasattr(
            self._bridge,
            "material_batch_selection_changed",
        ):
            self._bridge.material_batch_selection_changed.connect(
                self._on_official_material_batch_selection_changed
            )
        if self._bridge is not None and hasattr(
            self._bridge,
            "execution_target_changed",
        ):
            self._bridge.execution_target_changed.connect(
                self._on_execution_target_changed
            )
        self._apply_theme()

    def _build_token_audit_workbench(self) -> None:
        source_bar = QWidget(self._card)
        source_bar.setObjectName("scn_token_audit_source_bar")
        source_layout = QHBoxLayout(source_bar)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(10)
        source_copy = QVBoxLayout()
        source_copy.setContentsMargins(0, 0, 0, 0)
        source_copy.setSpacing(2)
        self._token_source_label = QLabel("校验来源：未选择", source_bar)
        self._token_source_label.setObjectName("scn_token_audit_source")
        self._token_source_label.setWordWrap(True)
        self._token_source_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        source_copy.addWidget(self._token_source_label)
        source_layout.addLayout(source_copy, 1)
        self._token_source_action_btn = QPushButton("选择来源", source_bar)
        self._token_source_action_btn.setObjectName("scn_token_audit_source_action")
        self._token_source_action_btn.clicked.connect(self._navigate_token_source_owner)
        self._token_source_action_btn.setVisible(False)
        source_layout.addWidget(self._token_source_action_btn)
        self._token_refresh_btn = QPushButton("重新校验", source_bar)
        self._token_refresh_btn.setObjectName("scn_token_audit_refresh")
        self._token_refresh_btn.clicked.connect(self._force_refresh_token_audit)
        source_layout.addWidget(self._token_refresh_btn)
        self._card.add_widget(source_bar)

        self._token_issue_panel = QFrame(self._card)
        self._token_issue_panel.setObjectName("scn_token_audit_issue_panel")
        issue_layout = QVBoxLayout(self._token_issue_panel)
        issue_layout.setContentsMargins(12, 12, 12, 12)
        issue_layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(8)
        self._token_search = QLineEdit(self._token_issue_panel)
        self._token_search.setObjectName("scn_token_audit_search")
        self._token_search.setPlaceholderText("搜索 Token")
        self._token_search.setClearButtonEnabled(True)
        self._token_search.textChanged.connect(self._refresh_token_audit_table)
        toolbar.addWidget(self._token_search, 1)

        self._token_view_control = SegmentedControl(parent=self._token_issue_panel)
        self._token_view_control.add_segment("不一致 0", "issues")
        self._token_view_control.add_segment("全部 Token 0", "all")
        self._token_view_control.current_changed.connect(
            self._refresh_token_audit_table
        )
        toolbar.addWidget(self._token_view_control)
        issue_layout.addLayout(toolbar)

        self._token_audit_table = QTableWidget(0, 5, self._token_issue_panel)
        self._token_audit_table.setObjectName("scn_token_audit_table")
        self._token_audit_table.setHorizontalHeaderLabels(
            ("Token", "模板", "资料包", "校验结果", "填写内容")
        )
        self._token_audit_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._token_audit_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._token_audit_table.setSelectionMode(QAbstractItemView.NoSelection)
        self._token_audit_table.setAlternatingRowColors(False)
        self._token_audit_table.setShowGrid(False)
        self._token_audit_table.setFocusPolicy(Qt.NoFocus)
        self._token_audit_table.setWordWrap(False)
        self._token_audit_table.setCornerButtonEnabled(False)
        self._token_audit_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._token_audit_table.verticalHeader().setVisible(False)
        self._token_audit_table.verticalHeader().setDefaultSectionSize(46)
        table_header = self._token_audit_table.horizontalHeader()
        table_header.setStretchLastSection(False)
        table_header.setSectionResizeMode(0, QHeaderView.Stretch)
        table_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table_header.setSectionResizeMode(4, QHeaderView.Stretch)
        for column in range(self._token_audit_table.columnCount()):
            header_item = self._token_audit_table.horizontalHeaderItem(column)
            if header_item is not None:
                header_item.setTextAlignment(
                    Qt.AlignLeft | Qt.AlignVCenter
                    if column in {0, 4}
                    else Qt.AlignCenter
                )
        self._token_audit_table.setMinimumHeight(320)
        self._token_audit_table.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )
        issue_layout.addWidget(self._token_audit_table, 1)

        self._token_audit_empty = QLabel(
            "选择模板后，这里会显示 Token 与资料包的存在性对照。",
            self._token_issue_panel,
        )
        self._token_audit_empty.setObjectName("scn_token_audit_empty")
        self._token_audit_empty.setAlignment(Qt.AlignCenter)
        self._token_audit_empty.setWordWrap(True)
        issue_layout.addWidget(self._token_audit_empty, 1)
        self._card.add_widget(self._token_issue_panel)

    def _apply_theme(self) -> None:
        super()._apply_theme()
        if not hasattr(self, "_material_rule_selector"):
            return
        self._material_rule_selector.apply_theme()
        line_edits = [
            self._token_search,
            self._watermark_text,
            *(
                widget
                for widget in self._official_material_fields.values()
                if isinstance(widget, QLineEdit)
            ),
        ]
        _apply_template_line_edit_contract(*line_edits)
        _apply_template_button_contract(
            (self._token_source_action_btn, "secondary"),
            (self._token_refresh_btn, "secondary"),
        )
        if hasattr(self, "_official_material_status"):
            t = get_theme()
            self._token_source_label.setStyleSheet(
                f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_emphasis};"
                f"color: {t.text_primary};"
            )
            self._token_audit_empty.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
                f"padding: 16px;"
            )
            panel_style = (
                f"background: {t.bg_card}; border: 1px solid {t.border_light};"
                f"border-radius: {t.radius_sm}px;"
            )
            self._token_issue_panel.setStyleSheet(
                f"QFrame#scn_token_audit_issue_panel {{ {panel_style} }}"
            )
            self._token_audit_table.setStyleSheet(
                f"QTableWidget {{ background: {t.bg_card}; color: {t.text_primary};"
                "border: 0; outline: 0; }}"
                f"QTableWidget::item {{ padding: 0 10px;"
                f"border-bottom: 1px solid {t.border_light}; }}"
                f"QTableWidget::item:hover {{ background: {t.bg_hover}; }}"
                f"QHeaderView::section {{ background: {t.bg_hover};"
                f"color: {t.text_secondary}; border: 0;"
                f"border-bottom: 1px solid {t.border_light}; padding: 8px 10px;"
                f"font-weight: {t.font_weight_emphasis}; }}"
            )
            self._official_material_status.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
                f"background: {t.bg_selected}; border: 1px solid {t.border_light};"
                f"border-radius: {t.radius_sm}px; padding: 8px 10px;"
            )
            self._official_material_contract.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
            )
            self._official_material_batch_status.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
                f"background: {t.bg_selected}; border: 1px solid {t.border_light};"
                f"border-radius: {t.radius_sm}px; padding: 8px 10px;"
            )

    def _refresh_token_audit(self, *_args) -> None:
        if self._current_scene is None:
            return
        target = None
        if self._bridge is not None and hasattr(
            self._bridge,
            "current_execution_target",
        ):
            target = self._bridge.current_execution_target()
        self._token_audit_projection = build_scene_token_audit_projection(
            self._current_scene,
            target,
            self._official_material_context(),
        )
        self._render_token_audit_projection()

    def _render_token_audit_projection(self) -> None:
        projection = self._token_audit_projection
        source_path = str(projection.source_path or "").strip()
        source_name = projection.source_label or (
            Path(source_path).name if source_path else "未选择"
        )
        source_text = f"{projection.source_kind_label}：{source_name}"
        self._token_source_label.setText(source_text)
        self._token_source_label.setToolTip(source_path)

        issue_count = projection.error_count + projection.warning_count
        self._token_view_control.set_segment_text(0, f"不一致 {issue_count}")
        self._token_view_control.set_segment_text(
            1,
            f"全部 Token {len(projection.rows)}",
        )
        ready = projection.scan_status == "ready"
        if ready and not self._token_view_initialized:
            self._token_view_control.set_current_index(0 if issue_count else 1)
            self._token_view_initialized = True
        self._token_view_control.setEnabled(ready)
        self._token_search.setVisible(ready and bool(projection.rows))
        self._sync_token_source_action()
        self._refresh_token_audit_table()

    def _refresh_token_audit_table(self, *_args) -> None:
        if not hasattr(self, "_token_audit_table"):
            return
        search_text = self._token_search.text().strip().casefold()
        issues_only = self._token_view_control.current_data() != "all"
        visible_rows = [
            row
            for row in self._token_audit_projection.rows
            if (not search_text or search_text in row.searchable_text)
            and (not issues_only or row.has_issue)
        ]
        self._visible_token_audit_rows = visible_rows

        table = self._token_audit_table
        table.blockSignals(True)
        try:
            table.clearContents()
            table.setRowCount(len(visible_rows))
            theme = get_theme()
            for table_row, row in enumerate(visible_rows):
                template_text = (
                    f"{row.occurrence_count} 处"
                    if row.template_present
                    else "缺少"
                )
                package_text = "存在" if row.package_present else "缺少"
                content_text = row.content_text if row.package_present else "—"
                values = (
                    row.token,
                    template_text,
                    package_text,
                    f"● {row.status_label}",
                    content_text,
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(Qt.UserRole, row.row_id)
                    item.setToolTip(row.content_text if column == 4 else row.detail)
                    if column in {1, 2, 3}:
                        item.setTextAlignment(Qt.AlignCenter)
                    if column == 0:
                        token_font = item.font()
                        token_font.setFamily("Consolas")
                        item.setFont(token_font)
                    if column == 3:
                        tone = {
                            "ok": theme.success,
                            "warning": theme.warning,
                            "error": theme.error,
                        }.get(row.status, theme.text_secondary)
                        item.setForeground(QBrush(QColor(tone)))
                    elif column == 1 and not row.template_present:
                        item.setForeground(QBrush(QColor(theme.error)))
                    elif column == 2 and row.package_present is False:
                        item.setForeground(QBrush(QColor(theme.error)))
                    elif column == 4 and value in {"未填写", "—"}:
                        item.setForeground(QBrush(QColor(theme.text_hint)))
                    table.setItem(table_row, column, item)
        finally:
            table.blockSignals(False)

        has_rows = bool(visible_rows)
        table.setVisible(has_rows)
        projection = self._token_audit_projection
        if projection.scan_status != "ready":
            empty_text = projection.scan_message
        elif search_text:
            empty_text = "没有符合搜索条件的 Token。"
        elif issues_only and not (projection.error_count or projection.warning_count):
            empty_text = "没有不一致项，可切换到“全部 Token”查看。"
        elif projection.token_count == 0:
            empty_text = "模板中未发现可与资料包校验的 Token。"
        else:
            empty_text = "没有符合当前视图的 Token。"
        self._token_audit_empty.setText(empty_text)
        self._token_audit_empty.setVisible(not has_rows)

    def _force_refresh_token_audit(self) -> None:
        self._refresh_token_audit()

    def _sync_token_source_action(self) -> None:
        projection = self._token_audit_projection
        if projection.source_path:
            self._token_source_action_btn.setText("打开来源位置")
            self._token_source_action_btn.setVisible(True)
            return
        if projection.scan_status == "not_applicable":
            self._token_source_action_btn.setVisible(False)
            return
        if projection.source_kind == "unresolved_master":
            self._token_source_action_btn.setText("检查方案母版")
        else:
            self._token_source_action_btn.setText("去工作台选择文档")
        self._token_source_action_btn.setVisible(True)

    def _navigate_token_source_owner(self) -> None:
        projection = self._token_audit_projection
        source_path = str(projection.source_path or "").strip()
        if source_path:
            folder = Path(source_path).resolve().parent
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
                Toast.show_error("无法打开来源文档所在位置")
            return
        if self._bridge is None or not hasattr(self._bridge, "navigate_to_intent"):
            return
        if projection.source_kind == "unresolved_master":
            self._bridge.navigate_to_intent.emit(
                {"panel_id": "scene", "card_id": "scn_exam_paper"}
            )
            return
        self._bridge.navigate_to_intent.emit(
            {
                "panel_id": "workbench",
                "card_id": "quick_execute",
                "return_panel_id": "scene",
                "return_card_id": "scn_content",
            }
        )

    def _on_execution_target_changed(self, _target) -> None:
        self._refresh_token_audit()

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            profile = scene.input_source_profile
            _set_combo_by_data(self._markdown_policy, profile.markdown_policy)
            _set_combo_by_data(self._latex_policy, profile.latex_policy)
            self._require_material.setChecked(profile.require_material_package)
            self._material_rule_selector.set_scene(scene)
            _set_combo_by_data(self._input_failure, profile.failure_policy)
            self._watermark_enabled.setChecked(scene.watermark.enabled)
            self._watermark_text.setText(scene.watermark.text)
            self._sync_watermark_text_state()
            self._input_summary.set_items(build_input_profile_summary_items(scene))
            self._material_rule_selector.refresh_preview(scene)
            self._material_rule_selector.sync_actions()
            self._sync_official_material_section()
        finally:
            self._is_syncing = False
        self._refresh_token_audit()

    def focus_navigation_field(self, field_id: str) -> bool:
        target = str(field_id or "").strip()
        if not target:
            return False
        widget = self._schema_focus_widget(target)
        if widget is None:
            return False
        self._highlight_navigation_widget(widget, target)
        return True

    def _schema_focus_widget(self, field_id: str) -> QWidget | None:
        target = str(field_id or "").strip()
        widget = self._material_rule_selector.navigation_widget_for_field(target)
        if widget is not None:
            return widget
        if "." not in target:
            return self._material_schema_id
        return None

    def _on_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        profile = self._current_scene.input_source_profile
        profile.markdown_policy = str(
            self._markdown_policy.currentData() or profile.markdown_policy
        )
        profile.latex_policy = str(
            self._latex_policy.currentData() or profile.latex_policy
        )
        profile.require_material_package = self._require_material.isChecked()
        self._material_rule_selector.apply_to_profile(profile)
        profile.failure_policy = str(
            self._input_failure.currentData() or profile.failure_policy
        )
        self._current_scene.watermark.enabled = self._watermark_enabled.isChecked()
        self._current_scene.watermark.text = self._watermark_text.text().strip()
        self._sync_watermark_text_state()
        self._input_summary.set_items(
            build_input_profile_summary_items(self._current_scene)
        )
        self._material_rule_selector.refresh_preview(self._current_scene)
        self._material_rule_selector.sync_actions()
        self._token_audit_refresh_timer.start()
        self.scene_edited.emit()

    def _on_material_context_changed(self, _context) -> None:
        if self._current_scene is None:
            return
        self._token_audit_refresh_timer.start()
        if not _scene_uses_official_document_surface(self._current_scene):
            return
        self._official_material_commit_timer.stop()
        self._is_syncing = True
        try:
            self._sync_official_material_section()
        finally:
            self._is_syncing = False

    def _on_official_document_type_changed(self, document_type_id: str) -> None:
        if self._current_scene is None:
            return
        if not _scene_uses_official_document_surface(self._current_scene):
            return
        self._official_material_commit_timer.stop()
        self._is_syncing = True
        try:
            _set_combo_by_data(self._official_material_profile, document_type_id)
            self._sync_official_material_section()
        finally:
            self._is_syncing = False

    def _sync_official_material_section(self) -> None:
        is_official = _scene_uses_official_document_surface(self._current_scene)
        self._official_material_section.setVisible(is_official)
        if not is_official:
            return

        if self._sync_official_batch_editor():
            return

        context = self._official_material_context()
        entity_data = dict(getattr(context, "entity_data", {}) or {})
        profile_id = ""
        if self._bridge is not None and hasattr(
            self._bridge,
            "current_official_document_type_id",
        ):
            profile_id = str(
                self._bridge.current_official_document_type_id() or ""
            ).strip()
        profile_id = profile_id or self._official_scene_default_profile_id() or "notice"
        _set_combo_by_data(self._official_material_profile, profile_id)

        for field_id, widget in self._official_material_fields.items():
            value = str(entity_data.get(field_id, "") or "")
            if isinstance(widget, TextArea):
                widget.set_text(value)
            elif isinstance(widget, QLineEdit):
                widget.setText(value)
        self._refresh_official_material_contract()

    def _on_official_material_edited(self, *_args) -> None:
        self._schedule_official_material_commit()

    def _schedule_official_material_commit(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        if not _scene_uses_official_document_surface(self._current_scene):
            return
        self._refresh_official_material_contract()
        self._official_material_commit_timer.start()

    def _on_official_material_profile_changed(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        if not _scene_uses_official_document_surface(self._current_scene):
            return
        if self._bridge is not None and hasattr(
            self._bridge,
            "set_current_official_document_type_id",
        ):
            self._bridge.set_current_official_document_type_id(
                self._selected_official_material_profile_id()
            )
        self._official_material_commit_timer.stop()
        self._commit_official_material_edits()

    def _commit_official_material_edits(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        if not _scene_uses_official_document_surface(self._current_scene):
            return
        if self._selected_official_batch_profile_id():
            self._write_official_batch_profile()
            self._refresh_official_material_contract()
            return
        self._write_official_material_context()
        self._refresh_official_material_contract()

    def _on_official_material_group_toggled(
        self,
        group: str,
        checked: bool,
    ) -> None:
        normalized = str(group or "").strip()
        if checked:
            self._official_material_expanded_groups.add(normalized)
        else:
            self._official_material_expanded_groups.discard(normalized)
        self._refresh_official_material_contract()

    def _on_official_material_batch_selection_changed(self, selection) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        if not _scene_uses_official_document_surface(self._current_scene):
            return
        self._sync_official_batch_editor(selection)

    def _on_official_batch_profile_changed(self, *_args) -> None:
        if self._is_syncing:
            return
        self._load_selected_official_batch_profile()

    def _sync_official_batch_editor(self, selection=None) -> bool:
        if (
            selection is None
            and self._bridge is not None
            and hasattr(
                self._bridge,
                "current_material_batch_selection",
            )
        ):
            selection = self._bridge.current_material_batch_selection()
        source_kind = str(getattr(selection, "source_kind", "") or "").strip()
        profiles = list(
            getattr(getattr(selection, "archive", None), "profiles", []) or []
        )
        active = source_kind == "official_document_table" and bool(profiles)
        self._official_batch_profile_row.setVisible(active)
        if not active:
            self._official_batch_profile.clear()
            return False

        current = str(self._official_batch_profile.currentData() or "").strip()
        selected_ids = set(getattr(selection, "profile_ids", []) or [])
        previous = self._is_syncing
        self._is_syncing = True
        try:
            self._official_batch_profile.clear()
            for profile in profiles:
                if selected_ids and profile.profile_id not in selected_ids:
                    continue
                self._official_batch_profile.addItem(
                    profile.profile_name or profile.profile_id,
                    profile.profile_id,
                )
            target = current or str(self._official_batch_profile.itemData(0) or "")
            _set_combo_by_data(self._official_batch_profile, target)
        finally:
            self._is_syncing = previous
        self._load_selected_official_batch_profile(selection)
        return True

    def _load_selected_official_batch_profile(self, selection=None) -> None:
        profile_id = self._selected_official_batch_profile_id()
        if not profile_id:
            return
        if selection is None:
            selection = self._bridge.current_material_batch_selection()
        profile = selection.archive.get_profile(profile_id)
        if profile is None:
            return
        entity_data = dict(profile.fields or {})
        document_type = str(entity_data.get("document_type") or "notice").strip()
        previous = self._is_syncing
        self._is_syncing = True
        try:
            _set_combo_by_data(self._official_material_profile, document_type)
            for field_id, widget in self._official_material_fields.items():
                value = str(entity_data.get(field_id, "") or "")
                if isinstance(widget, TextArea):
                    widget.set_text(value)
                elif isinstance(widget, QLineEdit):
                    widget.setText(value)
        finally:
            self._is_syncing = previous
        self._refresh_official_material_contract()

    def _write_official_batch_profile(self) -> None:
        if self._bridge is None or not hasattr(
            self._bridge,
            "set_current_material_batch_selection",
        ):
            return
        profile_id = self._selected_official_batch_profile_id()
        if not profile_id:
            return
        selection = self._bridge.current_material_batch_selection()
        profile = selection.archive.get_profile(profile_id)
        if profile is None:
            return
        entity_data = dict(profile.fields or {})
        document_type = self._selected_official_material_profile_id()
        projection = build_official_material_form_projection(
            document_type,
            entity_data,
            expanded_groups=self._official_material_expanded_groups,
        )
        allowed_fields = set(projection.field_keys)
        for field_id, widget in self._official_material_fields.items():
            if field_id not in allowed_fields:
                continue
            if isinstance(widget, TextArea):
                value = widget.get_text().strip()
            elif isinstance(widget, QLineEdit):
                value = widget.text().strip()
            else:
                value = ""
            if value:
                entity_data[field_id] = value
                profile.field_sources[field_id] = "edited_official_batch"
            else:
                entity_data.pop(field_id, None)
        entity_data["document_type"] = document_type
        profile.fields = entity_data
        contract = get_official_document_assembly_contract(document_type)
        required = self._official_required_material_fields(contract)
        missing = [
            field_id
            for field_id in required
            if not str(entity_data.get(field_id, "") or "").strip()
        ]
        metadata = dict(selection.item_metadata.get(profile_id, {}) or {})
        metadata["official_profile_id"] = document_type
        metadata["import_status"] = "ok" if not missing else "missing_required_fields"
        metadata["missing_required_fields"] = missing
        metadata["edited_in_batch"] = True
        selection.item_metadata[profile_id] = metadata
        previous = self._is_syncing
        self._is_syncing = True
        try:
            self._bridge.set_current_material_batch_selection(selection)
        finally:
            self._is_syncing = previous

    def _write_official_material_context(self) -> None:
        if self._bridge is None or not hasattr(
            self._bridge, "set_current_material_context"
        ):
            return
        profile_id = self._selected_official_material_profile_id()
        context = self._official_material_context()
        entity_data = dict(getattr(context, "entity_data", {}) or {})
        projection = build_official_material_form_projection(
            profile_id,
            entity_data,
            expanded_groups=self._official_material_expanded_groups,
        )
        allowed_fields = set(projection.field_keys)
        for field_id, widget in self._official_material_fields.items():
            if field_id not in allowed_fields:
                continue
            if isinstance(widget, TextArea):
                value = widget.get_text().strip()
            elif isinstance(widget, QLineEdit):
                value = widget.text().strip()
            else:
                value = ""
            if value:
                entity_data[field_id] = value
            else:
                entity_data.pop(field_id, None)
        entity_data["document_type"] = profile_id
        context.mode_id = "official"
        context.scene_id = str(
            getattr(self._current_scene, "scene_id", "") or ""
        ).strip()
        context.profile_id = f"official:{profile_id}"
        context.profile_name = "公文资料"
        context.entity_data = entity_data
        self._bridge.set_current_material_context(context)

    def _load_official_material_batch(self, path: Path | str):
        set_selection = getattr(
            self._bridge,
            "set_current_material_batch_selection",
            None,
        )
        if not callable(set_selection):
            Toast.show_warning("当前页面没有连接批量资料上下文")
            return None
        try:
            result = load_official_document_material_batch(
                path,
            )
        except Exception as exc:
            Toast.show_error(f"批量导入公文资料失败: {exc}")
            return None

        if not result.ready:
            Toast.show_warning(f"公文批次未导入: {result.status}")
            return result

        set_selection(result.selection)
        total = len(result.items)
        invalid = result.invalid_count
        if invalid:
            status_text = f"已载入 {total} 份公文资料，{invalid} 份需补齐或修正"
            Toast.show_warning(status_text)
        else:
            status_text = f"已载入 {total} 份公文资料，可到工作台批量生成"
            Toast.show_success(status_text)
        self._official_material_batch_status.setText(status_text)
        self._official_material_batch_status.setVisible(True)
        return result

    def _load_official_material_package(self, path: Path | str):
        if self._bridge is None or not hasattr(
            self._bridge, "set_current_material_context"
        ):
            Toast.show_warning("当前页面没有连接资料包上下文")
            return None
        try:
            result = _load_official_material_source(
                path,
                profile_id=self._selected_official_material_profile_id(),
            )
        except Exception as exc:
            Toast.show_error(f"导入公文资料失败: {exc}")
            return None

        if result.status in {
            "missing_profile",
            "profile_conflict",
            "unknown_profile",
            "invalid_package",
            "invalid_table",
            "multiple_records",
        }:
            Toast.show_warning(f"公文资料未导入: {result.status}")
            return result

        self._bridge.set_current_material_context(result.context)
        self._is_syncing = True
        try:
            self._sync_official_material_section()
        finally:
            self._is_syncing = False
        if result.status == "missing_required_fields":
            Toast.show_warning(
                f"已导入公文资料包，仍缺少必填字段: "
                f"{self._official_material_field_list(result.missing_required_fields)}"
            )
        elif result.unknown_fields:
            Toast.show_warning(
                f"已导入公文资料，包含未识别字段: "
                f"{self._official_material_field_list(result.unknown_fields)}"
            )
        else:
            Toast.show_success(f"已导入公文资料: {Path(path).name}")
        return result

    def _export_official_material_package_to_path(self, path: Path | str):
        self._write_official_material_context()
        context = self._official_material_context()
        profile_id = self._selected_official_material_profile_id()
        try:
            result = export_official_document_material_package(
                context,
                path,
                profile_id=profile_id,
            )
        except Exception as exc:
            Toast.show_error(f"导出公文资料包失败: {exc}")
            return None
        if result.status == "missing_required_fields":
            Toast.show_warning(
                f"已导出公文资料包，但缺少必填字段: "
                f"{self._official_material_field_list(result.missing_required_fields)}"
            )
        elif result.status == "ok":
            Toast.show_success(f"已导出公文资料包: {Path(path).name}")
        else:
            Toast.show_warning(f"已导出公文资料包，状态: {result.status}")
        return result

    def _save_official_material_package_to_library_with_label(self, label: str):
        self._write_official_material_context()
        context = self._official_material_context()
        profile_id = self._selected_official_material_profile_id()
        try:
            result = export_official_document_material_package_to_user_library(
                context,
                label=label,
                profile_id=profile_id,
            )
        except Exception as exc:
            Toast.show_error(f"保存公文资料包失败: {exc}")
            return None
        if result.status == "missing_required_fields":
            Toast.show_warning(
                f"已保存公文资料包，但缺少必填字段: "
                f"{self._official_material_field_list(result.missing_required_fields)}"
            )
        elif result.status == "ok":
            Toast.show_success(
                f"已保存公文资料包: {Path(result.package_path or '').name}"
            )
        else:
            Toast.show_warning(f"已保存公文资料包，状态: {result.status}")
        return result

    def _refresh_official_material_contract(self) -> None:
        profile_id = self._selected_official_material_profile_id()
        contract = get_official_document_assembly_contract(profile_id)
        entity_data = self._current_official_material_editor_data()
        projection = build_official_material_form_projection(
            profile_id,
            entity_data,
            expanded_groups=self._official_material_expanded_groups,
        )
        projected_fields = {field.field_key: field for field in projection.fields}
        for field_id, row in self._official_material_rows.items():
            field = projected_fields.get(field_id)
            row.setVisible(bool(field and field.visible))
            if field is not None:
                row.set_label(field.label + (" *" if field.required else ""))

        optional_fields = [
            field
            for field in projection.fields
            if field.spec.group in {"routing", "closing"} and not field.required
        ]
        advanced_fields = [
            field
            for field in projection.fields
            if field.spec.group in {"imprint", "archive"}
        ]
        self._official_optional_fields_toggle.setVisible(bool(optional_fields))
        self._official_optional_fields_toggle.setText(
            "收起常用选填"
            if "optional" in self._official_material_expanded_groups
            else f"展开常用选填（{len(optional_fields)} 项）"
        )
        self._official_advanced_fields_toggle.setVisible(bool(advanced_fields))
        self._official_advanced_fields_toggle.setText(
            "收起版记与高级"
            if "advanced" in self._official_material_expanded_groups
            else f"展开版记与高级（{len(advanced_fields)} 项）"
        )
        self._official_material_contract_row.setVisible(
            "advanced" in self._official_material_expanded_groups
        )

        for field_id in ("meeting_date", "participants"):
            row = self._official_material_rows.get(field_id)
            if row is not None and field_id not in projected_fields:
                row.setVisible(False)

        missing = list(projection.missing_required_field_keys)
        filled_count = sum(1 for field in projection.fields if field.value.strip())
        if missing:
            self._official_material_status.setText(
                f"公文资料：已填 {filled_count} 项；缺少必填字段 "
                f"{self._official_material_field_list(missing)}。"
            )
        else:
            self._official_material_status.setText(
                f"公文资料：已填 {filled_count} 项；必填字段已齐。"
            )

        if contract is None:
            self._official_material_contract.setText("当前文种尚未登记资料契约。")
            return
        schema_text = "、".join(projection.schema_ids)
        mapping_pairs = [
            f"{field.label} -> {field.placeholder_id}" for field in projection.fields
        ]
        self._official_material_contract.setText(
            f"资料规则：{schema_text}；字段映射：{'；'.join(mapping_pairs)}"
        )

    def _selected_official_material_profile_id(self) -> str:
        return (
            str(self._official_material_profile.currentData() or "notice").strip()
            or "notice"
        )

    def _selected_official_batch_profile_id(self) -> str:
        if self._official_batch_profile_row.isHidden():
            return ""
        return str(self._official_batch_profile.currentData() or "").strip()

    def _current_official_material_editor_data(self) -> dict[str, object]:
        batch_profile_id = self._selected_official_batch_profile_id()
        if (
            batch_profile_id
            and self._bridge is not None
            and hasattr(
                self._bridge,
                "current_material_batch_selection",
            )
        ):
            selection = self._bridge.current_material_batch_selection()
            profile = selection.archive.get_profile(batch_profile_id)
            if profile is not None:
                values = dict(profile.fields or {})
            else:
                values = {}
        else:
            context = self._official_material_context()
            values = dict(getattr(context, "entity_data", {}) or {})
        for field_id, widget in self._official_material_fields.items():
            if isinstance(widget, TextArea):
                value = widget.get_text().strip()
            elif isinstance(widget, QLineEdit):
                value = widget.text().strip()
            else:
                value = ""
            if value:
                values[field_id] = value
            else:
                values.pop(field_id, None)
        return values

    def _official_scene_default_profile_id(self) -> str:
        raw_profile = str(
            getattr(self._current_scene, "default_material_profile_id", "") or ""
        ).strip()
        if ":" in raw_profile:
            _prefix, raw_profile = raw_profile.split(":", 1)
        return raw_profile.strip()

    def _official_material_context(self) -> MaterialExecutionContext:
        if self._bridge is not None and hasattr(
            self._bridge, "current_material_context"
        ):
            context = self._bridge.current_material_context()
            if isinstance(context, MaterialExecutionContext):
                return context
        return MaterialExecutionContext()

    def _official_required_material_fields(self, contract) -> tuple[str, ...]:
        if contract is None:
            return ()
        return build_official_material_form_projection(
            contract.profile_id,
        ).required_field_keys

    def _official_material_field_list(self, fields) -> str:
        values = [
            official_material_field_label(field)
            for field in fields or ()
            if str(field or "").strip()
        ]
        return "、".join(values)

    def _sync_watermark_text_state(self) -> None:
        if not hasattr(self, "_watermark_text"):
            return
        enabled = bool(self._watermark_enabled.isChecked())
        self._watermark_text.setEnabled(enabled)
        self._watermark_text.setToolTip(
            "水印启用后可编辑状态文本" if enabled else "启用水印后可编辑状态文本"
        )

    def _selected_registry_schema_id(self) -> str:
        return self._material_rule_selector.selected_schema_id()

    def _schema_ids_from_inputs(self) -> tuple[str, ...]:
        return self._material_rule_selector.schema_ids_from_inputs()

    def _suggest_unknown_schema_replacement(self, missing_ids: tuple[str, ...]) -> str:
        return self._material_rule_selector._suggest_unknown_schema_replacement(
            missing_ids
        )

    def _sync_schema_registry_actions(self) -> None:
        self._material_rule_selector.sync_actions()

    def _set_selected_schema_as_primary(self) -> None:
        self._material_rule_selector.set_selected_schema_as_primary()

    def _append_selected_schema(self) -> None:
        self._material_rule_selector.append_selected_schema()

    def _replace_unknown_schemas(self) -> None:
        self._material_rule_selector.replace_unrecognized_schemas()

    def _remove_unknown_schemas(self) -> None:
        self._material_rule_selector.remove_unrecognized_schemas()
