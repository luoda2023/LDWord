"""Presenter mixin for retained local material settings controls."""

from __future__ import annotations

from src.qt_api import QLineEdit
from src.shared.ui.card import Card
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.template_form_layout import template_form_row
from src.shared.ui.text_area import TextArea
from src.ui.panels.assets.fields import _format_required_fields_text


class MaterialSettingsPresenterMixin:
    """Build local-only material rule and required-field settings."""

    def _setup_material_settings_card(self) -> None:
        advanced_card = Card(parent=self._section_contents["advanced"])
        self._advanced_card = advanced_card
        advanced_card.set_header("\u6942\u6a3c\u9a87\u7481\u5267\u7586", icon_name="settings")
        self._replacement_rules_edit = TextArea(
            placeholder="{{project_name}}=\u6d4b\u8bd5\u9879\u76ee\n\u65e7\u6587\u672c=\u65b0\u6587\u672c",
            min_height=80,
            max_height=160,
            parent=advanced_card,
        )
        self._replacement_rules_edit.text_changed.connect(self._refresh_summary)

        self._image_rules_edit = TextArea(
            placeholder="logo={{logo}}\nseal={{seal}}",
            min_height=80,
            max_height=160,
            parent=advanced_card,
        )
        self._image_rules_edit.text_changed.connect(self._refresh_summary)

        self._required_fields_edit = QLineEdit(advanced_card)
        self._required_fields_edit.setText(
            _format_required_fields_text(
                [],
                fallback=self._default_required_field_keys(),
            )
        )
        self._required_fields_edit.setPlaceholderText(
            "\u6e1a\u5b2a\ue6e7\u951b\u6c2c\u53d5\u9359\u7a3f\u6095\u7ec9\u822c\u20ac\u4f80\u300d\u9429\ue1bc\u6095\u7ec9?"
        )
        self._required_fields_edit.textChanged.connect(lambda *_: self._on_required_fields_changed())

        self._batch_output_template_edit = QLineEdit(advanced_card)
        self._batch_output_template_edit.setText("{entity_name}")
        self._batch_output_template_edit.textChanged.connect(
            lambda *_: self._on_batch_output_template_changed()
        )
        self._batch_output_template_row = template_form_row(
            "\u9477\ue044\u757e\u6d94\u590a\u61e1\u935a?",
            self._batch_output_template_edit,
            parent=advanced_card,
        )
        self._batch_output_template_row.setVisible(False)
        advanced_form = InspectorForm(parent=advanced_card)
        advanced_form.add_grid(
            [
                [
                    template_form_row(
                        "\u8e47\u546d\uff5e\u74a7\u52ec\u67a1",
                        self._required_fields_edit,
                        parent=advanced_form,
                    ),
                    self._batch_output_template_row,
                ],
            ]
        )
        advanced_form.add_field("\u9477\ue044\u757e\u6d94\u590b\u6d5b\u93b9?", self._replacement_rules_edit)
        advanced_form.add_field("\u9365\u5267\u5896\u93c0\u5267\u7586", self._image_rules_edit)
        advanced_card.add_widget(advanced_form)
        self._section_layouts["advanced"].addWidget(advanced_card)


__all__ = ["MaterialSettingsPresenterMixin"]
