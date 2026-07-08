"""Presenter mixin for building the profile and field editor card."""

from __future__ import annotations

from src.qt_api import QLabel, QLineEdit, QVBoxLayout, QWidget
from src.shared.ui.card import Card
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.template_form_layout import template_form_row
from src.shared.ui.text_area import TextArea
from src.ui.panels.assets import COMMON_FIELD_DEFS
from src.ui.panels.assets.layout_helpers import _chunk_form_rows


class ProfileEditorPresenterMixin:
    """Build the retained local profile and field editor card."""

    def _setup_profile_editor_card(self) -> None:
        profile_card = Card(parent=self._section_contents["fields"])
        self._profile_card = profile_card
        profile_card.set_header("文字资料", icon_name="type")
        self._profile_id_edit = QLineEdit(profile_card)
        self._profile_name_edit = QLineEdit(profile_card)
        self._profile_id_edit.setVisible(False)
        self._profile_id_edit.setPlaceholderText("这一份编号")
        self._profile_name_edit.setPlaceholderText("例如：主体公司")
        self._profile_id_edit.textChanged.connect(lambda *_: self._refresh_summary())
        self._profile_name_edit.textChanged.connect(lambda *_: self._refresh_summary())

        profile_form = InspectorForm(parent=profile_card)
        field_rows = [
            template_form_row("这一份名称", self._profile_name_edit, parent=profile_form),
        ]
        for key, label, placeholder in COMMON_FIELD_DEFS:
            field_widget = QWidget(profile_card)
            field_layout = QVBoxLayout(field_widget)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(4)
            field_edit = QLineEdit(field_widget)
            field_edit.setPlaceholderText(placeholder)
            field_edit.textChanged.connect(lambda *_args, field_key=key: self._on_structured_field_changed(field_key))
            status_label = QLabel(field_widget)
            status_label.setObjectName("asset_field_status")
            status_label.setWordWrap(True)
            field_layout.addWidget(field_edit)
            field_layout.addWidget(status_label)
            self._field_inputs[key] = field_edit
            self._field_status_labels[key] = status_label
            field_rows.append(template_form_row(label, field_widget, parent=profile_form))

        self._fields_edit = TextArea(
            placeholder="其他资料仍可用 key=value，例如：\ncustom_field=自定义内容",
            min_height=120,
            max_height=220,
            parent=profile_card,
        )
        self._fields_edit.text_changed.connect(self._on_more_fields_changed)
        profile_form.add_grid(_chunk_form_rows(field_rows, columns=2))
        profile_form.add_field("更多资料", self._fields_edit)
        profile_card.add_widget(profile_form)
        self._fields_hint_label = QLabel(profile_card)
        self._fields_hint_label.setWordWrap(True)
        profile_card.add_widget(self._fields_hint_label)
        self._unknown_fields_container = QWidget(profile_card)
        self._unknown_fields_layout = QVBoxLayout(self._unknown_fields_container)
        self._unknown_fields_layout.setContentsMargins(0, 0, 0, 0)
        self._unknown_fields_layout.setSpacing(8)
        profile_card.add_widget(self._unknown_fields_container)
        self._section_layouts["fields"].addWidget(profile_card)


__all__ = ["ProfileEditorPresenterMixin"]
