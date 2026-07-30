"""Presenter mixin for building the profile and field editor card."""

from __future__ import annotations

from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.template_form_layout import template_form_row
from src.shared.ui.text_area import TextArea
from src.shared.ui.token_column_guide import TokenColumnGuide
from src.shared.ui.token_section_header import TokenSectionHeader
from src.ui.panels.assets.layout_helpers import _chunk_form_rows


class ProfileEditorPresenterMixin:
    """Build the retained local profile and field editor card."""

    def _setup_profile_editor_card(self) -> None:
        profile_card = Card(parent=self._section_contents["fields"])
        self._profile_card = profile_card
        profile_card.set_header("字段资料", icon_name="type")
        self._profile_id_edit = QLineEdit(profile_card)
        self._profile_name_edit = QLineEdit(profile_card)
        self._profile_id_edit.setVisible(False)
        self._profile_id_edit.setPlaceholderText("这一份编号")
        self._profile_name_edit.setPlaceholderText("例如：项目 A / 第一份")
        self._profile_id_edit.textChanged.connect(
            lambda *_: self._schedule_summary_refresh()
        )
        self._profile_name_edit.textChanged.connect(
            lambda *_: self._schedule_summary_refresh()
        )

        profile_form = InspectorForm(parent=profile_card)
        self._profile_form = profile_form
        self._profile_name_row = template_form_row(
            "这一份名称",
            self._profile_name_edit,
            parent=profile_form,
        )
        field_rows = [self._profile_name_row]

        self._fields_edit = TextArea(
            placeholder="其他资料仍可用 key=value，例如：\ncustom_field=自定义内容",
            min_height=120,
            max_height=220,
            parent=profile_card,
        )
        self._fields_edit.text_changed.connect(self._on_more_fields_changed)
        # Kept as a hidden compatibility buffer for old imports. New fields use
        # the exact-key rows below instead of a free-form key=value textarea.
        self._fields_edit.setVisible(False)
        profile_form.add_grid(_chunk_form_rows(field_rows, columns=1))
        profile_card.add_widget(profile_form)
        self._fields_hint_label = QLabel(profile_card)
        self._fields_hint_label.setWordWrap(True)
        self._fields_hint_label.setVisible(False)
        profile_card.add_widget(self._fields_hint_label)
        self._field_mapping_example = QLabel(
            "样例：Word 中写 {{@text:公司名称}}，这里只编辑“公司名称”。",
            profile_card,
        )
        self._field_mapping_example.setObjectName("material_field_mapping_example")
        self._field_mapping_example.setWordWrap(True)
        profile_card.add_widget(self._field_mapping_example)
        field_toolbar = QWidget(profile_card)
        self._field_toolbar = field_toolbar
        field_toolbar_layout = QHBoxLayout(field_toolbar)
        field_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        field_toolbar_layout.setSpacing(8)
        self._template_fields_title = QLabel("资料字段", field_toolbar)
        self._add_material_field_btn = QPushButton("添加字段", field_toolbar)
        apply_button_variant(self._add_material_field_btn, "secondary")
        self._add_material_field_btn.clicked.connect(self._request_add_material_field)
        field_toolbar_layout.addWidget(self._template_fields_title, 1)
        field_toolbar_layout.addWidget(self._add_material_field_btn, 0)
        profile_card.add_widget(field_toolbar)
        field_columns = QWidget(profile_card)
        self._field_columns = field_columns
        field_columns_layout = QHBoxLayout(field_columns)
        field_columns_layout.setContentsMargins(10, 0, 78, 0)
        field_columns_layout.setSpacing(10)
        self._field_code_column_label = QLabel(
            "占位符",
            field_columns,
        )
        self._field_value_column_label = QLabel("字段内容", field_columns)
        field_columns_layout.addWidget(self._field_code_column_label, 2)
        field_columns_layout.addWidget(self._field_value_column_label, 3)
        profile_card.add_widget(field_columns)
        self._empty_fields_label = QLabel("暂无字段", profile_card)
        profile_card.add_widget(self._empty_fields_label)
        self._unknown_fields_container = QWidget(profile_card)
        self._unknown_fields_layout = QVBoxLayout(self._unknown_fields_container)
        self._unknown_fields_layout.setContentsMargins(0, 0, 0, 0)
        self._unknown_fields_layout.setSpacing(8)
        profile_card.add_widget(self._unknown_fields_container)

        self._official_fields_panel = QWidget(profile_card)
        official_layout = QVBoxLayout(self._official_fields_panel)
        official_layout.setContentsMargins(0, 0, 0, 0)
        official_layout.setSpacing(14)

        fixed_header = TokenSectionHeader(
            "固定字段",
            hint="长期复用",
            add_text="＋ 新增固定字段",
            parent=self._official_fields_panel,
        )
        self._official_fixed_title = fixed_header.title_label
        self._official_fixed_count = fixed_header.count_label
        self._official_fixed_hint = fixed_header.hint_label
        self._undo_official_fixed_remove_btn = fixed_header.undo_button
        self._undo_official_fixed_remove_btn.clicked.connect(
            self._undo_last_official_field_removal
        )
        self._add_official_fixed_btn = fixed_header.add_button
        self._add_official_fixed_btn.clicked.connect(
            lambda: self._request_official_field("fixed")
        )
        official_layout.addWidget(fixed_header)

        self._official_fixed_body = QWidget(self._official_fields_panel)
        fixed_body_layout = QVBoxLayout(self._official_fixed_body)
        fixed_body_layout.setContentsMargins(0, 0, 0, 0)
        fixed_body_layout.setSpacing(0)
        self._official_fixed_column_guide = TokenColumnGuide(
            parent=self._official_fixed_body,
        )
        self._official_fixed_column_guide.setProperty("fieldScope", "fixed")
        self._official_fixed_column_guide.metrics_changed.connect(
            lambda metrics: self._apply_official_field_column_metrics(
                "fixed",
                metrics,
            )
        )
        fixed_body_layout.addWidget(self._official_fixed_column_guide)

        self._official_fixed_container = QWidget(self._official_fixed_body)
        self._official_fixed_layout = QVBoxLayout(self._official_fixed_container)
        self._official_fixed_layout.setContentsMargins(0, 0, 0, 0)
        self._official_fixed_layout.setSpacing(0)
        fixed_body_layout.addWidget(self._official_fixed_container)
        official_layout.addWidget(self._official_fixed_body)

        floating_header = TokenSectionHeader(
            "自由字段",
            hint="每次填写",
            add_text="＋ 新增自由字段",
            parent=self._official_fields_panel,
        )
        self._official_floating_title = floating_header.title_label
        self._official_floating_count = floating_header.count_label
        self._official_floating_hint = floating_header.hint_label
        self._undo_official_floating_remove_btn = floating_header.undo_button
        self._undo_official_floating_remove_btn.clicked.connect(
            self._undo_last_official_field_removal
        )
        self._add_official_floating_btn = floating_header.add_button
        self._add_official_floating_btn.clicked.connect(
            lambda: self._request_official_field("floating")
        )
        official_layout.addWidget(floating_header)

        self._official_floating_body = QWidget(self._official_fields_panel)
        floating_body_layout = QVBoxLayout(self._official_floating_body)
        floating_body_layout.setContentsMargins(0, 0, 0, 0)
        floating_body_layout.setSpacing(0)
        self._official_floating_column_guide = TokenColumnGuide(
            parent=self._official_floating_body,
        )
        self._official_floating_column_guide.setProperty("fieldScope", "floating")
        self._official_floating_column_guide.metrics_changed.connect(
            lambda metrics: self._apply_official_field_column_metrics(
                "floating",
                metrics,
            )
        )
        floating_body_layout.addWidget(self._official_floating_column_guide)

        self._official_floating_container = QWidget(self._official_floating_body)
        self._official_floating_layout = QVBoxLayout(self._official_floating_container)
        self._official_floating_layout.setContentsMargins(0, 0, 0, 0)
        self._official_floating_layout.setSpacing(0)
        floating_body_layout.addWidget(self._official_floating_container)
        official_layout.addWidget(self._official_floating_body)

        self._official_fields_panel.setVisible(False)
        profile_card.add_widget(self._official_fields_panel)
        self._section_layouts["fields"].addWidget(profile_card)


__all__ = ["ProfileEditorPresenterMixin"]
