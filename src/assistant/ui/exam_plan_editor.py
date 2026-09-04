"""Side-drawer editor for user-owned exam plan requirements."""

from __future__ import annotations

from collections.abc import Sequence

from src.assistant.application.exam_plan_editing import (
    ExamPlanEditValues,
    validate_exam_plan_edit_values,
)
from src.qt_api import (
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.button_style import (
    apply_button_variant,
    build_button_stylesheet,
)
from src.shared.ui.card import Card
from src.shared.ui.flow_section import FlowSection
from src.shared.ui.folder_picker import FolderPicker
from src.shared.ui.inline_alert import InlineAlert
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.inspector_form import InspectorForm
from src.shared.ui.selection_control_style import build_checkbox_stylesheet
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.styled_spin_box import StyledSpinBox
from src.shared.ui.theme import bind_theme, get_theme
from src.ui.adapters.config_selector_models import SelectorOption


class ExamPlanEditor(QWidget):
    save_requested = Signal(object)
    cancel_requested = Signal()

    def __init__(
        self,
        values: ExamPlanEditValues,
        *,
        master_options: Sequence[SelectorOption] = (),
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._initial = values
        self._master_options = tuple(master_options)
        self._build_ui()
        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("exam_plan_editor_scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget(scroll)
        content.setObjectName("exam_plan_editor_content")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(18, 16, 18, 16)

        intro = InlineAlert(
            "修改后会生成新的计划版本；已有题稿和执行前检查将失效。",
            variant="info",
            parent=content,
        )
        self._content_layout.addWidget(intro)

        basic_card = Card("基本要求", parent=content)
        basic_form = InspectorForm(parent=basic_card)
        self.stage = _combo(
            ("小学", "初中", "初中预备班", "高中"),
            self._initial.school_stage or "小学",
            parent=basic_form,
        )
        self.grade = _line_edit(
            self._initial.grade,
            placeholder="例如：六年级、高一",
            parent=basic_form,
        )
        self.subject = _combo(
            (
                "语文",
                "数学",
                "英语",
                "物理",
                "化学",
                "生物",
                "历史",
                "地理",
                "道德与法治",
                "信息技术",
                "科学",
            ),
            self._initial.subject,
            editable=True,
            parent=basic_form,
        )
        self.exam_period = _combo(
            ("随堂测验", "单元测试", "期中考试", "期末考试"),
            self._initial.exam_period,
            editable=True,
            parent=basic_form,
        )
        self.question_count = _spin(
            1, 100, self._initial.question_count, " 道", basic_form
        )
        self.duration = _spin(
            5, 300, self._initial.duration_minutes, " 分钟", basic_form
        )
        self.total_score = _spin(1, 500, self._initial.total_score, " 分", basic_form)

        basic_form.add_field("学段", self.stage)
        basic_form.add_field("年级", self.grade)
        basic_form.add_field("学科", self.subject)
        basic_form.add_field("考试类型", self.exam_period)
        basic_form.add_field("题量", self.question_count)
        basic_form.add_field("考试时长", self.duration)
        basic_form.add_field("满分", self.total_score)
        basic_card.add_widget(basic_form)
        self._content_layout.addWidget(basic_card)

        format_card = Card("格式与交付", parent=content)
        format_form = InspectorForm(parent=format_card)
        self.master = StyledComboBox(format_form)
        self.master.set_full_width_mode(True)
        self._populate_master_options()

        self.student_copy = QCheckBox("学生卷", format_form)
        self.student_copy.setChecked(self._initial.include_student)
        self.answer_copy = QCheckBox("答案卷", format_form)
        self.answer_copy.setChecked(self._initial.include_answer)
        delivery_host = QWidget(format_form)
        delivery_layout = QHBoxLayout(delivery_host)
        delivery_layout.setContentsMargins(0, 0, 0, 0)
        delivery_layout.addWidget(self.student_copy)
        delivery_layout.addWidget(self.answer_copy)
        delivery_layout.addStretch(1)

        self.analysis = QCheckBox("每题包含详细解析", format_form)
        self.analysis.setChecked(self._initial.analysis_required)
        self.output_root = FolderPicker(
            placeholder="请选择生成文件的保存目录",
            parent=format_form,
        )
        self.output_root.set_path(self._initial.output_root)

        format_form.add_field("卷面模板", self.master)
        format_form.add_field("交付内容", delivery_host)
        format_form.add_field("解析", self.analysis)
        format_form.add_field("输出目录", self.output_root)
        format_card.add_widget(format_form)
        self._content_layout.addWidget(format_card)

        advanced = FlowSection("教材与范围", expanded=False, parent=content)
        advanced_form = InspectorForm(parent=advanced)
        self.textbook = _combo(
            ("", "统编版", "部编版", "人教版", "沪教版", "苏教版", "北师大版"),
            self._initial.textbook_edition,
            editable=True,
            parent=advanced_form,
        )
        self.semester = _combo(
            ("", "上学期", "下学期", "上册", "下册"),
            self._initial.semester,
            editable=True,
            parent=advanced_form,
        )
        self.scope = _line_edit(
            self._initial.scope_hint,
            placeholder="例如：Unit 1–4、上册第一至四单元",
            parent=advanced_form,
        )
        advanced_form.add_field("教材版本", self.textbook)
        advanced_form.add_field("学期/册次", self.semester)
        advanced_form.add_field("考试范围", self.scope)
        advanced.add_widget(advanced_form)
        self._content_layout.addWidget(advanced)

        self._error = InlineAlert("", variant="error", parent=content)
        self._error.hide()
        self._content_layout.addWidget(self._error)
        self._content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self._footer = QWidget(self)
        self._footer.setObjectName("exam_plan_editor_footer")
        footer_layout = QHBoxLayout(self._footer)
        footer_layout.setContentsMargins(18, 12, 18, 12)
        footer_layout.setSpacing(8)
        footer_layout.addStretch(1)
        self.cancel_button = QPushButton("取消", self._footer)
        apply_button_variant(self.cancel_button, "secondary")
        apply_size_class(self.cancel_button, "md")
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.save_button = QPushButton("应用修改", self._footer)
        apply_button_variant(self.save_button, "primary")
        apply_size_class(self.save_button, "md")
        self.save_button.clicked.connect(self._submit)
        footer_layout.addWidget(self.cancel_button)
        footer_layout.addWidget(self.save_button)
        root.addWidget(self._footer)

    def _populate_master_options(self) -> None:
        options = self._master_options
        if not options:
            options = (
                SelectorOption(
                    value=self._initial.master_id or "default_exam",
                    label="A4 标准卷面",
                    source_type="builtin",
                ),
            )
        for option in options:
            badge_text = "内置" if option.source_type == "builtin" else "自定"
            badge_kind = "neutral" if option.source_type == "builtin" else "user"
            index = self.master.add_badged_item(
                option.label,
                option.value,
                badge_text=badge_text,
                badge_kind=badge_kind,
            )
            if option.tooltip:
                self.master.setItemData(index, option.tooltip, Qt.ToolTipRole)
            item = getattr(self.master.model(), "item", lambda _index: None)(index)
            if item is not None and option.disabled:
                item.setEnabled(False)
        selected = self.master.findData(self._initial.master_id)
        if selected >= 0:
            self.master.setCurrentIndex(selected)

    def _submit(self) -> None:
        try:
            values = ExamPlanEditValues(
                school_stage=self.stage.currentText().strip(),
                grade=self.grade.text().strip(),
                subject=self.subject.currentText().strip(),
                exam_period=self.exam_period.currentText().strip(),
                question_count=round(self.question_count.value()),
                duration_minutes=round(self.duration.value()),
                total_score=round(self.total_score.value()),
                textbook_edition=self.textbook.currentText().strip(),
                semester=self.semester.currentText().strip(),
                scope_hint=self.scope.text().strip(),
                include_student=self.student_copy.isChecked(),
                include_answer=self.answer_copy.isChecked(),
                analysis_required=self.analysis.isChecked(),
                output_root=self.output_root.path().strip(),
                master_id=str(self.master.currentData() or "").strip(),
            )
            validate_exam_plan_edit_values(values)
        except ValueError as exc:
            messages = {
                "exam_plan_grade_required": "请填写年级。",
                "exam_plan_subject_required": "请填写学科。",
                "exam_plan_delivery_required": "学生卷和答案卷至少选择一项。",
            }
            self._error.set_message(messages.get(str(exc), "请检查试卷要求后再保存。"))
            self._error.show()
            return
        self._error.hide()
        self.save_requested.emit(values)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._content_layout.setSpacing(theme.spacing_md)
        self.grade.setStyleSheet(build_text_input_stylesheet(theme))
        self.scope.setStyleSheet(build_text_input_stylesheet(theme))
        for control in (self.grade, self.scope):
            apply_size_class(control, "md")
        checkbox_style = build_checkbox_stylesheet(theme)
        for control in (self.student_copy, self.answer_copy, self.analysis):
            control.setStyleSheet(checkbox_style)
        button_style = build_button_stylesheet(theme)
        self.cancel_button.setStyleSheet(button_style)
        self.save_button.setStyleSheet(button_style)
        self.setStyleSheet(
            f"""
            #exam_plan_editor_scroll,
            #exam_plan_editor_content {{
                background: {theme.bg_window};
                border: none;
            }}
            #exam_plan_editor_footer {{
                background: {theme.bg_card};
                border-top: 1px solid {theme.border_light};
            }}
            """
        )


def _combo(
    options: Sequence[str],
    value: str,
    *,
    editable: bool = False,
    parent=None,
) -> StyledComboBox:
    control = StyledComboBox(parent)
    control.setEditable(editable)
    control.addItems(tuple(options))
    control.setCurrentText(str(value or ""))
    control.set_full_width_mode(True)
    return control


def _line_edit(value: str, *, placeholder: str, parent=None) -> QLineEdit:
    control = QLineEdit(str(value or ""), parent)
    control.setPlaceholderText(placeholder)
    return control


def _spin(
    minimum: int,
    maximum: int,
    value: int,
    suffix: str,
    parent=None,
) -> StyledSpinBox:
    control = StyledSpinBox(parent)
    control.setDecimals(0)
    control.setRange(minimum, maximum)
    control.setSingleStep(1)
    control.setValue(max(minimum, min(maximum, int(value))))
    control.setSuffix(suffix)
    return control


__all__ = ["ExamPlanEditor"]
