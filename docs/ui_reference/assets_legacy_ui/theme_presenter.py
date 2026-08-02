"""Presenter mixin for applying AssetsPanel theme styles."""

from __future__ import annotations

from src.qt_api import QFrame, QLabel, QLineEdit, QPushButton, QSize
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.icon_button import apply_icon_button_style
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.official_field_value_edit import OfficialFieldValueEdit
from src.shared.ui.projected_text_edit import ProjectedTextEdit
from src.shared.ui.selection_control_style import build_checkbox_stylesheet
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import get_theme
from src.shared.ui.token_row_style import apply_token_row_style


class ThemePresenterMixin:
    """Apply theme styling for the assets panel and its presenter-owned widgets."""

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._apply_shell_theme(theme)
        self._apply_generate_action_icons(theme)
        self._apply_text_label_theme(theme)
        self._apply_form_input_theme(theme)
        self._apply_asset_row_theme(theme)
        self._apply_asset_icon_button_sizing(theme)
        self._apply_profile_list_theme(theme)
        self._apply_command_button_theme(theme)
        apply_timeline_theme = getattr(self, "_apply_timeline_theme", None)
        if callable(apply_timeline_theme):
            apply_timeline_theme()

    def _apply_shell_theme(self, theme) -> None:
        if hasattr(self, "_shell"):
            self._shell.apply_theme(theme)
            self._apply_responsive_layout()
        if hasattr(self, "_detail_stack"):
            self._detail_stack.setStyleSheet(
                f"""
                QStackedWidget#assets_detail_stack {{
                    background: {theme.bg_window};
                    border: none;
                }}
                """
            )
        if hasattr(self, "_section_scrolls"):
            for content in self._section_contents.values():
                content_name = content.objectName()
                content.setStyleSheet(
                    f"""
                    QWidget#{content_name} {{
                        background: {theme.bg_window};
                        border: none;
                    }}
                    """
                )
            for layout in self._section_layouts.values():
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(theme.template_detail_section_gap)

    def _apply_generate_action_icons(self, theme) -> None:
        for button in (
            getattr(self, "_fill_missing_btn", None),
            getattr(self, "_overview_preview_refresh_btn", None),
            getattr(self, "_apply_btn", None),
            getattr(self, "_batch_generate_btn", None),
        ):
            if button is None:
                continue
            icon_name = str(button.property("assets_generate_action_icon") or "")
            if icon_name:
                try:
                    from src.shared.ui.icons.catalog import get_icon

                    icon_color = theme.text_on_primary if button is getattr(self, "_apply_btn", None) else theme.icon_primary
                    button.setIcon(get_icon(icon_name, 16, icon_color))
                except Exception:
                    button.setIcon(button.icon())

    def _apply_text_label_theme(self, theme) -> None:
        self._title.setStyleSheet(
            f"font-size: {theme.font_size_xxl}px; font-weight: {theme.font_weight_emphasis}; color: {theme.text_primary};"
        )
        self._summary.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")
        if hasattr(self, "_return_bar"):
            self._return_bar.setStyleSheet(
                f"""
                QWidget#assets_return_bar {{
                    background: {theme.bg_hover};
                    border: 1px solid {theme.border};
                    border-radius: {theme.radius_sm}px;
                }}
                """
            )
            self._return_label.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};"
            )
            apply_button_variant(self._return_btn, "secondary")
        for label in (
            self._generation_status_label,
            self._generation_detail_label,
            self._image_assets_status_label,
            self._preview_label,
        ):
            label.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};")
        if hasattr(self, "_fields_hint_label"):
            self._fields_hint_label.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")
        if hasattr(self, "_template_fields_title"):
            self._template_fields_title.setStyleSheet(
                f"font-size: {theme.font_size_md}px; font-weight: {theme.font_weight_emphasis}; color: {theme.text_primary};"
            )
        if hasattr(self, "_empty_fields_label"):
            self._empty_fields_label.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};"
            )
        if hasattr(self, "_import_export_hint"):
            self._import_export_hint.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};")
        for name in ("_official_fixed_title", "_official_floating_title"):
            label = getattr(self, name, None)
            if label is not None and not label.property("tokenSectionHeaderPart"):
                label.setStyleSheet(
                    f"font-size: {theme.font_size_lg}px; font-weight: 700; color: {theme.text_primary};"
                )
        for name in (
            "_official_fixed_count",
            "_official_fixed_hint",
            "_official_floating_count",
            "_official_floating_hint",
        ):
            label = getattr(self, name, None)
            if label is not None and not label.property("tokenSectionHeaderPart"):
                label.setStyleSheet(
                    f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"
                )
        asset_separator = self.findChild(QFrame, "asset_section_separator")
        if asset_separator is not None:
            asset_separator.setStyleSheet(f"background: {theme.divider}; max-height: 1px;")
        for label in self.findChildren(QLabel, "official_material_field_index"):
            label.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; font-weight: {theme.font_weight_emphasis}; "
                f"color: {theme.primary}; background: transparent; border: none;"
            )
        for row in self.findChildren(QFrame, "unknown_field_suggestion"):
            row.setStyleSheet(
                f"""
                QFrame#unknown_field_suggestion {{
                    background: {theme.bg_input};
                    border: 1px solid {theme.border_light};
                    border-radius: {theme.input_radius}px;
                }}
                """
            )
            for label in row.findChildren(QLabel):
                label.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};")
            for button in row.findChildren(QPushButton):
                variant = (
                    "ghost-danger"
                    if button.objectName() == "material_field_remove_btn"
                    else "secondary"
                )
                apply_button_variant(button, variant)
                button.setStyleSheet(build_button_stylesheet(theme))

    def _apply_form_input_theme(self, theme) -> None:
        for edit in (
            self._archive_id_edit,
            self._archive_name_edit,
            self._profile_id_edit,
            self._profile_name_edit,
            self._batch_output_template_edit,
            *self._field_inputs.values(),
            *getattr(self, "_template_field_inputs", {}).values(),
        ):
            apply_size_class(edit, "md")
            if isinstance(edit, (ProjectedTextEdit, OfficialFieldValueEdit)):
                continue
            edit.setStyleSheet(build_text_input_stylesheet(theme))
        if hasattr(self, "_batch_output_naming_combo"):
            apply_size_class(self._batch_output_naming_combo, "md")
            if not isinstance(self._batch_output_naming_combo, StyledComboBox):
                self._batch_output_naming_combo.setStyleSheet(
                    build_text_input_stylesheet(theme, selector="QComboBox")
                )
        if hasattr(self, "_image_rule_watermark_edit"):
            apply_size_class(self._image_rule_watermark_edit, "md")
            self._image_rule_watermark_edit.setStyleSheet(
                build_text_input_stylesheet(theme)
            )
        for checkbox_name in (
            "_image_rule_adaptive_check",
            "_image_rule_watermark_check",
        ):
            checkbox = getattr(self, checkbox_name, None)
            if checkbox is not None:
                checkbox.setStyleSheet(build_checkbox_stylesheet(theme))

    def _apply_asset_row_theme(self, theme) -> None:
        for header_name in (
            "single_asset_section_header",
            "asset_group_section_header",
            "asset_preview_section_header",
        ):
            header = self.findChild(QFrame, header_name)
            if header is not None:
                header.setStyleSheet(
                    f"""
                    QFrame#{header_name} {{
                        background: transparent;
                        border: none;
                    }}
                    """
                )
        for label in self.findChildren(QLabel, "asset_section_title"):
            if label.property("tokenSectionHeaderPart"):
                continue
            label.setStyleSheet(
                f"font-size: {theme.font_size_md}px; font-weight: {theme.font_weight_emphasis}; "
                f"color: {theme.text_primary}; background: transparent; border: none;"
            )
        for label in self.findChildren(QLabel, "asset_section_hint"):
            label.setStyleSheet(
                f"font-size: {theme.font_size_xs}px; color: {theme.text_hint}; "
                "background: transparent; border: none;"
            )
        for label in self.findChildren(QLabel, "asset_section_count"):
            if label.property("tokenSectionHeaderPart"):
                continue
            label.setStyleSheet(
                f"font-size: {theme.font_size_xs}px; font-weight: {theme.font_weight_emphasis}; color: {theme.primary}; "
                f"background: {theme.primary_light}; border: none; "
                f"border-radius: {theme.radius_sm}px; padding: 2px 7px;"
            )
        slot_rows = [
            self._asset_slot_rows.get(spec.role)
            for spec in tuple(getattr(self, "_asset_slot_specs", ()))
        ]
        slot_rows = [row for row in slot_rows if row is not None]
        for index, slot_row in enumerate(slot_rows):
            apply_token_row_style(
                slot_row,
                object_name="asset_slot_row",
                is_last=index == len(slot_rows) - 1,
            )
            for label in slot_row.findChildren(QLabel):
                if label.objectName() == "asset_slot_status":
                    label.setStyleSheet(
                        f"font-size: {theme.font_size_xs}px; color: {theme.text_hint}; "
                        "border: none; background: transparent;"
                    )
        group_rows = [
            self._asset_group_rows.get(spec.role)
            for spec in tuple(getattr(self, "_asset_group_specs", ()))
        ]
        group_rows = [row for row in group_rows if row is not None]
        for index, group_row in enumerate(group_rows):
            apply_token_row_style(
                group_row,
                object_name="asset_group_row",
                is_last=index == len(group_rows) - 1,
            )
            for label in group_row.findChildren(QLabel):
                if label.objectName() == "asset_group_status":
                    label.setStyleSheet(
                        f"font-size: {theme.font_size_xs}px; color: {theme.text_hint}; "
                        "border: none; background: transparent;"
                    )
        attachment_sections = (
            tuple(
                self._attachment_role_rows.get(spec.role)
                for spec in self._attachment_role_specs
                if spec.source_kind == "single_file"
            ),
            tuple(
                self._attachment_role_rows.get(spec.role)
                for spec in self._attachment_role_specs
                if spec.source_kind != "single_file"
            ),
        )
        for section_rows in attachment_sections:
            rows = tuple(row for row in section_rows if row is not None)
            for index, row in enumerate(rows):
                apply_token_row_style(
                    row,
                    object_name="attachment_role_row",
                    is_last=index == len(rows) - 1,
                )
        for row in self.findChildren(QFrame, "attachment_role_row"):
            for label in row.findChildren(QLabel):
                if label.objectName() == "attachment_role_status":
                    label.setStyleSheet(
                        f"font-size: {theme.font_size_xs}px; color: {theme.text_hint}; "
                        "border: none; background: transparent;"
                    )
        for index_label in self.findChildren(QLabel, "asset_row_index"):
            index_label.setStyleSheet(
                f"font-size: {theme.font_size_sm}px; font-weight: {theme.font_weight_emphasis}; color: {theme.primary}; "
                "background: transparent; border: none;"
            )
        for thumb_name in (
            "asset_slot_thumbnail",
            "asset_group_thumbnail",
            "attachment_role_preview",
        ):
            thumbs = self.findChildren(QLabel, thumb_name)
            for thumb in thumbs:
                thumb.setStyleSheet(
                    f"""
                    QLabel#{thumb_name} {{
                        background: {theme.bg_card};
                        border: 1px solid {theme.border};
                        border-radius: {theme.radius_sm}px;
                        color: {theme.text_hint};
                        font-size: {theme.font_size_xs}px;
                    }}
                    """
                )
        for path_edit in (
            *getattr(self, "_asset_slot_path_edits", {}).values(),
            *getattr(self, "_asset_group_path_labels", {}).values(),
            *getattr(self, "_attachment_role_path_edits", {}).values(),
        ):
            if not isinstance(path_edit, QLineEdit):
                continue
            apply_size_class(path_edit, "md")
            path_edit.setStyleSheet(build_text_input_stylesheet(theme))
        if hasattr(self, "_image_preview_label"):
            self._image_preview_label.setStyleSheet(
                f"""
                QLabel#asset_preview_label {{
                    background: {theme.bg_input};
                    border: 1px solid {theme.border_light};
                    border-radius: {theme.input_radius}px;
                    color: {theme.text_hint};
                    font-size: {theme.font_size_sm}px;
                }}
                """
            )

    def _apply_asset_icon_button_sizing(self, theme) -> None:
        for button in (
            *self._asset_slot_choose_buttons.values(),
            *self._asset_slot_open_buttons.values(),
            *self._asset_slot_clear_buttons.values(),
            *getattr(self, "_asset_slot_add_buttons", {}).values(),
            *getattr(self, "_asset_slot_remove_buttons", {}).values(),
            *self._attachment_role_choose_buttons.values(),
            *self._attachment_role_open_buttons.values(),
            *self._attachment_role_clear_buttons.values(),
            *getattr(self, "_asset_group_choose_buttons", {}).values(),
            *getattr(self, "_asset_group_refresh_buttons", {}).values(),
            *getattr(self, "_asset_group_open_buttons", {}).values(),
            *getattr(self, "_asset_group_clear_buttons", {}).values(),
            *getattr(self, "_asset_group_add_buttons", {}).values(),
            *getattr(self, "_asset_group_remove_buttons", {}).values(),
            getattr(self, "_full_image_preview_btn", None),
        ):
            if button is None:
                continue
            if bool(button.property("compactRowAction")):
                continue
            icon_name = str(button.property("asset_icon_name") or "")
            if icon_name:
                try:
                    from src.shared.ui.icons.catalog import get_icon

                    variant = str(button.property("variant") or "secondary")
                    icon_color = (
                        theme.error
                        if icon_name in {"trash-2", "x"}
                        else theme.text_on_primary
                        if variant == "primary"
                        else theme.icon_primary
                    )
                    button.setIcon(get_icon(icon_name, 16, icon_color))
                except Exception:
                    button.setIcon(button.icon())
            if bool(button.property("asset_text_action")):
                variant = str(button.property("variant") or "secondary")
                button.setProperty("iconButton", False)
                button.setText(str(button.property("asset_action_text") or button.text()))
                button.setMinimumSize(0, 34)
                button.setMaximumSize(16777215, 34)
                button.setIconSize(QSize(16, 16))
                apply_button_variant(button, variant)
                button.setStyleSheet(build_button_stylesheet(theme))
                continue
            apply_icon_button_style(
                button,
                variant=(
                    "ghost-danger"
                    if icon_name in {"trash-2", "x"}
                    else "secondary"
                ),
                size=34,
                icon_size=16,
            )

    def _apply_profile_list_theme(self, theme) -> None:
        self._profile_list.setStyleSheet(
            f"""
            QListWidget#assets_profile_list {{
                background: {theme.bg_input};
                color: {theme.text_primary};
                border: 1px solid {theme.border};
                border-radius: {theme.input_radius}px;
                padding: 4px;
                font-size: {theme.font_size_md}px;
            }}
            QListWidget#assets_profile_list::item {{
                min-height: 30px;
                padding: 4px 8px;
            }}
            QListWidget#assets_profile_list::item:selected {{
                background: {theme.bg_selected};
                color: {theme.primary};
            }}
            """
        )
        self._batch_preview.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")

    def _apply_command_button_theme(self, theme) -> None:
        for button, variant in (
            (self._preview_auto_match_btn, "secondary"),
            (self._preview_filter_btn, "secondary"),
            (getattr(self, "_full_image_preview_btn", None), "secondary"),
            (self._add_profile_btn, "secondary"),
            (self._copy_profile_btn, "secondary"),
            (self._remove_profile_btn, "secondary"),
            (getattr(self, "_add_material_field_btn", None), "secondary"),
            (getattr(self, "_add_content_material_btn", None), "secondary"),
            (getattr(self, "_add_single_asset_btn", None), "secondary"),
            (getattr(self, "_add_asset_group_btn", None), "secondary"),
            *[(button, "secondary") for button in self._asset_slot_open_buttons.values()],
            *[(button, "secondary") for button in self._asset_slot_clear_buttons.values()],
            *[(button, "secondary") for button in getattr(self, "_asset_slot_add_buttons", {}).values()],
            *[(button, "ghost-danger") for button in getattr(self, "_asset_slot_remove_buttons", {}).values()],
            *[(button, "secondary") for button in self._attachment_role_choose_buttons.values()],
            *[(button, "secondary") for button in self._attachment_role_open_buttons.values()],
            *[(button, "secondary") for button in self._attachment_role_clear_buttons.values()],
            *[(button, "ghost-danger") for button in self._attachment_role_remove_buttons.values()],
        ):
            if button is None:
                continue
            if bool(button.property("compactRowAction")):
                continue
            icon_name = str(button.property("asset_icon_name") or "")
            if icon_name and not bool(button.property("asset_text_action")):
                apply_icon_button_style(
                    button,
                    variant=(
                        "ghost-danger"
                        if icon_name in {"trash-2", "x"}
                        else "secondary"
                    ),
                    size=34,
                    icon_size=16,
                )
                continue
            apply_button_variant(button, variant)
            button.setStyleSheet(build_button_stylesheet(theme))
        for slot_row in self.findChildren(QFrame, "asset_slot_row"):
            for button in slot_row.findChildren(QPushButton):
                if button.property("asset_icon_name") or button.property("compactRowAction"):
                    continue
                apply_button_variant(button, "secondary")
                button.setStyleSheet(build_button_stylesheet(theme))
        for row in self.findChildren(QFrame, "attachment_role_row"):
            for button in row.findChildren(QPushButton):
                if button.property("asset_icon_name"):
                    continue
                apply_button_variant(button, "secondary")
                button.setStyleSheet(build_button_stylesheet(theme))


__all__ = ["ThemePresenterMixin"]
