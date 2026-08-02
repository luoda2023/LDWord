"""Theme projection for the attachment preparation workbench."""

from __future__ import annotations

from src.shared.ui.button_style import build_button_stylesheet


def build_attachment_preparation_stylesheet(theme) -> str:
    """Return feature QSS while the shared shell keeps window chrome ownership."""

    return f"""
        QDialog#attachment_preparation_dialog {{
            background: transparent;
            color: {theme.text_primary};
        }}
        QFrame#attachment_preparation_body {{
            background: {theme.bg_window};
            border: 1px solid {theme.border_light};
            border-radius: {theme.radius_md}px;
        }}
        QFrame#attachment_preparation_left {{
            background: {theme.bg_card};
            border: none;
            border-right: 1px solid {theme.divider};
            border-top-left-radius: {theme.radius_md}px;
            border-bottom-left-radius: {theme.radius_md}px;
        }}
        QFrame#attachment_preparation_right {{
            background: {theme.bg_window};
            border: none;
            border-top-right-radius: {theme.radius_md}px;
            border-bottom-right-radius: {theme.radius_md}px;
        }}
        QFrame#attachment_preparation_footer {{
            background: {theme.bg_card};
            border: 1px solid {theme.border_light};
            border-radius: {theme.radius_md}px;
        }}
        QLabel#attachment_preparation_source,
        QLabel#attachment_preparation_page_summary,
        QLabel#attachment_preparation_footer_status,
        QLabel#attachment_preparation_section_hint {{
            color: {theme.text_hint};
            font-size: {theme.font_size_sm}px;
            background: transparent;
            border: none;
        }}
        QLabel#attachment_preparation_section_title,
        QLabel#attachment_preparation_page_title {{
            color: {theme.text_primary};
            font-size: {theme.font_size_lg}px;
            font-weight: {theme.font_weight_emphasis};
            background: transparent;
            border: none;
        }}
        QLabel#attachment_preparation_control_label,
        QLabel#attachment_preparation_column_label {{
            color: {theme.text_hint};
            font-size: {theme.font_size_sm}px;
            background: transparent;
            border: none;
        }}
        QFrame#attachment_preparation_column_header {{
            background: {theme.bg_input};
            border: 1px solid {theme.border_light};
            border-radius: {theme.radius_sm}px;
        }}
        QFrame#attachment_preparation_timeline_editor {{
            background: {theme.bg_card};
            border: 1px solid {theme.border_light};
            border-radius: {theme.radius_md}px;
        }}
        QLabel#attachment_preparation_relationship {{
            color: {theme.primary};
            font-size: {theme.font_size_md}px;
            font-weight: {theme.font_weight_emphasis};
            background: transparent;
            border: none;
        }}
        QLabel#attachment_preparation_empty_state {{
            color: {theme.text_hint};
            font-size: {theme.font_size_md}px;
            padding: 32px;
            background: {theme.bg_card};
            border: 1px solid {theme.border_light};
            border-radius: {theme.radius_md}px;
        }}
        QScrollArea {{
            background: transparent;
            border: none;
        }}
        QScrollArea > QWidget > QWidget {{
            background: {theme.bg_card};
        }}
        QScrollBar:vertical {{
            width: 8px;
            background: {theme.scrollbar_track};
            border: none;
            margin: 2px 0;
        }}
        QScrollBar::handle:vertical {{
            min-height: 28px;
            background: {theme.scrollbar_thumb};
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {theme.scrollbar_thumb_hover};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
            background: transparent;
        }}
        QCheckBox#attachment_preparation_field_filter {{
            color: {theme.text_secondary};
            spacing: 7px;
            background: transparent;
            border: none;
        }}
        QCheckBox#attachment_preparation_field_filter::indicator {{
            width: 15px;
            height: 15px;
            border: 1px solid {theme.border};
            border-radius: 4px;
            background: {theme.bg_card};
        }}
        QCheckBox#attachment_preparation_field_filter::indicator:checked {{
            border-color: {theme.primary};
            background: {theme.primary};
        }}
        QLabel#attachment_preparation_problem_title {{
            color: {theme.text_primary};
            font-size: {theme.font_size_md}px;
            font-weight: {theme.font_weight_emphasis};
            background: transparent;
            border: none;
        }}
        QLabel#attachment_preparation_problem_detail {{
            color: {theme.text_secondary};
            font-size: {theme.font_size_sm}px;
            background: transparent;
            border: none;
        }}
        QFrame#attachment_preparation_problem_row {{
            background: {theme.bg_card};
            border: 1px solid {theme.border_light};
            border-left: 3px solid {theme.warning};
            border-radius: {theme.radius_sm}px;
        }}
        QFrame#attachment_preparation_problem_row[kind="error"] {{
            border-left-color: {theme.error};
        }}
        QFrame#attachment_preparation_problem_row[kind="success"] {{
            border-left-color: {theme.success};
        }}
        {build_button_stylesheet(theme)}
    """


__all__ = ["build_attachment_preparation_stylesheet"]
