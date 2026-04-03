from __future__ import annotations

import html

from src.qt_api import QPushButton, QTextEdit, QVBoxLayout, QWidget, Qt
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.icons.catalog import get_icon


class LogStreamWidget(QWidget):
    """Append-only structured log stream with collapsible terminal view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines: list[str] = []
        self._error_count = 0
        self._is_expanded = False

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)

        # Toggle Button
        self._toggle_btn = QPushButton("展开日志详情 (0 Errors)", self)
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setObjectName("wb_v2_log_toggle")
        self._toggle_btn.clicked.connect(self._on_toggle)

        # Terminal View
        self._view = QTextEdit(self)
        self._view.setReadOnly(True)
        self._view.setVisible(False)
        self._view.setMinimumHeight(150)

        self._layout.addWidget(self._toggle_btn)
        self._layout.addWidget(self._view)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self):
        t = get_theme()

        # Style the toggle button to look subtle
        self._toggle_btn.setStyleSheet(f"""
            QPushButton#wb_v2_log_toggle {{
                background: transparent;
                border: 1px solid {t.border_light};
                border-radius: {t.radius_sm}px;
                color: {t.text_secondary};
                font-size: {t.font_size_sm}px;
                padding: 6px;
                text-align: left;
            }}
            QPushButton#wb_v2_log_toggle:hover {{
                background: {t.bg_hover};
            }}
            QPushButton#wb_v2_log_toggle:checked {{
                background: {t.bg_hover};
                color: {t.primary};
                border: 1px solid {t.primary_light};
            }}
        """)

        # Style the terminal view
        self._view.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1E1E2E;
                color: #A6ACCD;
                font-family: Consolas, monospace;
                border-radius: {t.radius_sm}px;
                padding: 12px;
                border: 1px solid #303040;
            }}
        """)

        icon_name = "chevron-down" if self._is_expanded else "chevron-right"
        self._toggle_btn.setIcon(get_icon(icon_name, size=16, color=t.primary if self._is_expanded else t.text_secondary))

    def _on_toggle(self, checked: bool):
        self._is_expanded = checked
        self._view.setVisible(checked)
        self._apply_theme() # update icon

    def append_log(self, level: str, message: str) -> None:
        raw_msg = str(message)
        line = f"[{level}] {raw_msg}"
        self._lines.append(line)

        if level.lower() in ("error", "critical", "fatal"):
            self._error_count += 1
            self._update_toggle_text()

        # Colorize based on level
        safe_msg = html.escape(raw_msg)
        if level.lower() == "info":
            color = "#A2B4C8" # light grey/blue
        elif level.lower() == "warning":
            color = "#FFCB6B" # yellow
        elif level.lower() in ("error", "critical"):
            color = "#F07178" # red
        elif level.lower() == "success":
            color = "#C3E88D" # green
        else:
            color = "#A6ACCD"

        html_line = f'<span style="color: {color};">[{level.upper()}] {safe_msg}</span>'
        self._view.append(html_line)

    def _update_toggle_text(self):
        text = "收起日志详情" if self._is_expanded else "展开日志详情"
        if self._error_count > 0:
            text += f" ({self._error_count} Errors)"
        self._toggle_btn.setText(text)

    def log_text(self) -> str:
        return "\n".join(self._lines)

    def clear(self) -> None:
        self._lines.clear()
        self._view.clear()
        self._error_count = 0
        self._update_toggle_text()
