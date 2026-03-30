from __future__ import annotations

from src.shared.ui.theme import AppTheme


def build_workbench_stylesheet(t: AppTheme) -> str:
    """任务中控 / 执行中心 shared styling."""
    return f"""
        #WorkbenchPanel {{
            background: {t.bg_window};
        }}

        #wb_command_bar,
        #wb_strategy_card {{
            background: {t.bg_card};
            border: 1px solid {t.border};
            border-radius: {t.radius_md}px;
        }}

        #wb_execution_center {{
            background: {t.bg_card};
            border: 2px solid {t.border_focus};
            border-radius: {t.radius_lg}px;
        }}

        #wb_heading_quick_card,
        #wb_quick_fill_card {{
            background: {t.bg_hover};
            border: 1px solid {t.border_light};
            border-radius: {t.radius_md}px;
        }}

        #wb_recent_run {{
            background: {t.bg_sidebar};
            border: 1px solid {t.border_light};
            border-radius: {t.radius_md}px;
        }}

        #wb_command_bar QLabel,
        #wb_strategy_card QLabel,
        #wb_execution_center QLabel {{
            color: {t.text_secondary};
        }}

        #wb_strategy_headline {{
            color: {t.text_primary};
            font-size: {t.font_size_lg}px;
            font-weight: {t.font_weight_bold};
        }}

        #wb_strategy_binding {{
            color: {t.text_secondary};
            font-size: {t.font_size_md}px;
        }}

        #wb_strategy_meta {{
            color: {t.text_hint};
            font-size: {t.font_size_sm}px;
        }}

        #wb_command_center_label,
        #wb_execution_title {{
            color: {t.text_primary};
            font-size: {t.font_size_lg}px;
            font-weight: {t.font_weight_bold};
        }}

        #wb_execution_section_title {{
            color: {t.text_primary};
            font-size: {t.font_size_sm}px;
            font-weight: {t.font_weight_bold};
        }}

        #wb_execution_status {{
            color: {t.text_primary};
            font-weight: {t.font_weight_bold};
        }}

        #wb_execution_summary {{
            background: {t.bg_hover};
            border: 1px solid {t.border_light};
            border-radius: {t.radius_sm}px;
        }}

        #wb_ready_badge {{
            background: {t.bg_hover};
            color: {t.text_primary};
            border-radius: {t.radius_sm}px;
            padding: 2px 8px;
        }}
    """
