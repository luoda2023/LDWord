from __future__ import annotations

from src.shared.ui.theme import AppTheme


def build_workbench_stylesheet(t: AppTheme) -> str:
    """任务中控 / 执行中心 shared styling."""
    return f"""
        #WorkbenchPanel {{
            background: {t.bg_window};
        }}

        #wb_command_bar,
        #wb_strategy_card,
        #wb_execution_center,
        #wb_recent_run {{
            background: {t.bg_card};
            border: 1px solid {t.border};
            border-radius: {t.radius_md}px;
        }}

        #wb_command_bar QLabel,
        #wb_strategy_card QLabel,
        #wb_execution_center QLabel {{
            color: {t.text_secondary};
        }}

        #wb_command_center_label {{
            color: {t.text_primary};
            font-size: {t.font_size_lg}px;
            font-weight: {t.font_weight_bold};
        }}

        #wb_ready_badge {{
            background: {t.bg_hover};
            color: {t.text_primary};
            border-radius: {t.radius_sm}px;
            padding: 2px 8px;
        }}
    """
