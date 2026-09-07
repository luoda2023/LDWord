"""Markdown workspace for opening, editing, and exporting standalone files.

The application owns Markdown persistence and DOCX export.  AI-authored
long documents are edited in the right-side embedded MarkText editor inside
the AI assistant; this panel handles standalone ``.md`` files.
"""

from __future__ import annotations

from pathlib import Path

from src.qt_api import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
    Qt,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.markdown_preview import MarkdownPreview
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.typography_policy import TextRole, apply_text_role
from src.ui.base_panel import BasePanel

_MARKDOWN_FILTER = "Markdown (*.md *.markdown);;All files (*.*)"


class MarkTextPanel(BasePanel):
    """Edit generated Markdown and export its structured content as DOCX."""

    panel_title = "MarkText 文档"
    panel_icon = "table"

    def __init__(self, bridge, parent=None) -> None:
        self._current_path = ""
        self._dirty = False
        super().__init__(bridge, parent)

    def _setup_ui(self) -> None:
        self.setObjectName("MarkTextPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QFrame(self)
        toolbar.setObjectName("marktext_toolbar")
        toolbar.setFixedHeight(54)
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(16, 8, 14, 8)
        bar.setSpacing(8)
        title = QLabel("MarkText 文档", toolbar)
        title.setObjectName("marktext_title")
        apply_text_role(title, TextRole.NAVIGATION_TITLE_ACTIVE)
        bar.addWidget(title)
        self._path_label = QLabel("未保存的 Markdown", toolbar)
        self._path_label.setObjectName("marktext_path")
        self._path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        apply_text_role(self._path_label, TextRole.CAPTION)
        bar.addWidget(self._path_label, 1)

        self._new_button = QPushButton("新建", toolbar)
        self._open_button = QPushButton("打开 Markdown", toolbar)
        self._save_button = QPushButton("保存", toolbar)
        self._export_button = QPushButton("导出 DOCX", toolbar)
        for button in (self._new_button, self._open_button, self._save_button):
            apply_button_variant(button, "secondary")
            button.setCursor(Qt.PointingHandCursor)
            bar.addWidget(button)
        apply_button_variant(self._export_button, "primary")
        self._export_button.setCursor(Qt.PointingHandCursor)
        bar.addWidget(self._export_button)
        root.addWidget(toolbar)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setObjectName("marktext_splitter")
        self._editor = QPlainTextEdit(splitter)
        self._editor.setObjectName("marktext_editor")
        self._editor.setPlaceholderText("在这里粘贴或编写 Markdown。AI 生成的 | 表格 | 会在右侧完整预览。")
        self._editor.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self._preview = MarkdownPreview(parent=splitter)
        splitter.addWidget(self._editor)
        splitter.addWidget(self._preview)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([560, 620])
        root.addWidget(splitter, 1)

        self._new_button.clicked.connect(self._new_document)
        self._open_button.clicked.connect(self._choose_open)
        self._save_button.clicked.connect(self._save_markdown)
        self._export_button.clicked.connect(self._export_docx)
        self._editor.textChanged.connect(self._on_editor_changed)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _connect_signals(self) -> None:
        return None

    def handle_navigation_intent(self, intent) -> None:
        from src.ui.bridge import navigation_intent_value

        payload = navigation_intent_value(intent, "payload", {})
        if not isinstance(payload, dict):
            return
        path_text = str(payload.get("open_path") or "")
        if path_text:
            self.open_path(path_text)

    def open_path(self, path_text: str) -> None:
        path = Path(str(path_text or "")).expanduser()
        if not path.is_file():
            self._show_warning("无法打开", f"文件不存在：{path}")
            return
        if path.suffix.casefold() not in {".md", ".markdown", ".txt"}:
            self._show_warning("仅支持 Markdown", "请先将内容保存或转换为 .md 后使用 MarkText 编辑。")
            return
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            self._show_warning("无法读取", str(exc))
            return
        self._editor.blockSignals(True)
        self._editor.setPlainText(text)
        self._editor.blockSignals(False)
        self._current_path = str(path.resolve())
        self._dirty = False
        self._refresh_path_label()
        self._preview.set_markdown(text)

    def _new_document(self) -> None:
        self._editor.blockSignals(True)
        self._editor.clear()
        self._editor.blockSignals(False)
        self._current_path = ""
        self._dirty = False
        self._preview.clear()
        self._refresh_path_label()
        self._editor.setFocus()

    def _choose_open(self) -> None:
        path_text, _ = QFileDialog.getOpenFileName(self, "打开 Markdown", "", _MARKDOWN_FILTER)
        if path_text:
            self.open_path(path_text)

    def _save_markdown(self) -> Path | None:
        target = Path(self._current_path) if self._current_path else None
        if target is None:
            path_text, _ = QFileDialog.getSaveFileName(
                self,
                "保存 Markdown",
                "未命名文档.md",
                _MARKDOWN_FILTER,
            )
            if not path_text:
                return None
            target = Path(path_text)
            if target.suffix.casefold() not in {".md", ".markdown"}:
                target = target.with_suffix(".md")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self._editor.toPlainText(), encoding="utf-8", newline="\n")
        except OSError as exc:
            self._show_warning("保存失败", str(exc))
            return None
        self._current_path = str(target.resolve())
        self._dirty = False
        self._refresh_path_label()
        return target

    def _export_docx(self) -> None:
        markdown = self._editor.toPlainText()
        if not markdown.strip():
            self._show_warning("没有内容", "请先输入 Markdown 内容。")
            return
        suggested = "未命名文档.docx"
        if self._current_path:
            suggested = str(Path(self._current_path).with_suffix(".docx"))
        path_text, _ = QFileDialog.getSaveFileName(
            self,
            "导出 DOCX",
            suggested,
            "Word 文档 (*.docx)",
        )
        if not path_text:
            return
        try:
            from src.services.markdown_docx_export import export_markdown_to_docx

            output = export_markdown_to_docx(markdown, path_text)
        except Exception as exc:  # noqa: BLE001 - UI export boundary
            self._show_warning("导出失败", str(exc))
            return
        from src.shared.ui.toast import Toast

        Toast.show_success(f"已导出 DOCX：{output}")

    def _on_editor_changed(self) -> None:
        text = self._editor.toPlainText()
        self._preview.set_markdown(text)
        self._dirty = True
        self._refresh_path_label()

    def _refresh_path_label(self) -> None:
        if self._current_path:
            suffix = " *" if self._dirty else ""
            self._path_label.setText(Path(self._current_path).name + suffix)
            self._path_label.setToolTip(self._current_path)
        else:
            self._path_label.setText("未保存的 Markdown" + (" *" if self._dirty else ""))
            self._path_label.setToolTip("")

    def _show_warning(self, title: str, message: str) -> None:
        from src.shared.ui.dialogs import warning

        warning(title, message, parent=self)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QFrame#marktext_toolbar {{
                background: {theme.bg_card};
                border-bottom: 1px solid {theme.divider};
            }}
            QLabel#marktext_title {{ color: {theme.text_primary}; background: transparent; }}
            QLabel#marktext_path {{ color: {theme.text_hint}; background: transparent; }}
            QPlainTextEdit#marktext_editor {{
                background: {theme.bg_window};
                color: {theme.text_primary};
                border: none;
                border-right: 1px solid {theme.divider};
                padding: 16px;
                font-family: Consolas, "Microsoft YaHei UI";
                font-size: {theme.font_size_md}px;
                selection-background-color: {theme.primary_light};
            }}
            QSplitter#marktext_splitter::handle {{ background: {theme.divider}; width: 1px; }}
            """
        )


__all__ = ["MarkTextPanel"]
