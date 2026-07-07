"""Reusable evidence list and action bar widgets."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from src.qt_api import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSize,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)

from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.theme import bind_theme, get_theme


@dataclass(frozen=True, slots=True)
class EvidenceLineItem:
    """One human-readable evidence row with an optional action."""

    kind: str
    label: str
    text: str
    action_type: str = ""
    action_value: str = ""
    action_label: str = ""
    tone: str = "neutral"

    def has_action(self) -> bool:
        return bool(self.action_type and self.action_value)

    def display_text(self) -> str:
        if self.text:
            return f"{self.label}：{self.text}"
        return self.label


class EvidenceActionBar(QWidget):
    """Compact action row for evidence-related navigation and artifacts."""

    action_requested = Signal(str, str)

    def __init__(self, *, parent=None) -> None:
        super().__init__(parent)
        self._items: list[EvidenceLineItem] = []
        self._buttons: dict[str, QPushButton] = {}
        self.setObjectName("shared_evidence_action_bar")

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.addStretch(1)
        self.setVisible(False)

    def set_actions(self, items: Iterable[EvidenceLineItem]) -> None:
        actions = [item for item in items if item.has_action()]
        self._items = _dedupe_evidence_actions(actions)
        self._rebuild()
        self.setVisible(bool(self._items))

    def clear(self) -> None:
        self.set_actions(())

    def current_actions(self) -> list[tuple[str, str, str]]:
        return [
            (item.kind, item.action_type, item.action_value)
            for item in self._items
        ]

    def button_for_action_type(self, action_type: str) -> QPushButton | None:
        return self._buttons.get(str(action_type or "").strip())

    def _rebuild(self) -> None:
        self._buttons.clear()
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        for line in self._items:
            button = QPushButton(line.action_label or _default_evidence_action_label(line), self)
            button.setObjectName(f"shared_evidence_action_btn_{line.action_type}")
            button.setCursor(Qt.PointingHandCursor)
            button.setIconSize(QSize(16, 16))
            button.setToolTip(f"{button.text()}：{line.action_value}")
            button.setStyleSheet(
                build_button_stylesheet(
                    get_theme(),
                    selector="QPushButton",
                    min_height=28,
                    padding_x=12,
                    padding_y=3,
                    font_size=get_theme().font_size_sm,
                )
            )
            apply_button_variant(button, "secondary")
            button.clicked.connect(
                lambda _checked=False, action=line.action_type, value=line.action_value: (
                    self.action_requested.emit(action, value)
                )
            )
            self._layout.insertWidget(max(0, self._layout.count() - 1), button, 0)
            self._buttons.setdefault(line.action_type, button)


class EvidenceLineList(QWidget):
    """Structured evidence rows used by compact detail panes."""

    action_requested = Signal(str, str)

    def __init__(self, *, show_inline_actions: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._items: list[EvidenceLineItem] = []
        self._rows: list[QWidget] = []
        self._show_inline_actions = bool(show_inline_actions)
        self.setObjectName("shared_evidence_line_list")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        self._apply_theme()
        bind_theme(self, self._apply_theme)
        self.setVisible(False)

    def set_items(self, items: Iterable[EvidenceLineItem]) -> None:
        self._items = [item for item in items if item.label or item.text]
        self._rebuild()
        self.setVisible(bool(self._items))

    def clear(self) -> None:
        self.set_items(())

    def current_items(self) -> list[EvidenceLineItem]:
        return list(self._items)

    def line_count(self) -> int:
        return len(self._items)

    def text_at(self, index: int) -> str:
        return self._items[index].display_text()

    def _rebuild(self) -> None:
        self._rows.clear()
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        for line in self._items:
            row = _EvidenceLineRow(
                line,
                show_action=self._show_inline_actions,
                parent=self,
            )
            row.action_requested.connect(self.action_requested.emit)
            self._layout.addWidget(row)
            self._rows.append(row)

    def _apply_theme(self) -> None:
        self.setStyleSheet("background: transparent;")


class _EvidenceLineRow(QFrame):
    action_requested = Signal(str, str)

    def __init__(
        self,
        item: EvidenceLineItem,
        *,
        show_action: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._item = item
        self.setObjectName("shared_evidence_line_row")
        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        self._label = QLabel(item.label, self)
        self._label.setObjectName("shared_evidence_line_label")
        self._label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._label.setMinimumWidth(72)
        self._label.setWordWrap(False)
        layout.addWidget(self._label, 0)

        self._body = QLabel(item.text, self)
        self._body.setObjectName("shared_evidence_line_text")
        self._body.setWordWrap(True)
        self._body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._body, 1)

        if show_action and item.has_action():
            self._action_btn = QPushButton(
                item.action_label or _default_evidence_action_label(item),
                self,
            )
            self._action_btn.setObjectName("shared_evidence_line_action")
            self._action_btn.setCursor(Qt.PointingHandCursor)
            self._action_btn.setToolTip(f"{self._action_btn.text()}：{item.action_value}")
            self._action_btn.clicked.connect(
                lambda _checked=False: self.action_requested.emit(
                    item.action_type,
                    item.action_value,
                )
            )
            apply_button_variant(self._action_btn, "ghost-primary")
            layout.addWidget(self._action_btn, 0)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        tone_color = {
            "primary": t.primary,
            "info": t.info,
            "success": t.success,
            "warning": t.warning,
            "error": t.error,
            "neutral": t.text_secondary,
        }.get(self._item.tone, t.text_secondary)
        self.setStyleSheet(
            f"""
            QFrame#shared_evidence_line_row {{
                background: {t.bg_input};
                border: 1px solid {t.border_light};
                border-radius: {t.radius_sm}px;
            }}
            QLabel#shared_evidence_line_label {{
                color: {t.text_hint};
                font-size: {t.font_size_sm}px;
                font-weight: {t.font_weight_emphasis};
                background: transparent;
            }}
            QLabel#shared_evidence_line_text {{
                color: {tone_color};
                font-size: {t.font_size_sm}px;
                background: transparent;
            }}
            """
        )


def _dedupe_evidence_actions(
    items: Iterable[EvidenceLineItem],
) -> list[EvidenceLineItem]:
    seen: set[tuple[str, str]] = set()
    result: list[EvidenceLineItem] = []
    for item in items:
        key = (item.action_type, item.action_value)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _default_evidence_action_label(item: EvidenceLineItem) -> str:
    action_type = str(item.action_type or "").strip()
    if action_type == "navigate_parameter":
        return "定位参数"
    if action_type == "open_output":
        return "打开输出"
    if action_type == "open_replacement":
        return "打开来源"
    return "打开证据"


__all__ = ["EvidenceActionBar", "EvidenceLineItem", "EvidenceLineList"]
