"""Reusable section header for editable material-token collections."""

from __future__ import annotations

from src.qt_api import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.sizing import apply_size_class, resolved_control_height
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.icons.catalog import get_icon


class TokenSectionHeader(QFrame):
    """Title, count, optional hint, undo action, and add action in one shell."""

    def __init__(
        self,
        title: str,
        *,
        hint: str = "",
        add_text: str = "",
        icon_name: str = "",
        object_name: str = "token_section_header",
        content_margins: tuple[int, int, int, int] = (0, 0, 0, 0),
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self._icon_name = str(icon_name or "")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*content_margins)
        layout.setSpacing(8)

        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(18, 18)
        self.title_label = QLabel(title, self)
        self.count_label = QLabel("", self)
        self.hint_label = QLabel(hint, self)
        self.undo_button = QPushButton("撤销删除", self)
        self.add_button = QPushButton(add_text, self)

        for label, part in (
            (self.icon_label, "icon"),
            (self.title_label, "title"),
            (self.count_label, "count"),
            (self.hint_label, "hint"),
        ):
            label.setProperty("tokenSectionHeaderPart", part)
        self.icon_label.setVisible(bool(self._icon_name))
        self.hint_label.setVisible(bool(hint))
        self.undo_button.setVisible(False)
        self.add_button.setVisible(bool(add_text))

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.count_label)
        layout.addWidget(self.hint_label)
        layout.addStretch(1)
        layout.addWidget(self.undo_button)
        layout.addWidget(self.add_button)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = get_theme()
        control_height = resolved_control_height(theme, "md")
        margins = self.layout().contentsMargins()
        self.setFixedHeight(control_height + margins.top() + margins.bottom())

        self.icon_label.setVisible(bool(self._icon_name))
        if self._icon_name:
            self.icon_label.setPixmap(
                get_icon(self._icon_name, 18, theme.primary).pixmap(18, 18)
            )
        self.title_label.setStyleSheet(
            f"font-size: {theme.font_size_lg}px; "
            f"font-weight: {theme.font_weight_emphasis}; color: {theme.text_primary}; "
            "background: transparent; border: none;"
        )
        metadata_style = (
            f"font-size: {theme.font_size_sm}px; color: {theme.text_secondary}; "
            "background: transparent; border: none; padding: 0;"
        )
        self.count_label.setStyleSheet(metadata_style)
        self.hint_label.setStyleSheet(metadata_style)
        for button, variant in (
            (self.undo_button, "ghost-primary"),
            (self.add_button, "secondary"),
        ):
            apply_size_class(button, "md")
            apply_button_variant(button, variant)
            button.setStyleSheet(build_button_stylesheet(theme))


__all__ = ["TokenSectionHeader"]
