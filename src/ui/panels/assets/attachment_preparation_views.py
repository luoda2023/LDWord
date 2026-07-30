"""Retained row widgets used by the attachment preparation workbench."""

from __future__ import annotations

from src.qt_api import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.config.entity import EntityProfile
from src.services.material_attachments import (
    AttachmentPreparationRequirement,
    AttachmentRequirementState,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.keyed_widget_list import KeyedWidgetListController
from src.shared.ui.material_text_views import ElidedValueEdit
from src.shared.ui.styled_combo_box import (
    SOURCE_BADGE_KIND_ROLE,
    SOURCE_BADGE_TEXT_ROLE,
    StyledComboBox,
)
from src.shared.ui.theme import bind_theme, get_theme


class AttachmentFieldPreparationRow(QFrame):
    """One exact field Token and the value for the selected data record."""

    value_committed = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("attachment_field_preparation_row")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._token = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 9, 14, 9)
        layout.setSpacing(14)

        self.token_label = QLabel(self)
        self.token_label.setObjectName("attachment_preparation_token")
        self.token_label.setWordWrap(True)
        self.token_label.setMinimumWidth(205)
        self.token_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.value_edit = ElidedValueEdit(parent=self)
        self.value_edit.setObjectName("attachment_preparation_value")
        self.value_edit.setPlaceholderText("待填写")
        self.value_edit.setMinimumWidth(175)
        self.value_edit.editingFinished.connect(self._emit_commit)

        self.usage_label = QLabel(self)
        self.usage_label.setObjectName("attachment_preparation_usage")
        self.usage_label.setAlignment(Qt.AlignCenter)
        self.usage_label.setFixedWidth(84)
        self.usage_label.setToolTip("")

        self.status_label = QLabel(self)
        self.status_label.setObjectName("attachment_preparation_row_status")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedWidth(64)

        layout.addWidget(self.token_label, 4)
        layout.addWidget(self.value_edit, 5)
        layout.addWidget(self.usage_label, 0)
        layout.addWidget(self.status_label, 0)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def update_requirement(
        self,
        requirement: AttachmentPreparationRequirement,
        *,
        profile_index: int,
        value: str,
    ) -> None:
        self._token = requirement.token
        self.token_label.setText(requirement.token)
        blocked = self.value_edit.blockSignals(True)
        try:
            self.value_edit.setText(value)
        finally:
            self.value_edit.blockSignals(blocked)
        self.usage_label.setText(
            f"{len(requirement.relative_paths)}文件·{requirement.occurrence_count}处"
        )
        profile_state = (
            requirement.profiles[profile_index].state
            if 0 <= profile_index < len(requirement.profiles)
            else AttachmentRequirementState.MISSING
        )
        profile_ready = profile_state is AttachmentRequirementState.RESOLVED
        self.status_label.setText(
            "待启用"
            if profile_state is AttachmentRequirementState.DISABLED
            else "已填写" if profile_ready else "待填写"
        )
        self.status_label.setProperty("ready", profile_ready)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.setAccessibleName(requirement.token)
        self.setAccessibleDescription(
            f"{self.status_label.text()}；{self.usage_label.text()}"
        )

    def _emit_commit(self) -> None:
        if self._token:
            self.value_committed.emit(self._token, self.value_edit.text())

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QFrame#attachment_field_preparation_row {{
                background: {theme.bg_card};
                border: none;
                border-bottom: 1px solid {theme.divider};
            }}
            QFrame#attachment_field_preparation_row:hover {{
                background: {theme.bg_hover};
            }}
            QLabel#attachment_preparation_token {{
                color: {theme.text_primary};
                font-size: {theme.font_size_md}px;
                font-weight: {theme.font_weight_emphasis};
                background: transparent;
                border: none;
            }}
            QLabel#attachment_preparation_usage {{
                color: {theme.text_hint};
                font-size: {theme.font_size_sm}px;
                background: transparent;
                border: none;
            }}
            QLabel#attachment_preparation_row_status {{
                color: {theme.warning};
                font-size: {theme.font_size_sm}px;
                background: {theme.warning_bg};
                border: none;
                border-radius: {theme.radius_sm}px;
                padding: 3px 5px;
            }}
            QLabel#attachment_preparation_row_status[ready="true"] {{
                color: {theme.success};
                background: {theme.success_bg};
            }}
            """
        )


class AttachmentTimelinePreparationRow(QFrame):
    """One timeline output with an inline ratio and deterministic preview."""

    ratio_changed = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("attachment_timeline_preparation_row")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._token = ""
        self._syncing = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 9, 14, 9)
        layout.setSpacing(14)

        self.token_label = QLabel(self)
        self.token_label.setObjectName("attachment_timeline_token")
        self.token_label.setWordWrap(True)
        self.token_label.setMinimumWidth(220)
        self.token_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.ratio_edit = ElidedValueEdit(parent=self)
        self.ratio_edit.setObjectName("attachment_timeline_ratio")
        self.ratio_edit.setFixedWidth(84)
        self.ratio_edit.textChanged.connect(self._on_ratio_changed)

        self.result_label = QLabel("—", self)
        self.result_label.setObjectName("attachment_timeline_result")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setFixedWidth(116)

        self.status_label = QLabel("待预览", self)
        self.status_label.setObjectName("attachment_timeline_status")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedWidth(84)

        layout.addWidget(self.token_label, 1)
        layout.addWidget(self.ratio_edit, 0)
        layout.addWidget(self.result_label, 0)
        layout.addWidget(self.status_label, 0)

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def update_requirement(
        self,
        requirement: AttachmentPreparationRequirement,
        *,
        ratio: str,
    ) -> None:
        self._token = requirement.token
        self.token_label.setText(requirement.token)
        self._syncing = True
        blocked = self.ratio_edit.blockSignals(True)
        try:
            self.ratio_edit.setText(ratio)
        finally:
            self.ratio_edit.blockSignals(blocked)
            self._syncing = False

    def ratio_text(self) -> str:
        return self.ratio_edit.text().strip()

    def set_preview(self, value: str, status: str) -> None:
        self.result_label.setText(str(value or "—"))
        self.status_label.setText(str(status or "待预览"))
        ready = bool(value)
        self.status_label.setProperty("ready", ready)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _on_ratio_changed(self, value: str) -> None:
        if not self._syncing and self._token:
            self.ratio_changed.emit(self._token, value)

    def _apply_theme(self) -> None:
        theme = get_theme()
        self.setStyleSheet(
            f"""
            QFrame#attachment_timeline_preparation_row {{
                background: {theme.bg_card};
                border: none;
                border-bottom: 1px solid {theme.divider};
            }}
            QFrame#attachment_timeline_preparation_row:hover {{
                background: {theme.bg_hover};
            }}
            QLabel#attachment_timeline_token {{
                color: {theme.text_primary};
                font-size: {theme.font_size_md}px;
                font-weight: {theme.font_weight_emphasis};
                background: transparent;
                border: none;
            }}
            QLabel#attachment_timeline_result {{
                color: {theme.text_secondary};
                font-size: {theme.font_size_md}px;
                background: transparent;
                border: none;
            }}
            QLabel#attachment_timeline_status {{
                color: {theme.warning};
                font-size: {theme.font_size_sm}px;
                background: {theme.warning_bg};
                border: none;
                border-radius: {theme.radius_sm}px;
                padding: 3px 5px;
            }}
            QLabel#attachment_timeline_status[ready="true"] {{
                color: {theme.success};
                background: {theme.success_bg};
            }}
            """
        )


def _scroll_column(
    parent: QWidget,
    object_name: str,
) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    scroll = QScrollArea(parent)
    scroll.setObjectName(object_name)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    content = QWidget(scroll)
    content.setObjectName(f"{object_name}_content")
    content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    scroll.setWidget(content)
    return scroll, content, layout


def _problem_row(
    parent: QWidget,
    title: str,
    detail: str,
    *,
    kind: str,
) -> QFrame:
    row = QFrame(parent)
    row.setObjectName("attachment_preparation_problem_row")
    row.setProperty("kind", kind)
    layout = QVBoxLayout(row)
    layout.setContentsMargins(14, 11, 14, 11)
    layout.setSpacing(4)
    title_label = QLabel(title, row)
    title_label.setObjectName("attachment_preparation_problem_title")
    title_label.setWordWrap(True)
    detail_label = QLabel(detail, row)
    detail_label.setObjectName("attachment_preparation_problem_detail")
    detail_label.setWordWrap(True)
    layout.addWidget(title_label)
    layout.addWidget(detail_label)
    return row


def _clear_dynamic_layout(layout, *, keep_stretch: bool = True) -> None:
    trailing = 1 if keep_stretch and layout.count() else 0
    while layout.count() > trailing:
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_dynamic_layout(child_layout, keep_stretch=False)


class AttachmentFieldPreparationPage(QWidget):
    """Field phase: one selected profile with exact Token/value rows."""

    profile_changed = Signal(int)
    filter_changed = Signal()
    value_committed = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._profiles: tuple[EntityProfile, ...] = ()
        self._profile_index = 0
        self._value_for = lambda _token, _index: ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)
        title = QLabel("字段资料", self)
        title.setObjectName("attachment_preparation_page_title")
        title_row.addWidget(title, 1)
        self.profile_selector_label = QLabel("当前数据", self)
        self.profile_selector_label.setObjectName(
            "attachment_preparation_control_label"
        )
        title_row.addWidget(self.profile_selector_label)
        self.profile_combo = StyledComboBox(self)
        self.profile_combo.setObjectName("attachment_preparation_profile_selector")
        self.profile_combo.setMinimumWidth(210)
        self.profile_combo.currentIndexChanged.connect(self.profile_changed)
        title_row.addWidget(self.profile_combo)
        self.filter_checkbox = QCheckBox("只看待填写", self)
        self.filter_checkbox.setObjectName("attachment_preparation_field_filter")
        self.filter_checkbox.setChecked(True)
        self.filter_checkbox.stateChanged.connect(lambda _state: self.filter_changed.emit())
        title_row.addWidget(self.filter_checkbox)
        layout.addLayout(title_row)

        self.meta_label = QLabel(self)
        self.meta_label.setObjectName("attachment_preparation_page_summary")
        self.meta_label.setWordWrap(True)
        layout.addWidget(self.meta_label)

        header = QFrame(self)
        header.setObjectName("attachment_preparation_column_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 7, 14, 7)
        header_layout.setSpacing(14)
        token_header = QLabel("Token", header)
        token_header.setMinimumWidth(205)
        value_header = QLabel("当前内容", header)
        value_header.setMinimumWidth(175)
        usage_header = QLabel("使用位置", header)
        usage_header.setFixedWidth(84)
        status_header = QLabel("状态", header)
        status_header.setFixedWidth(64)
        for label in (token_header, value_header, usage_header, status_header):
            label.setObjectName("attachment_preparation_column_label")
        usage_header.setAlignment(Qt.AlignCenter)
        status_header.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(token_header, 4)
        header_layout.addWidget(value_header, 5)
        header_layout.addWidget(usage_header, 0)
        header_layout.addWidget(status_header, 0)
        layout.addWidget(header)

        scroll, self._content, content_layout = _scroll_column(
            self,
            "attachment_preparation_field_scroll",
        )
        self.empty_label = QLabel(self._content)
        self.empty_label.setObjectName("attachment_preparation_empty_state")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setWordWrap(True)
        content_layout.addWidget(self.empty_label)
        content_layout.addStretch(1)
        self.rows = KeyedWidgetListController[
            AttachmentPreparationRequirement,
            str,
        ](
            layout=content_layout,
            create_widget=self._create_row,
            update_widget=self._update_row,
            key=lambda item: item.token,
            start_index=0,
        )
        layout.addWidget(scroll, 1)

    def set_profiles(
        self,
        profiles: tuple[EntityProfile, ...],
        requirements: tuple[AttachmentPreparationRequirement, ...],
        *,
        current_index: int,
    ) -> int:
        self._profiles = tuple(profiles)
        self._profile_index = max(0, min(current_index, len(self._profiles) - 1))
        blocked = self.profile_combo.blockSignals(True)
        try:
            self.profile_combo.clear()
            for index, profile in enumerate(self._profiles, start=1):
                label = str(
                    profile.profile_name or profile.profile_id or f"第 {index} 份"
                )
                badge_text, badge_kind = self._profile_badge(
                    requirements,
                    index - 1,
                )
                self.profile_combo.add_badged_item(
                    f"{index}. {label}",
                    index - 1,
                    badge_text=badge_text,
                    badge_kind=badge_kind,
                )
            self.profile_combo.setCurrentIndex(self._profile_index)
        finally:
            self.profile_combo.blockSignals(blocked)
        multi = len(self._profiles) > 1
        self.profile_selector_label.setVisible(multi)
        self.profile_combo.setVisible(multi)
        return self._profile_index

    def render(
        self,
        requirements: tuple[AttachmentPreparationRequirement, ...],
        *,
        profile_index: int,
        value_for,
    ) -> None:
        self._profile_index = max(0, min(profile_index, len(self._profiles) - 1))
        self._value_for = value_for
        pending = tuple(
            item
            for item in requirements
            if not (
                self._profile_index < len(item.profiles)
                and item.profiles[self._profile_index].state
                is AttachmentRequirementState.RESOLVED
            )
            and not (
                self._profile_index < len(item.profiles)
                and item.profiles[self._profile_index].state
                is AttachmentRequirementState.DISABLED
            )
        )
        visible = pending if self.filter_checkbox.isChecked() else requirements
        completed = sum(
            self._profile_index < len(item.profiles)
            and item.profiles[self._profile_index].state
            is AttachmentRequirementState.RESOLVED
            for item in requirements
        )
        disabled = sum(
            self._profile_index < len(item.profiles)
            and item.profiles[self._profile_index].state
            is AttachmentRequirementState.DISABLED
            for item in requirements
        )
        profile = self._profiles[self._profile_index]
        profile_name = str(
            profile.profile_name
            or profile.profile_id
            or f"第 {self._profile_index + 1} 份"
        )
        self.meta_label.setText(
            f"当前数据：{profile_name} · 已填写 {completed}/{len(requirements)}。"
            "修改会直接写回字段资料，附件生成时同步使用。"
        )
        if requirements and not visible and disabled:
            empty_text = "同步替换尚未启用，请先处理“源文件检查”中的问题。"
        elif requirements and not visible:
            empty_text = "当前数据已填写完整。取消“只看待填写”可核对全部字段。"
        else:
            empty_text = "附件中没有需要直接填写的字段 Token。"
        self.empty_label.setText(empty_text)
        self.empty_label.setVisible(not visible)
        self.rows.reconcile(visible)

    def update_profile_badges(
        self,
        requirements: tuple[AttachmentPreparationRequirement, ...],
    ) -> None:
        """Refresh coverage hints without rebuilding an open profile selector."""

        for profile_index in range(min(self.profile_combo.count(), len(self._profiles))):
            badge_text, badge_kind = self._profile_badge(
                requirements,
                profile_index,
            )
            self.profile_combo.setItemData(
                profile_index,
                badge_text,
                SOURCE_BADGE_TEXT_ROLE,
            )
            self.profile_combo.setItemData(
                profile_index,
                badge_kind,
                SOURCE_BADGE_KIND_ROLE,
            )
        self.profile_combo.update()

    @staticmethod
    def _pending_count(
        requirements: tuple[AttachmentPreparationRequirement, ...],
        profile_index: int,
    ) -> int:
        return sum(
            not (
                profile_index < len(requirement.profiles)
                and requirement.profiles[profile_index].state
                in {
                    AttachmentRequirementState.RESOLVED,
                    AttachmentRequirementState.DISABLED,
                }
            )
            for requirement in requirements
        )

    @classmethod
    def _profile_badge(
        cls,
        requirements: tuple[AttachmentPreparationRequirement, ...],
        profile_index: int,
    ) -> tuple[str, str]:
        disabled = any(
            profile_index < len(requirement.profiles)
            and requirement.profiles[profile_index].state
            is AttachmentRequirementState.DISABLED
            for requirement in requirements
        )
        if disabled:
            return "待启用", "error"
        pending = cls._pending_count(requirements, profile_index)
        return (
            (f"{pending} 待填", "warning")
            if pending
            else ("完整", "success")
        )

    def _create_row(
        self,
        _requirement: AttachmentPreparationRequirement,
    ) -> AttachmentFieldPreparationRow:
        row = AttachmentFieldPreparationRow(self._content)
        row.value_committed.connect(self.value_committed)
        return row

    def _update_row(
        self,
        widget: QWidget,
        requirement: AttachmentPreparationRequirement,
        _index: int,
    ) -> None:
        if isinstance(widget, AttachmentFieldPreparationRow):
            widget.update_requirement(
                requirement,
                profile_index=self._profile_index,
                value=self._value_for(requirement.token, self._profile_index),
            )


class AttachmentTimelinePreparationPage(QWidget):
    """Timeline phase with one shared anchor/rule editor."""

    editor_changed = Signal()
    ratio_changed = Signal(str, str)
    apply_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ratios: dict[str, str] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("时间计划", self)
        title.setObjectName("attachment_preparation_page_title")
        self.meta_label = QLabel(self)
        self.meta_label.setObjectName("attachment_preparation_page_summary")
        self.meta_label.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(self.meta_label)

        self.editor_frame = QFrame(self)
        self.editor_frame.setObjectName("attachment_preparation_timeline_editor")
        editor_layout = QVBoxLayout(self.editor_frame)
        editor_layout.setContentsMargins(14, 12, 14, 12)
        editor_layout.setSpacing(10)
        relationship = QLabel(
            "开始字段 + 结束字段  →  按比例生成下方全部时间节点",
            self.editor_frame,
        )
        relationship.setObjectName("attachment_preparation_relationship")
        editor_layout.addWidget(relationship)

        anchors = QHBoxLayout()
        anchors.setContentsMargins(0, 0, 0, 0)
        anchors.setSpacing(10)
        anchors.addWidget(QLabel("开始字段", self.editor_frame))
        self.start_edit = ElidedValueEdit(parent=self.editor_frame)
        self.start_edit.setPlaceholderText("例如：项目开始日期")
        anchors.addWidget(self.start_edit, 1)
        anchors.addWidget(QLabel("结束字段", self.editor_frame))
        self.end_edit = ElidedValueEdit(parent=self.editor_frame)
        self.end_edit.setPlaceholderText("例如：项目结束日期")
        anchors.addWidget(self.end_edit, 1)
        self.start_edit.textChanged.connect(lambda _text: self.editor_changed.emit())
        self.end_edit.textChanged.connect(lambda _text: self.editor_changed.emit())
        editor_layout.addLayout(anchors)
        layout.addWidget(self.editor_frame)

        self.column_header = QFrame(self)
        self.column_header.setObjectName("attachment_preparation_column_header")
        header_layout = QHBoxLayout(self.column_header)
        header_layout.setContentsMargins(14, 7, 14, 7)
        header_layout.setSpacing(14)
        token_header = QLabel("时间 Token", self.column_header)
        token_header.setMinimumWidth(220)
        ratio_header = QLabel("进度比例", self.column_header)
        ratio_header.setFixedWidth(84)
        result_header = QLabel("示例结果", self.column_header)
        result_header.setFixedWidth(116)
        status_header = QLabel("状态", self.column_header)
        status_header.setFixedWidth(84)
        for label in (token_header, ratio_header, result_header, status_header):
            label.setObjectName("attachment_preparation_column_label")
        ratio_header.setAlignment(Qt.AlignCenter)
        result_header.setAlignment(Qt.AlignCenter)
        status_header.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(token_header, 1)
        header_layout.addWidget(ratio_header, 0)
        header_layout.addWidget(result_header, 0)
        header_layout.addWidget(status_header, 0)
        layout.addWidget(self.column_header)

        scroll, self._content, content_layout = _scroll_column(
            self,
            "attachment_preparation_timeline_scroll",
        )
        self.empty_label = QLabel(self._content)
        self.empty_label.setObjectName("attachment_preparation_empty_state")
        self.empty_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self.empty_label)
        content_layout.addStretch(1)
        self.rows = KeyedWidgetListController[
            AttachmentPreparationRequirement,
            str,
        ](
            layout=content_layout,
            create_widget=self._create_row,
            update_widget=self._update_row,
            key=lambda item: item.token,
            start_index=0,
        )
        layout.addWidget(scroll, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.apply_button = QPushButton("应用到全部数据", self)
        self.apply_button.clicked.connect(self.apply_requested)
        apply_button_variant(self.apply_button, "primary")
        actions.addWidget(self.apply_button)
        layout.addLayout(actions)

    def set_anchors(self, start: str, end: str) -> None:
        start_blocked = self.start_edit.blockSignals(True)
        end_blocked = self.end_edit.blockSignals(True)
        try:
            self.start_edit.setText(start)
            self.end_edit.setText(end)
        finally:
            self.start_edit.blockSignals(start_blocked)
            self.end_edit.blockSignals(end_blocked)

    def render(
        self,
        requirements: tuple[AttachmentPreparationRequirement, ...],
        *,
        ratios: dict[str, str],
        profile_count: int,
        apply_text: str,
    ) -> None:
        self._ratios = ratios
        has_requirements = bool(requirements)
        self.editor_frame.setVisible(has_requirements)
        self.column_header.setVisible(has_requirements)
        self.apply_button.setVisible(has_requirements)
        self.empty_label.setVisible(not has_requirements)
        self.empty_label.setText("附件中没有需要统一计算的时间 Token。")
        self.meta_label.setText(
            (
                f"{len(requirements)} 个时间 Token 共用一套规则，"
                f"一次应用到 {profile_count} 条数据。"
            )
            if requirements
            else "无需配置时间计划。"
        )
        self.apply_button.setText(apply_text)
        self.rows.reconcile(requirements)

    def set_preview(self, token: str, value: str, status: str) -> None:
        widget = self.rows.widget_for(token)
        if isinstance(widget, AttachmentTimelinePreparationRow):
            widget.set_preview(value, status)

    def set_all_preview_status(self, status: str) -> None:
        for widget in self.rows.widgets():
            if isinstance(widget, AttachmentTimelinePreparationRow):
                widget.set_preview("", status)

    def _create_row(
        self,
        _requirement: AttachmentPreparationRequirement,
    ) -> AttachmentTimelinePreparationRow:
        row = AttachmentTimelinePreparationRow(self._content)
        row.ratio_changed.connect(self.ratio_changed)
        return row

    def _update_row(
        self,
        widget: QWidget,
        requirement: AttachmentPreparationRequirement,
        _index: int,
    ) -> None:
        if isinstance(widget, AttachmentTimelinePreparationRow):
            widget.update_requirement(
                requirement,
                ratio=self._ratios.get(requirement.token, ""),
            )


class AttachmentSourcePreparationPage(QWidget):
    """Source phase showing only problems outside inline preparation."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        title = QLabel("源文件检查", self)
        title.setObjectName("attachment_preparation_page_title")
        self.meta_label = QLabel(self)
        self.meta_label.setObjectName("attachment_preparation_page_summary")
        self.meta_label.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(self.meta_label)
        scroll, _content, self._rows_layout = _scroll_column(
            self,
            "attachment_preparation_source_scroll",
        )
        self._rows_layout.addStretch(1)
        layout.addWidget(scroll, 1)

    def render(self, problems: tuple[tuple[str, str, str], ...]) -> None:
        _clear_dynamic_layout(self._rows_layout)
        if not problems:
            problems = ((
                "源文件检查通过",
                "Word 文件均可读取，且没有需要返回其他资料模块处理的 Token。",
                "success",
            ),)
            self.meta_label.setText(
                "这里只列出无法在字段资料或时间计划中直接处理的问题。"
            )
        else:
            self.meta_label.setText(f"发现 {len(problems)} 个需要外部处理的问题。")
        for title, detail, kind in problems:
            self._rows_layout.insertWidget(
                self._rows_layout.count() - 1,
                _problem_row(self, title, detail, kind=kind),
            )


__all__ = [
    "AttachmentFieldPreparationRow",
    "AttachmentFieldPreparationPage",
    "AttachmentSourcePreparationPage",
    "AttachmentTimelinePreparationRow",
    "AttachmentTimelinePreparationPage",
]
