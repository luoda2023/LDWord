"""Typography — 统一文字组件"""

from __future__ import annotations

from src.qt_api import QLabel, Qt

from src.shared.ui.theme import bind_theme, get_theme


class Typography(QLabel):
    """统一的文字组件，支持多种文字样式。

    用法::

        # 标题
        title = Typography("页面标题", variant="h1")

        # 正文
        body = Typography("这是正文内容", variant="body")

        # 链接
        link = Typography("点击这里", variant="link")
        link.linkActivated.connect(lambda: print("链接被点击"))

        # 省略号
        text = Typography("很长的文本...", ellipsis=True)
    """

    def __init__(
        self,
        text: str = "",
        variant: str = "body",
        *,
        ellipsis: bool = False,
        parent=None,
    ):
        """初始化文字组件。

        Args:
            text: 文字内容
            variant: 样式变体 (h1/h2/h3/body/caption/link)
            ellipsis: 是否启用省略号
            parent: 父控件
        """
        super().__init__(text, parent)
        self._variant = variant
        self._ellipsis = ellipsis

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _setup_ui(self) -> None:
        """设置 UI 结构"""
        if self._ellipsis:
            self.setTextFormat(Qt.PlainText)
            self.setWordWrap(False)
        else:
            self.setWordWrap(True)

        if self._variant == "link":
            self.setOpenExternalLinks(False)
            self.setTextFormat(Qt.RichText)
            self.setTextInteractionFlags(
                Qt.TextBrowserInteraction | Qt.LinksAccessibleByMouse
            )
            self.setCursor(Qt.PointingHandCursor)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        t = get_theme()

        # 根据变体选择样式
        variant_styles = {
            "h1": {
                "font_size": t.font_size_xl,
                "font_weight": 600,
                "color": t.text_primary,
                "line_height": 1.3,
            },
            "h2": {
                "font_size": t.font_size_lg,
                "font_weight": 600,
                "color": t.text_primary,
                "line_height": 1.4,
            },
            "h3": {
                "font_size": t.font_size_md,
                "font_weight": 600,
                "color": t.text_primary,
                "line_height": 1.4,
            },
            "body": {
                "font_size": t.font_size_md,
                "font_weight": 400,
                "color": t.text_primary,
                "line_height": 1.6,
            },
            "caption": {
                "font_size": t.font_size_sm,
                "font_weight": 400,
                "color": t.text_secondary,
                "line_height": 1.5,
            },
            "link": {
                "font_size": t.font_size_md,
                "font_weight": 400,
                "color": t.text_link,
                "line_height": 1.6,
            },
        }

        style = variant_styles.get(self._variant, variant_styles["body"])

        stylesheet = f"""
            QLabel {{
                color: {style['color']};
                font-size: {style['font_size']}px;
                font-weight: {style['font_weight']};
                background: transparent;
                border: none;
            }}
        """

        if self._variant == "link":
            stylesheet += f"""
                QLabel:hover {{
                    color: {t.primary_hover};
                    text-decoration: underline;
                }}
            """

        self.setStyleSheet(stylesheet)

        # 设置省略号
        if self._ellipsis:
            self.setTextElideMode(Qt.ElideRight)

    def set_variant(self, variant: str) -> None:
        """设置样式变体"""
        self._variant = variant
        self._setup_ui()
        self._apply_theme()

    def variant(self) -> str:
        """获取样式变体"""
        return self._variant

    def set_ellipsis(self, ellipsis: bool) -> None:
        """设置是否启用省略号"""
        self._ellipsis = ellipsis
        self._setup_ui()
        self._apply_theme()

    def has_ellipsis(self) -> bool:
        """获取是否启用省略号"""
        return self._ellipsis
