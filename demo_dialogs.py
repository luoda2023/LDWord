"""弹窗组件演示 — 展示所有 5 种对话框类型。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.qt_api import QApplication, QFont, QPushButton, QVBoxLayout, QWidget, Qt

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
try:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
except AttributeError:
    pass

app = QApplication(sys.argv)

from src.shared.ui.theme import get_theme
from src.shared.ui.dialogs import info, success, warning, error, confirm, input_text

t = get_theme()
font = QFont(t.font_family.split(",")[0].strip("' "))
font.setPointSize(10)  # 用 pt 而非 px，跟随系统 DPI 缩放
app.setFont(font)


class DemoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("弹窗演示")
        self.setFixedSize(300, 380)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        for text, fn in [
            ("ℹ 信息提示", self._info),
            ("✓ 成功提示", self._success),
            ("⚠ 警告提示", self._warning),
            ("✕ 错误提示", self._error),
            ("❓ 确认对话框", self._confirm),
            ("❓ 危险确认", self._confirm_danger),
            ("✏ 输入对话框", self._input),
        ]:
            btn = QPushButton(text)
            btn.setFixedHeight(40)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(fn)
            layout.addWidget(btn)

    def _info(self):
        info("操作完成", "文件已成功保存到 output/ 目录。")

    def _success(self):
        success("格式化完成", "共处理 42 个段落，0 个错误。")

    def _warning(self):
        warning("覆盖警告", "目标文件已存在，继续操作将覆盖原有内容。")

    def _error(self):
        error(
            "格式化失败",
            "处理文档时发生错误，已记录到日志文件。",
            detail="Traceback (most recent call last):\n"
                   "  File \"pipeline.py\", line 42\n"
                   "    result = module.execute(doc)\n"
                   "ValueError: 无法解析段落样式 'Heading 99'",
            log_path="C:\\...\\lark_formatter.log",
        )

    def _confirm(self):
        ok = confirm("保存更改", "当前模板已修改，是否保存？")
        print(f"  确认结果: {ok}")

    def _confirm_danger(self):
        ok = confirm("删除模板", "确定要删除「论文格式 v2」？此操作不可撤销。",
                      confirm_text="删除", destructive=True)
        print(f"  删除确认: {ok}")

    def _input(self):
        name = input_text("新建模板", "请输入模板名称:",
                          placeholder="thesis-v2")
        print(f"  输入结果: {name}")


win = DemoWindow()
win.show()
sys.exit(app.exec())
