"""Small adapter mapping creative-home geometry to LDWord theme tokens."""

from __future__ import annotations

from dataclasses import dataclass

from src.shared.ui.theme import get_theme


@dataclass(frozen=True, slots=True)
class AssistantDesignTokens:
    session_rail_width: int = 240
    context_rail_width: int = 280
    content_max_width: int = 760
    message_column_max_width: int = 860
    assistant_message_max_width: int = 820
    plan_card_max_width: int = 760
    progress_card_max_width: int = 760
    user_message_max_width: int = 640
    compact_composer_height: int = 154
    compact_breakpoint: int = 900
    context_breakpoint: int = 1120
    panel_padding: int = 16
    message_spacing: int = 12
    composer_attachment_height: int = 34
    composer_attachment_max_width: int = 268
    user_attachment_card_width: int = 138
    user_attachment_card_height: int = 108
    user_attachment_strip_height: int = 122
    artifact_file_card_height: int = 92
    artifact_icon_box_size: int = 64
    question_option_height: int = 30

    @property
    def card_radius(self) -> int:
        return int(get_theme().radius_md)

    @property
    def focus_color(self) -> str:
        return str(get_theme().border_focus)


TOKENS = AssistantDesignTokens()

__all__ = ["AssistantDesignTokens", "TOKENS"]
