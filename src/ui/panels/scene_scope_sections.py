"""Minimal plan editor for logical document processing scope."""

from __future__ import annotations

from src.config.document_scope import (
    document_scope_role_label,
    selectable_document_scope_roles,
)
from src.qt_api import QLabel, QCheckBox, QVBoxLayout, QSizePolicy, QWidget, Signal
from src.shared.ui.card import Card
from src.shared.ui.segmented_control import SegmentedControl
from src.shared.ui.selection_control_style import build_checkbox_stylesheet
from src.shared.ui.theme import bind_theme, get_theme


DOCUMENT_SCOPE_MODE_OPTIONS = (
    ("all", "全部内容"),
    ("body", "仅正文"),
    ("selected", "自选区域"),
)

DOCUMENT_SCOPE_MODE_HELP = {
    "all": "处理当前文档中识别到的全部内容；原文没有的区域不会被创建。",
    "body": "只处理识别为正文的内容，其他已识别区域保持原样。",
    "selected": "只处理下方勾选且在当前文档中实际存在的区域。",
}

DOCUMENT_SCOPE_ROLE_NOTE = (
    "可选项由当前方案类型提供，不代表每份文件都包含这些内容。"
    "执行时会先识别当前文档，未识别到的参考文献、附录等区域不会被创建或处理。"
)


class DocumentScopeSection(QWidget):
    """One control group; document recognition is intentionally absent."""

    scope_changed = Signal(str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._is_syncing = False
        self._role_checks: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._card = Card(parent=self)
        self._card.set_header("处理范围", icon_name="crosshair")
        self._mode_control = SegmentedControl(parent=self._card)
        self._mode_control.setObjectName("scn_document_scope_mode")
        for mode, label in DOCUMENT_SCOPE_MODE_OPTIONS:
            self._mode_control.add_segment(label, mode)
        self._mode_control.current_changed.connect(self._emit_scope_changed)
        self._card.add_widget(self._mode_control)

        self._mode_help = QLabel(self._card)
        self._mode_help.setObjectName("scn_document_scope_mode_help")
        self._mode_help.setWordWrap(True)
        self._card.add_widget(self._mode_help)

        self._roles_widget = QWidget(self._card)
        self._roles_layout = QVBoxLayout(self._roles_widget)
        self._roles_layout.setContentsMargins(0, 8, 0, 0)
        self._roles_layout.setSpacing(6)
        self._roles_title = QLabel("允许处理的内容类型", self._roles_widget)
        self._roles_title.setObjectName("scn_document_scope_roles_title")
        self._roles_note = QLabel(DOCUMENT_SCOPE_ROLE_NOTE, self._roles_widget)
        self._roles_note.setObjectName("scn_document_scope_roles_note")
        self._roles_note.setWordWrap(True)
        self._roles_layout.addWidget(self._roles_title)
        self._roles_layout.addWidget(self._roles_note)
        self._role_checks_widget = QWidget(self._roles_widget)
        self._role_checks_layout = QVBoxLayout(self._role_checks_widget)
        self._role_checks_layout.setContentsMargins(0, 0, 0, 0)
        self._role_checks_layout.setSpacing(6)
        self._roles_layout.addWidget(self._role_checks_widget)
        self._card.add_widget(self._roles_widget)
        layout.addWidget(self._card)

        self.set_scope("all", ())
        self.set_mode_id("custom")
        bind_theme(self, self._apply_theme)
        self._apply_theme()

    @property
    def card(self) -> Card:
        return self._card

    @property
    def mode_control(self) -> SegmentedControl:
        return self._mode_control

    def set_mode_id(self, mode_id: str) -> None:
        roles = selectable_document_scope_roles(mode_id)
        if tuple(self._role_checks) == roles:
            return
        while self._role_checks_layout.count():
            item = self._role_checks_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._role_checks = {}
        for role_id in roles:
            checkbox = QCheckBox(
                document_scope_role_label(role_id),
                self._role_checks_widget,
            )
            checkbox.setObjectName(f"scn_document_scope_role_{role_id}")
            checkbox.toggled.connect(self._emit_scope_changed)
            self._role_checks[role_id] = checkbox
            self._role_checks_layout.addWidget(checkbox)
        self._apply_theme()
        self._sync_role_visibility()

    def set_scope(self, mode: str, selected_roles) -> None:
        self._is_syncing = True
        try:
            normalized = str(mode or "").strip() or "all"
            for index, (candidate, _label) in enumerate(DOCUMENT_SCOPE_MODE_OPTIONS):
                if candidate == normalized:
                    self._mode_control.set_current_index(index)
                    break
            else:
                self._mode_control.set_current_index(0)
            selected = {str(role or "").strip() for role in selected_roles or ()}
            for role_id, checkbox in self._role_checks.items():
                checkbox.setChecked(role_id in selected)
            self._sync_role_visibility()
        finally:
            self._is_syncing = False

    def mode(self) -> str:
        return str(self._mode_control.current_data() or "all")

    def selected_roles(self) -> list[str]:
        return [
            role_id
            for role_id, checkbox in self._role_checks.items()
            if checkbox.isChecked()
        ]

    def _emit_scope_changed(self, *_args) -> None:
        if (
            not self._is_syncing
            and self.mode() == "selected"
            and not self.selected_roles()
            and "body" in self._role_checks
        ):
            self._is_syncing = True
            try:
                self._role_checks["body"].setChecked(True)
            finally:
                self._is_syncing = False
        self._sync_role_visibility()
        if not self._is_syncing:
            self.scope_changed.emit(self.mode(), self.selected_roles())

    def _sync_role_visibility(self) -> None:
        self._mode_help.setText(
            DOCUMENT_SCOPE_MODE_HELP.get(
                self.mode(),
                DOCUMENT_SCOPE_MODE_HELP["all"],
            )
        )
        self._roles_widget.setVisible(self.mode() == "selected")

    def _apply_theme(self) -> None:
        theme = get_theme()
        style = build_checkbox_stylesheet(theme)
        self._mode_help.setStyleSheet(f"color:{theme.text_secondary};")
        self._roles_title.setStyleSheet(
            f"color:{theme.text_primary};font-weight:{theme.font_weight_emphasis};"
        )
        self._roles_note.setStyleSheet(f"color:{theme.text_secondary};")
        for checkbox in self._role_checks.values():
            checkbox.setStyleSheet(style)


__all__ = [
    "DOCUMENT_SCOPE_MODE_OPTIONS",
    "DOCUMENT_SCOPE_MODE_HELP",
    "DOCUMENT_SCOPE_ROLE_NOTE",
    "DocumentScopeSection",
]
