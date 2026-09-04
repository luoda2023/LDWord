"""Delivery/output configuration detail for the scene panel."""

from __future__ import annotations

import copy

from src.config.default_delivery_identity import project_default_delivery_identity
from src.config.delivery_preset_display import (
    delivery_preset_display_name,
    delivery_preset_option_tooltip,
)
from src.config.scene import DeliveryPreset, SceneWorkspace
from src.config.scene_family_application import (
    apply_planned_scene_family_defaults,
    has_planned_scene_family_application,
)
from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.summary_grid import SummaryGrid
from src.shared.ui.template_form_layout import TemplateFormStack, template_form_row
from src.shared.ui.text_area import TextArea
from src.shared.ui.theme import get_theme
from src.shared.ui.toggle_switch import ToggleSwitch
from src.ui.panels.scene_delivery_helpers import (
    _DELIVERY_PRESET_TEMPLATE_MAP,
    _VISIBILITY_ACTION_OPTIONS,
    _VISIBILITY_SELECTOR_RE,
    _append_visibility_rule_text,
    _apply_delivery_preset_template_artifacts,
    _build_delivery_preset_template_rules,
    _build_delivery_validation_items,
    _delivery_preset_template_label,
    _extract_visibility_selector_input,
    _format_visibility_rules,
    _mode_id_for_scene,
    _parse_visibility_rules,
    _populate_delivery_preset_template_combo,
    _populate_delivery_variable_combo,
    _populate_visibility_selector_combo,
    _safe_delivery_preset_id,
    _scene_compatible_template_ids,
    _scene_current_template_id,
    _scene_family_delivery_preview_tooltip,
    _template_display_label,
    _template_option_tooltip,
)
from src.ui.panels.scene_detail_base import _SimpleFormDetail
from src.ui.panels.scene_detail_support import (
    _apply_template_button_contract,
    _apply_template_line_edit_contract,
    _populate_combo,
    _set_combo_by_data,
)
from src.ui.panels.scene_product_summary_projection import (
    build_delivery_summary_items,
)
from src.config.scene_surface_registry import (
    scene_uses_official_document_surface as _scene_uses_official_document_surface,
)

