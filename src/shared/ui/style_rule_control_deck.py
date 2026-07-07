"""Scene section style-rule policy deck."""

from __future__ import annotations

from collections.abc import Sequence

from src.shared.ui.style_policy_control_deck import StylePolicyControlDeck
from src.shared.ui.style_policy_toggle_list import StylePolicyToggleOption


class StyleRuleControlDeck(StylePolicyControlDeck):
    """Scene-specific wrapper for section style policy controls."""

    def __init__(
        self,
        parent=None,
        *,
        toggle_options: Sequence[StylePolicyToggleOption] = (),
        object_name_prefix: str = "style_rule_control",
        toggle_title: str = "独立样式",
    ) -> None:
        super().__init__(
            parent,
            toggle_options=tuple(toggle_options),
            object_name_prefix=object_name_prefix,
            object_name_suffix="rule_control_deck",
            toggle_title=toggle_title,
            restore_all_label="全部跟随模板",
            restore_all_disabled_tooltip="当前没有独立样式",
            restore_all_enabled_tooltip="关闭所有分区的独立样式",
            restore_all_enabled_labels_prefix="将关闭独立样式：",
            undo_restore_all_label="撤销恢复",
            undo_restore_all_disabled_tooltip="暂无可撤销的恢复",
            undo_restore_all_enabled_tooltip="恢复上次被关闭的独立样式",
            undo_restore_all_enabled_labels_prefix="恢复独立样式：",
        )


__all__ = ["StyleRuleControlDeck"]
