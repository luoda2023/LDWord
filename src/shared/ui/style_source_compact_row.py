"""Compact reusable row for template and section style source."""

from __future__ import annotations

from src.qt_api import QBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget, Qt, Signal
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.theme import bind_theme, get_theme


class StyleSourceCompactRow(QWidget):
    """Show template baseline, section style status, and two navigation actions."""

    navigate_requested = Signal(str)
    HORIZONTAL_ACTION_MIN_WIDTH = 760

    def __init__(
        self,
        parent=None,
        *,
        object_name_prefix: str = "style_source",
    ) -> None:
        super().__init__(parent)
        self._target_card_id = ""
        self._secondary_target_card_id = ""
        self._icon_name = "type-outline"
        self.setObjectName(f"{object_name_prefix}_compact_row")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        self._icon = QLabel(self)
        self._icon.setFixedSize(18, 18)
        layout.addWidget(self._icon, 0, Qt.AlignTop)

        text_wrap = QWidget(self)
        text_lay = QVBoxLayout(text_wrap)
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(2)

        header = QWidget(text_wrap)
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.setSpacing(8)
        self._label = QLabel("样式来源", header)
        self._status = QLabel("", header)
        header_lay.addWidget(self._label)
        header_lay.addWidget(self._status)
        header_lay.addStretch(1)
        text_lay.addWidget(header)

        self._template_line = QLabel("", text_wrap)
        self._template_line.setWordWrap(True)
        text_lay.addWidget(self._template_line)

        self._section_line = QLabel("", text_wrap)
        self._section_line.setWordWrap(True)
        text_lay.addWidget(self._section_line)

        self._summary = QLabel("", text_wrap)
        self._summary.setWordWrap(True)
        self._summary.setVisible(False)
        text_lay.addWidget(self._summary)

        layout.addWidget(text_wrap, 1)

        self._actions_wrap = QWidget(self)
        self._actions_layout = QBoxLayout(QBoxLayout.LeftToRight, self._actions_wrap)
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._actions_layout.setSpacing(8)

        self._jump_btn = QPushButton("看模板", self._actions_wrap)
        self._jump_btn.clicked.connect(
            lambda: self.navigate_requested.emit(self._target_card_id)
        )
        self._actions_layout.addWidget(self._jump_btn)

        self._secondary_jump_btn = QPushButton("调例外", self._actions_wrap)
        self._secondary_jump_btn.clicked.connect(
            lambda: self.navigate_requested.emit(self._secondary_target_card_id)
        )
        self._actions_layout.addWidget(self._secondary_jump_btn)
        layout.addWidget(self._actions_wrap, 0, Qt.AlignTop)

        bind_theme(self, self.apply_theme)
        self.apply_theme()

    def set_spec(self, spec) -> None:
        self._target_card_id = str(getattr(spec, "target_card_id", "") or "").strip()
        self._secondary_target_card_id = str(
            getattr(spec, "secondary_target_card_id", "") or ""
        ).strip()
        self._icon_name = str(getattr(spec, "icon_name", "") or "type-outline")
        self._label.setText(str(getattr(spec, "label", "") or "样式来源"))
        self._status.setText(str(getattr(spec, "status", "") or ""))
        summary = str(getattr(spec, "summary", "") or "").strip()
        self._summary.setText(summary)
        self._template_line.setText(summary)
        self._section_line.setText("")
        self._section_line.setVisible(False)
        self._jump_btn.setText(str(getattr(spec, "action_label", "") or "看模板"))
        self._secondary_jump_btn.setText(
            str(getattr(spec, "secondary_action_label", "") or "调例外")
        )
        self.setProperty("style_source_view_mode", "scene_editable")
        self._apply_action_visibility("scene_editable")
        self.apply_theme()

    def apply_projection(self, projection) -> None:
        template_label = str(getattr(projection, "template_label", "") or "").strip()
        template_action = str(
            getattr(projection, "template_action_summary", "") or ""
        ).strip()
        section_status = str(
            getattr(projection, "section_status_label", "") or ""
        ).strip()
        primary_action = getattr(projection, "primary_action", None)
        secondary_action = getattr(projection, "secondary_action", None)
        view_mode = str(
            getattr(projection, "view_mode", "") or "scene_editable"
        ).strip()

        template_prefix = str(
            getattr(projection, "template_line_prefix", "") or "模板"
        ).strip()
        section_prefix = str(
            getattr(projection, "section_line_prefix", "") or "例外"
        ).strip()
        template_line = f"{template_prefix}：{template_label or '当前模板'}"
        if template_action:
            template_line = f"{template_line}，{template_action}"
        section_line = f"{section_prefix}：{section_status or '无格式例外'}"

        self._label.setText("样式来源")
        self._status.setText(str(getattr(projection, "status_label", "") or ""))
        self._template_line.setText(template_line)
        self._section_line.setText(section_line)
        self._section_line.setVisible(True)
        self._summary.setText(str(getattr(projection, "summary", "") or ""))

        self._target_card_id = str(
            getattr(primary_action, "target_card_id", "") or ""
        ).strip()
        self._secondary_target_card_id = str(
            getattr(secondary_action, "target_card_id", "") or ""
        ).strip()
        self._jump_btn.setText(str(getattr(primary_action, "label", "") or "看模板"))
        self._secondary_jump_btn.setText(
            str(getattr(secondary_action, "label", "") or "调例外")
        )
        self.setProperty("style_source_view_mode", view_mode)
        self._apply_action_visibility(view_mode)
        self.apply_theme()

    def _apply_action_visibility(self, view_mode: str) -> None:
        mode = str(view_mode or "").strip()
        if mode == "readonly":
            self._jump_btn.setVisible(False)
            self._secondary_jump_btn.setVisible(False)
            self._actions_wrap.setVisible(False)
            return

        primary_visible = bool(self._target_card_id)
        secondary_visible = bool(self._secondary_target_card_id)
        if mode == "template_baseline":
            secondary_visible = False

        self._jump_btn.setVisible(primary_visible)
        self._secondary_jump_btn.setVisible(secondary_visible)
        self._actions_wrap.setVisible(primary_visible or secondary_visible)
        self._sync_action_layout_direction()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_action_layout_direction()

    def _sync_action_layout_direction(self) -> None:
        if not hasattr(self, "_actions_layout"):
            return
        direction = (
            QBoxLayout.LeftToRight
            if self.width() >= self.HORIZONTAL_ACTION_MIN_WIDTH
            else QBoxLayout.TopToBottom
        )
        if self._actions_layout.direction() != direction:
            self._actions_layout.setDirection(direction)
        self._actions_layout.setSpacing(8 if direction == QBoxLayout.LeftToRight else 6)

    def summary_text(self) -> str:
        return self._summary.text()

    def apply_theme(self) -> None:
        t = get_theme()
        self._label.setStyleSheet(
            f"font-size: {t.font_size_md}px; font-weight: {t.font_weight_emphasis}; "
            f"color: {t.text_primary};"
        )
        line_style = f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        self._template_line.setStyleSheet(line_style)
        self._section_line.setStyleSheet(line_style)
        self._summary.setStyleSheet(line_style)
        self._status.setStyleSheet(
            f"font-size: {t.font_size_sm - 1}px; color: {t.primary}; "
            f"background: {t.info_bg}; border-radius: {t.radius_sm}px; padding: 1px 6px;"
        )
        stylesheet = build_button_stylesheet(t)
        for button in (self._jump_btn, self._secondary_jump_btn):
            apply_button_variant(button, "secondary")
            apply_size_class(button, "md")
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet(stylesheet)
        try:
            from src.ui.icons.catalog import get_icon

            self._icon.setPixmap(
                get_icon(self._icon_name, size=16, color=t.text_hint).pixmap(16, 16)
            )
            self._icon.setText("")
        except Exception:
            self._icon.setText("•")


__all__ = ["StyleSourceCompactRow"]