class _OutputDetail(_SimpleFormDetail):
    """Detail pane for output toggles."""

    family_defaults_applied = Signal()

    def __init__(self, parent=None):
        super().__init__(
            "生成结果",
            "folder-output",
            "设置这个方案会生成哪些文件和交付版本。",
            parent,
        )
        self._current_scene: SceneWorkspace | None = None
        self._visibility_rule_text_cache: dict[str, str] = {}

        self._delivery_summary = SummaryGrid(columns=2, parent=self._card)
        self._card.add_widget(self._delivery_summary)

        self._delivery_validation_summary = SummaryGrid(columns=3, parent=self._card)
        self._card.add_widget(self._delivery_validation_summary)

        self._default_delivery = StyledComboBox(self)
        self._default_delivery.setObjectName("scn_output_default_delivery")
        self._default_delivery.currentIndexChanged.connect(self._on_edited)
        primary_rows = [
            template_form_row("默认交付", self._default_delivery, parent=self._card)
        ]
        advanced_rows: list[QWidget] = []

        self._preset_actions = QWidget(self)
        preset_actions_layout = QHBoxLayout(self._preset_actions)
        preset_actions_layout.setContentsMargins(0, 0, 0, 0)
        preset_actions_layout.setSpacing(8)
        self._add_preset_btn = QPushButton("新增版本", self._preset_actions)
        self._copy_preset_btn = QPushButton("复制版本", self._preset_actions)
        self._remove_preset_btn = QPushButton("移除版本", self._preset_actions)
        self._move_up_preset_btn = QPushButton("上移", self._preset_actions)
        self._move_down_preset_btn = QPushButton("下移", self._preset_actions)
        self._add_preset_btn.clicked.connect(self._add_delivery_preset)
        self._copy_preset_btn.clicked.connect(self._copy_delivery_preset)
        self._remove_preset_btn.clicked.connect(self._remove_delivery_preset)
        self._move_up_preset_btn.clicked.connect(lambda: self._move_delivery_preset(-1))
        self._move_down_preset_btn.clicked.connect(
            lambda: self._move_delivery_preset(1)
        )
        preset_actions_layout.addWidget(self._add_preset_btn)
        preset_actions_layout.addWidget(self._copy_preset_btn)
        preset_actions_layout.addWidget(self._remove_preset_btn)
        preset_actions_layout.addWidget(self._move_up_preset_btn)
        preset_actions_layout.addWidget(self._move_down_preset_btn)
        preset_actions_layout.addStretch(1)
        primary_rows.append(
            template_form_row("版本管理", self._preset_actions, parent=self._card)
        )

        self._preset_template_tools = QWidget(self)
        preset_template_layout = QHBoxLayout(self._preset_template_tools)
        preset_template_layout.setContentsMargins(0, 0, 0, 0)
        preset_template_layout.setSpacing(8)
        self._delivery_preset_template_combo = StyledComboBox(
            self._preset_template_tools
        )
        self._delivery_preset_template_combo.setObjectName(
            "scn_output_business_template"
        )
        _populate_delivery_preset_template_combo(self._delivery_preset_template_combo)
        self._add_preset_template_btn = QPushButton(
            "套用模板", self._preset_template_tools
        )
        self._add_preset_template_btn.setToolTip("按所选版本模板新增交付版本。")
        self._add_preset_template_btn.clicked.connect(
            self._add_delivery_preset_from_template
        )
        self._apply_family_delivery_btn = QPushButton(
            "应用推荐", self._preset_template_tools
        )
        self._apply_family_delivery_btn.setToolTip("按当前方案类型补齐推荐交付版本。")
        self._apply_family_delivery_btn.clicked.connect(
            self._apply_scene_family_defaults
        )
        preset_template_layout.addWidget(self._delivery_preset_template_combo, 1)
        preset_template_layout.addWidget(self._add_preset_template_btn)
        preset_template_layout.addWidget(self._apply_family_delivery_btn)
        primary_rows.append(
            template_form_row(
                "版本模板", self._preset_template_tools, parent=self._card
            )
        )

        self._delivery_preset_id = QLineEdit(self)
        self._delivery_preset_id.setObjectName("scn_output_preset_id")
        self._delivery_preset_id.setPlaceholderText("自动生成，可按需修改")
        self._delivery_preset_id.setToolTip(
            "用于文件命名和内部引用；例如 review_copy。"
        )
        self._delivery_preset_id.editingFinished.connect(self._on_preset_id_edited)
        advanced_rows.append(
            template_form_row("交付编号", self._delivery_preset_id, parent=self._card)
        )

        self._delivery_label = QLineEdit(self)
        self._delivery_label.setObjectName("scn_output_preset_label")
        self._delivery_label.setPlaceholderText("例如 Review copy")
        self._delivery_label.textChanged.connect(self._on_edited)
        primary_rows.append(
            template_form_row("交付名称", self._delivery_label, parent=self._card)
        )

        self._delivery_target_template = QLineEdit(self)
        self._delivery_target_template.setObjectName("scn_output_target_template")
        self._delivery_target_template.setPlaceholderText("留空则使用当前模板")
        self._delivery_target_template.textChanged.connect(self._on_edited)
        advanced_rows.append(
            template_form_row(
                "目标模板", self._delivery_target_template, parent=self._card
            )
        )

        self._delivery_target_template_combo = StyledComboBox(self)
        self._delivery_target_template_combo.setObjectName("scn_output_template_option")
        self._delivery_target_template_combo.currentIndexChanged.connect(
            self._on_target_template_combo_changed
        )
        advanced_rows.append(
            template_form_row(
                "模板选项", self._delivery_target_template_combo, parent=self._card
            )
        )

        self._delivery_output_dir = QLineEdit(self)
        self._delivery_output_dir.setObjectName("scn_output_dir_template")
        self._delivery_output_dir.setPlaceholderText(
            "默认放到当前文档旁的 output 文件夹"
        )
        self._delivery_output_dir.setToolTip("支持占位符，例如 {document_dir}/output。")
        self._delivery_output_dir.textChanged.connect(self._on_edited)
        advanced_rows.append(
            template_form_row("输出目录", self._delivery_output_dir, parent=self._card)
        )

        self._delivery_filename = QLineEdit(self)
        self._delivery_filename.setObjectName("scn_output_filename_template")
        self._delivery_filename.setPlaceholderText("默认使用原文件名加交付编号")
        self._delivery_filename.setToolTip("支持占位符，例如 {stem}_{preset_id}。")
        self._delivery_filename.textChanged.connect(self._on_edited)
        advanced_rows.append(
            template_form_row("文件命名", self._delivery_filename, parent=self._card)
        )

        self._delivery_variable_tools = QWidget(self)
        variable_tools_layout = QHBoxLayout(self._delivery_variable_tools)
        variable_tools_layout.setContentsMargins(0, 0, 0, 0)
        variable_tools_layout.setSpacing(8)
        self._delivery_variable_combo = StyledComboBox(self._delivery_variable_tools)
        self._delivery_variable_combo.setObjectName("scn_output_variable_combo")
        _populate_delivery_variable_combo(self._delivery_variable_combo)
        self._delivery_variable_combo.setToolTip("选择要插入到目录或文件名中的信息。")
        self._insert_output_variable_btn = QPushButton(
            "放入目录", self._delivery_variable_tools
        )
        self._insert_filename_variable_btn = QPushButton(
            "放入文件名", self._delivery_variable_tools
        )
        self._insert_output_variable_btn.clicked.connect(
            lambda: self._insert_delivery_variable(self._delivery_output_dir)
        )
        self._insert_filename_variable_btn.clicked.connect(
            lambda: self._insert_delivery_variable(self._delivery_filename)
        )
        variable_tools_layout.addWidget(self._delivery_variable_combo, 1)
        variable_tools_layout.addWidget(self._insert_output_variable_btn)
        variable_tools_layout.addWidget(self._insert_filename_variable_btn)
        advanced_rows.append(
            template_form_row(
                "命名信息", self._delivery_variable_tools, parent=self._card
            )
        )

        self._visibility_rule_tools = QWidget(self)
        visibility_rule_layout = QHBoxLayout(self._visibility_rule_tools)
        visibility_rule_layout.setContentsMargins(0, 0, 0, 0)
        visibility_rule_layout.setSpacing(8)
        self._visibility_selector_combo = StyledComboBox(self._visibility_rule_tools)
        self._visibility_selector_combo.setObjectName(
            "scn_output_visibility_selector_combo"
        )
        _populate_visibility_selector_combo(self._visibility_selector_combo)
        self._visibility_selector_combo.currentIndexChanged.connect(
            self._on_visibility_selector_combo_changed
        )
        self._visibility_selector_input = QLineEdit(self._visibility_rule_tools)
        self._visibility_selector_input.setObjectName("scn_output_visibility_selector")
        self._visibility_selector_input.setPlaceholderText("或输入自定义内容块名")
        self._visibility_selector_input.setToolTip(
            "可粘贴 {{#visibility:answer}}，保存时只记录内容块名 answer。"
        )
        self._visibility_action_combo = StyledComboBox(self._visibility_rule_tools)
        self._visibility_action_combo.setObjectName("scn_output_visibility_action")
        _populate_combo(self._visibility_action_combo, _VISIBILITY_ACTION_OPTIONS)
        self._insert_visibility_rule_btn = QPushButton(
            "添加到规则", self._visibility_rule_tools
        )
        self._insert_visibility_rule_btn.clicked.connect(self._insert_visibility_rule)
        visibility_rule_layout.addWidget(self._visibility_selector_combo, 1)
        visibility_rule_layout.addWidget(self._visibility_selector_input, 1)
        visibility_rule_layout.addWidget(self._visibility_action_combo)
        visibility_rule_layout.addWidget(self._insert_visibility_rule_btn)
        advanced_rows.append(
            template_form_row(
                "添加内容块", self._visibility_rule_tools, parent=self._card
            )
        )

        self._final_docx = ToggleSwitch(self, checked=True)
        self._final_docx.setObjectName("scn_output_final_docx")
        self._final_docx.toggled_signal.connect(self._on_edited)
        primary_rows.append(
            template_form_row("最终 Word", self._final_docx, parent=self._card)
        )

        self._review_pdf = ToggleSwitch(self, checked=False)
        self._review_pdf.setObjectName("scn_output_review_pdf")
        self._review_pdf.setToolTip(
            "从内部审阅稿生成 PDF；当前环境没有可用渲染器时保留正式 Word，并在执行结果中提示。"
        )
        self._review_pdf.toggled_signal.connect(self._on_edited)
        self._review_pdf_row = template_form_row(
            "审阅 PDF",
            self._review_pdf,
            parent=self._card,
        )
        primary_rows.append(self._review_pdf_row)

        self._compare_docx = ToggleSwitch(self, checked=True)
        self._compare_docx.setObjectName("scn_output_compare_docx")
        self._compare_docx.toggled_signal.connect(self._on_edited)
        primary_rows.append(
            template_form_row("对比 Word", self._compare_docx, parent=self._card)
        )

        self._report_json = ToggleSwitch(self, checked=True)
        self._report_json.setObjectName("scn_output_report_json")
        self._report_json.toggled_signal.connect(self._on_edited)
        advanced_rows.append(
            template_form_row("报告 JSON", self._report_json, parent=self._card)
        )

        self._report_md = ToggleSwitch(self, checked=True)
        self._report_md.setObjectName("scn_output_report_md")
        self._report_md.toggled_signal.connect(self._on_edited)
        advanced_rows.append(
            template_form_row("报告 Markdown", self._report_md, parent=self._card)
        )

        self._material_manifest = ToggleSwitch(self, checked=False)
        self._material_manifest.setObjectName("scn_output_material_manifest")
        self._material_manifest.toggled_signal.connect(self._on_edited)
        primary_rows.append(
            template_form_row("资料清单", self._material_manifest, parent=self._card)
        )

        self._material_package = ToggleSwitch(self, checked=False)
        self._material_package.setObjectName("scn_output_material_package")
        self._material_package.toggled_signal.connect(self._on_edited)
        primary_rows.append(
            template_form_row("资料包", self._material_package, parent=self._card)
        )

        self._visibility_rules = TextArea(
            placeholder="answer=remove\nanalysis=remove",
            min_height=88,
            max_height=150,
            parent=self._card,
        )
        self._visibility_rules.setObjectName("scn_output_visibility_rules")
        self._visibility_rules._text_edit.setObjectName(
            "scn_output_visibility_rules_text"
        )
        self._visibility_rules.setToolTip(
            "每行一条内容块规则，例如 answer=remove。建议先用上方控件添加。"
        )
        self._visibility_rules.text_changed.connect(self._on_visibility_rules_edited)
        advanced_rows.append(
            template_form_row("内容块规则", self._visibility_rules, parent=self._card)
        )

        self._add_form_stack(primary_rows)

        self._advanced_output_expanded = False
        self._advanced_output_header = QWidget(self._card)
        advanced_header_layout = QHBoxLayout(self._advanced_output_header)
        advanced_header_layout.setContentsMargins(0, 8, 0, 0)
        advanced_header_layout.setSpacing(8)
        self._advanced_output_title = QLabel(
            "高级命名、规则与报告", self._advanced_output_header
        )
        self._advanced_output_title.setObjectName("scn_output_advanced_title")
        self._advanced_output_toggle_btn = QPushButton(
            "展开", self._advanced_output_header
        )
        self._advanced_output_toggle_btn.clicked.connect(self._toggle_advanced_output)
        advanced_header_layout.addWidget(self._advanced_output_title)
        advanced_header_layout.addStretch(1)
        advanced_header_layout.addWidget(self._advanced_output_toggle_btn)
        self._card.add_widget(self._advanced_output_header)

        self._advanced_output_container = QWidget(self._card)
        advanced_output_layout = QVBoxLayout(self._advanced_output_container)
        advanced_output_layout.setContentsMargins(0, 0, 0, 0)
        advanced_output_layout.setSpacing(0)
        advanced_output_layout.addWidget(
            TemplateFormStack(advanced_rows, parent=self._advanced_output_container)
        )
        self._card.add_widget(self._advanced_output_container)
        self._sync_advanced_output_visibility()
        self._apply_theme()

    def _apply_theme(self) -> None:
        super()._apply_theme()
        if not hasattr(self, "_delivery_preset_id"):
            return
        _apply_template_line_edit_contract(
            self._delivery_preset_id,
            self._delivery_label,
            self._delivery_target_template,
            self._delivery_output_dir,
            self._delivery_filename,
            self._visibility_selector_input,
        )
        _apply_template_button_contract(
            (self._add_preset_btn, "secondary"),
            (self._copy_preset_btn, "secondary"),
            (self._remove_preset_btn, "ghost-danger"),
            (self._move_up_preset_btn, "secondary"),
            (self._move_down_preset_btn, "secondary"),
            (self._add_preset_template_btn, "secondary"),
            (self._apply_family_delivery_btn, "secondary"),
            (self._insert_output_variable_btn, "secondary"),
            (self._insert_filename_variable_btn, "secondary"),
            (self._insert_visibility_rule_btn, "secondary"),
            (self._advanced_output_toggle_btn, "secondary"),
        )
        self._advanced_output_title.setStyleSheet(
            f"font-size: {get_theme().font_size_sm}px; "
            f"font-weight: {get_theme().font_weight_emphasis}; "
            f"color: {get_theme().text_primary};"
        )

    def _toggle_advanced_output(self) -> None:
        self._advanced_output_expanded = not self._advanced_output_expanded
        self._sync_advanced_output_visibility()

    def _sync_advanced_output_visibility(self) -> None:
        if not hasattr(self, "_advanced_output_container"):
            return
        self._advanced_output_container.setVisible(self._advanced_output_expanded)
        self._advanced_output_toggle_btn.setText(
            "收起" if self._advanced_output_expanded else "展开"
        )

    def focus_navigation_field(self, field_id: str) -> bool:
        target = str(field_id or "").strip()
        if not target:
            return False
        delivery_ids = {
            str(self._default_delivery.itemData(index) or "").strip()
            for index in range(self._default_delivery.count())
        }
        if target in delivery_ids:
            _set_combo_by_data(self._default_delivery, target)
            self._highlight_navigation_widget(self._default_delivery, target)
            return True

        mapping: dict[str, QWidget] = {
            "default_delivery": self._default_delivery,
            "preset_id": self._delivery_preset_id,
            "preset_label": self._delivery_label,
            "label": self._delivery_label,
            "target_template": self._delivery_target_template,
            "target_template_id": self._delivery_target_template,
            "template_options": self._delivery_target_template_combo,
            "output_dir": self._delivery_output_dir,
            "output_dir_template": self._delivery_output_dir,
            "filename": self._delivery_filename,
            "filename_template": self._delivery_filename,
            "visibility_selector_options": self._visibility_selector_combo,
            "visibility_selector": self._visibility_selector_input,
            "visibility_rules": self._visibility_rules,
            "final_docx": self._final_docx,
            "review_pdf": self._review_pdf,
            "compare_docx": self._compare_docx,
            "report_json": self._report_json,
            "report_markdown": self._report_md,
            "report_md": self._report_md,
            "material_manifest": self._material_manifest,
            "material_package": self._material_package,
        }
        widget = mapping.get(target)
        if widget is None:
            widget = self._default_delivery
        if widget in {
            self._delivery_preset_id,
            self._delivery_target_template,
            self._delivery_target_template_combo,
            self._delivery_output_dir,
            self._delivery_filename,
            self._visibility_selector_combo,
            self._visibility_selector_input,
            self._visibility_rules,
            self._report_json,
            self._report_md,
        }:
            self._advanced_output_expanded = True
            self._sync_advanced_output_visibility()
        self._highlight_navigation_widget(widget, target)
        return True

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            self._populate_delivery_combo(scene.default_delivery_preset_id)
            self._sync_delivery_fields()
            self._sync_output_toggles()
            self._review_pdf_row.setVisible(
                _scene_uses_official_document_surface(scene)
            )
            self._sync_visibility_rules()
            self._delivery_summary.set_items(build_delivery_summary_items(scene))
            self._sync_delivery_validation_summary()
            self._sync_preset_action_buttons()
        finally:
            if self._default_delivery.signalsBlocked():
                self._default_delivery.blockSignals(False)
            self._is_syncing = False

    def _on_edited(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        selected_id = str(self._default_delivery.currentData() or "")
        if (
            selected_id
            and selected_id != self._current_scene.default_delivery_preset_id
        ):
            self._current_scene.default_delivery_preset_id = selected_id
            self._populate_delivery_combo(selected_id)
            preset = self._selected_delivery_preset()
            if preset is not None:
                self._sync_delivery_fields()
                self._sync_output_toggles()
                self._sync_visibility_rules()
                self._delivery_summary.set_items(
                    build_delivery_summary_items(self._current_scene)
                )
                self._sync_delivery_validation_summary()
                self._sync_preset_action_buttons()
                self.scene_edited.emit()
                return

        preset = self._selected_delivery_preset()
        if preset is None:
            return
        artifacts = preset.artifacts
        artifacts.final_docx = self._final_docx.isChecked()
        artifacts.review_pdf = self._review_pdf.isChecked()
        artifacts.compare_docx = self._compare_docx.isChecked()
        artifacts.report_json = self._report_json.isChecked()
        artifacts.report_markdown = self._report_md.isChecked()
        artifacts.material_manifest = (
            self._material_manifest.isChecked()
        )
        artifacts.material_package = self._material_package.isChecked()
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        if preset_id:
            self._visibility_rule_text_cache[preset_id] = (
                self._visibility_rules.get_text()
            )
        preset.label = self._delivery_label.text().strip() or str(
            preset.preset_id or ""
        )
        preset.target_template_id = self._delivery_target_template.text().strip()
        self._populate_target_template_combo(preset.target_template_id)
        preset.output_dir_template = (
            self._delivery_output_dir.text().strip() or "{document_dir}/output"
        )
        preset.filename_template = (
            self._delivery_filename.text().strip() or "{stem}_{preset_id}"
        )
        preset.content_visibility_rules = _parse_visibility_rules(
            self._visibility_rules.get_text()
        )
        self._refresh_selected_delivery_label(preset)
        self._delivery_summary.set_items(
            build_delivery_summary_items(self._current_scene)
        )
        self._sync_delivery_validation_summary()
        self._sync_preset_action_buttons()
        self.scene_edited.emit()

    def _on_target_template_combo_changed(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        target_id = str(
            self._delivery_target_template_combo.currentData() or ""
        ).strip()
        self._set_line_text(self._delivery_target_template, target_id)
        self._on_edited()

    def _on_visibility_selector_combo_changed(self, *_args) -> None:
        selector = str(self._visibility_selector_combo.currentData() or "").strip()
        if selector:
            self._visibility_selector_input.setText(selector)

    def _on_visibility_rules_edited(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        preset = self._selected_delivery_preset()
        if preset is not None:
            preset_id = str(getattr(preset, "preset_id", "") or "").strip()
            if preset_id:
                self._visibility_rule_text_cache[preset_id] = (
                    self._visibility_rules.get_text()
                )
            preset.content_visibility_rules = _parse_visibility_rules(
                self._visibility_rules.get_text()
            )
        self._delivery_summary.set_items(
            build_delivery_summary_items(self._current_scene)
        )
        self._sync_delivery_validation_summary()
        self.scene_edited.emit()

    def _on_preset_id_edited(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        preset = self._selected_delivery_preset()
        if preset is None:
            return
        old_id = str(getattr(preset, "preset_id", "") or "").strip()
        requested_id = _safe_delivery_preset_id(self._delivery_preset_id.text())
        new_id = self._unique_delivery_preset_id(requested_id, exclude_preset=preset)
        if new_id != old_id:
            preset.preset_id = new_id
            self._current_scene.default_delivery_preset_id = new_id
            if old_id in self._visibility_rule_text_cache:
                self._visibility_rule_text_cache[new_id] = (
                    self._visibility_rule_text_cache.pop(old_id)
                )
        self._is_syncing = True
        try:
            self._set_line_text(self._delivery_preset_id, new_id)
            self._populate_delivery_combo(new_id)
            self._delivery_summary.set_items(
                build_delivery_summary_items(self._current_scene)
            )
            self._sync_delivery_validation_summary()
            self._sync_preset_action_buttons()
        finally:
            self._is_syncing = False
        self.scene_edited.emit()

    def _selected_delivery_preset(self):
        if self._current_scene is None:
            return None
        return project_default_delivery_identity(self._current_scene).preset

    def _populate_delivery_combo(self, selected_id: str = "") -> None:
        if self._current_scene is None:
            return
        identity = project_default_delivery_identity(self._current_scene)
        self._default_delivery.blockSignals(True)
        try:
            self._default_delivery.clear()
            if not identity.is_ok:
                placeholder = (
                    f"无效引用：{identity.requested_id}"
                    if identity.status == "invalid"
                    else "未设置默认交付"
                )
                self._default_delivery.addItem(placeholder, "")
                self._default_delivery.setItemData(
                    0,
                    (
                        "默认交付引用无效；请选择一个有效输出版本。"
                        if identity.status == "invalid"
                        else "尚未设置默认交付；请选择一个有效输出版本。"
                    ),
                    Qt.ToolTipRole,
                )
            for preset in self._current_scene.delivery_presets:
                preset_id = str(getattr(preset, "preset_id", "") or "").strip()
                if not preset_id:
                    continue
                self._default_delivery.addItem(
                    delivery_preset_display_name(preset),
                    preset_id,
                )
                self._default_delivery.setItemData(
                    self._default_delivery.count() - 1,
                    delivery_preset_option_tooltip(preset),
                    Qt.ToolTipRole,
                )
            if identity.is_ok:
                _set_combo_by_data(
                    self._default_delivery,
                    selected_id or identity.requested_id,
                )
            elif self._default_delivery.count():
                self._default_delivery.setCurrentIndex(0)
            self._default_delivery.setProperty(
                "deliveryIdentityStatus",
                identity.status,
            )
        finally:
            self._default_delivery.blockSignals(False)

    def _populate_target_template_combo(self, selected_id: str = "") -> None:
        if self._current_scene is None:
            return
        selected = str(selected_id or "").strip()
        self._delivery_target_template_combo.blockSignals(True)
        try:
            self._delivery_target_template_combo.clear()
            mode_id = _mode_id_for_scene(self._current_scene)
            current_id = _scene_current_template_id(self._current_scene)
            current_label = (
                _template_display_label(
                    current_id,
                    mode_id=mode_id,
                )
                if current_id
                else "当前模板"
            )
            self._delivery_target_template_combo.addItem(
                f"跟随当前模板 - {current_label}", ""
            )
            self._delivery_target_template_combo.setItemData(
                0,
                _template_option_tooltip(
                    current_id,
                    mode_id=mode_id,
                ),
                Qt.ToolTipRole,
            )
            for template_id in _scene_compatible_template_ids(self._current_scene):
                self._delivery_target_template_combo.addItem(
                    _template_display_label(
                        template_id,
                        mode_id=mode_id,
                    ),
                    template_id,
                )
                self._delivery_target_template_combo.setItemData(
                    self._delivery_target_template_combo.count() - 1,
                    _template_option_tooltip(
                        template_id,
                        mode_id=mode_id,
                    ),
                    Qt.ToolTipRole,
                )
            if selected and self._delivery_target_template_combo.findData(selected) < 0:
                custom_label = _template_display_label(
                    selected,
                    mode_id=mode_id,
                )
                self._delivery_target_template_combo.addItem(
                    f"自定义模板 - {custom_label}"
                    if custom_label != selected
                    else "自定义模板",
                    selected,
                )
                self._delivery_target_template_combo.setItemData(
                    self._delivery_target_template_combo.count() - 1,
                    _template_option_tooltip(
                        selected,
                        mode_id=mode_id,
                    ),
                    Qt.ToolTipRole,
                )
            _set_combo_by_data(self._delivery_target_template_combo, selected)
        finally:
            self._delivery_target_template_combo.blockSignals(False)

    def _add_delivery_preset(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        preset_id = self._unique_delivery_preset_id("delivery")
        current = self._selected_delivery_preset()
        assert current is not None
        preset = DeliveryPreset(
            preset_id=preset_id,
            label=f"交付 {len(self._current_scene.delivery_presets) + 1}",
            output_dir_template="{preset_id}",
            filename_template="{stem}_{preset_id}",
            artifacts=copy.deepcopy(current.artifacts),
        )
        self._current_scene.delivery_presets.append(preset)
        self._select_delivery_preset(preset_id)

    def _add_delivery_preset_from_template(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        template_id = str(
            self._delivery_preset_template_combo.currentData() or ""
        ).strip()
        spec = _DELIVERY_PRESET_TEMPLATE_MAP.get(template_id)
        if spec is None:
            return
        preset_id = self._unique_delivery_preset_id(
            str(spec.get("preset_id", "") or "delivery")
        )
        current = self._selected_delivery_preset()
        assert current is not None
        base_artifacts = copy.deepcopy(current.artifacts)
        artifacts = _apply_delivery_preset_template_artifacts(base_artifacts, spec)
        preset = DeliveryPreset(
            preset_id=preset_id,
            label=_delivery_preset_template_label(spec, preset_id),
            target_template_id=str(spec.get("target_template_id", "") or ""),
            output_dir_template=str(
                spec.get("output_dir_template", "") or "{preset_id}"
            ),
            filename_template=str(
                spec.get("filename_template", "") or "{stem}_{preset_id}"
            ),
            artifacts=artifacts,
            content_visibility_rules=_build_delivery_preset_template_rules(spec),
            include_structured_intermediate=bool(
                spec.get("include_structured_intermediate", False)
            ),
            report_level=str(spec.get("report_level", "") or "summary"),
        )
        self._current_scene.delivery_presets.append(preset)
        self._select_delivery_preset(preset_id)

    def _apply_scene_family_defaults(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        result = apply_planned_scene_family_defaults(self._current_scene)
        if not result.applied:
            self._sync_preset_action_buttons()
            return
        self._select_delivery_preset(result.default_delivery_preset_id)
        self.family_defaults_applied.emit()

    def _copy_delivery_preset(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        current = self._selected_delivery_preset()
        if current is None:
            return
        preset = copy.deepcopy(current)
        preset_id = str(getattr(current, "preset_id", "") or "delivery").strip()
        preset.preset_id = self._unique_delivery_preset_id(f"{preset_id}_copy")
        preset.label = f"{getattr(current, 'label', '') or preset_id} Copy"
        self._current_scene.delivery_presets.append(preset)
        self._select_delivery_preset(preset.preset_id)

    def _remove_delivery_preset(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        presets = list(self._current_scene.delivery_presets or [])
        if len(presets) <= 1:
            return
        selected_id = str(self._current_scene.default_delivery_preset_id or "").strip()
        selected_index = next(
            (
                index
                for index, preset in enumerate(presets)
                if str(getattr(preset, "preset_id", "") or "").strip() == selected_id
            ),
            0,
        )
        kept = [
            preset
            for preset in presets
            if str(getattr(preset, "preset_id", "") or "").strip() != selected_id
        ]
        if selected_id:
            self._visibility_rule_text_cache.pop(selected_id, None)
        self._current_scene.delivery_presets = kept
        next_index = min(selected_index, len(kept) - 1)
        next_id = str(getattr(kept[next_index], "preset_id", "") or "final").strip()
        self._select_delivery_preset(next_id)

    def _move_delivery_preset(self, offset: int) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        presets = list(self._current_scene.delivery_presets or [])
        selected_index = self._selected_delivery_preset_index()
        if selected_index < 0:
            return
        next_index = selected_index + int(offset)
        if next_index < 0 or next_index >= len(presets):
            self._sync_preset_action_buttons()
            return
        presets[selected_index], presets[next_index] = (
            presets[next_index],
            presets[selected_index],
        )
        self._current_scene.delivery_presets = presets
        selected_id = str(self._current_scene.default_delivery_preset_id or "").strip()
        self._is_syncing = True
        try:
            self._populate_delivery_combo(selected_id)
            self._delivery_summary.set_items(
                build_delivery_summary_items(self._current_scene)
            )
            self._sync_delivery_validation_summary()
            self._sync_preset_action_buttons()
        finally:
            self._is_syncing = False
        self.scene_edited.emit()

    def _select_delivery_preset(self, preset_id: str) -> None:
        if self._current_scene is None:
            return
        self._current_scene.default_delivery_preset_id = str(preset_id or "").strip()
        self._is_syncing = True
        try:
            self._populate_delivery_combo(
                self._current_scene.default_delivery_preset_id
            )
            self._sync_delivery_fields()
            self._sync_output_toggles()
            self._sync_visibility_rules()
            self._delivery_summary.set_items(
                build_delivery_summary_items(self._current_scene)
            )
            self._sync_delivery_validation_summary()
            self._sync_preset_action_buttons()
        finally:
            self._is_syncing = False
        self.scene_edited.emit()

    def _selected_delivery_preset_index(self) -> int:
        if self._current_scene is None:
            return -1
        selected_id = str(self._current_scene.default_delivery_preset_id or "").strip()
        return next(
            (
                index
                for index, preset in enumerate(
                    self._current_scene.delivery_presets or []
                )
                if str(getattr(preset, "preset_id", "") or "").strip() == selected_id
            ),
            -1,
        )

    def _unique_delivery_preset_id(self, base: str, *, exclude_preset=None) -> str:
        existing = {
            str(getattr(preset, "preset_id", "") or "").strip()
            for preset in list(
                getattr(self._current_scene, "delivery_presets", []) or []
            )
            if preset is not exclude_preset
        }
        root = _safe_delivery_preset_id(base)
        candidate = root
        index = 2
        while candidate in existing:
            candidate = f"{root}_{index}"
            index += 1
        return candidate

    def _sync_preset_action_buttons(self) -> None:
        has_scene = self._current_scene is not None
        preset_count = (
            len(list(getattr(self._current_scene, "delivery_presets", []) or []))
            if has_scene
            else 0
        )
        has_selected_preset = has_scene and self._selected_delivery_preset() is not None
        can_edit = bool(has_scene and has_selected_preset)
        self._default_delivery.setEnabled(has_scene and preset_count >= 1)
        self._add_preset_btn.setEnabled(can_edit)
        self._add_preset_template_btn.setEnabled(can_edit)
        self._delivery_preset_template_combo.setEnabled(can_edit)
        can_apply_family_delivery = can_edit and has_planned_scene_family_application(
            self._current_scene
        )
        self._apply_family_delivery_btn.setEnabled(can_apply_family_delivery)
        self._apply_family_delivery_btn.setToolTip(
            _scene_family_delivery_preview_tooltip(
                self._current_scene if has_scene else None
            )
        )
        self._copy_preset_btn.setEnabled(can_edit)
        self._remove_preset_btn.setEnabled(can_edit and preset_count > 1)
        self._insert_visibility_rule_btn.setEnabled(can_edit)
        selected_index = self._selected_delivery_preset_index() if has_scene else -1
        self._move_up_preset_btn.setEnabled(selected_index > 0)
        self._move_down_preset_btn.setEnabled(
            selected_index >= 0 and selected_index < preset_count - 1
        )

    def _sync_output_toggles(self) -> None:
        if self._current_scene is None:
            return
        preset = self._selected_delivery_preset()
        artifacts = getattr(preset, "artifacts", None)
        was_syncing = self._is_syncing
        self._is_syncing = True
        try:
            self._final_docx.setChecked(bool(getattr(artifacts, "final_docx", False)))
            self._review_pdf.setChecked(
                bool(getattr(artifacts, "review_pdf", False))
            )
            self._compare_docx.setChecked(bool(getattr(artifacts, "compare_docx", False)))
            self._report_json.setChecked(bool(getattr(artifacts, "report_json", False)))
            self._report_md.setChecked(
                bool(getattr(artifacts, "report_markdown", False))
            )
            self._material_manifest.setChecked(
                bool(getattr(artifacts, "material_manifest", False))
            )
            self._material_package.setChecked(
                bool(getattr(artifacts, "material_package", False))
            )
        finally:
            self._is_syncing = was_syncing

    def _insert_delivery_variable(self, line_edit: QLineEdit) -> None:
        variable = str(self._delivery_variable_combo.currentData() or "").strip()
        if not variable:
            return
        line_edit.insert(f"{{{variable}}}")
        line_edit.setFocus()

    def _insert_visibility_rule(self) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        selector_source = self._visibility_selector_input.text().strip()
        if not selector_source:
            selector_source = str(
                self._visibility_selector_combo.currentData() or ""
            ).strip()
        selector = _extract_visibility_selector_input(selector_source)
        if not selector or not _VISIBILITY_SELECTOR_RE.match(selector):
            self._visibility_selector_input.setFocus()
            self._visibility_selector_input.selectAll()
            return
        action = str(self._visibility_action_combo.currentData() or "remove")
        current_text = self._visibility_rules.get_text()
        next_text = _append_visibility_rule_text(current_text, selector, action)
        if next_text == current_text:
            self._visibility_selector_input.setFocus()
            self._visibility_selector_input.selectAll()
            return
        self._set_visibility_rules_text(next_text)
        self._visibility_selector_input.clear()
        _set_combo_by_data(self._visibility_selector_combo, "")
        self._on_visibility_rules_edited()

    def _sync_delivery_validation_summary(self) -> None:
        preset = self._selected_delivery_preset()
        self._delivery_validation_summary.set_items(
            _build_delivery_validation_items(
                preset,
                scene=self._current_scene,
                output_template=self._delivery_output_dir.text(),
                filename_template=self._delivery_filename.text(),
                visibility_text=self._visibility_rules.get_text(),
            )
        )

    def _sync_delivery_fields(self) -> None:
        preset = self._selected_delivery_preset()
        self._sync_delivery_editability(preset is not None)
        if preset is None:
            self._set_line_text(self._delivery_preset_id, "")
            self._set_line_text(self._delivery_label, "")
            self._set_line_text(self._delivery_target_template, "")
            self._populate_target_template_combo("")
            self._set_line_text(self._delivery_output_dir, "")
            self._set_line_text(self._delivery_filename, "")
            return
        self._set_line_text(
            self._delivery_preset_id,
            str(getattr(preset, "preset_id", "") or ""),
        )
        self._set_line_text(
            self._delivery_label,
            delivery_preset_display_name(preset),
        )
        self._set_line_text(
            self._delivery_target_template,
            str(getattr(preset, "target_template_id", "") or ""),
        )
        self._populate_target_template_combo(
            str(getattr(preset, "target_template_id", "") or "")
        )
        self._set_line_text(
            self._delivery_output_dir,
            str(getattr(preset, "output_dir_template", "") or "{document_dir}/output"),
        )
        self._set_line_text(
            self._delivery_filename,
            str(getattr(preset, "filename_template", "") or "{stem}_{preset_id}"),
        )

    def _sync_delivery_editability(self, enabled: bool) -> None:
        for widget in (
            self._delivery_preset_id,
            self._delivery_label,
            self._delivery_target_template,
            self._delivery_target_template_combo,
            self._delivery_output_dir,
            self._delivery_filename,
            self._delivery_variable_combo,
            self._insert_output_variable_btn,
            self._insert_filename_variable_btn,
            self._visibility_selector_combo,
            self._visibility_selector_input,
            self._visibility_action_combo,
            self._visibility_rules,
            self._final_docx,
            self._review_pdf,
            self._compare_docx,
            self._report_json,
            self._report_md,
            self._material_manifest,
            self._material_package,
        ):
            widget.setEnabled(enabled)

    def _set_line_text(self, line_edit: QLineEdit, text: str) -> None:
        line_edit.blockSignals(True)
        try:
            line_edit.setText(text)
        finally:
            line_edit.blockSignals(False)

    def _refresh_selected_delivery_label(self, preset) -> None:
        current_index = self._default_delivery.currentIndex()
        if current_index < 0:
            return
        preset_id = str(getattr(preset, "preset_id", "") or "").strip()
        selected_id = str(self._default_delivery.itemData(current_index) or "").strip()
        if preset_id and selected_id != preset_id:
            return
        self._default_delivery.setItemText(
            current_index,
            delivery_preset_display_name(preset),
        )
        self._default_delivery.setItemData(
            current_index,
            delivery_preset_option_tooltip(preset),
            Qt.ToolTipRole,
        )

    def _sync_visibility_rules(self) -> None:
        preset = self._selected_delivery_preset()
        preset_id = (
            str(getattr(preset, "preset_id", "") or "").strip() if preset else ""
        )
        cached_text = self._visibility_rule_text_cache.get(preset_id)
        self._set_visibility_rules_text(
            cached_text
            if cached_text is not None
            else _format_visibility_rules(
                getattr(preset, "content_visibility_rules", [])
            )
        )

    def _set_visibility_rules_text(self, text: str) -> None:
        self._visibility_rules.blockSignals(True)
        try:
            self._visibility_rules.set_text(text)
        finally:
            self._visibility_rules.blockSignals(False)
