"""MarkdownPreview - lightweight Markdown renderer with GFM table support."""

from __future__ import annotations

import html
import re

from src.qt_api import QTextEdit, QVBoxLayout, QWidget
from src.shared.ui.theme import bind_theme, get_theme


class MarkdownPreview(QWidget):
    """Render common Markdown and GFM tables using Qt-compatible HTML."""

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
        self._view = QTextEdit(self)
        self._view.setReadOnly(True)
        self._view.setFrameShape(QTextEdit.NoFrame)
        layout.addWidget(self._view)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._view.setStyleSheet(
            f"""
            QTextEdit {{
                background: {theme.bg_card};
                color: {theme.text_primary};
                border: none;
                padding: 8px;
                font-size: {theme.font_size_md}px;
                selection-background-color: {theme.primary_light};
            }}
            QScrollBar:vertical {{ background: transparent; width: 8px; border: none; }}
            QScrollBar::handle:vertical {{
                background: {theme.scrollbar_thumb}; border-radius: 4px; min-height: 20px;
            }}
            """
        )
        if self._raw:
            self._render()

    def _md_to_html(self, markdown: str) -> str:
        theme = get_theme()
        lines = str(markdown or "").splitlines()
        result: list[str] = []
        in_list = False
        index = 0
        while index < len(lines):
            table_end = _table_end(lines, index)
            if table_end is not None:
                if in_list:
                    result.append("</ul>")
                    in_list = False
                result.append(_render_table(lines[index:table_end], theme))
                index = table_end
                continue

            line = lines[index]
            if re.match(r"^[-*+]\s+", line):
                if not in_list:
                    result.append("<ul>")
                    in_list = True
                result.append(f"<li>{self._inline(re.sub(r'^[-*+]\\s+', '', line))}</li>")
                index += 1
                continue
            if in_list:
                result.append("</ul>")
                in_list = False

            heading = re.match(r"^(#{1,6})\s+(.*)", line)
            if heading:
                sizes = {1: "24", 2: "20", 3: "16", 4: "14", 5: "13", 6: "12"}
                size = sizes[len(heading.group(1))]
                result.append(
                    f'<p style="font-size:{size}px;font-weight:{theme.font_weight_emphasis};'
                    f'color:{theme.text_primary};margin:8px 0 4px 0;">'
                    f"{self._inline(heading.group(2))}</p>"
                )
            elif re.match(r"^[-_*]{3,}$", line.strip()):
                result.append(f'<hr style="border:none;border-top:1px solid {theme.divider};margin:8px 0;">')
            elif line.startswith("> "):
                result.append(
                    f'<blockquote style="border-left:3px solid {theme.primary};padding-left:12px;'
                    f'color:{theme.text_secondary};margin:4px 0;">{self._inline(line[2:])}</blockquote>'
                )
            elif not line.strip():
                result.append("<br>")
            else:
                result.append(f'<p style="margin:2px 0;color:{theme.text_primary};">{self._inline(line)}</p>')
            index += 1
        if in_list:
            result.append("</ul>")
        return "".join(result)

    def _inline(self, text: str) -> str:
        theme = get_theme()
        escaped = html.escape(str(text or ""))
        escaped = re.sub(
            r"`([^`]+)`",
            f'<code style="background:{theme.bg_hover};color:{theme.error};padding:1px 4px;">\\1</code>',
            escaped,
        )
        escaped = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda match: f"<b>{match.group(1) or match.group(2)}</b>", escaped)
        escaped = re.sub(r"\*([^*]+)\*|_([^_]+)_", lambda match: f"<i>{match.group(1) or match.group(2)}</i>", escaped)
        return re.sub(
            r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
            f'<a href="\\2" style="color:{theme.text_link};">\\1</a>',
            escaped,
        )

    def _render(self) -> None:
        self._view.setHtml(self._md_to_html(self._raw))

    def set_markdown(self, text: str) -> None:
        self._raw = str(text or "")
        self._render()

    def get_markdown(self) -> str:
        return self._raw

    def clear(self) -> None:
        self._raw = ""
        self._view.clear()


def _table_end(lines: list[str], start: int) -> int | None:
    if start + 1 >= len(lines) or "|" not in lines[start] or not _is_table_separator(lines[start + 1]):
        return None
    end = start + 2
    while end < len(lines) and "|" in lines[end] and lines[end].strip():
        end += 1
    return end


def _is_table_separator(line: str) -> bool:
    cells = _table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def _table_cells(line: str) -> list[str]:
    content = str(line or "").strip()
    if content.startswith("|"):
        content = content[1:]
    if content.endswith("|"):
        content = content[:-1]
    return [cell.strip() for cell in content.split("|")]


def _render_table(lines: list[str], theme) -> str:
    headers = _table_cells(lines[0])
    width = len(headers)
    rows = [_table_cells(line)[:width] for line in lines[2:]]
    rendered_rows = [
        "<tr>" + "".join(
            f'<th style="background:{theme.bg_hover};padding:6px;border:1px solid {theme.border_light};">{html.escape(cell)}</th>'
            for cell in headers
        ) + "</tr>"
    ]
    for row in rows:
        row += [""] * (width - len(row))
        rendered_rows.append(
            "<tr>" + "".join(
                f'<td style="padding:6px;border:1px solid {theme.border_light};">{html.escape(cell)}</td>'
                for cell in row
            ) + "</tr>"
        )
    return f'<table cellspacing="0" cellpadding="0" style="margin:8px 0;border-collapse:collapse;">{"".join(rendered_rows)}</table>'
