"""
Style preview widget.
"""

from __future__ import annotations

from src.qt_api import QLabel, QFont, Qt

from src.shared.ui.theme import bind_theme, get_theme


DEFAULT_SAMPLE_TEXT = "样式预览示例 AaBbCc 123"


class StylePreview(QLabel):
    """Preview label for typography settings."""

    SAMPLE_TEXT = DEFAULT_SAMPLE_TEXT

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText(self.SAMPLE_TEXT)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _apply_theme(self) -> None:
        t = get_theme()
        self.setMinimumHeight(t.style_preview_min_height)
        self.setStyleSheet(
            f"""
            QLabel {{
                background: {t.bg_input};
                border: 1px solid {t.border};
                border-radius: {t.radius_sm}px;
                padding: {t.style_preview_padding}px;
                color: {t.text_primary};
            }}
            """
        )

    def update_preview(
        self,
        *,
        font_cn: str = '',
        font_en: str = '',
        size_pt: float = 12,
        bold: bool = False,
        line_spacing: float = 1.5,
    ):
        font = QFont()
        if font_cn:
            font.setFamily(font_cn)
        elif font_en:
            font.setFamily(font_en)
        font.setPointSizeF(size_pt)
        font.setBold(bold)
        self.setFont(font)
