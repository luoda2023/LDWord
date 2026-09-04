"""Reusable Design-style file components for the assistant conversation."""

from __future__ import annotations

from src.assistant.ui.conversation_presentation import (
    FilePresentation,
    project_file_reference,
)
from src.assistant.ui.design_tokens import TOKENS
from src.qt_api import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.icons.catalog import get_icon


def _file_icon_name(file: FilePresentation) -> str:
    return {
        "image": "image",
        "link": "globe",
        "folder": "folder-open",
    }.get(file.kind, "file-text")


class _ElidingLabel(QLabel):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self._full_text = str(text or "")
        self.setText(self._full_text)
        self.setToolTip(self._full_text)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.setText(
            self.fontMetrics().elidedText(
                self._full_text,
                Qt.ElideRight,
                max(1, self.width()),
            )
        )


class AssistantComposerAttachmentChip(QFrame):
    """34px composer attachment chip for LDWord composer geometry."""

    remove_requested = Signal()
    reference_requested = Signal(object)

    def __init__(self, reference: dict[str, object], parent=None) -> None:
        super().__init__(parent)
        self.file = project_file_reference(reference)
        self.setObjectName("assistant_composer_attachment_chip")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(TOKENS.composer_attachment_height)
        self.setMaximumWidth(TOKENS.composer_attachment_max_width)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(f"附件：{self.file.title}")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 7, 0)
        layout.setSpacing(7)
        self._icon = QLabel(self)
        self._icon.setObjectName("assistant_composer_attachment_icon")
        self._icon.setFixedSize(16, 16)
        self._icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon)
        self._title = _ElidingLabel(self.file.title, self)
        self._title.setObjectName("assistant_composer_attachment_title")
        self._title.setMinimumWidth(80)
        self._title.setMaximumWidth(154)
        self._title.setToolTip(self.file.target)
        layout.addWidget(self._title)
        self._suffix = QLabel(self.file.suffix, self)
        self._suffix.setObjectName("assistant_composer_attachment_suffix")
        self._suffix.setFixedHeight(22)
        layout.addWidget(self._suffix)
        self._remove = QToolButton(self)
        self._remove.setObjectName("assistant_composer_attachment_remove")
        self._remove.setFixedSize(20, 20)
        self._remove.setAccessibleName(f"移除附件 {self.file.title}")
        self._remove.setCursor(Qt.PointingHandCursor)
        self._remove.clicked.connect(self.remove_requested.emit)
        layout.addWidget(self._remove)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if (
            event.button() == Qt.LeftButton
            and self.rect().contains(event.position().toPoint())
            and not self._remove.geometry().contains(event.position().toPoint())
        ):
            self.reference_requested.emit(dict(self.file.reference))
        super().mouseReleaseEvent(event)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._icon.setPixmap(
            get_icon(_file_icon_name(self.file), 15, theme.icon_accent).pixmap(15, 15)
        )
        self._remove.setIcon(get_icon("x", 12, theme.text_hint))
        self.setStyleSheet(
            f"""
            QFrame#assistant_composer_attachment_chip {{
                background: {theme.bg_selected};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
            }}
            QFrame#assistant_composer_attachment_chip:hover {{
                background: {theme.primary_light};
                border-color: {theme.border_focus};
            }}
            QLabel#assistant_composer_attachment_icon,
            QLabel#assistant_composer_attachment_title {{
                color: {theme.text_primary};
                background: transparent;
                border: none;
                font-size: {theme.font_size_sm}px;
            }}
            QLabel#assistant_composer_attachment_suffix {{
                color: {theme.text_secondary};
                background: {theme.bg_window};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_sm}px;
                padding: 0 6px;
                font-size: {theme.font_size_xs}px;
            }}
            QToolButton#assistant_composer_attachment_remove {{
                background: transparent;
                border: none;
                border-radius: 10px;
                padding: 0;
            }}
            QToolButton#assistant_composer_attachment_remove:hover {{
                background: {theme.bg_hover};
            }}
            """
        )


