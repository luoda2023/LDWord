from __future__ import annotations

from src.qt_api import QFrame, QHBoxLayout, QLabel, QSize, QVBoxLayout, QWidget

from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.theme import bind_theme, get_theme


class DesignSystemCard(RoundedSurfaceFrame):
    """Shared card primitive for content, navigation, and workbench surfaces."""

    def __init__(self, title: str = "", *, parent=None):
        super().__init__(parent=parent)
        self._surface_background_override: str | None = None
        self._surface_border_override: str | None = None
        self._surface_border_width_override: float | None = None
        # Content cards render directly. QGraphicsEffect on a QWidget applies
        # to all descendants and changes text/line compositing.
        self._shadow_enabled = False
        self._show_header_separator = False

        self._layout = QVBoxLayout(self)
        self._header_widget: QWidget | None = None
        self._header_layout: QHBoxLayout | None = None
        self._header_icon_label: QLabel | None = None
        self._header_icon_name: str | None = None
        self._header_actions_layout: QHBoxLayout | None = None
        self._title_label: QLabel | None = None
        self._description_label: QLabel | None = None
        self._sep: QFrame | None = None

        self._content_layout = QVBoxLayout()
        self._layout.addLayout(self._content_layout)
        if title:
            self.set_header(title)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_card_surface(
        self,
        *,
        background: str | None = None,
        border_color: str | None = None,
        border_width: float | None = None,
        shadow: bool | None = None,
    ) -> None:
        self._surface_background_override = background
        self._surface_border_override = border_color
        self._surface_border_width_override = border_width
        if shadow is not None:
            self._shadow_enabled = bool(shadow)
        self._apply_theme()

    def set_header(
        self,
        title: str,
        *,
        icon_name: str | None = None,
        show_separator: bool | None = None,
    ) -> QLabel:
        if self._header_widget is None:
            self._header_widget = QWidget(self)
            self._header_layout = QHBoxLayout(self._header_widget)
            self._header_layout.setContentsMargins(0, 0, 0, 0)
            self._header_layout.setSpacing(6)

            self._header_icon_label = QLabel(self._header_widget)
            self._header_icon_label.setFixedSize(18, 18)
            self._header_layout.addWidget(self._header_icon_label)

            self._title_label = QLabel(self._header_widget)
            self._header_layout.addWidget(self._title_label)
            self._header_layout.addStretch(1)

            self._header_actions_layout = QHBoxLayout()
            self._header_actions_layout.setContentsMargins(0, 0, 0, 0)
            self._header_actions_layout.setSpacing(8)
            self._header_layout.addLayout(self._header_actions_layout)

            self._layout.insertWidget(0, self._header_widget)
            self._sep = QFrame(self)
            self._sep.setFrameShape(QFrame.HLine)
            self._layout.insertWidget(1, self._sep)

        if show_separator is not None:
            self._show_header_separator = bool(show_separator)
        self._header_icon_name = icon_name
        assert self._title_label is not None
        self._title_label.setText(title)
        self._apply_theme()
        return self._title_label

    def set_description(self, text: str) -> QLabel:
        if self._description_label is None:
            self._description_label = QLabel(self)
            self._description_label.setWordWrap(True)
            insert_at = 2 if self._header_widget is not None else 0
            self._layout.insertWidget(insert_at, self._description_label)
        self._description_label.setText(text)
        self._apply_theme()
        return self._description_label

    def add_header_action(self, widget: QWidget) -> None:
        if self._header_widget is None:
            self.set_header("")
        assert self._header_actions_layout is not None
        self._header_actions_layout.addWidget(widget)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._layout.setContentsMargins(t.card_padding_x, t.card_padding_top, t.card_padding_x, t.card_padding_bottom)
        self._layout.setSpacing(t.card_spacing)
        self._content_layout.setSpacing(t.card_content_spacing)

        self.configure_surface(
            background=self._surface_background_override or t.bg_card,
            radius=t.radius_md,
            border_color=(
                self._surface_border_override
                if self._surface_border_override is not None
                else t.border_light
            ),
            border_width=(
                self._surface_border_width_override
                if self._surface_border_width_override is not None
                else 1.0
            ),
        )

        # A requested shadow is represented by a stronger border until a
        # parent-owned background-only elevation layer is needed. Never attach
        # a graphics effect to a card that owns text children.
        if self._shadow_enabled and self._surface_border_width_override is None:
            self._border_width = max(self._border_width, 1.0)

        if self._title_label:
            self._title_label.setStyleSheet(
                f"font-size: {t.font_size_lg}px; "
                f"font-weight: {t.font_weight_emphasis}; "
                f"color: {t.primary}; "
                f"background: transparent;"
            )
        if self._header_icon_label:
            self._header_icon_label.setVisible(bool(self._header_icon_name))
            if self._header_icon_name:
                from src.shared.ui.icons.catalog import get_icon

                self._header_icon_label.setPixmap(
                    get_icon(self._header_icon_name, 18, t.primary).pixmap(18, 18)
                )
        if self._description_label:
            self._description_label.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
            )
        if self._sep:
            self._sep.setVisible(self._show_header_separator)
            self._sep.setStyleSheet(f"background: {t.divider}; max-height: 1px;")

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._content_layout.addLayout(layout)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API contract
        return self._layout.sizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API contract
        return self._layout.minimumSize()


__all__ = ["DesignSystemCard"]
