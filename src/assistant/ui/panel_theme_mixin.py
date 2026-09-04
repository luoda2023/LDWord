"""Theme presentation for the assistant panel."""

from __future__ import annotations

from src.shared.ui.button_style import build_button_stylesheet
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.theme import get_theme


class AssistantPanelThemeMixin:
    """Own the assistant panel's theme projection and icon refresh."""

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QWidget#AssistantPanel, QFrame#assistant_center,
            QWidget#assistant_empty_page, QWidget#assistant_active_page {{
                background: {theme.bg_window};
            }}
            QWidget#assistant_message_host, QWidget#assistant_message_viewport,
            QWidget#assistant_interaction_reading_column {{
                background: transparent;
                border: none;
            }}
            QFrame#assistant_session_rail, QFrame#assistant_context_rail {{
                background: {theme.bg_card};
                border: none;
            }}
            QFrame#assistant_session_rail {{ border-right: 1px solid {theme.divider}; }}
            QFrame#assistant_context_rail {{ border-left: 1px solid {theme.divider}; }}
            QWidget#assistant_header {{
                background: {theme.bg_card};
                border-bottom: 1px solid {theme.divider};
            }}
            QWidget#assistant_composer_host {{
                background: transparent;
                border: none;
            }}
            QLabel#assistant_rail_title, QLabel#assistant_context_title,
            QLabel#assistant_conversation_title {{
                color: {theme.text_primary};
                font-size: {theme.font_size_lg}px;
                font-weight: {theme.font_weight_emphasis};
            }}
            QLabel#assistant_hero_title {{
                color: {theme.text_primary};
                font-size: {theme.font_size_xxl}px;
                font-weight: {theme.font_weight_emphasis};
            }}
            QLabel#assistant_hero_subtitle, QLabel#assistant_rail_privacy,
            QLabel#assistant_context_disclosure {{
                color: {theme.text_secondary};
                font-size: {theme.font_size_sm}px;
            }}
            QLabel#assistant_context_caption {{
                color: {theme.text_hint};
                font-size: {theme.font_size_sm}px;
            }}
            QLabel#assistant_context_value {{
                color: {theme.text_primary};
                font-size: {theme.font_size_md}px;
            }}
            QComboBox#assistant_provider_combo {{
                color: {theme.primary};
                background: {theme.primary_light};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_sm}px;
                padding: 3px 7px;
            }}
            QToolButton#assistant_provider_settings {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: {theme.radius_sm}px;
            }}
            QToolButton#assistant_provider_settings:hover {{
                background: {theme.bg_hover};
                border-color: {theme.border_light};
            }}
            QComboBox#assistant_session_combo {{
                color: {theme.text_primary};
                background: {theme.bg_input};
                border: 1px solid {theme.border};
                border-radius: {theme.radius_sm}px;
                padding: 3px 7px;
            }}
            QLineEdit#assistant_session_search {{
                color: {theme.text_primary};
                background: {theme.bg_input};
                border: 1px solid {theme.border};
                border-radius: {theme.input_radius}px;
                padding: 7px 9px;
            }}
            QLineEdit#assistant_session_search:focus {{ border-color: {theme.border_focus}; }}
            QListWidget#assistant_session_list {{
                color: {theme.text_primary};
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget#assistant_session_list::item {{
                border-radius: {theme.radius_sm}px;
                padding: 9px 8px;
                margin: 1px 0;
            }}
            QListWidget#assistant_session_list::item:hover {{ background: {theme.bg_hover}; }}
            QListWidget#assistant_session_list::item:selected {{
                background: {theme.bg_selected};
                color: {theme.text_primary};
            }}
            QScrollArea#assistant_message_scroll {{ background: transparent; border: none; }}
            QScrollArea#assistant_message_scroll QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 2px 0;
                border: none;
            }}
            QScrollArea#assistant_message_scroll QScrollBar::handle:vertical {{
                background: {theme.scrollbar_thumb};
                border-radius: 4px;
                min-height: 28px;
            }}
            QScrollArea#assistant_message_scroll QScrollBar::handle:vertical:hover {{
                background: {theme.scrollbar_thumb_hover};
            }}
            QScrollArea#assistant_message_scroll QScrollBar::handle:vertical:disabled {{
                background: transparent;
            }}
            QScrollArea#assistant_message_scroll QScrollBar::add-line:vertical,
            QScrollArea#assistant_message_scroll QScrollBar::sub-line:vertical {{
                height: 0;
                background: transparent;
                border: none;
            }}
            QScrollArea#assistant_message_scroll QScrollBar::add-page:vertical,
            QScrollArea#assistant_message_scroll QScrollBar::sub-page:vertical {{
                background: transparent;
                border: none;
            }}
            QToolButton#assistant_task_header_more,
            QToolButton#assistant_jump_latest {{
                color: {theme.text_secondary};
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_sm}px;
                padding: 3px 8px;
            }}
            QToolButton#assistant_task_header_more:hover,
            QToolButton#assistant_jump_latest:hover {{
                color: {theme.text_primary};
                background: {theme.bg_hover};
                border-color: {theme.border};
            }}
            """
        )
        button_style = build_button_stylesheet(theme)
        for button in (
            self._new_session_button,
            self._session_toggle,
            self._context_toggle,
            self._stop_button,
            *self._quick_buttons,
        ):
            button.setStyleSheet(button_style)
        self._provider_settings_button.setIcon(
            get_icon("settings", 16, theme.icon_secondary)
        )
        self._header_icon.setPixmap(
            get_icon("file-text", 22, theme.icon_primary).pixmap(22, 22)
        )
        self._header_more_button.setIcon(
            get_icon("ellipsis", 17, theme.icon_secondary)
        )
        self._jump_latest_button.setIcon(
            get_icon("chevron-down", 14, theme.icon_secondary)
        )


__all__ = ["AssistantPanelThemeMixin"]