class AssistantAttachmentDropOverlay(QFrame):
    """Transient drop affordance used by both hero and compact composers."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("assistant_attachment_drop_overlay")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(7)
        layout.addStretch(1)
        self._icon = QLabel(self)
        self._icon.setObjectName("assistant_attachment_drop_icon")
        self._icon.setFixedHeight(38)
        self._icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon)
        self._title = QLabel("松开以添加文档材料", self)
        self._title.setObjectName("assistant_attachment_drop_title")
        self._title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title)
        self._caption = QLabel("支持 DOCX、Markdown；单次最多 6 份", self)
        self._caption.setObjectName("assistant_attachment_drop_caption")
        self._caption.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._caption)
        layout.addStretch(1)
        self.hide()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._icon.setPixmap(
            get_icon("file-text", 34, theme.icon_accent).pixmap(34, 34)
        )
        self.setStyleSheet(
            f"""
            QFrame#assistant_attachment_drop_overlay {{
                background: {theme.bg_card};
                border: 2px solid {theme.border_focus};
                border-radius: {theme.radius_lg}px;
            }}
            QLabel#assistant_attachment_drop_icon {{
                background: transparent;
                border: none;
            }}
            QLabel#assistant_attachment_drop_title {{
                color: {theme.text_primary};
                background: transparent;
                border: none;
                font-size: {theme.font_size_lg}px;
                font-weight: {theme.font_weight_emphasis};
            }}
            QLabel#assistant_attachment_drop_caption {{
                color: {theme.text_hint};
                background: transparent;
                border: none;
                font-size: {theme.font_size_sm}px;
            }}
            """
        )


class AssistantMessageFileCard(QFrame):
    """A user attachment preview or an assistant artifact file card."""

    reference_requested = Signal(object)

    def __init__(
        self,
        file: FilePresentation,
        *,
        variant: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        if variant not in {"attachment", "artifact"}:
            raise ValueError(f"Unsupported assistant file-card variant: {variant!r}")
        self.file = file
        self.variant = variant
        self.setObjectName(f"assistant_{variant}_file_card")
        self.setProperty("state", file.state)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor if file.actionable else Qt.ArrowCursor)
        self.setFocusPolicy(Qt.StrongFocus if file.actionable else Qt.NoFocus)
        self.setAccessibleName(
            f"{'附件' if variant == 'attachment' else '产物'}：{file.title}"
        )
        if variant == "attachment":
            self._build_attachment()
        else:
            self._build_artifact()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _build_attachment(self) -> None:
        self.setFixedSize(
            TOKENS.user_attachment_card_width,
            TOKENS.user_attachment_card_height,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 7)
        layout.setSpacing(5)
        self._preview = QFrame(self)
        self._preview.setObjectName("assistant_attachment_preview")
        self._preview.setFixedHeight(58)
        preview_layout = QVBoxLayout(self._preview)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self._icon = QLabel(self._preview)
        self._icon.setObjectName("assistant_file_card_icon")
        self._icon.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self._icon)
        layout.addWidget(self._preview)
        footer = QHBoxLayout()
        footer.setContentsMargins(2, 0, 0, 0)
        footer.setSpacing(5)
        self._title = _ElidingLabel(self.file.title, self)
        self._title.setObjectName("assistant_file_card_title")
        self._title.setToolTip(self.file.target)
        self._title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        footer.addWidget(self._title, 1)
        self._suffix = QLabel(
            "MISSING" if self.file.state == "missing" else self.file.suffix,
            self,
        )
        self._suffix.setObjectName("assistant_file_card_suffix")
        footer.addWidget(self._suffix)
        layout.addLayout(footer)
        self._open = None
        self._subtitle = None

    def _build_artifact(self) -> None:
        self.setFixedHeight(TOKENS.artifact_file_card_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(14)
        self._preview = QFrame(self)
        self._preview.setObjectName("assistant_artifact_icon_box")
        self._preview.setFixedSize(
            TOKENS.artifact_icon_box_size,
            TOKENS.artifact_icon_box_size,
        )
        preview_layout = QVBoxLayout(self._preview)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self._icon = QLabel(self._preview)
        self._icon.setObjectName("assistant_file_card_icon")
        self._icon.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self._icon)
        layout.addWidget(self._preview)
        copy = QVBoxLayout()
        has_subtitle = bool(self.file.subtitle)
        copy.setContentsMargins(
            0,
            7 if has_subtitle else 0,
            0,
            7 if has_subtitle else 0,
        )
        copy.setSpacing(3)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(7)
        self._title = _ElidingLabel(self.file.title, self)
        self._title.setObjectName("assistant_file_card_title")
        self._title.setToolTip(self.file.target)
        title_row.addWidget(self._title, 1)
        self._suffix = QLabel(
            "MISSING" if self.file.state == "missing" else self.file.suffix,
            self,
        )
        self._suffix.setObjectName("assistant_file_card_suffix")
        title_row.addWidget(self._suffix)
        if not has_subtitle:
            copy.addStretch(1)
        copy.addLayout(title_row)
        self._subtitle = QLabel(self.file.subtitle, self)
        self._subtitle.setObjectName("assistant_artifact_subtitle")
        self._subtitle.setVisible(has_subtitle)
        copy.addWidget(self._subtitle)
        if not has_subtitle:
            copy.addStretch(1)
        layout.addLayout(copy, 1)
        self._open = QToolButton(self)
        self._open.setObjectName("assistant_artifact_open")
        self._open.setAccessibleName(f"打开 {self.file.title}")
        self._open.setFixedSize(30, 30)
        self._open.setEnabled(self.file.actionable)
        self._open.setCursor(
            Qt.PointingHandCursor if self.file.actionable else Qt.ArrowCursor
        )
        self._open.clicked.connect(self._request_reference)
        layout.addWidget(self._open)

    def _request_reference(self) -> None:
        if self.file.actionable:
            self.reference_requested.emit(dict(self.file.reference))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if (
            self.file.actionable
            and event.button() == Qt.LeftButton
            and self.rect().contains(event.position().toPoint())
            and (
                self._open is None
                or not self._open.geometry().contains(event.position().toPoint())
            )
        ):
            self._request_reference()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self.file.actionable and event.key() in {
            Qt.Key_Return,
            Qt.Key_Enter,
            Qt.Key_Space,
        }:
            self._request_reference()
            event.accept()
            return
        super().keyPressEvent(event)

    def _apply_theme(self) -> None:
        theme = get_theme()
        muted = self.file.state == "missing"
        icon_color = theme.text_hint if muted else theme.icon_accent
        icon_size = 32 if self.variant == "attachment" else 38
        self._icon.setPixmap(
            get_icon(_file_icon_name(self.file), icon_size, icon_color).pixmap(
                icon_size, icon_size
            )
        )
        if self._open is not None:
            self._open.setIcon(
                get_icon(
                    "eye",
                    16,
                    theme.text_disabled if muted else theme.icon_secondary,
                )
            )
        self.setStyleSheet(
            f"""
            QFrame#assistant_attachment_file_card,
            QFrame#assistant_artifact_file_card {{
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_sm}px;
            }}
            QFrame#assistant_attachment_file_card:hover,
            QFrame#assistant_artifact_file_card:hover {{
                background: {theme.bg_hover};
                border-color: {theme.border_focus};
            }}
            QFrame#assistant_attachment_file_card[state="missing"],
            QFrame#assistant_artifact_file_card[state="missing"] {{
                background: {theme.bg_window};
                border-color: {theme.border_light};
            }}
            QFrame#assistant_attachment_preview,
            QFrame#assistant_artifact_icon_box {{
                background: {theme.bg_window};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_sm}px;
            }}
            QLabel#assistant_file_card_icon {{
                background: transparent;
                border: none;
            }}
            QLabel#assistant_file_card_title {{
                color: {theme.text_primary if not muted else theme.text_hint};
                background: transparent;
                border: none;
                font-size: {theme.font_size_sm}px;
                font-weight: {theme.font_weight_medium};
            }}
            QLabel#assistant_file_card_suffix {{
                color: {theme.text_secondary if not muted else theme.text_hint};
                background: {theme.bg_window};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_sm}px;
                padding: 1px 5px;
                font-size: {theme.font_size_xs}px;
            }}
            QLabel#assistant_artifact_subtitle {{
                color: {theme.text_hint};
                background: transparent;
                border: none;
                font-size: {theme.font_size_sm}px;
            }}
            QToolButton#assistant_artifact_open {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: {theme.radius_sm}px;
            }}
            QToolButton#assistant_artifact_open:hover {{
                background: {theme.bg_hover};
                border-color: {theme.border_light};
            }}
            """
        )


class AssistantAttachmentStrip(QScrollArea):
    """Horizontal user-message attachment preview strip."""

    reference_requested = Signal(object)

    def __init__(self, files: tuple[FilePresentation, ...], parent=None) -> None:
        super().__init__(parent)
        self.files = tuple(files)
        self.setObjectName("assistant_attachment_strip")
        self.setFrameShape(QFrame.NoFrame)
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAsNeeded if len(self.files) > 4 else Qt.ScrollBarAlwaysOff
        )
        self.setFixedHeight(TOKENS.user_attachment_strip_height)
        self.setMaximumWidth(
            min(
                582,
                max(
                    TOKENS.user_attachment_card_width,
                    len(self.files) * (TOKENS.user_attachment_card_width + 10) - 10,
                ),
            )
        )
        self._host = QWidget(self)
        self._host.setObjectName("assistant_attachment_strip_host")
        row = QHBoxLayout(self._host)
        row.setContentsMargins(0, 0, 0, 7)
        row.setSpacing(10)
        self.cards: list[AssistantMessageFileCard] = []
        for file in self.files:
            card = AssistantMessageFileCard(
                file,
                variant="attachment",
                parent=self._host,
            )
            card.reference_requested.connect(self.reference_requested.emit)
            row.addWidget(card)
            self.cards.append(card)
        row.addStretch(1)
        self.setWidget(self._host)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QScrollArea#assistant_attachment_strip,
            QWidget#assistant_attachment_strip_host {{
                background: transparent;
                border: none;
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 7px;
                margin: 0 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {theme.border};
                min-width: 32px;
                border-radius: 3px;
            }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {{
                background: transparent;
                border: none;
                width: 0;
            }}
            """
        )


__all__ = [
    "AssistantAttachmentDropOverlay",
    "AssistantAttachmentStrip",
    "AssistantComposerAttachmentChip",
    "AssistantMessageFileCard",
]
