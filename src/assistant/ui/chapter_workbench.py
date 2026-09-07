# -*- coding: utf-8 -*-
"""Word-style document workbench for long-form engineering writing.

Presents the AI-authored long document as a *Word-like editor* instead of a
plain chat stream:

* Left: chapter outline navigator — every chapter shows state, character
  count, a 0–100 score and a progress bar.
* Center: a WYSIWYG rich-text viewport (QTextEdit) that visually mirrors a
  Word page — Heading 1 / Heading 2 / body / numbered sub-items are styled by
  real block formats, and the document keeps full edit / undo / redo.
* Toolbar: save to a new .docx (never overwrites the source), undo / redo,
  auto-fit reading width.

The workbench is a *view over the sidecar cache* (:mod:`chapter_cache`):
streamed deltas land in the cache on the worker thread and this widget only
renders snapshot text on the UI thread, so tens of megabytes stay smooth.
"""
from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from src.assistant.ui.status_toast import (
    status_toast_kind,
    status_toast_text,
)
from src.qt_api import (
    QAction,
    QColor,
    QColorDialog,
    QFrame,
    QMenu,
    QFontDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextBlockFormat,
    QTextCharFormat,
    QTextImageFormat,
    QTextCursor,
    QTextEdit,
    QTextFrameFormat,
    QTextListFormat,
    QTextTableFormat,
    QTimer,
    QToolButton,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.typography_policy import TextRole, apply_text_role

_WORKBENCH_FONT_FAMILY = "Microsoft YaHei UI"
_HEADING1_PX = 22
_HEADING2_PX = 17
_HEADING3_PX = 15
_BODY_PX = 14

# Inline markdown image ``![alt](src)`` anywhere inside a text run (not just
# on its own line).  Group 1 is the alt text, group 2 the src/path.
_INLINE_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)\)')

# How big the “broken image” placeholder is rendered in the rich editor.
_BROKEN_IMAGE_PX = 22


def _broken_image_pixmap(size: int = _BROKEN_IMAGE_PX):
    """Compose a small “image could not load” glyph (picture frame + alert)."""
    from PySide6.QtCore import Qt as _Qt, QPoint
    from PySide6.QtGui import QPainter, QPixmap

    from src.shared.ui.theme import get_theme

    theme = get_theme()
    px = QPixmap(size, size)
    px.fill(_Qt.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.Antialiasing, True)
    base = get_icon("image", size, theme.text_disabled).pixmap(size, size)
    badge = get_icon("circle-alert", int(size * 0.62), theme.error).pixmap(
        int(size * 0.62), int(size * 0.62)
    )
    painter.drawPixmap(0, 0, base)
    # Small alert badge at the bottom-right to signal the load failed.
    off = max(1, int(size * 0.34))
    painter.drawPixmap(QPoint(off, off), badge)
    painter.end()
    return px


