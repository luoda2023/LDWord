"""Presenter mixin for applying AssetsPanel theme styles."""

from __future__ import annotations

from src.qt_api import QFrame, QLabel, QPushButton, QSize
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.theme import get_theme


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
            getattr(self, "_apply_btn", None),
            getattr(self, "_batch_generate_btn", None),
        ):
            if button is None:
                continue
            icon_name = str(button.property("assets_generate_action_icon") or "")
            if icon_name:
                try:
                    from src.ui.icons.catalog import get_icon

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
        if hasattr(self, "_attachment_inventory_label"):
            self._attachment_inventory_label.setStyleSheet(
                f"font-size: {theme.font_size_md}px; font-weight: {theme.font_weight_emphasis}; color: {theme.text_primary};"
            )
        if hasattr(self, "_field_status_labels"):
            for label in self._field_status_labels.values():
                label.setStyleSheet(f"font-size: {theme.font_size_xs}px; color: {theme.text_hint};")
        if hasattr(self, "_fields_hint_label"):
            self._fields_hint_label.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_hint};")
        if hasattr(self, "_import_export_hint"):
            self._import_export_hint.setStyleSheet(f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};")
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
                apply_button_variant(button, "secondary")
                button.setStyleSheet(build_button_stylesheet(theme))

    def _apply_form_input_theme(self, theme) -> None:
        for edit in (
            self._archive_id_edit,
            self._archive_name_edit,
            self._profile_id_edit,
            self._profile_name_edit,
            self._required_fields_edit,
            self._batch_output_template_edit,
            *self._field_inputs.values(),
        ):
            apply_size_class(edit, "md")
            edit.setStyleSheet(build_text_input_stylesheet(theme))
        if hasattr(self, "_batch_output_naming_combo"):
            apply_size_class(self._batch_output_naming_combo, "md")
            self._batch_output_naming_combo.setStyleSheet(build_text_input_stylesheet(theme))
        if getattr(self, "_full_image_preview_compare_combo", None) is not None:
            apply_size_class(self._full_image_preview_compare_combo, "md")
            self._full_image_preview_compare_combo.setStyleSheet(
                build_text_input_stylesheet(theme, selector="QComboBox")
            )

    def _apply_asset_row_theme(self, theme) -> None:
        for slot_row in self.findChildren(QFrame, "asset_slot_row"):
            slot_row.setStyleSheet(
                f"""
                QFrame#asset_slot_row {{
                    background: {theme.bg_input};
                    border: 1px solid {theme.border_light};
                    border-radius: {theme.input_radius}px;
                }}
                """
            )
        for row in self.findChildren(QFrame, "attachment_role_row"):
            row.setStyleSheet(
                f"""
                QFrame#attachment_role_row {{
                    background: {theme.bg_input};
                    border: 1px solid {theme.border_light};
                    border-radius: {theme.input_radius}px;
                }}
                """
            )
            for label in row.findChildren(QLabel):
                object_name = label.objectName()
                if object_name == "attachment_role_title":
                    label.setStyleSheet(
                        f"font-size: {theme.font_size_sm}px; font-weight: {theme.font_weight_emphasis}; color: {theme.text_primary};"
                    )
                else:
                    label.setStyleSheet(f"font-size: {theme.font_size_xs}px; color: {theme.text_hint};")
        for thumb in self.findChildren(QLabel, "asset_slot_thumbnail"):
            thumb.setStyleSheet(
                f"""
                QLabel#asset_slot_thumbnail {{
                    background: {theme.bg_card};
                    border: 1px solid {theme.border};
                    border-radius: {theme.radius_sm}px;
                    color: {theme.text_hint};
                    font-size: {theme.font_size_xs}px;
                }}
                """
            )
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
            *self._asset_slot_view_buttons.values(),
            *self._asset_slot_open_buttons.values(),
            *self._asset_slot_clear_buttons.values(),
            *self._attachment_role_choose_buttons.values(),
            *self._attachment_role_open_buttons.values(),
            *self._attachment_role_clear_buttons.values(),
            getattr(self, "_full_image_preview_btn", None),
        ):
            if button is None:
                continue
            icon_name = str(button.property("asset_icon_name") or "")
            if icon_name:
                try:
                    from src.ui.icons.catalog import get_icon

                    button.setIcon(get_icon(icon_name, 16, theme.icon_primary))
                except Exception:
                    button.setIcon(button.icon())
            button.setFixedSize(34, 34)
            button.setIconSize(QSize(16, 16))

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
            (self._load_btn, "secondary"),
            (self._save_btn, "secondary"),
            (self._load_mapping_btn, "secondary"),
            (self._import_batch_from_io_btn, "secondary"),
            (self._apply_btn, "primary"),
            (self._fill_missing_btn, "secondary"),
            (self._batch_generate_btn, "secondary"),
            (self._preview_auto_match_btn, "secondary"),
            (self._preview_filter_btn, "secondary"),
            (getattr(self, "_full_image_preview_btn", None), "secondary"),
            (self._add_profile_btn, "secondary"),
            (self._copy_profile_btn, "secondary"),
            (self._import_batch_profiles_btn, "secondary"),
            (self._remove_profile_btn, "secondary"),
            *[(button, "secondary") for button in self._asset_slot_view_buttons.values()],
            *[(button, "secondary") for button in self._asset_slot_open_buttons.values()],
            *[(button, "secondary") for button in self._asset_slot_clear_buttons.values()],
            *[(button, "secondary") for button in self._attachment_role_choose_buttons.values()],
            *[(button, "secondary") for button in self._attachment_role_open_buttons.values()],
            *[(button, "secondary") for button in self._attachment_role_clear_buttons.values()],
        ):
            if button is None:
                continue
            apply_button_variant(button, variant)
            button.setStyleSheet(build_button_stylesheet(theme))
        for slot_row in self.findChildren(QFrame, "asset_slot_row"):
            for button in slot_row.findChildren(QPushButton):
                apply_button_variant(button, "secondary")
                button.setStyleSheet(build_button_stylesheet(theme))
        for row in self.findChildren(QFrame, "attachment_role_row"):
            for button in row.findChildren(QPushButton):
                apply_button_variant(button, "secondary")
                button.setStyleSheet(build_button_stylesheet(theme))


__all__ = ["ThemePresenterMixin"]
