"""
GlobalInputGuard — 全局输入守卫

一劳永逸修复 Qt 原生 SpinBox / ComboBox 的恼人默认行为：
    1. 滚轮劫持：阻止 ComboBox / SpinBox 在页面滚动时被鼠标掠过而意外改值。
    2. Enter 确认退出：按 Enter 后提交值 + 取消全选 + 释放焦点（离开 SpinBox）。

交互设计（最终确认版）：
    - 单击 SpinBox → 定位光标（精确编辑）
    - 双击 SpinBox → 全选文本（Qt 默认行为，保留）
    - Enter → 确认值并离开
    - 滚轮 → 被拦截，防止意外改值

用法：在 QApplication 创建后、show() 之前调用一次：

    from src.shared.ui.input_guard import install_global_input_guard
    install_global_input_guard(app)
"""

from __future__ import annotations

from src.qt_api import QAbstractItemView, QAbstractSlider, QAbstractSpinBox, QComboBox, QEvent, QObject, QScrollBar, Qt


def _get_spinbox(obj: QObject):
    """如果 obj 是 SpinBox 或其内部子控件，返回该 SpinBox；否则 None。"""
    # obj 自身就是 SpinBox
    if isinstance(obj, QAbstractSpinBox):
        return obj
    # 沿 parent 链向上查找
    p = obj.parent() if obj else None
    while p:
        if isinstance(p, QAbstractSpinBox):
            return p
        p = p.parent()
    return None


class GlobalInputGuard(QObject):
    """App 级 EventFilter，自动覆盖所有 SpinBox / ComboBox 实例。"""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        etype = event.type()

        # ── 1. 滚轮守卫 ──
        if etype == QEvent.Wheel:
            
            # 允许下拉框 Popup 菜单自身的滚动
            curr = obj
            while curr:
                if isinstance(curr, QAbstractItemView):
                    return False
                curr = curr.parent()

            # 封杀 ComboBox / SpinBox / Slider 滚轮改值
            # 但排除 QScrollBar — 否则 QScrollArea 无法滚轮滚动
            curr = obj
            while curr:
                if isinstance(curr, QScrollBar):
                    return False  # 放行，让滚动条正常工作
                if isinstance(curr, (QComboBox, QAbstractSpinBox, QAbstractSlider)):
                    event.ignore()
                    return True
                curr = curr.parent()

        # ── 2. Enter 键守卫 ──
        # Qt 默认行为：SpinBox 按 Enter → interpretText() → selectAll()
        # 我们想要：Enter → interpretText() → deselect()
        #
        # 关键：App 级 eventFilter 会对同一个按键看到两次事件：
        #   - 第 1 次 obj = QLineEdit（SpinBox 内部的输入框）
        #   - 第 2 次 obj = QSpinBox（SpinBox 自身）
        # 我们必须两次都拦截，否则第 2 次会触发 Qt 默认的 selectAll。
        if etype == QEvent.KeyPress and hasattr(event, 'key'):
            try:
                key = event.key()
            except Exception:
                key = None
            if key in (Qt.Key_Return, Qt.Key_Enter):
                spinbox = _get_spinbox(obj)
                if spinbox is not None:
                    le = spinbox.lineEdit()
                    spinbox.interpretText()
                    if le:
                        le.deselect()
                        le.clearFocus()  # 确认值后释放焦点，离开 SpinBox
                    # 风险防护 R1: 仍用 return True 拦截，因为 clearFocus()
                    # 已将焦点移走，后续 Enter 事件不会再命中 SpinBox。
                    # 对话框 Default 按钮的 Enter 不受影响（焦点已不在 SpinBox 上）。
                    return True

        return super().eventFilter(obj, event)


def install_global_input_guard(app) -> GlobalInputGuard:
    """在 QApplication 上安装全局输入守卫。返回守卫实例（需保持引用防止 GC）。"""
    guard = GlobalInputGuard(app)
    app.installEventFilter(guard)
    return guard
