"""Dedicated project and third-party license readers."""

from __future__ import annotations

from src.app_meta import APP_DISPLAY_NAME, APP_VERSION
from src.qt_api import (
    QHBoxLayout,
    QSize,
    QSizePolicy,
    QTextBlockFormat,
    QTextCursor,
    QTextEdit,
    QWidget,
    Qt,
)
from src.services.license_catalog import LicenseCatalog
from src.shared.ui.preview_dialog import PreviewShellDialog
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.typography_policy import (
    LATIN_UI_FONT_FAMILIES,
    build_font,
)


_COMPONENT_SEPARATOR = "\n\n---\n\n"


class _LicenseTextView(QTextEdit):
    """A single selectable, consistently typeset legal-text surface."""

    def __init__(self, *, embedded: bool, parent=None) -> None:
        super().__init__(parent)
        self._embedded = bool(embedded)
        self.setObjectName("license_text_view")
        self.setProperty("embeddedLicenseReader", self._embedded)
        self.setReadOnly(True)
        self.setAcceptRichText(False)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        self.document().setDocumentMargin(28)
        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def set_license_text(self, text: str) -> None:
        self.setPlainText(str(text or "").replace("\r\n", "\n"))
        self._apply_text_layout()
        cursor = self.textCursor()
        cursor.setPosition(0)
        self.setTextCursor(cursor)
        self.verticalScrollBar().setValue(0)

    def _apply_text_layout(self) -> None:
        cursor = QTextCursor(self.document())
        cursor.select(QTextCursor.Document)
        block_format = QTextBlockFormat()
        block_format.setLineHeight(
            138.0,
            int(QTextBlockFormat.ProportionalHeight.value),
        )
        cursor.mergeBlockFormat(block_format)
        cursor.clearSelection()

    def _apply_theme(self) -> None:
        theme = get_theme()
        legal_font = build_font(
            LATIN_UI_FONT_FAMILIES,
            pixel_size=max(14, theme.font_size_md),
            weight=theme.font_weight_normal,
        )
        self.setFont(legal_font)
        self.document().setDefaultFont(legal_font)
        self.setStyleSheet(
            f"""
            QTextEdit#license_text_view {{
                color: {theme.text_primary};
                background: {theme.bg_card};
                border: {'none' if self._embedded else f'1px solid {theme.border_light}'};
                border-radius: {theme.radius_md}px;
                padding: 0;
                selection-background-color: {theme.primary_light};
                selection-color: {theme.text_primary};
            }}
            QTextEdit#license_text_view QScrollBar:vertical {{
                background: {theme.scrollbar_track};
                width: 10px;
                margin: 5px 2px 5px 0;
            }}
            QTextEdit#license_text_view QScrollBar::handle:vertical {{
                background: {theme.scrollbar_thumb};
                border-radius: 4px;
                min-height: 36px;
            }}
            QTextEdit#license_text_view QScrollBar::handle:vertical:hover {{
                background: {theme.scrollbar_thumb_hover};
            }}
            QTextEdit#license_text_view QScrollBar::add-line:vertical,
            QTextEdit#license_text_view QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QTextEdit#license_text_view QScrollBar::add-page:vertical,
            QTextEdit#license_text_view QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QTextEdit#license_text_view QScrollBar::up-arrow:vertical,
            QTextEdit#license_text_view QScrollBar::down-arrow:vertical {{
                width: 0;
                height: 0;
            }}
            """
        )
        if self.toPlainText():
            self._apply_text_layout()


def _compose_third_party_text(catalog: LicenseCatalog) -> str:
    """Compose a concise notice index; verbatim sources remain in the bundle."""

    component_sections: list[str] = []
    for component in catalog.components:
        heading = " · ".join(
            part
            for part in (
                component.name,
                component.version,
                component.display_license,
            )
            if part
        )
        section_lines = [heading]
        if component.homepage:
            section_lines.append(component.homepage)
        if component.note:
            section_lines.extend(("", component.note))
        component_sections.append("\n".join(section_lines))

    raw_notice = (
        "完整许可原文\n"
        "未经修改的许可与归属声明已随安装包提供，位于 licenses/ 目录。"
    )
    component_sections.append(raw_notice)
    return _COMPONENT_SEPARATOR.join(component_sections).rstrip() + "\n"