class WorkbenchEditor(QTextEdit):
    """Rich-text, editable, undo/redo-aware document viewport.

    Maps a flat outline of blocks (heading levels 1/2, body, subsection
    number) onto real QTextBlock formats so the result *looks* like a Word
    page while remaining fully editable.
    """

    changed = Signal()
    edited_snapshot = Signal(str)  # plain text snapshot after each edit batch
    ai_continue_requested = Signal(str)  # 从光标处续写（携带用户要求占位）
    ai_rewrite_requested = Signal(str)  # 对选中文本改写（携带选中文本）

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("workbench_editor")
        self.setFrameShape(QFrame.NoFrame)
        self.setAcceptRichText(True)
        self.setUndoRedoEnabled(True)
        self.document().setDocumentMargin(28)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._suppress_change = False
        self._image_base_dir = str(Path.cwd())
        self.textChanged.connect(self._on_text_changed)
        self._apply_base_theme()

    def set_image_base_dir(self, directory: str) -> None:
        """Base directory used to resolve relative ``images/...`` src paths
        when rendering inline markdown images in a text block."""
        base = str(directory or "")
        if base:
            self._image_base_dir = str(Path(base).expanduser())

    def image_base_dir(self) -> str:
        return self._image_base_dir

    def _on_text_changed(self) -> None:
        if self._suppress_change:
            return
        self.changed.emit()

    # ---- 右键：Word/WPS 风格 + AI 融合 -----------------------------------
    def contextMenuEvent(self, event) -> None:  # noqa: N802
        menu = self.createStandardContextMenu(event.pos())
        menu.addSeparator()

        # 字体…（系统字体对话框，与 Word 一致）
        act_font = QAction("字体(F)…", menu)
        act_font.triggered.connect(self.open_font_dialog)
        menu.addAction(act_font)

        # 文字颜色 → 高亮颜色
        color_menu = QMenu("文字颜色…", menu)
        act_color = QAction("文字颜色…", color_menu)
        act_color.triggered.connect(self.pick_text_color)
        color_menu.addAction(act_color)
        act_highlight = QAction("高亮颜色…", color_menu)
        act_highlight.triggered.connect(self.pick_highlight_color)
        color_menu.addAction(act_highlight)
        menu.addMenu(color_menu)

        # 段落格式
        para_menu = QMenu("段落…", menu)
        act_left = QAction("左对齐", para_menu)
        act_left.triggered.connect(lambda: self.set_alignment(Qt.AlignLeft))
        para_menu.addAction(act_left)
        act_center = QAction("居中", para_menu)
        act_center.triggered.connect(lambda: self.set_alignment(Qt.AlignHCenter))
        para_menu.addAction(act_center)
        act_right = QAction("右对齐", para_menu)
        act_right.triggered.connect(lambda: self.set_alignment(Qt.AlignRight))
        para_menu.addAction(act_right)
        act_justify = QAction("两端对齐", para_menu)
        act_justify.triggered.connect(lambda: self.set_alignment(Qt.AlignJustify))
        para_menu.addAction(act_justify)
        para_menu.addSeparator()
        act_bullet = QAction("项目符号", para_menu)
        act_bullet.triggered.connect(lambda: self.toggle_list(False))
        para_menu.addAction(act_bullet)
        act_number = QAction("编号", para_menu)
        act_number.triggered.connect(lambda: self.toggle_list(True))
        para_menu.addAction(act_number)
        menu.addMenu(para_menu)

        # 插入表格 / 图片
        insert_menu = QMenu("插入…", menu)
        act_table = QAction("表格…", insert_menu)
        act_table.triggered.connect(self.insert_table_dialog)
        insert_menu.addAction(act_table)
        act_image = QAction("图片…", insert_menu)
        act_image.triggered.connect(self.insert_image_dialog)
        insert_menu.addAction(act_image)
        menu.addMenu(insert_menu)

        # AI 三入口
        menu.addSeparator()
        selected = self.textCursor().selectedText()
        act_continue = QAction("✍️ 用 AI 从光标处续写…", menu)
        act_continue.setEnabled(self.textCursor().hasSelection() is False)
        act_continue.triggered.connect(lambda: self.ai_continue_requested.emit(""))
        menu.addAction(act_continue)
        act_rewrite = QAction("🤖 选中文本交给 AI 改写…", menu)
        act_rewrite.setEnabled(bool(selected and selected.strip()))
        act_rewrite.triggered.connect(lambda: self.ai_rewrite_requested.emit(str(selected or "")))
        menu.addAction(act_rewrite)
        act_fix = QAction("🧹 选中文本交 AI 优化润色…", menu)
        act_fix.setEnabled(bool(selected and selected.strip()))
        act_fix.triggered.connect(
            lambda: self.ai_rewrite_requested.emit(str(selected or "") + "\n[润色]")
        )
        menu.addAction(act_fix)
        menu.exec(event.globalPos())

    # ---- Word/WPS 风格格式动作（右键菜单与工具条共用） ------------------
    def _merge_char(self, fmt: "QTextCharFormat") -> None:
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            self.mergeCurrentCharFormat(fmt)
        self.setFocus()

    def toggle_bold(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(700 if not self.fontWeight() >= 700 else 400)
        self._merge_char(fmt)

    def toggle_italic(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.fontItalic())
        self._merge_char(fmt)

    def toggle_underline(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.fontUnderline())
        self._merge_char(fmt)

    def toggle_strike(self) -> None:
        cursor = self.textCursor()
        was_struck = bool(cursor.charFormat().fontStrikeOut())
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not was_struck)
        self._merge_char(fmt)

    def set_font_family(self, family: str) -> None:
        if not str(family or "").strip():
            return
        fmt = QTextCharFormat()
        fmt.setFontFamily(str(family))
        self._merge_char(fmt)

    def set_font_size_pt(self, size_pt: float) -> None:
        try:
            size = float(size_pt)
        except (TypeError, ValueError):
            return
        if size <= 0:
            return
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        self._merge_char(fmt)

    def open_font_dialog(self) -> None:
        from src.qt_api import QFontDialog
        from PySide6.QtGui import QFont

        current = self.currentFont()
        ok, font = QFontDialog.getFont(current, self, "字体")
        if ok:
            fmt = QTextCharFormat()
            fmt.setFont(font)
            self._merge_char(fmt)

    def pick_text_color(self) -> None:
        color = QColorDialog.getColor(QColor("#222222"), self, "文字颜色")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self._merge_char(fmt)

    def pick_highlight_color(self) -> None:
        color = QColorDialog.getColor(QColor("#FFFF00"), self, "高亮颜色")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setBackground(color)
            self._merge_char(fmt)

    def set_alignment(self, align: Qt.AlignmentFlag) -> None:
        fmt = QTextBlockFormat()
        fmt.setAlignment(align)
        cursor = self.textCursor()
        cursor.mergeBlockFormat(fmt)
        self.setFocus()

    def toggle_list(self, numbered: bool) -> None:
        cursor = self.textCursor()
        block = cursor.block()
        current = block.textList()
        if current is not None and (current.format().style() == QTextListFormat.ListDecimal) == numbered:
            cursor.createList(QTextListFormat.ListDisc)
            return
        style = QTextListFormat.ListDecimal if numbered else QTextListFormat.ListDisc
        cursor.createList(style)
        self.setFocus()

    def insert_table_dialog(self) -> None:
        from src.qt_api import QInputDialog

        rows, ok = QInputDialog.getInt(self, "插入表格", "行数：", 3, 1, 100, 1)
        if not ok:
            return
        cols, ok2 = QInputDialog.getInt(self, "插入表格", "列数：", 3, 1, 30, 1)
        if not ok2:
            return
        self._insert_table(rows, cols)

    def _insert_table(self, rows: int, cols: int) -> None:
        from PySide6.QtGui import QTextTableFormat

        cursor = self.textCursor()
        fmt = QTextTableFormat()
        fmt.setBorder(0.5)
        fmt.setBorderStyle(QTextFrameFormat.BorderStyle_Solid)  # SolidLine
        fmt.setCellPadding(4)
        fmt.setCellSpacing(0)
        table = cursor.insertTable(max(1, rows), max(1, cols), fmt)
        table.setObjectName("doc_table")
        self.setFocus()

    def insert_image_dialog(self) -> None:
        from src.qt_api import QFileDialog

        path_text, _f = QFileDialog.getOpenFileName(
            self, "插入图片", "", "图片 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        if not path_text:
            return
        self._insert_image(str(path_text))

    def _insert_image(self, path_text: str) -> None:
        from PySide6.QtGui import QImage, QTextImageFormat

        img = QImage(path_text)
        if img.isNull():
            return
        fmt = QTextImageFormat()
        fmt.setName(path_text)
        page_w = max(1, self.viewport().width() - 80)
        scaled = min(float(page_w) / max(1, img.width()), 1.0)
        if scaled < 1.0:
            fmt.setWidth(int(img.width() * scaled))
            fmt.setHeight(int(img.height() * scaled))
        else:
            fmt.setWidth(img.width())
            fmt.setHeight(img.height())
        self.textCursor().insertImage(fmt)
        self.setFocus()

    def _insert_image_at(self, cursor: QTextCursor, path_text: str) -> None:
        """Insert an image at ``cursor`` (used by the block renderer)."""
        from PySide6.QtGui import QImage, QTextImageFormat

        path_text = str(path_text or "").strip()
        if not path_text:
            return
        img = QImage(path_text)
        if img.isNull():
            self._insert_image_missing_placeholder(cursor, path_text)
            return
        fmt = QTextImageFormat()
        fmt.setName(path_text)
        page_w = max(1, self.viewport().width() - 80)
        scaled = min(float(page_w) / max(1, img.width()), 1.0)
        if scaled < 1.0:
            fmt.setWidth(int(img.width() * scaled))
            fmt.setHeight(int(img.height() * scaled))
        else:
            fmt.setWidth(img.width())
            fmt.setHeight(img.height())
        cursor.insertImage(fmt)

    def _insert_image_missing_placeholder(
        self,
        cursor: QTextCursor,
        display_text: str,
        block_format: QTextCharFormat | None = None,
    ) -> None:
        """Render the unified “image could not load” placeholder at ``cursor``:
        a small broken-image icon followed by a muted hint naming the source.

        Used by every image path (standalone block, inline markdown) so a
        missing picture never silently disappears or shows as raw markdown.
        """
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QTextDocument

        display = str(display_text or "").strip()
        name = f"broken-image://{uuid4().hex}"
        doc = self.document()
        doc.addResource(
            QTextDocument.ImageResource,
            QUrl(name),
            _broken_image_pixmap(_BROKEN_IMAGE_PX),
        )
        icon_fmt = QTextImageFormat()
        icon_fmt.setName(name)
        icon_fmt.setWidth(_BROKEN_IMAGE_PX)
        icon_fmt.setHeight(_BROKEN_IMAGE_PX)
        cursor.insertImage(icon_fmt)

        theme = get_theme()
        hint = QTextCharFormat(block_format) if block_format is not None else QTextCharFormat()
        hint.setFontFamily(_WORKBENCH_FONT_FAMILY)
        hint.setForeground(QColor(theme.text_hint))
        hint.setFontPointSize(max(9.0, _BODY_PX - 2))
        hint.setFontItalic(True)
        suffix = f"图片加载失败：{display}" if display else "图片加载失败"
        cursor.insertText(f" {suffix}", hint)

    def set_char_format_presets(self, preset: str) -> None:
        """按预设直接设置当前光标/选区的字号与加粗（供工具条调用）。"""
        mapping = {
            "标题 1": (_HEADING1_PX, True),
            "标题 2": (_HEADING2_PX, True),
            "标题 3": (_HEADING3_PX, True),
            "正文": (_BODY_PX, False),
        }
        if preset not in mapping:
            return
        size, bold = mapping[preset]
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        fmt.setFontWeight(700 if bold else 400)
        self._merge_char(fmt)

    @property
    def current_preset(self) -> str:
        size = self.currentFont().pointSizeF()
        if size >= _HEADING1_PX - 1:
            return "标题 1"
        if size >= _HEADING2_PX - 1:
            return "标题 2"
        if size >= _HEADING3_PX - 1:
            return "标题 3"
        return "正文"

    def char_state(self) -> dict:
        """当前光标处字符/段落格式状态，供 Word 工具条同步勾选态。"""
        cursor = self.textCursor()
        cf = cursor.charFormat()
        bf = cursor.blockFormat()
        font = cf.font() if hasattr(cf, "font") else self.currentFont()
        return {
            "bold": bool(cf.fontWeight() >= 700),
            "italic": bool(cf.fontItalic()),
            "underline": bool(cf.fontUnderline()),
            "strike": bool(cf.fontStrikeOut()),
            "family": str(font.family() or ""),
            "size": float(cf.fontPointSize() or font.pointSizeF() or 0),
            "align": int(bf.alignment()),
        }
    def clear_document(self) -> None:
        self.document().clear()
        self.document().clearUndoRedoStacks()

    def refresh_image_resources(self) -> None:
        """Force every currently-displayed image to re-read from its backing
        file on the next paint.

        Qt may keep a per-URL image in the document cache, so re-registering
        each referenced image from disk under the same name makes the next
        layout show the fresh file instead of a stale picture after an image
        (or its base directory) changed.
        """
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QImage, QTextCursor, QTextDocument

        doc = self.document()
        # Collect the absolute file names of every image fragment currently in
        # the document (PySide6 exposes no block-fragment iterator, so walk
        # positions with a cursor).
        names: set[str] = set()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.Start)
        while not cursor.atEnd():
            char_format = cursor.charFormat()
            if char_format.isImageFormat():
                image_fmt = char_format.toImageFormat()
                name = image_fmt.name() or ""
                if name and not name.startswith("broken-image://"):
                    names.add(name)
            if not cursor.movePosition(QTextCursor.NextCharacter):
                break
        for name in names:
            path = Path(name)
            if not path.is_file():
                continue
            image = QImage(str(path))
            if image.isNull():
                continue
            try:
                doc.addResource(QTextDocument.ImageResource, QUrl(name), image)
            except (TypeError, RuntimeError):
                pass

    def load_plain(self, text: str) -> None:
        """Load an outline-agnostic plain snapshot (used by viewer tests)."""
        self.clear_document()
        self._suppress_change = True
        self.setPlainText(str(text or ""))
        self._suppress_change = False
        self.document().clearUndoRedoStacks()

    def set_outline_document(
        self,
        blocks: list[tuple[int, str]],
    ) -> None:
        """Render a list of ``(kind, text)`` blocks into styled paragraphs.

        ``kind``: 1 = Heading 1, 2 = Heading 2, 0 = body paragraph.
        """
        cursor = self.textCursor()
        self.clear_document()
        cursor = self.textCursor()
        self._suppress_change = True
        first = True
        for kind, text in blocks:
            text = str(text or "").rstrip()
            if not text.strip():
                continue
            if not first:
                cursor.insertBlock()
            self._format_block(cursor, int(kind), text)
            first = False
        self._suppress_change = False
        self.document().clearUndoRedoStacks()
        self._apply_base_theme()

    def append_live(self, kind: int, text: str) -> None:
        """Append one streamed block at the caret end (AI typing effect)."""
        text = str(text or "")
        if not text.strip():
            return
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._suppress_change = True
        if not self.document().isEmpty():
            cursor.insertBlock()
        self._format_block(cursor, int(kind), text)
        self._suppress_change = False

    def append_raw(self, delta: str) -> None:
        """Append raw characters at the end (typing stream into last block)."""
        delta = str(delta or "")
        if not delta:
            return
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        self._suppress_change = True
        cursor.insertText(delta)
        self._suppress_change = False

    def _format_block(self, cursor: QTextCursor, kind: int, text: str) -> None:
        from src.shared.engine.ooxml_ops import qn  # noqa: F401 - keeps style hook simple

        theme = get_theme()
        if kind == 4:
            # Standalone image block (markdown `![alt](src)`): render the
            # actual picture instead of the markdown text. `text` is the src
            # path, already resolved to an absolute path by the caller.
            self._insert_image_at(cursor, str(text or ""))
            return
        block_format = QTextBlockFormat()
        char_format = QTextCharFormat()
        char_format.setFontFamily(_WORKBENCH_FONT_FAMILY)
        if kind == 1:
            char_format.setFontPointSize(_HEADING1_PX)
            char_format.setFontWeight(700)
            char_format.setForeground(QColor(theme.text_primary))
            block_format.setTopMargin(14)
            block_format.setBottomMargin(6)
            block_format.setLeftMargin(0)
        elif kind == 2:
            char_format.setFontPointSize(_HEADING2_PX)
            char_format.setFontWeight(600)
            char_format.setForeground(QColor(theme.text_primary))
            block_format.setTopMargin(10)
            block_format.setBottomMargin(4)
            block_format.setLeftMargin(0)
        elif kind == 3:
            char_format.setFontPointSize(_HEADING3_PX)
            char_format.setFontWeight(600)
            char_format.setForeground(QColor(theme.text_primary))
            block_format.setTopMargin(8)
            block_format.setBottomMargin(3)
            block_format.setLeftMargin(0)
        else:
            char_format.setFontPointSize(_BODY_PX)
            char_format.setFontWeight(400)
            char_format.setForeground(QColor(theme.text_primary))
            block_format.setTopMargin(2)
            block_format.setBottomMargin(4)
            block_format.setLineHeight(150, QTextBlockFormat.ProportionalHeight.value)
        cursor.setBlockFormat(block_format)
        cursor.setCharFormat(char_format)
        # Render any inline markdown images (文字中混入 ![alt](src)) as real
        # pictures; the words around them keep this block's char format.
        self._insert_text_with_inline_images(cursor, str(text or ""), char_format)

    def _insert_text_with_inline_images(
        self, cursor: QTextCursor, text: str, char_format: QTextCharFormat
    ) -> None:
        """Insert ``text``, turning any inline ``![alt](src ...)`` markdown
        image token into an actual inline picture while surrounding words keep
        the given character format.  A token whose file cannot be resolved is
        kept verbatim as text so nothing silently disappears."""
        from PySide6.QtGui import QImage, QTextImageFormat

        text = str(text or "")
        if "![" not in text:
            cursor.insertText(text, char_format)
            return
        pos = 0
        for match in _INLINE_IMAGE_RE.finditer(text):
            head = text[pos : match.start()]
            if head:
                cursor.insertText(head, char_format)
            path_text = self._resolve_image_src(str(match.group(2) or ""))
            img = QImage(path_text) if path_text else QImage()
            if img.isNull():
                # Unify with the standalone-image fallback: show a broken-image
                # placeholder + the offending src rather than raw markdown.
                src_token = str(match.group(2) or "").strip()
                self._insert_image_missing_placeholder(cursor, src_token, char_format)
            else:
                fmt = QTextImageFormat()
                fmt.setName(path_text)
                page_w = max(1, self.viewport().width() - 80)
                scaled = min(float(page_w) / max(1, img.width()), 1.0)
                if scaled < 1.0:
                    fmt.setWidth(int(img.width() * scaled))
                    fmt.setHeight(int(img.height() * scaled))
                else:
                    fmt.setWidth(img.width())
                    fmt.setHeight(img.height())
                cursor.insertImage(fmt)
            pos = match.end()
        tail = text[pos:]
        if tail:
            cursor.insertText(tail, char_format)

    def _resolve_image_src(self, src: str) -> str:
        """Resolve a markdown image ``src`` (relative or absolute) to an
        existing file path, or ``""`` when nothing can be resolved."""
        src = str(src or "").strip()
        if not src:
            return ""
        if src.startswith("file://"):
            src = src[7:]
        elif src.startswith(("http://", "https://", "data:")):
            # Network / data-URL images are not fetched by the local editor;
            # leave them as markdown text so they stay visible and exportable.
            return ""
        path = Path(src).expanduser()
        if not path.is_absolute():
            path = (Path(self._image_base_dir or Path.cwd()) / path).resolve()
        try:
            return str(path) if path.is_file() else ""
        except OSError:
            return ""

    def text_snapshot(self) -> str:
        return self.toPlainText()
    # ---- typing-engine formatting hooks ---------------------------------
    def _char_format_for_block(self, block) -> "QTextCharFormat":
        """Return the per-block char format used by the AI typing engine."""
        theme = get_theme()
        char_format = QTextCharFormat()
        kind = int(getattr(block, "kind", 0) or 0)
        text = str(getattr(block, "text", "") or "")
        char_format.setFontFamily(_WORKBENCH_FONT_FAMILY)
        char_format.setForeground(QColor(theme.text_primary))
        if kind == 1:
            char_format.setFontPointSize(_HEADING1_PX)
            char_format.setFontWeight(700)
        elif kind == 2:
            char_format.setFontPointSize(_HEADING2_PX)
            char_format.setFontWeight(600)
        elif kind == 3:
            char_format.setFontPointSize(_HEADING3_PX)
            char_format.setFontWeight(600)
        else:
            char_format.setFontPointSize(_BODY_PX)
            char_format.setFontWeight(400)
            if text.startswith("\uff5c"):
                char_format.setFontFamily("Consolas")
        return char_format

    def _format_current_block_format(self, block) -> None:
        """Apply block-level margins/spacing before typing into a new block."""
        kind = int(getattr(block, "kind", 0) or 0)
        block_format = QTextBlockFormat()
        if kind == 1:
            block_format.setTopMargin(14)
            block_format.setBottomMargin(6)
        elif kind == 2:
            block_format.setTopMargin(10)
            block_format.setBottomMargin(4)
        elif kind == 3:
            block_format.setTopMargin(8)
            block_format.setBottomMargin(3)
        else:
            block_format.setTopMargin(2)
            block_format.setBottomMargin(4)
            block_format.setLineHeight(
                150, QTextBlockFormat.ProportionalHeight.value
            )
        cursor = self.textCursor()
        cursor.setBlockFormat(block_format)
        self.setTextCursor(cursor)


    # ---- theme ------------------------------------------------------------
    def _apply_base_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QTextEdit#workbench_editor {{
                background: {theme.bg_card};
                color: {theme.text_primary};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
                padding: 4px;
                selection-background-color: {theme.primary_light};
                selection-color: {theme.text_primary};
                font-family: "{_WORKBENCH_FONT_FAMILY}";
                font-size: {_BODY_PX}px;
            }}
            QTextEdit#workbench_editor QScrollBar:vertical {{
                background: transparent; width: 8px; margin: 0;
            }}
            QTextEdit#workbench_editor QScrollBar::handle:vertical {{
                background: {theme.scrollbar_thumb}; border-radius: 4px; min-height: 24px;
            }}
            QTextEdit#workbench_editor QScrollBar::add-line:vertical,
            QTextEdit#workbench_editor QScrollBar::sub-line:vertical {{
                background: transparent; height: 0;
            }}
            """
        )


class ChapterNavigatorRow(QWidget):
    """One clickable chapter row in the left navigator."""

    clicked = Signal(int)

    def __init__(self, index: int, title: str, parent=None) -> None:
        super().__init__(parent)
        self.index = int(index)
        self.setObjectName("workbench_chapter_row")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self._state_icon = QLabel(self)
        self._state_icon.setFixedSize(15, 15)
        layout.addWidget(self._state_icon, 0, Qt.AlignVCenter)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(2)
        self._title = QLabel(str(title or ""), self)
        self._title.setWordWrap(True)
        self._title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        apply_text_role(self._title, TextRole.CAPTION)
        text_box.addWidget(self._title)
        self._meta = QLabel("待写", self)
        self._meta.setObjectName("workbench_chapter_meta")
        apply_text_role(self._meta, TextRole.MICRO)
        text_box.addWidget(self._meta)
        layout.addLayout(text_box, 1)

        self._score_label = QLabel("", self)
        self._score_label.setObjectName("workbench_chapter_score")
        self._score_label.setFixedWidth(30)
        self._score_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        apply_text_role(self._score_label, TextRole.MICRO)
        layout.addWidget(self._score_label, 0, Qt.AlignVCenter)

        self._state = "pending"
        self._chars = 0
        self._score = 0
        self._grade = "待写"
        self._refresh()
        bind_theme(self, self._refresh)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.index)
        super().mouseReleaseEvent(event)

    def set_state(self, state: str) -> None:
        self._state = str(state or "pending").strip()
        if self._state not in {"pending", "running", "done", "failed"}:
            self._state = "pending"
        self._refresh()

    def set_stats(self, *, chars: int | None = None, score: int | None = None,
                  grade: str | None = None) -> None:
        if chars is not None:
            self._chars = max(0, int(chars))
        if score is not None:
            self._score = max(0, min(100, int(score)))
        if grade is not None:
            self._grade = str(grade or "")
        self._refresh()

    def stats(self) -> tuple[int, int, str]:
        return self._chars, self._score, self._grade

    def _refresh(self) -> None:
        theme = get_theme()
        color = theme.text_hint
        if self._state == "running":
            color = theme.primary
        elif self._state == "done":
            color = theme.success
        elif self._state == "failed":
            color = theme.error
        icon_name = {
            "pending": "circle",
            "running": "loader",
            "done": "circle-check",
            "failed": "circle-alert",
        }.get(self._state, "circle")
        self._state_icon.setPixmap(get_icon(icon_name, 14, color).pixmap(14, 14))
        if self._state == "running":
            meta = f"写作中 · {self._chars:,} 字"
        elif self._state == "done":
            meta = f"{self._chars:,} 字 · {self._grade}"
        elif self._state == "failed":
            meta = "中断"
        else:
            meta = "待写"
        self._meta.setText(meta)
        self._score_label.setText(str(self._score) if self._state != "pending" else "")
        self._score_label.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
        )
        self.setStyleSheet(
            f"""
            QWidget#workbench_chapter_row {{
                background: {theme.bg_card if self._state != 'running' else theme.bg_selected};
                border: 1px solid {theme.border_focus if self._state == 'running' else theme.border_light};
                border-radius: {theme.radius_sm}px;
            }}
            QLabel#workbench_chapter_meta {{ color: {theme.text_hint}; background: transparent; border: none; }}
            """
        )


class ChapterNavigator(QWidget):
    """Left navigator listing chapters with live state + score."""

    chapter_selected = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("workbench_navigator")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(232)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        header = QLabel("目录大纲", self)
        header.setObjectName("workbench_nav_header")
        apply_text_role(header, TextRole.NAVIGATION_TITLE_ACTIVE)
        root.addWidget(header)

        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("workbench_nav_scroll")
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._host = QWidget(self._scroll)
        self._list = QVBoxLayout(self._host)
        self._list.setContentsMargins(0, 0, 2, 0)
        self._list.setSpacing(4)
        self._list.addStretch(1)
        self._scroll.setWidget(self._host)
        root.addWidget(self._scroll, 1)

        self._rows: dict[int, ChapterNavigatorRow] = {}
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_outline(self, titles: list[str]) -> None:
        for i in range(self._list.count() - 1, -1, -1):
            item = self._list.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()
        for index, title in enumerate(titles, start=1):
            row = ChapterNavigatorRow(index, title, self._host)
            row.clicked.connect(self.chapter_selected.emit)
            self._rows[index] = row
            self._list.insertWidget(self._list.count() - 1, row)

    def row(self, index: int) -> ChapterNavigatorRow | None:
        return self._rows.get(int(index))

    def set_state(self, index: int, state: str) -> None:
        row = self._rows.get(int(index))
        if row is not None:
            row.set_state(state)

    def set_stats(self, index: int, *, chars: int | None = None,
                  score: int | None = None, grade: str | None = None) -> None:
        row = self._rows.get(int(index))
        if row is not None:
            row.set_stats(chars=chars, score=score, grade=grade)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QWidget#workbench_navigator {{
                background: {theme.bg_window};
                border-right: 1px solid {theme.divider};
            }}
            QLabel#workbench_nav_header {{ color: {theme.text_primary}; background: transparent; }}
            QScrollArea#workbench_nav_scroll {{ background: transparent; border: none; }}
            QWidget {{ background: transparent; }}
            """
        )
        for row in self._rows.values():
            row._refresh()


