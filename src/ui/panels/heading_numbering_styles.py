"""
Shared stylesheet builder for HeadingNumberingPanel.
"""

from __future__ import annotations

from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.selection_control_style import build_checkbox_stylesheet
from src.shared.ui.theme import AppTheme


def build_heading_numbering_panel_stylesheet(t: AppTheme) -> str:
    selection_qss = build_checkbox_stylesheet(
        t,
        selector="#HeadingNumberingPanel QCheckBox",
    )
    return f"""
        #HeadingNumberingPanel {{ background: transparent; }}

        #hn_label, #hn_form_label {{
            font-size: {t.font_size_md}px;
            color: {t.text_primary};
        }}
        #hn_form_label {{ font-weight: {t.font_weight_bold}; }}

        #hn_small_label {{
            font-size: {t.font_size_sm}px;
            color: {t.text_secondary};
        }}
        
        #hn_detail_title {{
            font-size: {t.font_size_lg}px;
            font-weight: {t.font_weight_bold};
            color: {t.text_primary};
        }}

        #hn_preset_frame, #hn_simple_frame, #hn_detail_frame {{
            background: {t.bg_card};
            border: 1px solid {t.border};
            border-radius: {t.radius_xs}px;
        }}
        
        #hn_nn_frame, #hn_expert_frame {{
            background: {t.bg_input};
            border: 1px solid {t.border};
            border-radius: {t.radius_xs}px;
        }}
        
        #hn_list_frame {{
            background: {t.bg_card};
            border: 1px solid {t.border};
            border-radius: {t.radius_xs}px;
        }}
        
        #hn_list_header {{
            font-size: {t.font_size_md}px;
            color: {t.text_secondary};
            background: {t.bg_input};
            border-bottom: 1px solid {t.border};
        }}

        #hn_preview_row {{
            background: transparent;
        }}
        
        #hn_preview_tag, #hn_list_lv {{
            font-size: {t.font_size_sm}px;
            color: {t.text_secondary};
        }}
        
        #hn_list_txt {{
            font-size: {t.font_size_md}px;
            color: {t.text_primary};
        }}

        #hn_preview_num {{
            font-size: {t.font_size_md}px;
            font-weight: {t.font_weight_bold};
            color: {t.text_primary};
        }}
        
        #hn_preview_demo {{
            font-size: {t.font_size_md}px;
            color: {t.text_secondary};
        }}

        #hn_preview_tag[muted="true"],
        #hn_preview_num[muted="true"],
        #hn_preview_demo[muted="true"],
        #hn_list_txt[muted="true"] {{
            color: {t.text_disabled};
        }}
        
        #hn_divider {{
            background-color: {t.border};
        }}

        #hn_section_toggle {{
            font-size: {t.font_size_sm}px;
            color: {t.primary};
            text-align: left;
            padding: 0;
        }}
        #hn_section_toggle:hover {{
            text-decoration: underline;
        }}

        #hn_mode_container {{
            background: {t.bg_input};
            border: 1px solid {t.border};
            border-radius: {t.radius_sm}px;
        }}
        
        QListWidget#hn_level_list {{
            background: transparent;
            border: none;
            outline: none;
        }}
        QListWidget#hn_level_list::item {{
            border-bottom: 1px solid {t.border};
        }}
        QListWidget#hn_level_list::item:hover {{
            background: {t.bg_hover};
        }}
        QListWidget#hn_level_list::item:selected {{
            background: {t.bg_input};
            border-left: 3px solid {t.primary};
        }}

        {build_text_input_stylesheet(
            t,
            "#HeadingNumberingPanel QLineEdit",
            background=t.bg_card,
            focus_border_color=t.primary,
            padding_y=0,
        )}

        {selection_qss}
    """
