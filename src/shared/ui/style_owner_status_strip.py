"""Compact owner-status strip shared by template and scene style panes."""

from __future__ import annotations

from src.qt_api import QLabel, QHBoxLayout, QSizePolicy, QWidget
from src.shared.ui.theme import bind_theme, get_theme


class StyleOwnerStatusStrip(QWidget):
    """Show where a style comes from, what it affects, and whether it can edit."""

    _ORDER = (
        ("source", "来源"),
        ("scope", "影响"),
        ("edit", "编辑"),
    )

    def __init__(
        self,
        parent=None,
        *,
        object_name_prefix: str = "style_owner_status",
    ) -> None:
        super().__init__(parent)
        prefix = str(object_name_prefix or "style_owner_status").strip()
        self.setObjectName(prefix)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._labels: dict[str, QLabel] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for key, label in self._ORDER:
            widget = QLabel(f"{label}：-", self)
            widget.setObjectName(f"{prefix}_{key}")
            widget.setWordWrap(True)
            self._labels[key] = widget
            layout.addWidget(widget, 1)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    @property
    def source_label(self) -> QLabel:
        return self._labels["source"]

    @property
    def scope_label(self) -> QLabel:
        return self._labels["scope"]

    @property
    def edit_label(self) -> QLabel:
        return self._labels["edit"]

    def apply_owner_state(self, owner_state) -> None:
        surface_state = owner_state.surface_state
        source = (
            str(getattr(owner_state, "source_status", "") or "").strip()
            or str(getattr(surface_state, "source_label", "") or "").strip()
            or "-"
        )
        scope = (
            str(getattr(owner_state, "scope_status", "") or "").strip()
            or _fallback_scope_label(str(getattr(surface_state, "owner_kind", "") or ""))
        )
        edit = (
            str(getattr(owner_state, "edit_status", "") or "").strip()
            or ("可编辑" if bool(getattr(surface_state, "editable", False)) else "不可编辑")
        )
        self.set_status(source=source, scope=scope, edit=edit)

    def set_status(self, *, source: str, scope: str, edit: str) -> None:
        values = {
            "source": str(source or "-").strip() or "-",
            "scope": str(scope or "-").strip() or "-",
            "edit": str(edit or "-").strip() or "-",
        }
        for key, title in self._ORDER:
            self._labels[key].setText(f"{title}：{values[key]}")
            self.setProperty(f"style_owner_{key}_status", values[key])

    def apply_theme(self) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        style = (
            f"font-size: {theme.font_size_sm}px; "
            f"color: {theme.text_secondary}; "
            f"background: {theme.bg_card}; "
            f"border: 1px solid {theme.border}; "
            f"border-radius: {theme.radius_sm}px; "
            "padding: 5px 8px;"
        )
        for label in self._labels.values():
            label.setStyleSheet(style)


def _fallback_scope_label(owner_kind: str) -> str:
    if owner_kind == "template_body_style":
        return "模板全局"
    return "-"


__all__ = ["StyleOwnerStatusStrip"]
