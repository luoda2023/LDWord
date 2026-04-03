"""MarkdownPreview — Markdown 富文本渲染控件"""

from __future__ import annotations

import re

from src.qt_api import (
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    Qt,
)

from src.shared.ui.theme import bind_theme, get_theme


class MarkdownPreview(QWidget):
    """Markdown → 富文本渲染控件（使用 Qt HTML 子集）。

    支持：# 标题, **粗体**, *斜体*, `行内代码`, --- 分割线,
          - 无序列表, > 引用块, [链接](url)

    用法::

        preview = MarkdownPreview()
        preview.set_markdown("# 你好\n\n这是 **粗体** 和 *斜体*。")
    """

    def __init__(self, *, parent=None):
        super().__init__(parent)
        self._raw = ""

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._view = QTextEdit()
        self._view.setReadOnly(True)
        self._view.setFrameShape(QTextEdit.NoFrame)
        layout.addWidget(self._view)

    def _apply_theme(self) -> None:
        t = get_theme()
        self._view.setStyleSheet(
            f"""
            QTextEdit {{
                background: {t.bg_card};
                color: {t.text_primary};
                border: none;
                padding: 8px;
                font-size: {t.font_size_md}px;
                selection-background-color: {t.primary_light};
            }}
            QScrollBar:vertical {{
                background: transparent; width: 8px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {t.scrollbar_thumb};
                border-radius: 4px; min-height: 20px;
            }}
            """
        )
        # 重新渲染以使颜色生效
        if self._raw:
            self._render()

    # ── 转换 ─────────────────────────────────────────────────────────────────

    def _md_to_html(self, md: str) -> str:
        """简易 Markdown → Qt HTML 转换"""
        t = get_theme()
        lines = md.split("\n")
        html_lines = []
        in_ul = False

        for line in lines:
            # 无序列表
            if re.match(r"^[-*+]\s+", line):
                if not in_ul:
                    html_lines.append("<ul>")
                    in_ul = True
                content = re.sub(r"^[-*+]\s+", "", line)
                html_lines.append(f"<li>{self._inline(content)}</li>")
                continue
            else:
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False

            # 标题
            m = re.match(r"^(#{1,6})\s+(.*)", line)
            if m:
                level = len(m.group(1))
                sizes = {1: "24", 2: "20", 3: "16", 4: "14", 5: "13", 6: "12"}
                sz = sizes.get(level, "14")
                html_lines.append(
                    f'<p style="font-size:{sz}px;font-weight:600;'
                    f'color:{t.text_primary};margin:8px 0 4px 0;">'
                    f'{self._inline(m.group(2))}</p>'
                )
                continue

            # 水平分割线
            if re.match(r"^[-_*]{3,}$", line.strip()):
                html_lines.append(
                    f'<hr style="border:none;border-top:1px solid {t.divider};margin:8px 0;">'
                )
                continue

            # 引用块
            if line.startswith("> "):
                content = line[2:]
                html_lines.append(
                    f'<blockquote style="border-left:3px solid {t.primary};'
                    f'padding-left:12px;color:{t.text_secondary};margin:4px 0;">'
                    f'{self._inline(content)}</blockquote>'
                )
                continue

            # 空行
            if line.strip() == "":
                html_lines.append("<br>")
                continue

            # 普通段落
            html_lines.append(
                f'<p style="margin:2px 0;color:{t.text_primary};">'
                f'{self._inline(line)}</p>'
            )

        if in_ul:
            html_lines.append("</ul>")

        return "".join(html_lines)

    def _inline(self, text: str) -> str:
        """处理行内元素"""
        t = get_theme()
        # 行内代码
        text = re.sub(
            r"`([^`]+)`",
            f'<code style="background:{t.bg_hover};color:{t.error};'
            f'padding:1px 4px;border-radius:3px;font-family:monospace;">'
            r"\1</code>",
            text,
        )
        # 粗体
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"__(.+?)__",   r"<b>\1</b>", text)
        # 斜体
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        text = re.sub(r"_(.+?)_",   r"<i>\1</i>", text)
        # 链接
        text = re.sub(
            r"\[(.+?)\]\((.+?)\)",
            f'<a href="\\2" style="color:{t.text_link};">\\1</a>',
            text,
        )
        return text

    def _render(self) -> None:
        html = self._md_to_html(self._raw)
        self._view.setHtml(html)

    # ── 公共 API ─────────────────────────────────────────────────────────────

    def set_markdown(self, text: str) -> None:
        """设置 Markdown 内容"""
        self._raw = text
        self._render()

    def get_markdown(self) -> str:
        return self._raw

    def clear(self) -> None:
        self._raw = ""
        self._view.clear()
