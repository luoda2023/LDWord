"""Design-style typed question, plan, approval, progress and artifact cards."""

from __future__ import annotations

from collections.abc import Mapping

from src.assistant.ui.conversation_presentation import (
    ActionPresentation,
    build_question_response,
    project_interaction,
)
from src.assistant.ui.design_tokens import TOKENS
from src.assistant.ui.message_components import AssistantMessageFileCard
from src.qt_api import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.icons.catalog import get_icon


class _ChoiceButton(QPushButton):
    """A 30px Design question option with explicit selected state."""

    def __init__(
        self,
        choice_id: str,
        label: str,
        description: str,
        *,
        multiple: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.choice_id = str(choice_id)
        self.choice_label = str(label)
        self.choice_description = str(description)
        self.multiple = bool(multiple)
        self.setObjectName("assistant_question_choice")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(TOKENS.question_option_height)
        self.setAccessibleName(f"选项：{label}")
        self.toggled.connect(self._sync_text)
        self._sync_text(False)

    def _sync_text(self, checked: bool) -> None:
        marker = (
            ("☑" if checked else "□")
            if self.multiple
            else ("●" if checked else "○")
        )
        copy = self.choice_label
        if self.choice_description:
            copy += f"  ·  {self.choice_description}"
        self.setText(f"{marker}  {copy}")


class AssistantInteractionCard(QFrame):
    """Typed card that renders Form state using Design's interaction grammar."""

    action_requested = Signal(str, object)

    def __init__(
        self,
        *,
        interaction_type: str,
        title: str,
        body: str,
        payload: Mapping[str, object] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.payload = dict(payload or {})
        self.presentation = project_interaction(
            interaction_type=interaction_type,
            title=title,
            body=body,
            payload=self.payload,
        )
        self.interaction_type = self.presentation.interaction_type
        self.setObjectName("assistant_interaction_card")
        self.setProperty("tone", self.presentation.tone)
        self.setProperty("active", self.presentation.active)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAccessibleName(
            f"{self.presentation.eyebrow}：{self.presentation.title}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(7)
        self._type_icon = QLabel(self)
        self._type_icon.setObjectName("assistant_card_type_icon")
        self._type_icon.setFixedSize(18, 18)
        header.addWidget(self._type_icon)
        self._eyebrow = QLabel(self.presentation.eyebrow, self)
        self._eyebrow.setObjectName("assistant_card_eyebrow")
        header.addWidget(self._eyebrow)
        header.addStretch(1)
        layout.addLayout(header)

        self._title = QLabel(self.presentation.title, self)
        self._title.setObjectName("assistant_card_title")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)
        self._body = QLabel(self.presentation.body, self)
        self._body.setObjectName("assistant_card_body")
        self._body.setWordWrap(True)
        self._body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._body.setVisible(bool(self.presentation.body) and not self.presentation.facts)
        layout.addWidget(self._body)

        self._fact_host: QWidget | None = None
        if self.presentation.facts:
            self._fact_host = QWidget(self)
            self._fact_host.setObjectName("assistant_plan_facts")
            facts = QGridLayout(self._fact_host)
            facts.setContentsMargins(0, 2, 0, 2)
            facts.setHorizontalSpacing(12)
            facts.setVerticalSpacing(6)
            for index, (label, value) in enumerate(self.presentation.facts):
                label_widget = QLabel(label, self._fact_host)
                label_widget.setObjectName("assistant_plan_fact_label")
                value_widget = QLabel(value, self._fact_host)
                value_widget.setObjectName("assistant_plan_fact_value")
                value_widget.setWordWrap(True)
                row, column = divmod(index, 2)
                facts.addWidget(label_widget, row, column * 2)
                facts.addWidget(value_widget, row, column * 2 + 1)
            facts.setColumnStretch(1, 1)
            facts.setColumnStretch(3, 1)
            layout.addWidget(self._fact_host)
            if self.presentation.notices:
                self._body.setText(
                    "\n".join(f"• {item}" for item in self.presentation.notices)
                )
                self._body.show()

        self._file_cards: list[AssistantMessageFileCard] = []
        if self.presentation.files:
            file_stack = QWidget(self)
            file_stack.setObjectName("assistant_artifact_stack")
            stack_layout = QVBoxLayout(file_stack)
            stack_layout.setContentsMargins(0, 2, 0, 0)
            stack_layout.setSpacing(8)
            for file in self.presentation.files:
                card = AssistantMessageFileCard(
                    file,
                    variant="artifact",
                    parent=file_stack,
                )
                card.reference_requested.connect(self._open_reference)
                stack_layout.addWidget(card)
                self._file_cards.append(card)
            layout.addWidget(file_stack)

        self._choice_buttons: list[_ChoiceButton] = []
        self._choice_group: QButtonGroup | None = None
        self._other_input: QLineEdit | None = None
        self._question_submit: QPushButton | None = None
        self._question_skip: QToolButton | None = None
        if self.presentation.choices:
            self._build_question_choices(layout)

        self._progress: QProgressBar | None = None
        if self.interaction_type == "progress":
            self._progress = QProgressBar(self)
            self._progress.setObjectName("assistant_card_progress")
            current = int(self.payload.get("current") or 0)
            total = int(self.payload.get("total") or 0)
            if total > 0:
                self._progress.setRange(0, total)
                self._progress.setValue(max(0, min(total, current)))
                self._progress.setTextVisible(True)
            else:
                self._progress.setRange(0, 0)
                self._progress.setTextVisible(False)
            layout.addWidget(self._progress)

        self._actions = QHBoxLayout()
        self._actions.setContentsMargins(0, 4, 0, 0)
        self._actions.setSpacing(8)
        self._buttons: list[QPushButton] = []
        if not self.presentation.choices:
            for action in self.presentation.actions:
                self._add_action_button(action)
        self._actions.addStretch(1)
        if self._buttons:
            layout.addLayout(self._actions)

        receipt_text = {
            "question": "已提交 · 当前问题仅供回看",
            "disclosure": "已处理 · 当前披露确认仅供回看",
            "permission": "不可执行 · 没有可验证的权限恢复通道",
            "plan_candidate": "已处理 · 当前候选已不再生效",
            "plan": "已进入后续阶段 · 当前计划仅供回看",
            "approval": "审批状态已变化 · 当前卡片仅供回看",
            "progress": "该处理阶段已经结束",
        }.get(self.interaction_type, "")
        self._receipt = QLabel(receipt_text, self)
        self._receipt.setObjectName("assistant_card_receipt")
        self._receipt.setVisible(bool(receipt_text) and not self.presentation.active)
        if receipt_text:
            layout.addWidget(self._receipt)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def _build_question_choices(self, layout: QVBoxLayout) -> None:
        self._choice_group = QButtonGroup(self)
        self._choice_group.setExclusive(not self.presentation.multiple)
        choice_host = QWidget(self)
        choice_host.setObjectName("assistant_question_choices")
        choice_layout = QVBoxLayout(choice_host)
        choice_layout.setContentsMargins(0, 2, 0, 0)
        choice_layout.setSpacing(7)
        for choice in self.presentation.choices:
            button = _ChoiceButton(
                choice.choice_id,
                choice.label,
                choice.description,
                multiple=self.presentation.multiple,
                parent=choice_host,
            )
            button.toggled.connect(self._sync_question_submit)
            button.setEnabled(self.presentation.active)
            self._choice_group.addButton(button)
            self._choice_buttons.append(button)
            choice_layout.addWidget(button)
        if self.presentation.allow_other:
            self._other_input = QLineEdit(choice_host)
            self._other_input.setObjectName("assistant_question_other")
            self._other_input.setPlaceholderText("其他，请补充…")
            self._other_input.setMinimumHeight(TOKENS.question_option_height)
            self._other_input.setEnabled(self.presentation.active)
            self._other_input.textChanged.connect(self._sync_question_submit)
            choice_layout.addWidget(self._other_input)
        layout.addWidget(choice_host)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 2, 0, 0)
        footer.setSpacing(8)
        self._question_submit = QPushButton("提交", self)
        self._question_submit.setObjectName("assistant_question_submit")
        apply_button_variant(self._question_submit, "primary")
        self._question_submit.setEnabled(False)
        self._question_submit.clicked.connect(self._submit_question)
        footer.addWidget(self._question_submit)
        if self.presentation.can_skip:
            self._question_skip = QToolButton(self)
            self._question_skip.setObjectName("assistant_question_skip")
            self._question_skip.setText("跳过")
            self._question_skip.setEnabled(self.presentation.active)
            self._question_skip.setCursor(Qt.PointingHandCursor)
            self._question_skip.clicked.connect(
                lambda: self._submit_question(skipped=True)
            )
            footer.addWidget(self._question_skip)
        footer.addStretch(1)
        layout.addLayout(footer)

    def _selected_choice_labels(self) -> tuple[str, ...]:
        return tuple(
            button.choice_label for button in self._choice_buttons if button.isChecked()
        )

    def _sync_question_submit(self, *_args) -> None:
        if self._question_submit is None:
            return
        other = self._other_input.text().strip() if self._other_input is not None else ""
        self._question_submit.setEnabled(
            self.presentation.active
            and bool(self._selected_choice_labels() or other)
        )

    def _submit_question(self, _checked: bool = False, *, skipped: bool = False) -> None:
        response = build_question_response(
            self._selected_choice_labels(),
            other_text=self._other_input.text() if self._other_input is not None else "",
            skipped=skipped,
        )
        if not response:
            return
        emitted = {
            **self.payload,
            "response": response,
            "selected_choice_ids": [
                button.choice_id
                for button in self._choice_buttons
                if button.isChecked()
            ],
            "skipped": bool(skipped),
        }
        self.action_requested.emit("submit_question_answer", emitted)

    def _add_action_button(self, action: ActionPresentation) -> None:
        button = QPushButton(action.label, self)
        button.setObjectName("assistant_card_action")
        variant = action.variant
        if variant == "ghost":
            variant = "ghost-primary"
        if variant not in {
            "primary",
            "secondary",
            "danger",
            "ghost-primary",
            "ghost-danger",
        }:
            variant = "secondary"
        apply_button_variant(button, variant)
        button.setEnabled(action.enabled and self.presentation.active)
        button.clicked.connect(
            lambda _checked=False, value=action.action_id: self.action_requested.emit(
                value,
                dict(self.payload),
            )
        )
        self._actions.addWidget(button)
        self._buttons.append(button)

    def _open_reference(self, reference: object) -> None:
        payload = {**self.payload, "reference": reference}
        self.action_requested.emit("runtime_open_reference", payload)

    def _type_label(self) -> str:
        """Compatibility helper retained for existing integrations."""

        return self.presentation.eyebrow

    def _tone_colors(self):
        theme = get_theme()
        return {
            "warning": (theme.warning, theme.warning_bg),
            "danger": (theme.error, theme.error_bg),
            "success": (theme.success, theme.success_bg),
            "progress": (theme.primary, theme.info_bg),
        }.get(self.presentation.tone, (theme.primary, theme.bg_card))

    def _apply_theme(self) -> None:
        theme = get_theme()
        accent, surface = self._tone_colors()
        icon_name = {
            "question": "circle-help",
            "disclosure": "eye",
            "permission": "alert-triangle",
            "plan_candidate": "sparkles",
            "plan": "list-ordered",
            "preflight": "scan",
            "approval": "circle-check",
            "progress": "clock",
            "artifact": "file-text",
            "boundary": "circle-alert",
            "recovery": "circle-alert",
        }.get(self.interaction_type, "info")
        self._type_icon.setPixmap(get_icon(icon_name, 16, accent).pixmap(16, 16))
        self.setStyleSheet(
            f"""
            QFrame#assistant_interaction_card {{
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-left: 3px solid {accent};
                border-radius: {theme.radius_md}px;
            }}
            QWidget#assistant_artifact_stack,
            QWidget#assistant_question_choices,
            QWidget#assistant_plan_facts {{
                background: transparent;
                border: none;
            }}
            QLabel#assistant_card_type_icon {{
                background: transparent;
                border: none;
            }}
            QLabel#assistant_card_eyebrow {{
                color: {accent};
                background: transparent;
                font-size: {theme.font_size_sm}px;
                font-weight: {theme.font_weight_emphasis};
            }}
            QLabel#assistant_card_title {{
                color: {theme.text_primary};
                background: transparent;
                font-size: {theme.font_size_lg}px;
                font-weight: {theme.font_weight_emphasis};
            }}
            QLabel#assistant_card_body {{
                color: {theme.text_secondary};
                background: transparent;
                font-size: {theme.font_size_md}px;
            }}
            QLabel#assistant_card_receipt {{
                color: {theme.text_hint};
                background: {theme.bg_window};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_sm}px;
                padding: 5px 8px;
                font-size: {theme.font_size_sm}px;
            }}
            QLabel#assistant_plan_fact_label {{
                color: {theme.text_hint};
                background: transparent;
                border: none;
                font-size: {theme.font_size_sm}px;
            }}
            QLabel#assistant_plan_fact_value {{
                color: {theme.text_primary};
                background: {theme.bg_window};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_sm}px;
                padding: 4px 7px;
                font-size: {theme.font_size_sm}px;
            }}
            QPushButton#assistant_question_choice {{
                color: {theme.text_primary};
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_sm}px;
                padding: 5px 10px;
                text-align: left;
            }}
            QPushButton#assistant_question_choice:hover {{
                background: {theme.bg_hover};
                border-color: {theme.border};
            }}
            QPushButton#assistant_question_choice:checked {{
                color: {theme.primary};
                background: {theme.primary_light};
                border-color: {theme.border_focus};
            }}
            QLineEdit#assistant_question_other {{
                color: {theme.text_primary};
                background: {theme.bg_input};
                border: 1px solid {theme.border};
                border-radius: {theme.radius_sm}px;
                padding: 4px 8px;
            }}
            QLineEdit#assistant_question_other:focus {{
                border-color: {theme.border_focus};
            }}
            QToolButton#assistant_question_skip {{
                color: {theme.text_secondary};
                background: transparent;
                border: 1px solid transparent;
                border-radius: {theme.radius_sm}px;
                padding: 4px 8px;
            }}
            QToolButton#assistant_question_skip:hover {{
                color: {theme.text_primary};
                background: {theme.bg_hover};
                border-color: {theme.border_light};
            }}
            QProgressBar#assistant_card_progress {{
                color: {theme.text_secondary};
                background: {surface};
                border: 1px solid {theme.border_light};
                border-radius: 4px;
                min-height: 8px;
                max-height: 8px;
                text-align: center;
            }}
            QProgressBar#assistant_card_progress::chunk {{
                background: {accent};
                border-radius: 3px;
            }}
            """
        )
        button_style = build_button_stylesheet(theme)
        for button in self._buttons:
            button.setStyleSheet(button_style)
        if self._question_submit is not None:
            self._question_submit.setStyleSheet(button_style)


__all__ = ["AssistantInteractionCard"]
