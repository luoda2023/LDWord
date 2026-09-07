"""Design-style typed question, plan, approval, progress and artifact cards."""

from __future__ import annotations

from collections.abc import Mapping

from src.assistant.ui.conversation_presentation import (
    ActionPresentation,
    action_icon_name,
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
    QSize,
    Qt,
    QToolButton,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.theme import bind_theme, get_theme


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
        # Every typed interaction shares one card shell.  Keeping this
        # compatibility attribute avoids making older integrations care about
        # the visual migration while preventing card kinds from drifting back
        # to the former stacked-title/left-accent variant.
        self._uses_compact_heading = True
        self.setObjectName("assistant_interaction_card")
        self.setProperty("tone", self.presentation.tone)
        self.setProperty("active", self.presentation.active)
        self.setProperty(
            "structuredQuestion",
            bool(self.presentation.question_inputs),
        )
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAccessibleName(
            f"{self.presentation.eyebrow}：{self.presentation.title}"
        )

        layout = QVBoxLayout(self)
        if self.interaction_type == "plan":
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(10)
        elif self.interaction_type == "progress":
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(7)
        else:
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(8)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        self._type_icon = QLabel(self)
        self._type_icon.setObjectName("assistant_card_type_icon")
        self._type_icon.setAlignment(Qt.AlignCenter)
        self._type_icon.setFixedSize(30, 30)
        header.addWidget(self._type_icon)
        self._eyebrow = QLabel(self.presentation.eyebrow, self)
        self._eyebrow.setObjectName("assistant_card_eyebrow")
        self._title = QLabel(self.presentation.title, self)
        self._title.setObjectName("assistant_card_title")
        self._title.setWordWrap(True)
        self._eyebrow.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._title.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self._eyebrow)
        header.addWidget(self._title, 1)
        header.setAlignment(self._type_icon, Qt.AlignVCenter)
        layout.addLayout(header)

        self._body = QLabel(self.presentation.body, self)
        self._body.setObjectName("assistant_card_body")
        self._body.setWordWrap(True)
        self._body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._body.setVisible(bool(self.presentation.body) and not self.presentation.facts)
        layout.addWidget(self._body)

        # 章节目录确认卡内嵌编辑器：改标题、增删章、上下移排序都在卡上
        # 直接完成，确认时随 payload 回传编辑后的目录。
        self._outline_editor_host: QWidget | None = None
        self._outline_editors: list[QLineEdit] = []
        self._outline_rows_host: QVBoxLayout | None = None
        if (
            self.interaction_type == "outline_confirm"
            and isinstance(self.payload.get("editable_outline"), (list, tuple))
        ):
            self._build_outline_editor(layout)

        self._fact_host: QWidget | None = None
        if self.presentation.facts:
            self._fact_host = QWidget(self)
            self._fact_host.setObjectName("assistant_plan_facts")
            if self.interaction_type == "plan":
                self._fact_host.setAttribute(Qt.WA_StyledBackground, True)
            facts = QGridLayout(self._fact_host)
            facts.setContentsMargins(
                10 if self.interaction_type == "plan" else 0,
                8 if self.interaction_type == "plan" else 2,
                10 if self.interaction_type == "plan" else 0,
                8 if self.interaction_type == "plan" else 2,
            )
            facts.setHorizontalSpacing(18)
            facts.setVerticalSpacing(7 if self.interaction_type == "plan" else 8)
            for index, (label, value) in enumerate(self.presentation.facts):
                label_widget = QLabel(label, self._fact_host)
                label_widget.setObjectName("assistant_plan_fact_label")
                value_widget = QLabel(value, self._fact_host)
                value_widget.setObjectName("assistant_plan_fact_value")
                value_widget.setWordWrap(True)
                value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
                row, column = divmod(index, 2)
                facts.addWidget(label_widget, row, column * 2)
                facts.addWidget(value_widget, row, column * 2 + 1)
            facts.setColumnStretch(1, 1)
            facts.setColumnStretch(3, 1)
            layout.addWidget(self._fact_host)
            if self.presentation.body or self.presentation.notices:
                notice_text = (
                    "\n".join(self.presentation.notices)
                    if self.interaction_type == "plan"
                    else "\n".join(
                        f"• {item}" for item in self.presentation.notices
                    )
                )
                if self.interaction_type == "plan" and self.presentation.notices:
                    self._body.setProperty("variant", "notice")
                body_text = str(self.presentation.body or "").strip()
                self._body.setText(
                    "\n".join(
                        item for item in (body_text, notice_text) if item
                    )
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
        self._choice_toggle: QToolButton | None = None
        self._other_input: QLineEdit | None = None
        self._question_inputs: dict[str, QLineEdit] = {}
        self._question_submit: QPushButton | None = None
        self._question_skip: QToolButton | None = None
        if self.presentation.choices or self.presentation.question_inputs:
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
                # 不确定进度（等待中）也铺满卡片宽度，不再限制为 180px 短条。
            layout.addWidget(self._progress)

        self._actions = QHBoxLayout()
        self._actions.setContentsMargins(0, 4, 0, 0)
        self._actions.setSpacing(8)
        self._buttons: list[QPushButton] = []
        if not (
            self.presentation.choices or self.presentation.question_inputs
        ):
            left_actions = tuple(
                action
                for action in self.presentation.actions
                if action.alignment != "right"
            )
            right_actions = tuple(
                action
                for action in self.presentation.actions
                if action.alignment == "right"
            )
            for action in left_actions:
                self._add_action_button(action)
            self._actions.addStretch(1)
            for action in right_actions:
                self._add_action_button(action)
        else:
            self._actions.addStretch(1)
        if self._buttons:
            layout.addLayout(self._actions)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    # ---- 章节目录内嵌编辑器 -------------------------------------------
    def _build_outline_editor(self, layout: QVBoxLayout) -> None:
        titles = [
            str(item or "").strip()
            for item in (self.payload.get("editable_outline") or ())
            if str(item or "").strip()
        ]
        if not titles:
            return
        host = QWidget(self)
        host.setObjectName("assistant_outline_editor")
        rows = QVBoxLayout(host)
        rows.setContentsMargins(0, 2, 0, 0)
        rows.setSpacing(6)
        self._outline_rows_host = rows
        self._outline_editor_host = host
        layout.addWidget(host)
        for title in titles:
            self._add_outline_row(title)
        add_btn = QToolButton(host)
        add_btn.setObjectName("assistant_outline_add")
        add_btn.setText("＋ 添加章节")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setEnabled(self.presentation.active)
        add_btn.clicked.connect(self._on_outline_add)
        rows.addWidget(add_btn, 0, Qt.AlignLeft)
        self._sync_outline_payload()

    def _add_outline_row(self, title: str) -> None:
        rows = self._outline_rows_host
        if rows is None:
            return
        index = len(self._outline_editors)
        row = QWidget(self._outline_editor_host)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        num = QLabel(f"{index + 1}.", row)
        num.setObjectName("assistant_outline_num")
        editor = QLineEdit(str(title or ""), row)
        editor.setObjectName("assistant_outline_edit")
        editor.setPlaceholderText("章节标题")
        editor.setEnabled(self.presentation.active)
        editor.textChanged.connect(self._sync_outline_payload)
        row_layout.addWidget(num, 0)
        row_layout.addWidget(editor, 1)
        for symbol, offset, tooltip in (
            ("↑", -1, "上移"),
            ("↓", 1, "下移"),
            ("✕", 0, "删除本章"),
        ):
            btn = QToolButton(row)
            btn.setText(symbol)
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setEnabled(self.presentation.active)
            if offset:
                btn.clicked.connect(
                    lambda _c=False, i=index, off=offset: self._move_outline_row(i, off)
                )
            else:
                btn.clicked.connect(
                    lambda _c=False, i=index: self._remove_outline_row(i)
                )
            row_layout.addWidget(btn, 0)
        rows.insertWidget(rows.count() - 1, row)  # above the add button
        self._outline_editors.append(editor)

    def _rebuild_outline_rows(self, titles: list[str]) -> None:
        rows = self._outline_rows_host
        if rows is None:
            return
        for editor in self._outline_editors:
            parent = editor.parentWidget()
            if parent is not None:
                parent.deleteLater()
        self._outline_editors = []
        for title in titles:
            self._add_outline_row(str(title))
        self._sync_outline_payload()

    def _outline_titles(self) -> list[str]:
        return [
            editor.text().strip()
            for editor in self._outline_editors
            if editor.text().strip()
        ]

    def _raw_outline_titles(self) -> list[str]:
        """All row titles including empty ones, so row indexes stay aligned."""
        return [editor.text() for editor in self._outline_editors]

    def _sync_outline_payload(self) -> None:
        self.payload["editable_outline"] = self._outline_titles()

    def _on_outline_add(self) -> None:
        self._add_outline_row("")
        if self._outline_editors:
            self._outline_editors[-1].setFocus()
        self._sync_outline_payload()

    def _move_outline_row(self, index: int, offset: int) -> None:
        titles = self._raw_outline_titles()
        target = index + int(offset)
        if index < 0 or index >= len(titles) or not 0 <= target < len(titles):
            return
        titles[index], titles[target] = titles[target], titles[index]
        self._rebuild_outline_rows(titles)

    def _remove_outline_row(self, index: int) -> None:
        titles = self._raw_outline_titles()
        if not 0 <= index < len(titles):
            return
        del titles[index]
        if not any(str(item).strip() for item in titles):
            return  # never collapse to a card with zero rows
        self._rebuild_outline_rows(titles)

    def _build_question_choices(self, layout: QVBoxLayout) -> None:
        self._choice_group = QButtonGroup(self)
        self._choice_group.setExclusive(not self.presentation.multiple)
        choice_host = QWidget(self)
        choice_host.setObjectName("assistant_question_choices")
        choice_layout = QVBoxLayout(choice_host)
        choice_layout.setContentsMargins(0, 2, 0, 0)
        choice_layout.setSpacing(9)
        if self.presentation.choices:
            if self.presentation.choices_label:
                label = QLabel(self.presentation.choices_label, choice_host)
                label.setObjectName("assistant_question_section_label")
                choice_layout.addWidget(label)
            choice_grid = QGridLayout()
            choice_grid.setContentsMargins(0, 0, 0, 0)
            choice_grid.setHorizontalSpacing(8)
            choice_grid.setVerticalSpacing(8)
            for index, choice in enumerate(self.presentation.choices):
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
                if (
                    self.presentation.initial_choice_count > 0
                    and index >= self.presentation.initial_choice_count
                ):
                    button.setVisible(False)
                row, column = divmod(
                    index,
                    self.presentation.choice_columns,
                )
                choice_grid.addWidget(button, row, column)
            for column in range(self.presentation.choice_columns):
                choice_grid.setColumnStretch(column, 1)
            choice_layout.addLayout(choice_grid)
            hidden_count = len(self.presentation.choices) - (
                self.presentation.initial_choice_count or len(self.presentation.choices)
            )
            if hidden_count > 0:
                self._choice_toggle = QToolButton(choice_host)
                self._choice_toggle.setObjectName(
                    "assistant_question_choice_toggle"
                )
                self._choice_toggle.setCheckable(True)
                self._choice_toggle.setCursor(Qt.PointingHandCursor)
                self._choice_toggle.setArrowType(Qt.DownArrow)
                self._choice_toggle.setToolButtonStyle(
                    Qt.ToolButtonTextBesideIcon
                )
                self._choice_toggle.setText(
                    self.presentation.expand_choices_label
                    or f"更多选项（{hidden_count}）"
                )
                self._choice_toggle.setEnabled(self.presentation.active)
                self._choice_toggle.toggled.connect(
                    self._set_choice_options_expanded
                )
                choice_layout.addWidget(
                    self._choice_toggle,
                    0,
                    Qt.AlignLeft,
                )
        if self.presentation.allow_other:
            self._other_input = QLineEdit(choice_host)
            self._other_input.setObjectName("assistant_question_other")
            self._other_input.setPlaceholderText(
                self.presentation.other_placeholder or "其他，请补充…"
            )
            self._other_input.setMinimumHeight(TOKENS.question_option_height)
            self._other_input.setEnabled(self.presentation.active)
            self._other_input.textChanged.connect(self._sync_question_submit)
            choice_layout.addWidget(self._other_input)
        if self.presentation.question_inputs:
            if self.presentation.inputs_label:
                label = QLabel(self.presentation.inputs_label, choice_host)
                label.setObjectName("assistant_question_section_label")
                choice_layout.addWidget(label)
            input_panel = QWidget(choice_host)
            input_panel.setObjectName("assistant_question_input_panel")
            input_panel.setAttribute(Qt.WA_StyledBackground, True)
            input_grid = QGridLayout(input_panel)
            input_grid.setContentsMargins(10, 9, 10, 10)
            input_grid.setHorizontalSpacing(10)
            input_grid.setVerticalSpacing(8)
            input_columns = self.presentation.question_input_columns
            cursor = 0
            for input_spec in self.presentation.question_inputs:
                span = min(input_columns, input_spec.column_span)
                column = cursor % input_columns
                if column + span > input_columns:
                    cursor += input_columns - column
                    column = 0
                field = QWidget(input_panel)
                field.setObjectName("assistant_question_input_field")
                field_layout = QVBoxLayout(field)
                field_layout.setContentsMargins(0, 0, 0, 0)
                field_layout.setSpacing(4)
                label = QLabel(
                    f"{input_spec.label}{' *' if input_spec.required else ''}",
                    field,
                )
                label.setObjectName("assistant_question_input_label")
                editor = QLineEdit(field)
                editor.setObjectName("assistant_question_input")
                editor.setPlaceholderText(input_spec.placeholder)
                editor.setText(input_spec.value)
                editor.setMinimumHeight(TOKENS.question_option_height)
                editor.setEnabled(self.presentation.active)
                editor.textChanged.connect(self._sync_question_submit)
                field_layout.addWidget(label)
                field_layout.addWidget(editor)
                row = cursor // input_columns
                input_grid.addWidget(field, row, column, 1, span)
                cursor += span
                self._question_inputs[input_spec.input_id] = editor
            for column in range(input_columns):
                input_grid.setColumnStretch(column, 1)
            choice_layout.addWidget(input_panel)
        layout.addWidget(choice_host)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 2, 0, 0)
        footer.setSpacing(8)
        if any(item.required for item in self.presentation.question_inputs):
            required_hint = QLabel("* 为必填项", self)
            required_hint.setObjectName("assistant_question_required_hint")
            footer.addWidget(required_hint)
        self._question_submit = QPushButton(
            self.presentation.submit_label or "提交",
            self,
        )
        self._question_submit.setObjectName("assistant_question_submit")
        self._question_submit.setProperty(
            "iconName",
            action_icon_name(
                "submit_question_answer",
                self.presentation.submit_label or "提交",
                alignment="right",
            ),
        )
        self._question_submit.setIconSize(QSize(16, 16))
        if self._uses_compact_heading:
            self._question_submit.setMinimumWidth(96)
        apply_button_variant(self._question_submit, "primary")
        self._question_submit.setEnabled(False)
        self._question_submit.clicked.connect(self._submit_question)
        if self.presentation.can_skip:
            self._question_skip = QToolButton(self)
            self._question_skip.setObjectName("assistant_question_skip")
            self._question_skip.setText("跳过")
            self._question_skip.setProperty(
                "iconName",
                action_icon_name(
                    "skip_question_answer",
                    "跳过",
                    alignment="left",
                ),
            )
            self._question_skip.setIconSize(QSize(16, 16))
            self._question_skip.setEnabled(self.presentation.active)
            self._question_skip.setCursor(Qt.PointingHandCursor)
            self._question_skip.clicked.connect(
                lambda: self._submit_question(skipped=True)
            )
            footer.addWidget(self._question_skip)
        footer.addStretch(1)
        footer.addWidget(self._question_submit)
        layout.addLayout(footer)
        self._sync_question_submit()

    def _set_choice_options_expanded(self, expanded: bool) -> None:
        visible_count = self.presentation.initial_choice_count
        if visible_count <= 0:
            return
        for index, button in enumerate(self._choice_buttons):
            if index >= visible_count:
                button.setVisible(bool(expanded))
        if self._choice_toggle is None:
            return
        hidden_count = max(0, len(self._choice_buttons) - visible_count)
        self._choice_toggle.setArrowType(
            Qt.UpArrow if expanded else Qt.DownArrow
        )
        self._choice_toggle.setText(
            (
                self.presentation.collapse_choices_label
                or "收起更多选项"
            )
            if expanded
            else (
                self.presentation.expand_choices_label
                or f"更多选项（{hidden_count}）"
            )
        )

    def _selected_choice_labels(self) -> tuple[str, ...]:
        return tuple(
            button.choice_label for button in self._choice_buttons if button.isChecked()
        )

    def _sync_question_submit(self, *_args) -> None:
        if self._question_submit is None:
            return
        other = self._other_input.text().strip() if self._other_input is not None else ""
        input_values = self._question_input_values()
        required_inputs_ready = all(
            bool(input_values.get(item.input_id))
            for item in self.presentation.question_inputs
            if item.required
        )
        choice_ready = bool(self._selected_choice_labels() or other)
        has_response = bool(choice_ready or any(input_values.values()))
        self._question_submit.setEnabled(
            self.presentation.active
            and required_inputs_ready
            and (
                choice_ready
                if self.presentation.requires_choice
                else has_response
            )
        )
        self._apply_button_icon(self._question_submit, get_theme())

    def _question_input_values(self) -> dict[str, str]:
        return {
            input_id: editor.text().strip()
            for input_id, editor in self._question_inputs.items()
            if editor.text().strip()
        }

    def _submit_question(self, _checked: bool = False, *, skipped: bool = False) -> None:
        input_values = self._question_input_values()
        input_labels = {
            item.input_id: item.label
            for item in self.presentation.question_inputs
        }
        response_labels = list(self._selected_choice_labels())
        response_labels.extend(
            f"{input_labels.get(input_id, input_id)}：{value}"
            for input_id, value in input_values.items()
        )
        response = build_question_response(
            response_labels,
            other_text=self._other_input.text() if self._other_input is not None else "",
            skipped=skipped,
        )
        if not response:
            return
        emitted = {
            **self.payload,
            "response": response,
            "other_text": (
                self._other_input.text().strip()
                if self._other_input is not None
                else ""
            ),
            "selected_choice_ids": [
                button.choice_id
                for button in self._choice_buttons
                if button.isChecked()
            ],
            "field_values": input_values,
            "skipped": bool(skipped),
        }
        self.action_requested.emit("submit_question_answer", emitted)

    def _add_action_button(self, action: ActionPresentation) -> None:
        button = QPushButton(action.label, self)
        button.setObjectName("assistant_card_action")
        button.setProperty("actionId", action.action_id)
        button.setProperty("iconName", action.icon_name)
        button.setIconSize(QSize(16, 16))
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
        # ActionPresentation already applies the card lifecycle policy while
        # allowing explicitly safe read-only actions to outlive a workflow.
        button.setEnabled(action.enabled)
        button.clicked.connect(
            lambda _checked=False, value=action.action_id: self._emit_action(value)
        )
        self._actions.addWidget(button)
        self._buttons.append(button)

    def _emit_action(self, action_id: str) -> None:
        if action_id in {
            "approve_execute",
            "generate_content_draft",
            "preflight",
            "retry_preflight",
        }:
            for button in self._buttons:
                button.setEnabled(False)
            self._apply_action_icons(get_theme())
        self.action_requested.emit(action_id, dict(self.payload))

    @staticmethod
    def _apply_button_icon(button, theme) -> None:
        icon_name = str(button.property("iconName") or "").strip()
        if not icon_name:
            return
        variant = str(button.property("variant") or "").strip()
        if not button.isEnabled():
            color = theme.text_disabled
        elif variant in {"primary", "danger"}:
            color = theme.text_on_primary
        elif variant == "ghost-danger":
            color = theme.error
        elif variant == "ghost-primary":
            color = theme.primary
        else:
            color = theme.icon_secondary
        button.setIcon(get_icon(icon_name, 16, color))

    def _apply_action_icons(self, theme) -> None:
        for button in self._buttons:
            self._apply_button_icon(button, theme)
        if self._question_submit is not None:
            self._apply_button_icon(self._question_submit, theme)
        if self._question_skip is not None:
            self._apply_button_icon(self._question_skip, theme)

    def _open_reference(self, reference: object) -> None:
        payload = {**self.payload, "reference": reference}
        if (
            isinstance(reference, Mapping)
            and str(reference.get("owner") or "") == "form"
            and str(reference.get("kind") or "") == "template_config"
        ):
            self.action_requested.emit("open_template_artifact", payload)
            return
        self.action_requested.emit("runtime_open_reference", payload)

    def _type_label(self) -> str:
        """Compatibility helper retained for existing integrations."""

        return self.presentation.eyebrow

    def preferred_width(self, available_width: int) -> int:
        """卡片宽度与对话消息同轴：跟随调用方给出的阅读列宽（视口 3/4）。

        卡片是结构化交互面，内部通过网格/边距自然约束可读性，不再用固定
        上限在宽屏下单独截窄，保证“对话窗口宽度一致、最多 3/4”的视觉规则。
        窄视口时仍保 260px 下限避免挤压。
        """

        return max(260, int(available_width))

    def _tone_colors(self):
        theme = get_theme()
        return {
            "warning": (theme.warning, theme.warning_bg),
            "danger": (theme.error, theme.error_bg),
            "success": (theme.success, theme.success_bg),
            "progress": (theme.primary, theme.info_bg),
        }.get(self.presentation.tone, (theme.primary, theme.primary_light))

    def _apply_theme(self) -> None:
        theme = get_theme()
        accent, surface = self._tone_colors()
        fact_surface = theme.bg_window if self.interaction_type == "plan" else "transparent"
        icon_name = {
            "question": "circle-help",
            "disclosure": "eye",
            "permission": "alert-triangle",
            "plan_candidate": "sparkles",
            "plan": "list-ordered",
            "preflight": "scan",
            "approval": "circle-check",
            "progress": "loader",
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
                border-radius: {theme.radius_lg}px;
            }}
            QWidget#assistant_artifact_stack,
            QWidget#assistant_question_choices,
            QWidget#assistant_question_input_field {{
                background: transparent;
                border: none;
            }}
            QWidget#assistant_question_input_panel {{
                background: {theme.bg_window};
                border: none;
                border-radius: {theme.radius_sm}px;
            }}
            QWidget#assistant_plan_facts {{
                background: {fact_surface};
                border: none;
                border-radius: {theme.radius_sm}px;
            }}
            QLabel#assistant_card_type_icon {{
                background: {surface};
                border: none;
                border-radius: {theme.radius_sm}px;
            }}
            QLabel#assistant_card_eyebrow {{
                color: {accent};
                background: transparent;
                font-size: {theme.font_size_lg}px;
                font-weight: {theme.font_weight_emphasis};
            }}
            QLabel#assistant_card_title {{
                color: {theme.text_primary};
                background: transparent;
                font-size: {theme.font_size_md}px;
                font-weight: {theme.font_weight_normal};
            }}
            QLabel#assistant_card_body {{
                color: {theme.text_secondary};
                background: transparent;
                font-size: {theme.font_size_md}px;
            }}
            QFrame#assistant_interaction_card[structuredQuestion="true"]
            QLabel#assistant_card_body {{
                color: {theme.text_secondary};
                font-size: {theme.font_size_sm}px;
            }}
            QLabel#assistant_card_body[variant="notice"] {{
                color: {theme.text_secondary};
                background: {theme.primary_light};
                border: none;
                border-radius: {theme.radius_sm}px;
                padding: 6px 9px;
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
                background: transparent;
                border: none;
                padding: 1px 0;
                font-size: {theme.font_size_sm}px;
                font-weight: {theme.font_weight_emphasis};
            }}
            QPushButton#assistant_question_choice {{
                color: {theme.text_primary};
                background: {theme.bg_card};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_sm}px;
                padding: 5px 10px;
                text-align: left;
            }}
            QFrame#assistant_interaction_card[structuredQuestion="true"]
            QPushButton#assistant_question_choice {{
                background: {theme.bg_window};
                border-color: transparent;
                padding: 5px 9px;
                font-size: {theme.font_size_sm}px;
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
            QToolButton#assistant_question_choice_toggle {{
                color: {theme.primary};
                background: transparent;
                border: none;
                border-radius: {theme.radius_sm}px;
                padding: 4px 7px;
                font-size: {theme.font_size_sm}px;
                font-weight: {theme.font_weight_emphasis};
            }}
            QToolButton#assistant_question_choice_toggle:hover {{
                background: {theme.primary_light};
            }}
            QLabel#assistant_question_section_label {{
                color: {theme.text_primary};
                background: transparent;
                border: none;
                font-size: {theme.font_size_sm}px;
                font-weight: {theme.font_weight_emphasis};
            }}
            QLabel#assistant_question_input_label {{
                color: {theme.text_secondary};
                background: transparent;
                border: none;
                font-size: {theme.font_size_sm}px;
            }}
            QLabel#assistant_question_required_hint {{
                color: {theme.text_hint};
                background: transparent;
                border: none;
                font-size: {theme.font_size_sm}px;
            }}
            QLineEdit#assistant_question_other,
            QLineEdit#assistant_question_input {{
                color: {theme.text_primary};
                background: {theme.bg_input};
                border: 1px solid {theme.border};
                border-radius: {theme.radius_sm}px;
                padding: 4px 8px;
            }}
            QLineEdit#assistant_question_other:focus,
            QLineEdit#assistant_question_input:focus {{
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
                background: {theme.progress_track};
                border: none;
                border-radius: 2px;
                min-height: 4px;
                max-height: 4px;
                text-align: center;
            }}
            QProgressBar#assistant_card_progress::chunk {{
                background: {accent};
                border-radius: 2px;
            }}
            """
        )
        button_style = build_button_stylesheet(theme)
        for button in self._buttons:
            button.setStyleSheet(button_style)
        if self._question_submit is not None:
            self._question_submit.setStyleSheet(button_style)
        self._apply_action_icons(theme)


__all__ = ["AssistantInteractionCard"]
