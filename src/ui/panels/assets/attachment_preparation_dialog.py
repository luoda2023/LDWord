"""Window-modal workbench for preparing one Token-aware attachment package."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.config.attachment_materials import AttachmentBinding
from src.config.entity import EntityProfile
from src.qt_api import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSize,
    QStackedWidget,
    Qt,
    QVBoxLayout,
)
from src.services.material_attachments import (
    AttachmentPreparationReport,
    AttachmentPreparationRequirement,
    AttachmentRequirementState,
)
from src.services.material_attachments.requirements import AttachmentRequirementOwner
from src.services.material_attachments.timeline_preparation import (
    AttachmentTimelineConflict,
    build_attachment_timeline_plan,
    common_attachment_timeline_plan,
)
from src.shared.engine.material_timeline import (
    DEFAULT_DATE_FORMAT,
    infer_timeline_date_format,
    resolve_timeline_plans,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.deferred_call import defer_qt_method
from src.shared.ui.dialogs import confirm
from src.shared.ui.dynamic_navigation_rail import DynamicNavigationRail
from src.shared.ui.theme import get_theme
from src.shared.ui.workspace_dialog import WorkspaceDialog
from src.ui.panels.assets.attachment_preparation_session import (
    AttachmentPreparationSession,
)
from src.ui.panels.assets.attachment_preparation_style import (
    build_attachment_preparation_stylesheet,
)
from src.ui.panels.assets.attachment_preparation_views import (
    AttachmentFieldPreparationPage,
    AttachmentSourcePreparationPage,
    AttachmentTimelinePreparationPage,
)
from src.ui.panels.assets.batch_import import _load_batch_profiles_from_path


_PHASE_FIELDS = "fields"
_PHASE_TIMELINE = "timeline"
_PHASE_SOURCE = "source"
_PHASE_TITLES = {
    _PHASE_FIELDS: "字段资料",
    _PHASE_TIMELINE: "时间计划",
    _PHASE_SOURCE: "源文件检查",
}


class AttachmentPreparationDialog(WorkspaceDialog):
    """Edit canonical batch fields and timeline rules in one transaction.

    The preparation report is the only readiness state machine.  Page objects
    own layout and rendering; this dialog owns only the draft transaction,
    phase routing, timeline rule construction, and commit boundary.
    """

    def __init__(
        self,
        *,
        role: str,
        binding: AttachmentBinding,
        profiles: list[EntityProfile],
        current_profile_index: int = 0,
        image_token_bindings: dict[str, str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(
            title="附件包准备",
            preferred_size=QSize(1100, 760),
            parent=parent,
        )
        self.setObjectName("attachment_preparation_dialog")
        self.setMinimumSize(980, 640)

        self._session = AttachmentPreparationSession(
            role=role,
            binding=binding,
            profiles=profiles,
            current_profile_index=current_profile_index,
            image_token_bindings=image_token_bindings,
        )
        self._role = self._session.role
        self._binding = self._session.binding
        self._current_profile_index = self._session.current_profile_index
        self._field_profile_index = self._session.current_profile_index
        self._saved_complete = False
        self._current_phase = ""
        self._closing_without_prompt = False
        self._timeline_editor_initialized = False
        self._timeline_ratio_values: dict[str, str] = {}
        self._timeline_plan_id = ""

        self._build_ui()
        self._refresh_report(select_phase=self._first_incomplete_phase())
        self._apply_theme()

    def result_profiles(self) -> list[EntityProfile]:
        return self._session.result_profiles()

    def saved_complete(self) -> bool:
        return self._saved_complete

    def profiles_replaced(self) -> bool:
        return self._session.profiles_replaced

    @property
    def _draft_profiles(self) -> tuple[EntityProfile, ...]:
        return self._session.profiles

    @property
    def _report(self) -> AttachmentPreparationReport:
        return self._session.report

    @property
    def _dirty(self) -> bool:
        return self._session.dirty

    @_dirty.setter
    def _dirty(self, value: bool) -> None:
        self._session.dirty = bool(value)

    def reject(self) -> None:
        if self._closing_without_prompt:
            super().reject()
            return
        if not self._confirm_discard_if_needed():
            return
        self._closing_without_prompt = True
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if not self._closing_without_prompt and not self._confirm_discard_if_needed():
            event.ignore()
            return
        self._closing_without_prompt = True
        super().closeEvent(event)

    def _confirm_discard_if_needed(self) -> bool:
        return not self._dirty or confirm(
            "放弃附件包修改？",
            "当前工作台中还有未保存的修改。",
            confirm_text="放弃修改",
            destructive=True,
            parent=self,
        )

    # ------------------------------------------------------------------
    # Shell and phase routing
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._source_label = QLabel(self._toolbar)
        self._source_label.setObjectName("attachment_preparation_source")
        self._source_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.add_toolbar_widget(self._source_label)

        self._import_button = QPushButton("替换数据表", self._toolbar)
        self._import_button.setObjectName("attachment_preparation_import")
        self._import_button.clicked.connect(self._import_profiles)
        apply_button_variant(self._import_button, "secondary")
        self.add_toolbar_widget(self._import_button)

        body = QFrame(self._surface)
        body.setObjectName("attachment_preparation_body")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        left = QFrame(body)
        left.setObjectName("attachment_preparation_left")
        left.setFixedWidth(236)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(14, 18, 10, 18)
        left_layout.setSpacing(8)
        left_title = QLabel("准备流程", left)
        left_title.setObjectName("attachment_preparation_section_title")
        left_hint = QLabel("按阶段处理，Token 只在右侧出现一次", left)
        left_hint.setObjectName("attachment_preparation_section_hint")
        left_hint.setWordWrap(True)
        left_layout.addWidget(left_title)
        left_layout.addWidget(left_hint)
        self._phase_nav = DynamicNavigationRail(parent=left)
        self._phase_nav.setFixedWidth(212)
        left_layout.addWidget(self._phase_nav, 1)

        right = QFrame(body)
        right.setObjectName("attachment_preparation_right")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(22, 18, 22, 18)
        right_layout.setSpacing(0)
        self._pages = QStackedWidget(right)
        self._field_page = AttachmentFieldPreparationPage(right)
        self._timeline_page = AttachmentTimelinePreparationPage(right)
        self._source_page = AttachmentSourcePreparationPage(right)
        self._phase_pages = {
            _PHASE_FIELDS: self._field_page,
            _PHASE_TIMELINE: self._timeline_page,
            _PHASE_SOURCE: self._source_page,
        }
        for page in self._phase_pages.values():
            self._pages.addWidget(page)
        right_layout.addWidget(self._pages, 1)
        body_layout.addWidget(left)
        body_layout.addWidget(right, 1)
        self._surface_layout.addWidget(body, 1)

        self._phase_cards = {
            _PHASE_FIELDS: self._phase_nav.add_item(
                _PHASE_FIELDS,
                "字段资料",
                icon_name="type",
            ),
            _PHASE_TIMELINE: self._phase_nav.add_item(
                _PHASE_TIMELINE,
                "时间计划",
                icon_name="chart-no-axes-gantt",
            ),
            _PHASE_SOURCE: self._phase_nav.add_item(
                _PHASE_SOURCE,
                "源文件检查",
                icon_name="file-text",
            ),
        }
        self._phase_nav.card_selected.connect(self._on_phase_selected)
        self._field_page.profile_changed.connect(self._on_field_profile_changed)
        self._field_page.filter_changed.connect(self._refresh_field_page)
        self._field_page.value_committed.connect(self._on_field_value_committed)
        self._timeline_page.editor_changed.connect(self._refresh_timeline_preview)
        self._timeline_page.ratio_changed.connect(self._on_timeline_ratio_changed)
        self._timeline_page.apply_requested.connect(self._apply_timeline_plan)

        footer = QFrame(self._surface)
        footer.setObjectName("attachment_preparation_footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 10, 18, 10)
        footer_layout.setSpacing(10)
        self._footer_status = QLabel(footer)
        self._footer_status.setObjectName("attachment_preparation_footer_status")
        footer_layout.addWidget(self._footer_status, 1)
        cancel = QPushButton("取消", footer)
        cancel.clicked.connect(self.reject)
        apply_button_variant(cancel, "secondary")
        self._save_button = QPushButton("保存草稿", footer)
        self._save_button.clicked.connect(self._save_draft)
        apply_button_variant(self._save_button, "secondary")
        self._complete_button = QPushButton(footer)
        self._complete_button.clicked.connect(self._on_primary_action)
        apply_button_variant(self._complete_button, "primary")
        footer_layout.addWidget(cancel)
        footer_layout.addWidget(self._save_button)
        footer_layout.addWidget(self._complete_button)
        self._surface_layout.addWidget(footer, 0)

    def _refresh_report(
        self,
        *,
        select_phase: str | None = None,
        rebuild_profile_selector: bool = False,
    ) -> None:
        self._session.refresh()
        self.set_title_text(
            "附件包准备",
            f"{self._binding.label or self._role} · "
            f"{self._report.docx_count} 个 Word · "
            f"{self._report.token_count} 个 Token · "
            f"{self._report.occurrence_count} 处引用",
        )
        if (
            rebuild_profile_selector
            or self._field_page.profile_combo.count() != len(self._draft_profiles)
        ):
            self._refresh_profile_selector()
        else:
            self._field_page.update_profile_badges(self._field_requirements())
        self._refresh_source_label()
        self._refresh_phase_cards()
        self._footer_status.setText(self._readiness_status_text())
        target = select_phase or self._current_phase or self._first_incomplete_phase()
        if target not in self._phase_pages:
            target = self._first_incomplete_phase()
        self._phase_nav.select_card(target)

    def _refresh_source_label(self) -> None:
        if self._session.source_path:
            self._source_label.setText(
                f"{Path(self._session.source_path).name} · "
                f"{len(self._draft_profiles)} 条数据"
            )
            self._import_button.setText("替换数据表")
            return
        self._source_label.setText(f"当前 {len(self._draft_profiles)} 条数据")
        self._import_button.setText("导入数据表")

    def _refresh_phase_cards(self) -> None:
        field_requirements = self._field_requirements()
        timeline_requirements = self._timeline_requirements()
        field_disabled = any(
            item.state is AttachmentRequirementState.DISABLED
            for item in field_requirements
        )
        timeline_disabled = any(
            item.state is AttachmentRequirementState.DISABLED
            for item in timeline_requirements
        )
        field_pending = self._actionable_pending_count(field_requirements)
        timeline_pending = self._actionable_pending_count(
            timeline_requirements
        )
        source_pending = self._source_problem_count()
        field_state = self._phase_task_state(
            pending=field_pending,
            disabled=field_disabled,
            pending_text=f"{field_pending} 项待填写",
            ready_text="字段已完整",
        )
        timeline_state = self._phase_task_state(
            pending=timeline_pending,
            disabled=timeline_disabled,
            pending_text=f"{timeline_pending} 个节点待配置",
            ready_text="时间计划已就绪",
        )
        states = {
            _PHASE_FIELDS: field_state,
            _PHASE_TIMELINE: timeline_state,
            _PHASE_SOURCE: (
                f"{source_pending} 个问题" if source_pending else "源文件正常",
                str(source_pending) if source_pending else "✓",
                "error" if source_pending else "success",
            ),
        }
        for phase, (subtitle, badge, variant) in states.items():
            card = self._phase_cards[phase]
            card.set_subtitle(subtitle)
            card.set_badge(badge, variant)

    @staticmethod
    def _phase_task_state(
        *,
        pending: int,
        disabled: bool,
        pending_text: str,
        ready_text: str,
    ) -> tuple[str, str, str]:
        if disabled:
            return "同步未启用", "—", "neutral"
        if pending:
            return pending_text, str(pending), "warning"
        return ready_text, "✓", "success"

    def _first_incomplete_phase(self) -> str:
        if self._disabled_requirements():
            return _PHASE_SOURCE
        if self._actionable_pending_count(self._field_requirements()):
            return _PHASE_FIELDS
        if self._actionable_pending_count(self._timeline_requirements()):
            return _PHASE_TIMELINE
        if self._report.issue_requirements or self._report.unreadable_paths:
            return _PHASE_SOURCE
        return _PHASE_FIELDS

    def _on_phase_selected(self, phase: str) -> None:
        if phase not in self._phase_pages:
            return
        self._current_phase = phase
        self._pages.setCurrentWidget(self._phase_pages[phase])
        if phase == _PHASE_FIELDS:
            self._refresh_field_page()
        elif phase == _PHASE_TIMELINE:
            self._refresh_timeline_page()
        elif phase == _PHASE_SOURCE:
            self._refresh_source_page()
        self._refresh_primary_action()

    def _refresh_primary_action(self) -> None:
        if self._report.is_ready:
            self._complete_button.setEnabled(True)
            self._complete_button.setText("完成准备")
            return
        target = self._first_incomplete_phase()
        on_blocking_phase = target == self._current_phase
        self._complete_button.setEnabled(not on_blocking_phase)
        prefix = "请先完成" if on_blocking_phase else "去处理"
        self._complete_button.setText(f"{prefix}：{_PHASE_TITLES[target]}")

    def _on_primary_action(self) -> None:
        if self._report.is_ready:
            self._complete_preparation()
            return
        self._phase_nav.select_card(self._first_incomplete_phase())

    # ------------------------------------------------------------------
    # Field phase
    # ------------------------------------------------------------------

    def _field_requirements(self) -> tuple[AttachmentPreparationRequirement, ...]:
        return tuple(
            item
            for item in self._report.requirements
            if item.owner is AttachmentRequirementOwner.FIELD
        )

    def _refresh_profile_selector(self) -> None:
        self._field_profile_index = self._field_page.set_profiles(
            self._draft_profiles,
            self._field_requirements(),
            current_index=self._field_profile_index,
        )

    def _on_field_profile_changed(self, index: int) -> None:
        if not 0 <= index < len(self._draft_profiles):
            return
        self._field_profile_index = index
        self._refresh_field_page()

    def _refresh_field_page(self) -> None:
        self._field_page.render(
            self._field_requirements(),
            profile_index=self._field_profile_index,
            value_for=self._session.field_value,
        )

    def _on_field_value_committed(self, token: str, value: str) -> None:
        if not self._session.set_field_value(
            token,
            self._field_profile_index,
            value,
        ):
            return
        # Focus loss is also how users click the profile selector or the next
        # phase.  Refreshing the whole projection inside editingFinished would
        # rebuild the clicked control before that mouse event completes.
        defer_qt_method(self, "_refresh_after_field_commit")

    def _refresh_after_field_commit(self) -> None:
        self._refresh_report(
            select_phase=self._current_phase or _PHASE_FIELDS,
        )

    # ------------------------------------------------------------------
    # Timeline phase
    # ------------------------------------------------------------------

    def _timeline_requirements(self) -> tuple[AttachmentPreparationRequirement, ...]:
        return tuple(
            item
            for item in self._report.requirements
            if item.owner is AttachmentRequirementOwner.TIMELINE
        )

    def _show_timeline_requirements(self) -> None:
        self._phase_nav.select_card(_PHASE_TIMELINE)

    def _refresh_timeline_page(self) -> None:
        requirements = self._timeline_requirements()
        if requirements:
            self._initialize_timeline_editor()
        self._timeline_page.render(
            requirements,
            ratios=self._timeline_ratio_values,
            profile_count=len(self._draft_profiles),
            apply_text="更新全部数据" if self._timeline_plan_id else "应用到全部数据",
        )
        if requirements:
            self._refresh_timeline_preview()

    def _initialize_timeline_editor(self, *, force: bool = False) -> None:
        if self._timeline_editor_initialized and not force:
            return
        requirements = self._timeline_requirements()
        plan_id, plan = self._existing_timeline_plan(requirements)
        self._timeline_plan_id = plan_id
        self._timeline_page.set_anchors(*self._default_timeline_anchors(plan))

        existing_ratios: dict[str, str] = {}
        if plan:
            for node in list(plan.get("nodes", []) or []):
                node_data = dict(node)
                outputs = list(node_data.get("outputs", []) or [])
                rule = dict(node_data.get("rule", {}) or {})
                if str(rule.get("operation", "ratio")) != "ratio":
                    continue
                for output in outputs:
                    field = str(dict(output).get("field", "") or "").strip()
                    if field:
                        existing_ratios[field] = str(rule.get("value", "") or "")
        denominator = max(1, len(requirements) - 1)
        self._timeline_ratio_values = {
            requirement.token: existing_ratios.get(
                requirement.identifier,
                _decimal_text(Decimal(index) / Decimal(denominator)),
            )
            for index, requirement in enumerate(requirements)
        }
        self._timeline_editor_initialized = True

    def _on_timeline_ratio_changed(self, token: str, value: str) -> None:
        self._timeline_ratio_values[token] = str(value or "").strip()
        self._refresh_timeline_preview()

    def _existing_timeline_plan(
        self,
        requirements: tuple[AttachmentPreparationRequirement, ...],
    ) -> tuple[str, dict[str, object] | None]:
        return common_attachment_timeline_plan(
            self._draft_profiles,
            tuple(item.identifier for item in requirements),
        )

    def _default_timeline_anchors(
        self,
        plan: dict[str, object] | None,
    ) -> tuple[str, str]:
        if plan:
            start = str(plan.get("start_field", "") or "").strip()
            end = str(plan.get("end_field", "") or "").strip()
            if start and end:
                return start, end
        direct_time = [
            item.identifier
            for item in self._report.requirements
            if item.namespace == "time"
            and item.owner is AttachmentRequirementOwner.FIELD
        ]
        start = next((item for item in direct_time if "开始" in item), "项目开始日期")
        end = next((item for item in direct_time if "结束" in item), "项目结束日期")
        return start, end

    def _refresh_timeline_preview(self) -> None:
        if not self._timeline_editor_initialized:
            return
        plan = self._timeline_plan_from_editor(validate=False)
        if plan is None:
            self._timeline_page.set_all_preview_status("检查设置")
            return
        sample = next(
            (
                profile
                for profile in self._draft_profiles
                if str(profile.fields.get(plan["start_field"], "") or "").strip()
                and str(profile.fields.get(plan["end_field"], "") or "").strip()
            ),
            self._draft_profiles[0],
        )
        result = resolve_timeline_plans(sample.fields, {"preview": plan})
        for requirement in self._timeline_requirements():
            value = str(result.values.get(requirement.identifier, "") or "")
            self._timeline_page.set_preview(
                requirement.token,
                value,
                "可生成" if value else "待补日期",
            )

    def _apply_timeline_plan(self) -> None:
        plan = self._timeline_plan_from_editor(validate=True)
        if plan is None:
            return
        try:
            self._timeline_plan_id = self._session.apply_timeline_plan(plan)
        except AttachmentTimelineConflict as exc:
            self._timeline_page.meta_label.setText(
                f"不能覆盖字段资料中的既有时间计划：{exc}。"
                "请先在时间计划模块调整冲突计划。"
            )
            return
        self._refresh_report(select_phase=_PHASE_TIMELINE)

    def _timeline_plan_from_editor(
        self,
        *,
        validate: bool,
    ) -> dict[str, object] | None:
        start_field = self._timeline_page.start_edit.text().strip()
        end_field = self._timeline_page.end_edit.text().strip()
        if not start_field or not end_field:
            if validate:
                self._timeline_page.meta_label.setText(
                    "开始字段和结束字段都必须填写。"
                )
            return None
        requirements = self._timeline_requirements()
        if not requirements:
            return None
        ratios: list[Decimal] = []
        for index, requirement in enumerate(requirements, start=1):
            raw = self._timeline_ratio_values.get(requirement.token, "")
            try:
                ratio = Decimal(str(raw))
            except (InvalidOperation, ValueError):
                if validate:
                    self._timeline_page.meta_label.setText(
                        f"第 {index} 个节点的比例不是数字。"
                    )
                return None
            if ratio < 0 or ratio > 1:
                if validate:
                    self._timeline_page.meta_label.setText(
                        "节点比例必须位于 0 到 1 之间。"
                    )
                return None
            ratios.append(ratio)
        if ratios != sorted(ratios):
            if validate:
                self._timeline_page.meta_label.setText(
                    "节点比例需要按从小到大排列。"
                )
            return None
        sample_text = next(
            (
                str(profile.fields.get(start_field, "") or "")
                or str(profile.fields.get(end_field, "") or "")
                for profile in self._draft_profiles
                if profile.fields.get(start_field) or profile.fields.get(end_field)
            ),
            "",
        )
        date_format = (
            infer_timeline_date_format(sample_text)
            if sample_text
            else DEFAULT_DATE_FORMAT
        )
        return build_attachment_timeline_plan(
            start_field=start_field,
            end_field=end_field,
            outputs=tuple(
                (requirement.identifier, ratio)
                for requirement, ratio in zip(requirements, ratios)
            ),
            date_format=date_format,
        )

    # ------------------------------------------------------------------
    # Source phase and persistent readiness projection
    # ------------------------------------------------------------------

    def _refresh_source_page(self) -> None:
        problems: list[tuple[str, str, str]] = []
        disabled = self._disabled_requirements()
        if disabled:
            problems.append(
                (
                    "同步替换尚未启用",
                    f"附件中的 {len(disabled)} 个 Token 当前按原样交付。"
                    "请返回附件资料启用同步替换后再次打开准备窗口。",
                    "error",
                )
            )
        problems.extend(
            (
                "源文件无法读取",
                f"{path} · 请确认文件未损坏、未被占用，然后重新绑定附件包。",
                "error",
            )
            for path in self._report.unreadable_paths
        )
        for requirement in self._report.issue_requirements:
            if requirement.state is AttachmentRequirementState.DISABLED:
                continue
            usage = (
                f"{len(requirement.relative_paths)}文件·"
                f"{requirement.occurrence_count}处"
            )
            if requirement.owner is AttachmentRequirementOwner.IMAGE:
                detail = f"图片资料待补充 · {usage}"
            elif requirement.owner is AttachmentRequirementOwner.CONFLICT:
                detail = f"不同数据中的资料来源冲突，需要先统一映射 · {usage}"
            else:
                detail = f"Token 格式或来源不受支持，需要修改模板源文件 · {usage}"
            problems.append((requirement.token, detail, "warning"))
        self._source_page.render(tuple(problems))

    def _readiness_status_text(self) -> str:
        field_pending = self._actionable_pending_count(self._field_requirements())
        timeline_pending = self._actionable_pending_count(
            self._timeline_requirements()
        )
        source_pending = self._source_problem_count()
        ready_text = (
            f"{self._report.ready_profile_count}/{self._report.profile_count} "
            "份数据可生成"
        )
        if self._report.is_ready:
            output_count = self._report.profile_count * len(self._binding.items)
            return f"已准备完成 · {ready_text} · 预计输出 {output_count} 个文件"

        blockers: list[str] = []
        if field_pending:
            blockers.append(f"字段资料还缺 {field_pending} 项")
        if timeline_pending:
            blockers.append(f"时间计划还缺 {timeline_pending} 个节点")
        if source_pending:
            source_text = f"源文件问题 {source_pending} 项"
            if self._report.unreadable_paths:
                source_text += (
                    f"（其中 {len(self._report.unreadable_paths)} 个源文件无法读取）"
                )
            blockers.append(source_text)
        if not blockers:
            blockers.append(f"还有 {len(self._report.pending_requirements)} 项资料未就绪")
        return " · ".join((ready_text, *blockers))

    def _disabled_requirements(
        self,
    ) -> tuple[AttachmentPreparationRequirement, ...]:
        return tuple(
            item
            for item in self._report.requirements
            if item.state is AttachmentRequirementState.DISABLED
        )

    @staticmethod
    def _actionable_pending_count(
        requirements: tuple[AttachmentPreparationRequirement, ...],
    ) -> int:
        return sum(
            not item.is_ready and item.state is not AttachmentRequirementState.DISABLED
            for item in requirements
        )

    def _source_problem_count(self) -> int:
        non_disabled_issues = sum(
            item.state is not AttachmentRequirementState.DISABLED
            for item in self._report.issue_requirements
        )
        return (
            len(self._report.unreadable_paths)
            + non_disabled_issues
            + int(bool(self._disabled_requirements()))
        )

    def _show_unreadable_paths(self) -> None:
        self._phase_nav.select_card(_PHASE_SOURCE)

    # ------------------------------------------------------------------
    # Import, save, and completion
    # ------------------------------------------------------------------

    def _import_profiles(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "导入附件包数据表",
            self._session.source_path,
            "资料表 (*.xlsx *.xlsm *.csv *.json);;Excel (*.xlsx *.xlsm);;"
            "CSV (*.csv);;JSON (*.json)",
        )
        if not path:
            return
        try:
            imported = _load_batch_profiles_from_path(path)
        except Exception as exc:
            self._source_label.setText(f"导入失败：{exc}")
            return
        if not imported:
            self._source_label.setText("数据表中没有可导入的记录")
            return
        self._session.replace_profiles(imported, source_path=path)
        self._current_profile_index = 0
        self._field_profile_index = 0
        self._timeline_editor_initialized = False
        self._refresh_report(
            select_phase=self._first_incomplete_phase(),
            rebuild_profile_selector=True,
        )

    def _save_draft(self) -> None:
        self._saved_complete = False
        self._closing_without_prompt = True
        super().accept()

    def _complete_preparation(self) -> None:
        self._session.refresh()
        self._refresh_report(select_phase=self._first_incomplete_phase())
        if not self._report.is_ready:
            return
        self._saved_complete = True
        self._closing_without_prompt = True
        super().accept()

    def _apply_theme(self) -> None:
        theme = get_theme()
        if hasattr(self, "_phase_nav"):
            self._phase_nav.set_background_color(theme.bg_card)
        self._apply_shell_theme(build_attachment_preparation_stylesheet(theme))


def _decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


__all__ = ["AttachmentPreparationDialog"]