class ChapterWorkbench(QFrame):
    """Full workbench: navigator (left) + Word-like editor (center)."""

    closed = Signal()
    save_requested = Signal()
    chapter_navigated = Signal(int)
    edited = Signal(str)  # session-facing snapshot after user edits

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("chapter_workbench")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._source_path: str = ""
        self._current_index = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── toolbar ───────────────────────────────────────────────────
        toolbar = QFrame(self)
        toolbar.setObjectName("workbench_toolbar")
        toolbar.setFixedHeight(44)
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(10, 4, 10, 4)
        bar.setSpacing(6)

        self._close_button = QToolButton(self)
        self._close_button.setObjectName("workbench_close")
        self._close_button.setToolTip("关闭文档工作台（返回对话）")
        self._close_button.setFixedSize(26, 26)
        self._close_button.clicked.connect(self.closed.emit)
        bar.addWidget(self._close_button)

        self._doc_label = QLabel("文档工作台", self)
        self._doc_label.setObjectName("workbench_doc_label")
        apply_text_role(self._doc_label, TextRole.SUBTITLE)
        bar.addWidget(self._doc_label)
        bar.addStretch(1)

        self._undo_button = QToolButton(self)
        self._undo_button.setToolTip("撤销")
        self._redo_button = QToolButton(self)
        self._redo_button.setToolTip("重做")
        self._save_button = QPushButton("保存为新文档", self)
        self._save_button.setObjectName("workbench_save")
        self._save_button.setCursor(Qt.PointingHandCursor)
        for button in (self._undo_button, self._redo_button):
            button.setObjectName("workbench_tool")
            button.setFixedSize(26, 26)
            button.setCursor(Qt.PointingHandCursor)
            bar.addWidget(button)
        bar.addWidget(self._save_button)
        root.addWidget(toolbar)

        # ── body: navigator | editor ──────────────────────────────────
        self._splitter = QSplitter(self)
        self._splitter.setObjectName("workbench_splitter")
        self._splitter.setChildrenCollapsible(False)
        self._navigator = ChapterNavigator(self._splitter)
        self._editor = WorkbenchEditor(self._splitter)
        self._splitter.addWidget(self._navigator)
        self._splitter.addWidget(self._editor)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([232, 860])
        root.addWidget(self._splitter, 1)

        self._navigator.chapter_selected.connect(self._on_navigate)
        self._undo_button.clicked.connect(self._editor.undo)
        self._redo_button.clicked.connect(self._editor.redo)
        self._save_button.clicked.connect(self._request_save)

        # Transient toast so left-workbench state changes (undo-history reset
        # on chapter switch, save success…) mirror the right-side editor's hints.
        self._toast = QLabel(self)
        self._toast.setObjectName("workbench_toast")
        self._toast.setAlignment(Qt.AlignCenter)
        self._toast.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._toast.hide()
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.setInterval(2200)
        self._toast_timer.timeout.connect(self._toast.hide)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    # ---- public API -------------------------------------------------------
    @property
    def editor(self) -> WorkbenchEditor:
        return self._editor

    @property
    def navigator(self) -> ChapterNavigator:
        return self._navigator

    @property
    def current_index(self) -> int:
        return self._current_index

    def set_navigator_visible(self, visible: bool) -> None:
        """Show/hide the workbench's own left navigator.

        When the persistent conversation outline dock is fused next to this
        workbench, the dock becomes the single chapter index and the built-in
        navigator is hidden so the editor fills the remaining width.
        """
        visible = bool(visible)
        self._navigator.setVisible(visible)
        if visible:
            if self._splitter.indexOf(self._navigator) < 0:
                self._splitter.insertWidget(0, self._navigator)
            self._splitter.setSizes([232, max(420, self._splitter.width() - 232)])
        else:
            index = self._splitter.indexOf(self._navigator)
            if index >= 0:
                self._splitter.widget(index).setParent(self)
                self._splitter.refresh()
            self._splitter.setSizes([0, self._splitter.width()])

    def navigator_visible(self) -> bool:
        nav = getattr(self, "_navigator", None)
        return nav is not None and nav.isVisible()

    def open_document(self, source_path: str, title: str) -> None:
        self._source_path = str(source_path or "")
        self._doc_label.setText(f"文档工作台 · {Path(self._source_path).name if self._source_path else title}")
        self._sync_render_context()
        self._editor.clear_document()

    def _sync_render_context(self) -> None:
        """Point the editor's image-base directory at the *current* source
        document and drop any cached image resources so a later re-render
        resolves relative paths against the live workbench directory.

        Without this, an inline ``images/...`` src whose backing file (or the
        workbench source path) changed between renders could keep resolving
        against the old directory and show a stale picture.
        """
        self._editor.set_image_base_dir(
            str(Path(self._source_path).resolve().parent)
            if self._source_path
            else str(Path.cwd())
        )
        self._editor.refresh_image_resources()

    def prepare_for_render(self) -> None:
        """Re-derive the image resolution context before a left-workbench
        render (called on chapter sync after an image insertion / path
        change) so image relative paths always map to the current files."""
        self._sync_render_context()

    def set_outline(self, titles: list[str]) -> None:
        self._navigator.set_outline(list(titles or ()))

    def render_plain(self, text: str) -> None:
        self._editor.load_plain(str(text or ""))

    def _request_save(self) -> None:
        self.save_requested.emit()

    def _on_editor_changed(self) -> None:
        self.edited.emit(self._editor.text_snapshot())

    def _select_chapter_index(self, index: int, *, force: bool = False) -> None:
        """Select *index*; re-selecting the current chapter keeps its undo stack.

        A same-chapter re-click just re-focuses that row and leaves the loaded
        content and undo/redo history intact (mirroring the right-hand editor),
        so an accidental click never wipes edits the user could still undo.
        Only a real chapter switch reloads the body (which clears history) and
        shows the reset toast.  Pass ``force=True`` to reload the current
        chapter anyway.
        """
        target = int(index)
        previous = self._current_index
        if previous and target == previous and not force:
            self._current_index = target
            return
        self._current_index = target
        if previous and target != previous:
            # Route the chapter-switch baseline through the single undo strategy
            # so the reset action + toast come from one place (undo_policy
            # resolves a real chapter switch to CLEAR + chapter_reset).
            from src.assistant.ui.undo_policy import UndoEvent, resolve

            resolution = resolve(UndoEvent.CHAPTER_SWITCH)
            toast_key = resolution.toast_for()
            self.show_toast(
                status_toast_text(toast_key),
                kind=status_toast_kind(toast_key),
            )
        self.chapter_navigated.emit(target)

    def _on_navigate(self, index: int, *, force: bool = False) -> None:
        self._select_chapter_index(index, force=force)

    def navigate_chapter(self, index: int, *, force: bool = False) -> None:
        self._select_chapter_index(index, force=force)

    def show_toast(self, text: str, kind: str = "") -> None:
        """Show a short-lived status toast over the editor, mirroring the
        right-side MarkText hints so both columns give consistent feedback
        (e.g. “已切换章节，撤销历史已重置”).  ``kind`` selects the accent:
        ``success`` / ``warning`` / ``error`` / ``''`` (neutral)."""
        toast = getattr(self, "_toast", None)
        if toast is None:
            return
        theme = get_theme()
        accent = {
            "success": getattr(theme, "primary", "#1677FF"),
            "warning": getattr(theme, "warning", "#FAAD14"),
            "error": getattr(theme, "error", "#FF4D4F"),
        }.get(kind, "")
        radius = int(getattr(theme, "radius_md", 10) or 10)
        toast.setText(str(text or ""))
        if accent:
            toast.setStyleSheet(
                f"""
                QLabel#workbench_toast {{
                    background: {theme.bg_card};
                    border: 1px solid {theme.border_light};
                    border-left: 3px solid {accent};
                    border-radius: {radius}px;
                    color: {theme.text_primary};
                    padding: 6px 14px;
                    font-size: {getattr(theme, 'font_size_sm', 12)}px;
                }}
                """
            )
        else:
            toast.setStyleSheet(
                f"""
                QLabel#workbench_toast {{
                    background: {theme.bg_card};
                    border: 1px solid {theme.border_light};
                    border-radius: {radius}px;
                    color: {theme.text_primary};
                    padding: 6px 14px;
                    font-size: {getattr(theme, 'font_size_sm', 12)}px;
                }}
                """
            )
        self._position_toast()
        toast.show()
        toast.raise_()
        self._toast_timer.start()

    def _position_toast(self) -> None:
        toast = getattr(self, "_toast", None)
        if toast is None:
            return
        toast.adjustSize()
        editor = self._editor
        # Compute the editor's top-left and bottom-right in *this* widget's
        # coordinates (the editor lives inside the splitter, not directly on us).
        left = 0
        top = 0
        right = self.width()
        bottom = self.height()
        if editor is not None:
            try:
                from PySide6.QtCore import QPoint

                tl = editor.mapTo(self, QPoint(0, 0))
                br = editor.mapTo(self, QPoint(editor.width(), editor.height()))
                left = tl.x()
                top = tl.y()
                right = br.x()
                bottom = br.y()
            except Exception:  # noqa: BLE001 - fall back to centering on self
                pass
        center_x = (left + right) // 2
        toast.move(
            max(0, min(self.width() - toast.width(), center_x - toast.width() // 2)),
            max(0, min(self.height() - toast.height() - 8, top + 10)),
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        toast = getattr(self, "_toast", None)
        if toast is not None and toast.isVisible():
            self._position_toast()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QFrame#chapter_workbench {{
                background: {theme.bg_window};
                border: 1px solid {theme.border};
                border-radius: {theme.radius_md}px;
            }}
            QFrame#workbench_toolbar {{
                background: {theme.bg_card};
                border-bottom: 1px solid {theme.divider};
                border-top-left-radius: {theme.radius_md}px;
                border-top-right-radius: {theme.radius_md}px;
            }}
            QLabel#workbench_doc_label {{ color: {theme.text_primary}; background: transparent; }}
            QToolButton#workbench_close, QToolButton#workbench_tool {{
                background: transparent; border: 1px solid transparent;
                border-radius: {theme.radius_xs}px; color: {theme.text_secondary};
            }}
            QToolButton#workbench_close:hover, QToolButton#workbench_tool:hover {{
                background: {theme.bg_hover}; border-color: {theme.border_light};
            }}
            QPushButton#workbench_save {{
                color: {theme.text_on_primary};
                background: {theme.primary};
                border: none;
                border-radius: {theme.radius_md}px;
                padding: 5px 14px;
                font-size: {theme.font_size_sm}px;
                font-weight: {theme.font_weight_emphasis};
            }}
            QPushButton#workbench_save:hover {{ background: {theme.primary_hover}; }}
            QSplitter#workbench_splitter {{ background: transparent; border: none; }}
            """
        )
        theme = get_theme()
        self._close_button.setIcon(get_icon("x", 14, theme.text_hint))
        self._undo_button.setIcon(get_icon("undo-2", 15, theme.text_secondary))
        self._redo_button.setIcon(get_icon("redo-2", 15, theme.text_secondary))


__all__ = ["ChapterWorkbench", "WorkbenchEditor", "ChapterNavigator"]