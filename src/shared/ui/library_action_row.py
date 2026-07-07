"""Shared library-selector action row used by template and scene overview cards."""

from __future__ import annotations

from src.qt_api import QHBoxLayout, QPushButton, QSize, QSizePolicy, QWidget, Qt

from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.flow_layout import FlowLayout
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.theme import bind_theme, get_theme


class LibraryActionRow(QWidget):
    """Responsive action row with left-side actions and a right-side danger action."""

    def __init__(
        self,
        parent=None,
        *,
        object_name: str = "",
        top_margin: int = 8,
        spacing: int = 8,
    ):
        super().__init__(parent)
        self._style_object_name = object_name or f"library_action_row_{id(self)}"
        self.setObjectName(self._style_object_name)
        self._buttons: dict[str, QPushButton] = {}
        self._variants: dict[str, str] = {}
        self._icons: dict[str, str] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, top_margin, 0, 0)
        layout.setSpacing(spacing)

        self._left_actions = QWidget(self)
        self._left_actions.setObjectName(f"{self._style_object_name}_left")
        self._left_actions.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._left_layout = FlowLayout(self._left_actions, h_spacing=spacing, v_spacing=spacing)
        self._left_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._left_actions, 1)

        self._right_actions = QWidget(self)
        self._right_actions.setObjectName(f"{self._style_object_name}_right")
        self._right_actions.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        self._right_layout = FlowLayout(self._right_actions, h_spacing=spacing, v_spacing=spacing)
        self._right_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._right_actions, 0, Qt.AlignTop | Qt.AlignRight)

        bind_theme(self, self.apply_theme)

    def add_action(
        self,
        key: str,
        text: str,
        *,
        object_name: str = "",
        icon_name: str = "",
        variant: str = "secondary",
        side: str = "left",
        callback=None,
    ) -> QPushButton:
        button = QPushButton(text, self)
        if object_name:
            button.setObjectName(object_name)
        if callback is not None:
            button.clicked.connect(callback)

        font = button.font()
        font.setBold(True)
        button.setFont(font)
        button.setIconSize(QSize(16, 16))
        button.setCursor(Qt.PointingHandCursor)

        self._buttons[key] = button
        self._variants[key] = variant
        self._icons[key] = icon_name

        if side == "right":
            self._right_layout.addWidget(button)
        else:
            self._left_layout.addWidget(button)
        self.apply_theme()
        return button

    def button(self, key: str) -> QPushButton:
        return self._buttons[key]

    def apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QWidget#{self.objectName()},
            QWidget#{self._left_actions.objectName()},
            QWidget#{self._right_actions.objectName()} {{
                background: transparent;
                border: none;
            }}
            """
        )
        stylesheet = build_button_stylesheet(theme)
        for key, button in self._buttons.items():
            apply_button_variant(button, self._variants.get(key, "secondary"))
            apply_size_class(button, "md")
            button.setStyleSheet(stylesheet)
        try:
            from src.ui.icons.catalog import get_icon

            for key, button in self._buttons.items():
                icon_name = self._icons.get(key, "")
                if not icon_name:
                    continue
                color = theme.error if self._variants.get(key) == "ghost-danger" else theme.primary
                button.setIcon(get_icon(icon_name, 16, color))
        except Exception:
            pass


__all__ = ["LibraryActionRow"]
