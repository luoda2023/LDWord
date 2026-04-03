"""Phase A 控件测试脚本"""

import sys
from src.qt_api import QApplication, QVBoxLayout, QWidget
from src.shared.ui import Divider, TagChip, Spin, Typography
from src.shared.ui.theme import set_theme, LIGHT


def main():
    app = QApplication(sys.argv)
    set_theme(LIGHT)

    # 创建测试窗口
    window = QWidget()
    window.setWindowTitle("Phase A 控件测试")
    window.resize(400, 500)

    layout = QVBoxLayout(window)
    layout.setSpacing(16)
    layout.setContentsMargins(20, 20, 20, 20)

    # Typography 测试
    layout.addWidget(Typography("标题 H1", variant="h1"))
    layout.addWidget(Typography("标题 H2", variant="h2"))
    layout.addWidget(Typography("正文内容示例", variant="body"))
    layout.addWidget(Typography("辅助说明文字", variant="caption"))

    # Divider 测试
    layout.addWidget(Divider())

    # TagChip 测试
    layout.addWidget(Typography("标签示例：", variant="body"))
    tag_layout = QVBoxLayout()
    tag_layout.setSpacing(8)
    tag_layout.addWidget(TagChip("默认标签", variant="default"))
    tag_layout.addWidget(TagChip("主要标签", variant="primary"))
    tag_layout.addWidget(TagChip("成功标签", variant="success"))
    tag_layout.addWidget(TagChip("警告标签", variant="warning"))
    tag_layout.addWidget(TagChip("错误标签", variant="error"))
    tag_layout.addWidget(TagChip("可关闭标签", variant="info", closable=True))
    layout.addLayout(tag_layout)

    # Divider 测试
    layout.addWidget(Divider())

    # Spin 测试
    layout.addWidget(Typography("加载指示器：", variant="body"))
    layout.addWidget(Spin(tip="加载中..."))

    layout.addStretch()

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