class LicenseDialog(PreviewShellDialog):
    """One shared shell with a single continuous reader in both modes."""

    PROJECT = "project"
    THIRD_PARTY = "third_party"

    def __init__(
        self,
        *,
        mode: str,
        project_text: str = "",
        catalog: LicenseCatalog | None = None,
        parent=None,
    ) -> None:
        self._mode = mode
        self._catalog = catalog
        if mode == self.PROJECT:
            title = "本软件许可"
            subtitle = f"{APP_DISPLAY_NAME} {APP_VERSION} · MIT License"
            preferred_size = QSize(780, 640)
        elif mode == self.THIRD_PARTY and catalog is not None:
            title = "第三方组件"
            subtitle = f"许可概要 · {catalog.component_count} 项"
            preferred_size = QSize(940, 680)
        else:
            raise ValueError("LicenseDialog requires a valid mode and catalog")

        super().__init__(
            title=title,
            subtitle=subtitle,
            preferred_size=preferred_size,
            parent=parent,
        )
        self.setObjectName("license_dialog")
        if mode == self.PROJECT:
            self._build_project_reader(project_text)
        else:
            self._build_third_party_reader(catalog)
        self._apply_theme()

    @classmethod
    def for_project(cls, text: str, *, parent=None) -> "LicenseDialog":
        return cls(mode=cls.PROJECT, project_text=text, parent=parent)

    @classmethod
    def for_third_party(
        cls,
        catalog: LicenseCatalog,
        *,
        parent=None,
    ) -> "LicenseDialog":
        return cls(mode=cls.THIRD_PARTY, catalog=catalog, parent=parent)

    def _build_project_reader(self, text: str) -> None:
        self._project_reader_wrap = self._build_reader_wrap(
            object_name="project_license_reader_wrap"
        )
        self.project_viewer = _LicenseTextView(
            embedded=False,
            parent=self._project_reader_wrap,
        )
        self.project_viewer.setMinimumWidth(640)
        self.project_viewer.setMaximumWidth(760)
        self.project_viewer.set_license_text(text)
        self._finish_reader_wrap(
            self._project_reader_wrap,
            self.project_viewer,
            centered=True,
        )

    def _build_third_party_reader(self, catalog: LicenseCatalog) -> None:
        self._third_party_reader_wrap = self._build_reader_wrap(
            object_name="third_party_license_reader_wrap"
        )
        self.third_party_viewer = _LicenseTextView(
            embedded=False,
            parent=self._third_party_reader_wrap,
        )
        self.third_party_viewer.setMinimumWidth(760)
        self.third_party_viewer.setMaximumWidth(1120)
        self.third_party_viewer.set_license_text(_compose_third_party_text(catalog))
        self._finish_reader_wrap(
            self._third_party_reader_wrap,
            self.third_party_viewer,
            centered=False,
        )

    def _build_reader_wrap(self, *, object_name: str) -> QWidget:
        wrap = QWidget(self._surface)
        wrap.setObjectName(object_name)
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(18, 2, 18, 6)
        layout.setSpacing(0)
        return wrap

    def _finish_reader_wrap(
        self,
        wrap: QWidget,
        viewer: _LicenseTextView,
        *,
        centered: bool,
    ) -> None:
        viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = wrap.layout()
        if centered:
            layout.addStretch(1)
        layout.addWidget(viewer, 1)
        if centered:
            layout.addStretch(1)
        self._surface_layout.addWidget(wrap, 1)

    def _apply_theme(self) -> None:
        self._apply_shell_theme("")


__all__ = ["LicenseDialog"]
