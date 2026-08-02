"""Plan-owned input cleanup controls shown inside the scene rules page."""

from __future__ import annotations

from src.config.scene import SceneWorkspace
from src.qt_api import (
    QCheckBox,
    QLabel,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.card import Card
from src.shared.ui.flow_layout import FlowLayout
from src.shared.ui.selection_control_style import build_checkbox_stylesheet
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.template_form_layout import TemplateFormStack, template_form_row
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toggle_switch import ToggleSwitch

MARKDOWN_POLICY_LABELS: tuple[tuple[str, str], ...] = (
    ("disabled", "不处理"),
    ("cleanup_only", "自动清理残留"),
    ("preview_and_cleanup", "预览后清理"),
)

_MARKDOWN_FORMAT_IDS = frozenset({"md", "markdown"})

_WHITESPACE_OPTION_LABELS: tuple[tuple[str, str], ...] = (
    ("normalize_space_variants", "统一空格"),
    ("convert_tabs", "转换制表符"),
    ("remove_zero_width", "移除零宽字符"),
    ("collapse_multiple_spaces", "收束连续空格"),
    ("trim_paragraph_edges", "清理段首尾空白"),
    ("smart_full_half_convert", "智能全半角"),
)


class SceneInputCleanupRulesCard(QWidget):
    """Edit source-aware Markdown and whitespace cleanup policy."""

    scene_edited = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._is_syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._card = Card(parent=self)
        self._card.set_header("输入清理", icon_name="sliders-horizontal")

        self._hint = QLabel(
            "只处理实际输入中适用的文本。Markdown 规则仅对 Markdown 来源生效；"
            "对象安全预检和生成后验收由执行链自动完成。",
            self._card,
        )
        self._hint.setObjectName("scn_input_cleanup_hint")
        self._hint.setWordWrap(True)
        self._card.add_widget(self._hint)

        self._markdown_policy = StyledComboBox(self._card)
        self._markdown_policy.setObjectName("scn_input_cleanup_markdown_policy")
        self._markdown_policy.set_full_width_mode()
        for value, label in MARKDOWN_POLICY_LABELS:
            self._markdown_policy.addItem(label, value)
        self._markdown_policy.currentIndexChanged.connect(
            self._on_markdown_policy_changed
        )
        self._markdown_row = template_form_row(
            "Markdown 输入",
            self._markdown_policy,
            parent=self._card,
        )

        self._whitespace_enabled = ToggleSwitch(self._card, checked=False)
        self._whitespace_enabled.setObjectName(
            "scn_input_cleanup_whitespace_enabled"
        )
        self._whitespace_enabled.toggled_signal.connect(
            self._on_whitespace_enabled_changed
        )
        self._whitespace_row = template_form_row(
            "空白规范化",
            self._whitespace_enabled,
            parent=self._card,
        )

        self._whitespace_options = QWidget(self._card)
        self._whitespace_options.setObjectName("scn_input_cleanup_whitespace_options")
        options_layout = FlowLayout(
            self._whitespace_options,
            h_spacing=18,
            v_spacing=8,
        )
        options_layout.setContentsMargins(0, 0, 0, 0)
        self._whitespace_option_checks: dict[str, QCheckBox] = {}
        for field_name, label in _WHITESPACE_OPTION_LABELS:
            checkbox = QCheckBox(label, self._whitespace_options)
            checkbox.setObjectName(f"scn_input_cleanup_{field_name}")
            checkbox.setCursor(Qt.PointingHandCursor)
            checkbox.toggled.connect(self._on_whitespace_option_changed)
            self._whitespace_option_checks[field_name] = checkbox
            options_layout.addWidget(checkbox)
        self._whitespace_options_row = template_form_row(
            "处理项目",
            self._whitespace_options,
            parent=self._card,
        )

        self._card.add_widget(
            TemplateFormStack(
                [
                    self._markdown_row,
                    self._whitespace_row,
                    self._whitespace_options_row,
                ],
                parent=self._card,
            )
        )
        layout.addWidget(self._card)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            profile = scene.input_source_profile
            policy = str(profile.markdown_policy or "disabled").strip() or "disabled"
            self._ensure_markdown_policy_item(policy)
            index = self._markdown_policy.findData(policy)
            self._markdown_policy.setCurrentIndex(max(0, index))

            accepted_formats = {
                str(value or "").strip().casefold()
                for value in list(profile.accepted_formats or ())
            }
            markdown_applicable = bool(
                accepted_formats.intersection(_MARKDOWN_FORMAT_IDS)
                or policy != "disabled"
            )
            self._markdown_row.setVisible(markdown_applicable)
            self._markdown_policy.setEnabled(markdown_applicable)

            whitespace_enabled = bool(
                scene.module_switches.get("whitespace_normalize", False)
            )
            self._whitespace_enabled.setChecked(whitespace_enabled)
            for field_name, checkbox in self._whitespace_option_checks.items():
                checkbox.setChecked(bool(getattr(scene.whitespace, field_name)))
            self._sync_whitespace_option_state()
        finally:
            self._is_syncing = False

    def focus_navigation_field(self, field_id: str) -> bool:
        target = str(field_id or "").strip()
        if target in {
            "markdown_policy",
            "input_source_profile.markdown_policy",
            "scene.input_source_profile.markdown_policy",
            "md_cleanup",
            "module_switches.md_cleanup",
        }:
            self._markdown_policy.setFocus(Qt.OtherFocusReason)
            return not self._markdown_row.isHidden()
        if target in {
            "whitespace",
            "whitespace_normalize",
            "module_switches.whitespace_normalize",
        }:
            self._whitespace_enabled.setFocus(Qt.OtherFocusReason)
            return True
        for field_name, checkbox in self._whitespace_option_checks.items():
            if target in {field_name, f"whitespace.{field_name}"}:
                checkbox.setFocus(Qt.OtherFocusReason)
                return True
        return False

    def _ensure_markdown_policy_item(self, policy: str) -> None:
        if self._markdown_policy.findData(policy) >= 0:
            return
        self._markdown_policy.addItem(f"未知策略：{policy}", policy)

    def _on_markdown_policy_changed(self, _index: int = -1) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        policy = str(self._markdown_policy.currentData() or "disabled")
        self._current_scene.input_source_profile.markdown_policy = policy
        formula_cleanup_requested = bool(
            self._current_scene.md_cleanup.formula_copy_noise_cleanup
            or self._current_scene.md_cleanup.suppress_formula_fake_lists
        )
        self._current_scene.module_switches["md_cleanup"] = bool(
            policy != "disabled" or formula_cleanup_requested
        )
        self.scene_edited.emit()

    def _on_whitespace_enabled_changed(self, enabled: bool) -> None:
        self._sync_whitespace_option_state()
        if self._is_syncing or self._current_scene is None:
            return
        self._current_scene.module_switches["whitespace_normalize"] = bool(enabled)
        self.scene_edited.emit()

    def _on_whitespace_option_changed(self, *_args) -> None:
        if self._is_syncing or self._current_scene is None:
            return
        for field_name, checkbox in self._whitespace_option_checks.items():
            setattr(
                self._current_scene.whitespace,
                field_name,
                checkbox.isChecked(),
            )
        self.scene_edited.emit()

    def _sync_whitespace_option_state(self) -> None:
        enabled = self._whitespace_enabled.isChecked()
        self._whitespace_options.setEnabled(enabled)
        self._whitespace_options_row.setVisible(enabled)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._hint.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary};"
        )
        stylesheet = build_checkbox_stylesheet(theme)
        for checkbox in self._whitespace_option_checks.values():
            checkbox.setStyleSheet(stylesheet)


__all__ = ["MARKDOWN_POLICY_LABELS", "SceneInputCleanupRulesCard"]
