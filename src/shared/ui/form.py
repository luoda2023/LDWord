"""Form — 表单容器控件（校验 / 提交 / 错误态）"""

from __future__ import annotations

from typing import Callable

from src.qt_api import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)

from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.divider import Divider
from src.shared.ui.inline_alert import InlineAlert


class FormField:
    """单个表单字段的元数据。"""

    def __init__(
        self,
        name: str,
        widget: QWidget,
        *,
        label: str = "",
        required: bool = False,
        validator: Callable[[str], str | None] | None = None,
    ):
        self.name = name
        self.widget = widget
        self.label = label or name
        self.required = required
        self.validator = validator
        self.error_lbl: QLabel | None = None


class Form(QWidget):
    """表单容器，管理字段校验、错误提示和提交逻辑。

    用法::

        form = Form()

        name_edit = QLineEdit()
        form.add_field("name", name_edit, label="姓名", required=True)

        age_edit = QLineEdit()
        form.add_field(
            "age", age_edit, label="年龄",
            validator=lambda v: "请输入数字" if not v.isdigit() else None
        )

        form.submitted.connect(lambda data: print(data))
        form.add_submit_button("提交")
    """

    submitted = Signal(dict)    # 校验通过后提交，参数为 {name: value}
    cancelled = Signal()

    def __init__(self, *, parent=None):
        super().__init__(parent)
        self._fields: list[FormField] = []
        self._alert: InlineAlert | None = None

        self._setup_ui()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(16)

        # 顶层错误提示（隐藏）
        self._alert = InlineAlert("", variant="error", closable=False)
        self._alert.hide()
        self._layout.addWidget(self._alert)

        # 按钮行占位（始终在底部）
        self._btn_row = QHBoxLayout()
        self._btn_row.setSpacing(8)
        self._btn_row.addStretch()

    def _apply_theme(self) -> None:
        t = get_theme()
        self.setStyleSheet("Form { background: transparent; }")
        # 更新所有字段错误标签颜色
        for field in self._fields:
            if field.error_lbl:
                field.error_lbl.setStyleSheet(
                    f"color:{t.error};font-size:{t.font_size_sm}px;"
                    f"background:transparent;border:none;"
                )

    # ── 字段管理 ─────────────────────────────────────────────────────────────

    def add_field(
        self,
        name: str,
        widget: QWidget,
        *,
        label: str = "",
        required: bool = False,
        validator: Callable[[str], str | None] | None = None,
    ) -> "Form":
        """添加表单字段，返回 self 支持链式调用。"""
        t = get_theme()
        ff = FormField(
            name, widget,
            label=label, required=required, validator=validator,
        )
        self._fields.append(ff)

        field_widget = QWidget()
        field_l = QVBoxLayout(field_widget)
        field_l.setContentsMargins(0, 0, 0, 0)
        field_l.setSpacing(4)

        # 标签
        lbl_text = f"{ff.label}{'  *' if required else ''}"
        lbl = QLabel(lbl_text)
        lbl.setStyleSheet(
            f"color:{t.text_primary};font-size:{t.font_size_md}px;"
            f"font-weight:{t.font_weight_medium};background:transparent;border:none;"
        )
        field_l.addWidget(lbl)

        # 输入控件
        field_l.addWidget(widget)

        # 错误信息标签（默认隐藏）
        err_lbl = QLabel()
        err_lbl.setStyleSheet(
            f"color:{t.error};font-size:{t.font_size_sm}px;"
            f"background:transparent;border:none;"
        )
        err_lbl.hide()
        field_l.addWidget(err_lbl)
        ff.error_lbl = err_lbl

        # 插入在按钮行之前
        insert_pos = self._layout.count() - 1   # 按钮行在最后
        self._layout.insertWidget(insert_pos, field_widget)
        return self

    def add_divider(self) -> "Form":
        insert_pos = self._layout.count() - 1
        self._layout.insertWidget(insert_pos, Divider())
        return self

    def add_submit_button(
        self,
        text: str = "提交",
        *,
        cancel_text: str = "",
    ) -> "Form":
        """添加提交按钮（和可选的取消按钮），最终推入布局。"""
        t = get_theme()

        if cancel_text:
            cancel_btn = QPushButton(cancel_text)
            cancel_btn.setCursor(Qt.PointingHandCursor)
            cancel_btn.clicked.connect(self.cancelled.emit)
            apply_button_variant(cancel_btn, "secondary")
            apply_size_class(cancel_btn, "md")
            cancel_btn.setStyleSheet(build_button_stylesheet(t))
            self._btn_row.addWidget(cancel_btn)

        submit_btn = QPushButton(text)
        submit_btn.setCursor(Qt.PointingHandCursor)
        submit_btn.clicked.connect(self._on_submit)
        apply_button_variant(submit_btn, "primary")
        apply_size_class(submit_btn, "md")
        submit_btn.setStyleSheet(build_button_stylesheet(t))
        self._btn_row.addWidget(submit_btn)
        self._layout.addLayout(self._btn_row)
        return self

    # ── 校验 & 提交 ───────────────────────────────────────────────────────────

    def _get_field_value(self, field: FormField) -> str:
        """从各类控件提取文本值"""
        w = field.widget
        for method in ("text", "toPlainText", "currentText", "get_text"):
            if hasattr(w, method):
                val = getattr(w, method)()
                return str(val) if val is not None else ""
        return ""

    def _on_submit(self) -> None:
        errors = self.validate()
        if not errors:
            data = {f.name: self._get_field_value(f) for f in self._fields}
            self._alert.hide()
            self.submitted.emit(data)
        else:
            msg = "；".join(errors)
            self._alert.set_message(msg)
            self._alert.show()

    def validate(self) -> list[str]:
        """校验所有字段，返回错误信息列表（为空表示校验通过）。"""
        errors: list[str] = []
        for field in self._fields:
            value = self._get_field_value(field)

            # 必填校验
            if field.required and not value.strip():
                msg = f"{field.label} 不能为空"
                errors.append(msg)
                if field.error_lbl:
                    field.error_lbl.setText(msg)
                    field.error_lbl.show()
                continue

            # 自定义校验
            if field.validator:
                msg = field.validator(value)
                if msg:
                    errors.append(msg)
                    if field.error_lbl:
                        field.error_lbl.setText(msg)
                        field.error_lbl.show()
                    continue

            # 通过：清除错误
            if field.error_lbl:
                field.error_lbl.hide()

        return errors

    def reset(self) -> None:
        """清空所有错误状态"""
        self._alert.hide()
        for field in self._fields:
            if field.error_lbl:
                field.error_lbl.hide()
