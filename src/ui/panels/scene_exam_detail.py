"""Exam and official-document plan preview detail for the scene workspace."""

from __future__ import annotations

from pathlib import Path

from src.config.material_context import MaterialExecutionContext
from src.config.master_library import get_master, list_masters
from src.config.official_document_profiles import (
    get_official_document_assembly_contract,
    get_official_document_profile,
    list_common_official_document_profiles,
)
from src.config.scene import ExamPaperConfig, SceneWorkspace, coerce_exam_paper_config
from src.config.scene_surface_registry import (
    scene_uses_official_document_surface as _scene_uses_official_document_surface,
)
from src.config.work_mode import resolve_work_mode_id
from src.qt_api import (
    QApplication,
    QCheckBox,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from src.shared.engine.document_word_preview import DocumentWordPreviewResult
from src.shared.engine.docx_page_renderer import real_word_preview_enabled
from src.shared.engine.exam_paper_style import (
    EXAM_AI_PROMPT_OPTIONS,
    PROJECT_ROOT,
    USER_EXAM_MASTER_DIR,
    exam_ai_prompt_text,
    exam_blank_style_label,
    resolve_exam_blank_style,
    sync_user_exam_blank_master_files,
)
from src.shared.engine.exam_word_preview import build_exam_word_preview_request
from src.shared.engine.official_document_material_package import (
    export_official_document_material_package,
    get_official_document_material_package_sample,
    load_official_document_material_package_sample,
)
from src.shared.engine.official_document_sample_verification import (
    verify_official_document_sample_visual,
)
from src.shared.engine.official_word_preview import build_official_word_preview_request
from src.shared.ui import (
    FlowLayout,
    LibraryActionRow,
    SegmentedControl,
    apply_button_variant,
    build_button_stylesheet,
)
from src.shared.ui.card import Card
from src.shared.ui.document_page_preview import DocumentPagePreview
from src.shared.ui.layout_sync import refresh_layout_chain_later
from src.shared.ui.selection_control_style import build_checkbox_stylesheet
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.text_area import TextArea
from src.shared.ui.theme import get_theme
from src.shared.ui.toast import Toast
from src.ui.adapters.config_selector_models import (
    master_selector_options,
    material_package_sample_selector_options,
)
from src.ui.panels.document_word_preview_controller import DocumentWordPreviewController
from src.ui.panels.scene_delivery_helpers import (
    _scene_current_template_id,
)
from src.ui.panels.scene_detail_base import _SimpleFormDetail
from src.ui.panels.scene_detail_support import (
    _load_official_material_source,
    _set_combo_by_data,
    open_local_path,
)
from src.ui.panels.scene_official_preview_projection import (
    build_official_plan_preview_projection,
)
from src.ui.panels.scene_state_projection import scene_is_exam as _scene_is_exam


EXAM_RUNTIME_FIELD_OPTIONS: tuple[tuple[str, str], ...] = (
    ("title", "标题"),
    ("subject", "科目"),
    ("grade", "年级"),
    ("duration", "考试时间"),
    ("total_score", "满分"),
    ("class_name", "班级"),
    ("teacher", "命题人"),
    ("exam_date", "日期"),
)

EXAM_DEFAULT_RUNTIME_FIELDS = ("title", "subject", "grade", "duration", "total_score")


def _bridge_work_mode_id(bridge, scene: SceneWorkspace | None) -> str:
    current_mode = getattr(bridge, "current_work_mode_id", None)
    requested_mode = str(current_mode() or "").strip() if callable(current_mode) else ""
    return resolve_work_mode_id(scene, requested_mode_id=requested_mode)


def _official_sample_output_dir() -> Path:
    return PROJECT_ROOT / "output" / "official_master_samples"


def _option_label(
    options: tuple[tuple[str, str], ...], value: str, fallback: str = ""
) -> str:
    target = str(value or "").strip()
    for option_value, label in options:
        if option_value == target:
            return label
    return fallback or target


def ensure_exam_paper_config(scene: SceneWorkspace) -> ExamPaperConfig:
    """Return the scene-owned exam config after coercing legacy mapping values."""

    config = coerce_exam_paper_config(getattr(scene, "exam_paper", None))
    scene.exam_paper = config
    return config


class ExamPaperDetail(_SimpleFormDetail):
    """Scene-specific assembly rules for exam papers."""

    execute_requested = Signal()
    navigate_material_requested = Signal()

    def __init__(self, bridge=None, parent=None):
        super().__init__(
            "方案概览",
            "layers",
            "查看当前方案的成品结构；版式和资料分别在对应页面管理。",
            parent,
        )
        self._bridge = bridge
        self._current_scene: SceneWorkspace | None = None
        self._is_syncing = False
        self._open_sample_path_handler = open_local_path
        self._runtime_checks: dict[str, QCheckBox] = {}
        self._detail_summary.setVisible(False)

        self._build_exam_master_controls()
        self._build_document_preview_surface()
        self._build_exam_prompt_surface()
        self._build_official_preview_controls()
        self._build_runtime_field_controls()
        self._install_bridge_connections()
        self._apply_theme()

    def _build_exam_master_controls(self) -> None:
        self._reset_btn = QPushButton("恢复默认", self._card)
        self._reset_btn.clicked.connect(self._reset_defaults)
        self._workbench_btn = QPushButton("去工作台填写", self._card)
        self._workbench_btn.clicked.connect(self.execute_requested.emit)
        self._card.add_header_action(self._reset_btn)
        self._card.add_header_action(self._workbench_btn)
        self._card.setVisible(False)

        self._blank_style = StyledComboBox(self)
        for option in master_selector_options(
            "exam",
            user_master_dir=USER_EXAM_MASTER_DIR,
        ):
            self._blank_style.addItem(option.label, option.value)
        self._blank_style.set_full_width_mode(True)
        self._blank_style.setToolTip("选择试卷的空白外框样式。")
        self._blank_style.currentIndexChanged.connect(self._on_blank_style_changed)
        self._blank_style.setVisible(False)

        self._master_card = Card(parent=self)
        self._master_card.set_header(
            "当前卷面", icon_name="layers", show_separator=False
        )
        self._master_card.setVisible(False)

        self._master_card.add_widget(self._blank_style)

        self._style_action_row = LibraryActionRow(
            self._master_card,
            object_name="scn_exam_master_action_row",
        )
        self._default_master_btn = self._style_action_row.add_action(
            "default",
            "默认卷面",
            object_name="scn_exam_master_default_btn",
            icon_name="refresh-ccw",
            callback=self._reset_defaults,
        )
        self._open_master_folder_btn = self._style_action_row.add_action(
            "open_folder",
            "打开文件夹",
            object_name="scn_exam_master_open_folder_btn",
            icon_name="folder-open",
            callback=self._open_blank_master_folder,
        )
        self._default_master_btn.setToolTip("切回内置默认卷面。")
        self._open_master_folder_btn.setToolTip("打开当前选中的卷面所在文件夹。")
        self._master_card.add_widget(self._style_action_row)
        self._style_action_row.setVisible(False)

    def _build_document_preview_surface(self) -> None:
        self._plan_preview_card = Card(parent=self)
        self._plan_preview_card.set_header(
            "方案概览", icon_name="eye", show_separator=False
        )
        self._preview_mode_control = SegmentedControl(parent=self._plan_preview_card)
        self._preview_mode_control.setObjectName("scn_exam_master_preview_mode")
        self._preview_mode_control.add_segment("学生卷", "student")
        self._preview_mode_control.add_segment("答案版", "answer")
        self._preview_mode_control.setFixedWidth(220)
        self._preview_mode_control.setToolTip(
            "切换真实 Word 样张；这里只改变预览版本，不修改生成结果设置。"
        )
        self._plan_preview_card.add_header_action(self._preview_mode_control)

        self._document_word_preview = DocumentPagePreview(self._plan_preview_card)
        self._document_word_preview.setObjectName("scn_plan_document_preview")
        self._document_word_preview.refresh_requested.connect(
            self._refresh_real_document_preview
        )
        self._plan_preview_card.add_header_action(
            self._document_word_preview.toolbar_widget()
        )
        self._plan_preview_card.add_widget(self._document_word_preview)

        self._real_preview_enabled = real_word_preview_enabled()
        self._document_preview_failure_notified = False
        self._active_preview_provider_id = ""
        if self._real_preview_enabled:
            self._document_word_preview_controller = DocumentWordPreviewController(self)
            self._document_word_preview_controller.result_ready.connect(
                self._on_document_word_preview_ready
            )
            self._document_word_preview_controller.render_failed.connect(
                self._on_document_word_preview_failed
            )
        else:
            self._document_word_preview.set_error("当前环境未启用真实 Word 渲染")

        self._preview_mode_control.current_changed.connect(self._refresh_master_preview)

    def _build_exam_prompt_surface(self) -> None:
        self._prompt_card = Card(parent=self)
        self._prompt_card.set_header(
            "AI 提示词", icon_name="sparkles", show_separator=False
        )

        self._prompt_mode_control = SegmentedControl(parent=self._prompt_card)
        self._prompt_mode_control.setObjectName("scn_exam_ai_prompt_mode")
        for prompt_id, label, _text in EXAM_AI_PROMPT_OPTIONS:
            self._prompt_mode_control.add_segment(label, prompt_id)
        self._prompt_mode_control.setFixedWidth(240)
        if self._prompt_card._header_layout is not None:
            self._prompt_card._header_layout.insertWidget(
                2,
                self._prompt_mode_control,
                0,
                Qt.AlignVCenter,
            )
        else:
            self._prompt_card.add_header_action(self._prompt_mode_control)

        self._copy_prompt_btn = QPushButton("复制提示词", self._prompt_card)
        self._copy_prompt_btn.clicked.connect(self._copy_current_exam_prompt)
        self._prompt_card.add_header_action(self._copy_prompt_btn)

        self._prompt_area = TextArea(
            min_height=260, max_height=420, parent=self._prompt_card
        )
        self._prompt_area.set_text(exam_ai_prompt_text("markdown"))
        self._prompt_area._text_edit.setReadOnly(True)
        self._prompt_area._text_edit.setObjectName("scn_exam_ai_prompt_text")
        self._prompt_card.add_widget(self._prompt_area)
        self._prompt_mode_control.current_changed.connect(self._refresh_exam_prompt)

    def _build_official_preview_controls(self) -> None:
        self._official_profile = StyledComboBox(self._plan_preview_card)
        self._official_profile.setObjectName("scn_official_profile_combo")
        self._official_profile.set_full_width_mode(True)
        for profile in list_common_official_document_profiles():
            self._official_profile.addItem(
                f"{profile.label} / {profile.profile_id}",
                profile.profile_id,
            )
        _set_combo_by_data(self._official_profile, "notice")
        self._official_profile.currentIndexChanged.connect(
            self._on_official_profile_changed
        )
        self._official_profile.setVisible(False)

        self._official_material_sample = StyledComboBox(self._plan_preview_card)
        self._official_material_sample.setObjectName(
            "scn_official_material_sample_combo"
        )
        self._official_material_sample.set_full_width_mode(True)
        self._official_material_sample.setToolTip(
            "选择当前公文方案要套用的内置资料包样例。"
        )
        self._official_material_sample.currentIndexChanged.connect(
            self._on_official_material_sample_changed
        )
        self._official_material_sample.setVisible(False)

        self._official_master = StyledComboBox(self._plan_preview_card)
        self._official_master.setObjectName("scn_official_master_combo")
        self._official_master.set_full_width_mode(True)
        self._official_master.currentIndexChanged.connect(
            self._refresh_official_preview
        )
        self._official_master.setVisible(False)

        self._official_template = QLabel("", self._plan_preview_card)
        self._official_template.setObjectName("scn_official_template_label")
        self._official_template.setWordWrap(True)
        self._official_template.setVisible(False)

        self._plan_preview_card.add_widget(self._official_template)

        self._official_material_status = QLabel("", self._plan_preview_card)
        self._official_material_status.setObjectName("scn_official_material_status")
        self._official_material_status.setWordWrap(True)
        self._official_material_status.setVisible(False)
        self._plan_preview_card.add_widget(self._official_material_status)

        self._official_contract = QLabel("", self._plan_preview_card)
        self._official_contract.setObjectName("scn_official_contract")
        self._official_contract.setWordWrap(True)
        self._official_contract.setVisible(False)
        self._plan_preview_card.add_widget(self._official_contract)

        self._official_action_row = LibraryActionRow(
            self._plan_preview_card,
            object_name="scn_official_preview_action_row",
        )
        self._official_apply_sample_btn = self._official_action_row.add_action(
            "apply_sample",
            "套用示例资料",
            object_name="scn_official_apply_sample_btn",
            icon_name="check",
            callback=self._apply_official_sample_material,
        )
        self._official_sample_btn = self._official_action_row.add_action(
            "sample",
            "生成公文样张",
            object_name="scn_official_sample_btn",
            icon_name="folder-output",
            callback=self._generate_official_sample,
        )
        self._official_open_master_btn = self._official_action_row.add_action(
            "open_master",
            "打开版式",
            object_name="scn_official_open_master_btn",
            icon_name="file-text",
            callback=self._open_official_master,
        )
        self._official_action_row.setVisible(False)

    def _build_runtime_field_controls(self) -> None:
        self._runtime_fields_widget = QWidget(self)
        self._runtime_fields_widget.setVisible(False)
        self._runtime_fields_widget.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        self._runtime_fields_widget.setMinimumHeight(40)
        self._runtime_fields_widget.setMaximumHeight(88)
        runtime_layout = FlowLayout(
            self._runtime_fields_widget, h_spacing=10, v_spacing=8
        )
        runtime_layout.setContentsMargins(0, 0, 0, 0)
        for field_id, label in EXAM_RUNTIME_FIELD_OPTIONS:
            checkbox = QCheckBox(label, self._runtime_fields_widget)
            checkbox.setCursor(Qt.PointingHandCursor)
            checkbox.toggled.connect(self._on_runtime_fields_changed)
            self._runtime_checks[field_id] = checkbox
            runtime_layout.addWidget(checkbox)

        self._live_summary = QLabel("", self)
        self._live_summary.setObjectName("scn_exam_paper_live_summary")
        self._live_summary.setWordWrap(True)
        self._live_summary.setVisible(False)

        self._runtime_note = QLabel(
            "方案配置只保存长期装配规则；具体标题、科目、考试时间等每次执行时再填写。",
            self,
        )
        self._runtime_note.setWordWrap(True)
        self._runtime_note.setVisible(False)

    def _install_bridge_connections(self) -> None:
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(1, self._master_card)
            layout.insertWidget(2, self._plan_preview_card)
            layout.insertWidget(3, self._prompt_card)
        if self._bridge is not None and hasattr(
            self._bridge, "material_context_changed"
        ):
            self._bridge.material_context_changed.connect(
                self._on_material_context_changed
            )
        if self._bridge is not None and hasattr(
            self._bridge,
            "official_document_type_changed",
        ):
            self._bridge.official_document_type_changed.connect(
                self._on_official_document_type_changed
            )

    def attach_plan_card(self, card: QWidget) -> None:
        """Place the real plan selector above the read-only plan preview."""
        if getattr(self, "_attached_plan_card", None) is card:
            return
        self.detach_plan_card()
        layout = self.layout()
        if not isinstance(layout, QVBoxLayout):
            return
        self._attached_plan_card = card
        card.setParent(self)
        layout.insertWidget(1, card)
        card.setVisible(True)

    def detach_plan_card(self) -> QWidget | None:
        card = getattr(self, "_attached_plan_card", None)
        if card is None:
            return None
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.removeWidget(card)
        card.setParent(None)
        self._attached_plan_card = None
        return card

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        mode_id = _bridge_work_mode_id(self._bridge, scene)
        if _scene_uses_official_document_surface(scene, mode_id=mode_id):
            self._is_syncing = True
            try:
                self._set_plan_preview_surface("official")
                self._sync_official_master_options()
                self._sync_official_profile_from_material_context()
                self._sync_official_material_sample_options(
                    profile_id=self._selected_official_profile_id()
                )
                self._refresh_official_preview()
            finally:
                self._is_syncing = False
            return

        if not _scene_is_exam(
            scene,
            mode_id=_bridge_work_mode_id(self._bridge, scene),
        ):
            self._set_plan_preview_surface("")
            return

        self._set_plan_preview_surface("exam")
        config = ensure_exam_paper_config(scene)
        self._is_syncing = True
        try:
            self._refresh_blank_style_options(config)
            _set_combo_by_data(self._blank_style, scene.master_id)
            selected_fields = set(config.runtime_fields or EXAM_DEFAULT_RUNTIME_FIELDS)
            for field_id, checkbox in self._runtime_checks.items():
                checkbox.setChecked(field_id in selected_fields)
            self._refresh_style_status(config)
            self._refresh_live_summary(config)
        finally:
            self._is_syncing = False

    def refresh_resource_options_for_work_mode(self, mode_id: str) -> None:
        """Refresh mode-owned selector libraries without publishing a scene.

        ``MainWindow`` owns the mode-to-default-scene transaction.  The detail
        still owns its read-only master/sample option projections, including
        component tests and embedded uses where no ``MainWindow`` is present.
        """

        normalized = str(mode_id or "").strip()
        previous = self._is_syncing
        self._is_syncing = True
        try:
            if normalized == "official":
                self._sync_official_master_options()
                self._sync_official_material_sample_options(
                    profile_id=self._selected_official_profile_id()
                )
            elif normalized == "exam":
                config = (
                    self._config()
                    if self._current_scene is not None
                    and _scene_is_exam(
                        self._current_scene,
                        mode_id=_bridge_work_mode_id(
                            self._bridge,
                            self._current_scene,
                        ),
                    )
                    else ExamPaperConfig()
                )
                self._refresh_blank_style_options(config)
        finally:
            self._is_syncing = previous

    def _set_plan_preview_surface(self, surface: str) -> None:
        normalized = str(surface or "").strip()
        is_exam = normalized == "exam"
        is_official = normalized == "official"
        # Custom exam layouts are an external, tutorial-driven workflow. This
        # surface only projects the selected plan and its generated appearance.
        self._master_card.setVisible(False)
        self._plan_preview_card.setVisible(is_exam or is_official)
        self._preview_mode_control.setVisible(is_exam)
        self._prompt_card.setVisible(is_exam)
        self._active_preview_provider_id = (
            "exam" if is_exam else "official" if is_official else ""
        )
        self._runtime_fields_widget.setVisible(False)
        self._live_summary.setVisible(False)
        self._runtime_note.setVisible(False)

    def focus_navigation_field(self, field_id: str) -> bool:
        widgets = {
            "master_id": self._blank_style,
            "exam_paper.runtime_fields": self._workbench_btn,
        }
        widget = widgets.get(str(field_id or "").strip())
        if widget is None:
            return False
        self._highlight_navigation_widget(widget, field_id)
        return True

    def _refresh_blank_style_options(self, config: ExamPaperConfig) -> None:
        current = str(
            getattr(self._current_scene, "master_id", "") or "default_exam"
        )
        sync_user_exam_blank_master_files(config, USER_EXAM_MASTER_DIR)
        self._blank_style.clear()
        for option in master_selector_options(
            "exam",
            exam_config=config,
            user_master_dir=USER_EXAM_MASTER_DIR,
        ):
            self._blank_style.addItem(option.label, option.value)
        _set_combo_by_data(self._blank_style, current)

    def _refresh_style_status(self, config: ExamPaperConfig | None = None) -> None:
        if self._current_scene is None:
            return
        config = config or ensure_exam_paper_config(self._current_scene)
        style_id = str(
            self._blank_style.currentData()
            or getattr(self._current_scene, "master_id", "")
            or "default_exam"
        )
        resolve_exam_blank_style(config, style_id)
        self._refresh_master_preview(config=config, style_id=style_id)

    def _config(self) -> ExamPaperConfig | None:
        if self._current_scene is None:
            return None
        return ensure_exam_paper_config(self._current_scene)

    def _selected_blank_style_id(self, config: ExamPaperConfig) -> str:
        del config
        return str(
            self._blank_style.currentData()
            or getattr(self._current_scene, "master_id", "")
            or "default_exam"
        )

    def _on_blank_style_changed(self, *_args) -> None:
        if self._is_syncing:
            return
        config = self._config()
        if config is None:
            return
        if self._current_scene is None:
            return
        self._current_scene.master_id = str(
            self._blank_style.currentData() or "default_exam"
        )
        self._refresh_style_status(config)
        self._refresh_live_summary(config)
        self.scene_edited.emit()

    def _open_blank_master_folder(self) -> None:
        try:
            USER_EXAM_MASTER_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            Toast.show_error(f"卷面文件夹打开失败: {exc}")
            return
        if self._open_sample_path_handler(USER_EXAM_MASTER_DIR):
            Toast.show_success(f"已打开卷面文件夹: {USER_EXAM_MASTER_DIR}")
        else:
            Toast.show_warning(f"无法自动打开卷面文件夹: {USER_EXAM_MASTER_DIR}")

    def _on_runtime_fields_changed(self, *_args) -> None:
        if self._is_syncing:
            return
        config = self._config()
        if config is None:
            return
        selected = [
            field_id
            for field_id, _label in EXAM_RUNTIME_FIELD_OPTIONS
            if self._runtime_checks[field_id].isChecked()
        ]
        if not selected:
            selected = list(EXAM_DEFAULT_RUNTIME_FIELDS)
            self._is_syncing = True
            try:
                for field_id, checkbox in self._runtime_checks.items():
                    checkbox.setChecked(field_id in selected)
            finally:
                self._is_syncing = False
        config.runtime_fields = selected
        self._refresh_live_summary(config)
        self.scene_edited.emit()

    def _refresh_exam_prompt(self, *_args) -> None:
        prompt_id = str(self._prompt_mode_control.current_data() or "markdown")
        self._prompt_area.set_text(exam_ai_prompt_text(prompt_id))
        refresh_layout_chain_later(self)

    def _copy_current_exam_prompt(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self._prompt_area.get_text())
        Toast.show_success("已复制提示词")

    def _refresh_master_preview(
        self,
        *_args,
        config: ExamPaperConfig | None = None,
        style_id: str | None = None,
    ) -> None:
        if self._current_scene is None:
            return
        config = config or ensure_exam_paper_config(self._current_scene)
        selected_style_id = str(
            style_id
            or self._blank_style.currentData()
            or getattr(self._current_scene, "master_id", "")
            or "default_exam"
        )
        self._request_exam_word_preview(
            config=config,
            style_id=selected_style_id,
        )

    def _refresh_real_document_preview(self) -> None:
        if self._active_preview_provider_id == "exam":
            self._request_exam_word_preview(force=True)
        elif self._active_preview_provider_id == "official":
            self._request_official_word_preview(force=True)

    def _request_exam_word_preview(
        self,
        *,
        config: ExamPaperConfig | None = None,
        style_id: str | None = None,
        force: bool = False,
    ) -> None:
        if not self._real_preview_enabled or self._current_scene is None:
            return
        config = config or ensure_exam_paper_config(self._current_scene)
        selected_style_id = str(
            style_id
            or self._blank_style.currentData()
            or getattr(self._current_scene, "master_id", "")
            or "default_exam"
        )
        preview_kind = str(self._preview_mode_control.current_data() or "student")
        preview_label = "答案版" if preview_kind == "answer" else "学生卷"
        self._document_word_preview.set_loading(
            f"正在生成{preview_label}真实 Word 预览…"
        )
        request = build_exam_word_preview_request(
            style_id=selected_style_id,
            config=config,
            preview_kind=preview_kind,
            template_id=_scene_current_template_id(self._current_scene),
        )
        self._document_word_preview_controller.request_preview(request, force=force)

    def _reset_defaults(self) -> None:
        if self._current_scene is None:
            return
        current = ensure_exam_paper_config(self._current_scene)
        config = ExamPaperConfig(
            question_structure_mode=current.question_structure_mode,
            answer_policy=current.answer_policy,
            runtime_fields=list(current.runtime_fields or EXAM_DEFAULT_RUNTIME_FIELDS),
        )
        self._current_scene.master_id = "default_exam"
        self._current_scene.exam_paper = config
        self.set_scene(self._current_scene)
        self.scene_edited.emit()

    def _refresh_live_summary(self, config: ExamPaperConfig | None = None) -> None:
        if self._current_scene is None:
            self._live_summary.setText("")
            return
        config = config or ensure_exam_paper_config(self._current_scene)
        blank = exam_blank_style_label(self._current_scene.master_id, config)
        fields = [
            _option_label(EXAM_RUNTIME_FIELD_OPTIONS, field_id, field_id)
            for field_id in config.runtime_fields
            if str(field_id or "").strip()
        ]
        field_text = "、".join(fields) if fields else "标题、科目、年级、考试时间、满分"
        self._live_summary.setText(f"当前会使用“{blank}”；工作台会填写：{field_text}。")
        refresh_layout_chain_later(self)

    def _on_material_context_changed(self, _context) -> None:
        if self._current_scene is None:
            return
        if not _scene_uses_official_document_surface(
            self._current_scene,
            mode_id=_bridge_work_mode_id(self._bridge, self._current_scene),
        ):
            return
        previous = self._is_syncing
        self._is_syncing = True
        try:
            self._sync_official_profile_from_material_context()
            self._sync_official_material_sample_options(
                profile_id=self._selected_official_profile_id()
            )
            self._refresh_official_preview()
        finally:
            self._is_syncing = previous

    def _on_official_document_type_changed(self, document_type_id: str) -> None:
        if self._current_scene is None:
            return
        if not _scene_uses_official_document_surface(
            self._current_scene,
            mode_id=_bridge_work_mode_id(self._bridge, self._current_scene),
        ):
            return
        previous = self._is_syncing
        self._is_syncing = True
        try:
            _set_combo_by_data(self._official_profile, document_type_id)
            self._sync_official_master_for_profile(document_type_id)
            self._sync_official_material_sample_options(profile_id=document_type_id)
            self._refresh_official_preview()
        finally:
            self._is_syncing = previous

    def _on_official_profile_changed(self, *_args) -> None:
        if self._is_syncing:
            return
        if self._bridge is not None and hasattr(
            self._bridge,
            "set_current_official_document_type_id",
        ):
            self._bridge.set_current_official_document_type_id(
                self._selected_official_profile_id()
            )
        self._sync_official_master_for_profile(self._selected_official_profile_id())
        self._sync_official_material_sample_options(
            profile_id=self._selected_official_profile_id()
        )
        self._refresh_official_preview()

    def _on_official_material_sample_changed(self, *_args) -> None:
        if self._is_syncing:
            return
        sample = self._selected_official_material_sample()
        if sample is None:
            self._refresh_official_preview()
            return
        if sample.profile_id != self._selected_official_profile_id():
            previous = self._is_syncing
            self._is_syncing = True
            try:
                _set_combo_by_data(self._official_profile, sample.profile_id)
                self._sync_official_material_sample_options(
                    profile_id=sample.profile_id,
                    preferred_sample_id=sample.qualified_id,
                )
            finally:
                self._is_syncing = previous
        self._refresh_official_preview()

    def _request_official_word_preview(self, *, force: bool = False) -> None:
        if not self._real_preview_enabled:
            return
        master = self._selected_official_master()
        if master is None or not Path(master.docx_path).is_file():
            self._on_document_word_preview_failed(
                DocumentWordPreviewResult(
                    status="master_missing",
                    provider_id="official",
                    variant_id=self._selected_official_profile_id(),
                    issues=("当前 DOCX 母版不可用",),
                )
            )
            return
        profile_id = self._selected_official_profile_id()
        material_context = self._official_material_context()
        entity_data = dict(getattr(material_context, "entity_data", {}) or {})
        field_aliases = dict(getattr(material_context, "field_aliases", {}) or {})
        template_id = (
            str(getattr(master, "template_config_id", "") or "").strip()
            or str(getattr(self._current_scene, "template_id", "") or "").strip()
            or "official_gbt"
        )
        self._document_word_preview.set_loading()
        request = build_official_word_preview_request(
            profile_id=profile_id,
            entity_data=entity_data,
            field_aliases=field_aliases,
            master=master,
            template_id=template_id,
        )
        self._document_word_preview_controller.request_preview(request, force=force)

    def _on_document_word_preview_ready(
        self, result: DocumentWordPreviewResult
    ) -> None:
        if result.provider_id != self._active_preview_provider_id:
            return
        self._document_preview_failure_notified = False
        self._document_word_preview.set_pages(
            result.page_paths,
            uses_sample_data=result.uses_sample_data,
            cache_hit=result.cache_hit,
            renderer=result.renderer,
        )
        refresh_layout_chain_later(self)

    def _on_document_word_preview_failed(
        self, result: DocumentWordPreviewResult
    ) -> None:
        if result.provider_id != self._active_preview_provider_id:
            return
        issues = "；".join(result.issues[:2]) or result.status or "未知错误"
        self._document_word_preview.set_error(issues)
        if not self._document_preview_failure_notified:
            self._document_preview_failure_notified = True
            label = "试卷" if result.provider_id == "exam" else "公文"
            Toast.show_warning(f"{label}真实 Word 预览暂不可用，可点击刷新重试")

    def _refresh_official_preview(self, *_args) -> None:
        profile_id = self._selected_official_profile_id()
        master = self._selected_official_master()
        contract = get_official_document_assembly_contract(profile_id)
        projection = build_official_plan_preview_projection(
            profile_id=profile_id,
            master=master,
            contract=contract,
            material_context=self._official_material_context(),
            current_template_id=str(
                getattr(self._current_scene, "template_id", "") or ""
            ),
        )
        self._official_template.setText(projection.header_text)
        self._official_material_status.setText(projection.material_status_text)
        self._official_contract.setText(projection.contract_text)
        self._official_sample_btn.setEnabled(projection.sample_enabled)
        self._official_open_master_btn.setEnabled(projection.open_master_enabled)
        if projection.request_word_preview:
            self._request_official_word_preview()

    def _apply_official_sample_material(self) -> None:
        if self._bridge is None or not hasattr(
            self._bridge, "set_current_material_context"
        ):
            Toast.show_warning("当前页面没有连接资料包上下文")
            return
        sample_id = str(self._official_material_sample.currentData() or "").strip()
        if not sample_id:
            Toast.show_warning("当前没有可套用的公文资料包样例")
            return
        try:
            result = load_official_document_material_package_sample(sample_id)
        except Exception as exc:
            Toast.show_error(f"套用公文资料包样例失败: {exc}")
            return
        if result.status in {
            "sample_not_found",
            "sample_ambiguous",
            "unknown_profile",
            "invalid_package",
        }:
            Toast.show_warning(f"公文资料包样例未套用: {result.status}")
            return

        self._bridge.set_current_material_context(result.context)
        self._sync_official_profile_from_material_context()
        self._sync_official_material_sample_to_profile(
            self._selected_official_profile_id()
        )
        self._refresh_official_preview()
        if result.status == "missing_required_fields":
            Toast.show_warning(
                f"已套用公文资料包样例，仍缺少必填字段: "
                f"{self._official_field_list(result.missing_required_fields)}"
            )
        else:
            Toast.show_success("已套用公文资料包样例，可到工作台执行生成")

    def _load_official_material_package(self, path: Path | str):
        if self._bridge is None or not hasattr(
            self._bridge, "set_current_material_context"
        ):
            Toast.show_warning("当前页面没有连接资料包上下文")
            return None
        try:
            result = _load_official_material_source(
                path,
                profile_id=self._selected_official_profile_id(),
            )
        except Exception as exc:
            Toast.show_error(f"导入公文资料失败: {exc}")
            return None

        if result.status in {
            "missing_profile",
            "profile_conflict",
            "unknown_profile",
            "invalid_package",
            "invalid_table",
            "multiple_records",
        }:
            Toast.show_warning(f"公文资料未导入: {result.status}")
            return result

        self._bridge.set_current_material_context(result.context)
        self._sync_official_profile_from_material_context()
        self._sync_official_material_sample_to_profile(
            self._selected_official_profile_id()
        )
        self._refresh_official_preview()
        if result.status == "missing_required_fields":
            Toast.show_warning(
                f"已导入公文资料包，仍缺少必填字段: "
                f"{self._official_field_list(result.missing_required_fields)}"
            )
        elif result.unknown_fields:
            Toast.show_warning(
                f"已导入公文资料，包含未识别字段: "
                f"{self._official_field_list(result.unknown_fields)}"
            )
        else:
            Toast.show_success(f"已导入公文资料: {Path(path).name}")
        return result

    def _export_official_material_package_to_path(self, path: Path | str):
        context = self._official_material_context()
        profile_id = self._selected_official_profile_id()
        try:
            result = export_official_document_material_package(
                context,
                path,
                profile_id=profile_id,
            )
        except Exception as exc:
            Toast.show_error(f"导出公文资料包失败: {exc}")
            return None
        if result.status == "missing_required_fields":
            Toast.show_warning(
                f"已导出公文资料包，但缺少必填字段: "
                f"{self._official_field_list(result.missing_required_fields)}"
            )
        elif result.status == "ok":
            Toast.show_success(f"已导出公文资料包: {Path(path).name}")
        else:
            Toast.show_warning(f"已导出公文资料包，状态: {result.status}")
        return result

    def _generate_official_sample(self) -> None:
        profile_id = self._selected_official_profile_id()
        master = self._selected_official_master()
        context = self._official_material_context()
        entity_data = dict(getattr(context, "entity_data", {}) or {})
        entity_data.setdefault("document_type", profile_id)
        try:
            result = verify_official_document_sample_visual(
                profile_id,
                _official_sample_output_dir(),
                entity_data=entity_data,
                filename=f"{profile_id}_official_sample.docx",
                master=master,
            )
        except Exception as exc:
            Toast.show_error(f"生成公文样张失败: {exc}")
            return
        if result.sample_docx_path is not None and result.sample_docx_path.exists():
            if result.ok:
                Toast.show_success(f"已生成公文样张: {result.sample_docx_path.name}")
            else:
                Toast.show_warning(f"已生成公文样张，视觉验证状态: {result.status}")
            self._open_sample_path_handler(result.sample_docx_path.parent)
            self._refresh_official_preview()
            return
        missing = self._official_field_list(result.missing_required_fields)
        if result.status == "missing_required_fields" and missing:
            Toast.show_warning(f"公文资料缺少必填字段: {missing}")
            self._refresh_official_preview()
            return
        Toast.show_warning(f"公文样张未生成: {result.status}")
        self._refresh_official_preview()

    def _open_official_master(self) -> None:
        master = self._selected_official_master()
        if master is None:
            Toast.show_warning("未找到公文版式")
            return
        if not master.docx_path.exists():
            Toast.show_warning(f"公文版式不存在: {master.docx_path}")
            return
        if self._open_sample_path_handler(master.docx_path):
            Toast.show_success(f"已打开公文版式: {master.docx_path.name}")
        else:
            Toast.show_warning(f"无法自动打开公文版式: {master.docx_path}")

    def _sync_official_master_options(self) -> None:
        bound_master_id = str(
            getattr(self._current_scene, "master_id", "") or ""
        ).strip()
        self._official_master.clear()
        for option in master_selector_options("official"):
            self._official_master.addItem(option.label, option.value)
        profile_id = self._selected_official_profile_id()
        contract = get_official_document_assembly_contract(profile_id)
        bound_master = (
            get_master(bound_master_id, "official") if bound_master_id else None
        )
        target = str(getattr(contract, "master_id", "") or "official_gbt_standard")
        if (
            bound_master is not None
            and bound_master.source_type == "user"
            and (
                not bound_master.supported_assembly_types
                or profile_id in bound_master.supported_assembly_types
            )
        ):
            target = bound_master.master_id
        _set_combo_by_data(self._official_master, target)

    def _sync_official_master_for_profile(self, profile_id: str) -> None:
        normalized = self._normalize_official_profile_id(profile_id)
        current = self._selected_official_master()
        if (
            current is not None
            and current.source_type == "user"
            and (
                not current.supported_assembly_types
                or normalized in current.supported_assembly_types
            )
        ):
            return
        contract = get_official_document_assembly_contract(normalized)
        target = str(getattr(contract, "master_id", "") or "official_gbt_standard")
        _set_combo_by_data(self._official_master, target)

    def _sync_official_material_sample_options(
        self,
        *,
        profile_id: str | None = None,
        preferred_sample_id: str = "",
    ) -> None:
        target_profile = self._normalize_official_profile_id(
            profile_id
            or self._selected_official_profile_id()
            or self._official_scene_default_profile_id()
            or "notice"
        )
        current = str(
            preferred_sample_id or self._official_material_sample.currentData() or ""
        ).strip()
        previous = self._is_syncing
        self._is_syncing = True
        try:
            self._official_material_sample.clear()
            for option in material_package_sample_selector_options(
                "official",
                profile_id=target_profile,
            ):
                self._official_material_sample.addItem(option.label, option.value)
            current_sample = get_official_document_material_package_sample(current)
            target = ""
            if (
                current_sample is not None
                and current_sample.profile_id == target_profile
            ):
                target = current
            if not target:
                target = self._official_material_sample_id_for_profile(target_profile)
            if target:
                _set_combo_by_data(self._official_material_sample, target)
                self._official_material_sample.setEnabled(True)
                self._official_apply_sample_btn.setEnabled(True)
                return

            label = self._official_profile_label(target_profile)
            self._official_material_sample.addItem(f"暂无{label}资料包样例", "")
            self._official_material_sample.setCurrentIndex(
                max(0, self._official_material_sample.count() - 1)
            )
            self._official_material_sample.setEnabled(
                self._official_material_sample.count() > 1
            )
            self._official_apply_sample_btn.setEnabled(False)
        finally:
            self._is_syncing = previous

    def _sync_official_material_sample_to_profile(self, profile_id: str) -> bool:
        target_profile = self._normalize_official_profile_id(profile_id)
        sample_id = self._official_material_sample_id_for_profile(target_profile)
        if not sample_id:
            self._sync_official_material_sample_options(profile_id=target_profile)
            return False
        previous = self._is_syncing
        self._is_syncing = True
        try:
            _set_combo_by_data(self._official_material_sample, sample_id)
        finally:
            self._is_syncing = previous
        return True

    def _official_material_sample_id_for_profile(self, profile_id: str) -> str:
        target_profile = self._normalize_official_profile_id(profile_id)
        for index in range(self._official_material_sample.count()):
            sample_id = str(
                self._official_material_sample.itemData(index) or ""
            ).strip()
            sample = get_official_document_material_package_sample(sample_id)
            if sample is not None and sample.profile_id == target_profile:
                return sample_id
        return ""

    def _normalize_official_profile_id(self, profile_id: str | None) -> str:
        target_profile = str(profile_id or "").strip()
        if target_profile.startswith("official:"):
            target_profile = target_profile.split(":", 1)[1]
        return target_profile

    def _official_profile_label(self, profile_id: str) -> str:
        profile = get_official_document_profile(
            self._normalize_official_profile_id(profile_id)
        )
        if profile is not None:
            return str(profile.label or profile.profile_id).strip()
        return self._normalize_official_profile_id(profile_id) or "当前文种"

    def _selected_official_material_sample(self):
        sample_id = str(self._official_material_sample.currentData() or "").strip()
        if not sample_id:
            return None
        return get_official_document_material_package_sample(sample_id)

    def _sync_official_profile_from_material_context(self) -> None:
        if self._bridge is not None and hasattr(
            self._bridge,
            "current_official_document_type_id",
        ):
            profile_id = str(
                self._bridge.current_official_document_type_id() or ""
            ).strip()
            if profile_id:
                _set_combo_by_data(self._official_profile, profile_id)
                return
        context = self._official_material_context()
        profile_id = str(getattr(context, "profile_id", "") or "").strip()
        if profile_id.startswith("official:"):
            profile_id = profile_id.split(":", 1)[1]
        if not profile_id:
            profile_id = str(
                getattr(context, "entity_data", {}).get("document_type", "") or ""
            )
        if not profile_id:
            profile_id = self._official_scene_default_profile_id()
        _set_combo_by_data(self._official_profile, profile_id or "notice")

    def _official_scene_default_profile_id(self) -> str:
        raw_profile = str(
            getattr(self._current_scene, "default_material_profile_id", "") or ""
        ).strip()
        if ":" in raw_profile:
            _prefix, raw_profile = raw_profile.split(":", 1)
        return raw_profile.strip()

    def _selected_official_profile_id(self) -> str:
        return str(self._official_profile.currentData() or "notice").strip() or "notice"

    def _selected_official_master(self):
        master_id = str(self._official_master.currentData() or "").strip()
        masters = list_masters("official")
        for master in masters:
            if master.master_id == master_id or master.qualified_id == master_id:
                return master
        return masters[0] if masters else None

    def _official_material_context(self) -> MaterialExecutionContext:
        if self._bridge is not None and hasattr(
            self._bridge, "current_material_context"
        ):
            context = self._bridge.current_material_context()
            if isinstance(context, MaterialExecutionContext):
                return context
        return MaterialExecutionContext()

    def _official_field_list(self, fields) -> str:
        values = [
            str(field or "").strip()
            for field in fields or ()
            if str(field or "").strip()
        ]
        return "、".join(values)

    def closeEvent(self, event) -> None:
        self._shutdown_document_word_preview()
        super().closeEvent(event)

    def _shutdown_document_word_preview(self, timeout_ms: int = 250) -> bool:
        controller = getattr(self, "_document_word_preview_controller", None)
        if controller is None:
            return True
        return bool(controller.shutdown(timeout_ms=timeout_ms))

    def _apply_theme(self) -> None:
        super()._apply_theme()
        t = get_theme()
        if hasattr(self, "_reset_btn"):
            stylesheet = build_button_stylesheet(t)
            for button, variant in (
                (self._reset_btn, "secondary"),
                (self._workbench_btn, "primary"),
            ):
                button.setStyleSheet(stylesheet)
                apply_button_variant(button, variant)
        if hasattr(self, "_live_summary"):
            self._live_summary.setStyleSheet(
                f"font-size: {t.font_size_md}px; color: {t.text_primary};"
                f"background: {t.bg_selected}; border: 1px solid {t.border_light};"
                f"border-radius: {t.radius_sm}px; padding: 8px 10px;"
            )
        if hasattr(self, "_copy_prompt_btn"):
            self._copy_prompt_btn.setStyleSheet(build_button_stylesheet(t))
            apply_button_variant(self._copy_prompt_btn, "secondary")
        if hasattr(self, "_runtime_note"):
            self._runtime_note.setStyleSheet(
                f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
            )
        if hasattr(self, "_runtime_checks"):
            stylesheet = build_checkbox_stylesheet(t)
            for checkbox in self._runtime_checks.values():
                checkbox.setStyleSheet(stylesheet)
