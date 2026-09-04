from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from src.application.materials import MaterialPreviewSnapshot
from src.config.library import load_scene_from_library
from src.config.scene import SceneWorkspace
from src.config.scene_surface_registry import scene_uses_exam_paper_surface
from src.domain.materials import MaterialRunSelection
from src.qt_api import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    Qt,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui import ThemedRadioButton
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.icons.catalog import get_icon
from src.shared.ui.path_action_semantics import PathAction, path_action_presentation
from src.shared.ui.path_drop import PathAcceptancePolicy, attach_path_drop
from src.shared.ui.rounded_surface import RoundedSurfaceFrame
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme, theme_rgba
from src.ui.adapters.config_selector_models import (
    plan_selector_options,
    strip_source_prefix,
    template_selector_options,
)

from .document_input_manifest import (
    DocumentInputManifest,
    discover_document_inputs,
)
from .quick_execution_result_presenter import build_execution_result_presentation
from .state import ExecutionProgressState, ExecutionResultState


class FileBatchSourceArea(RoundedSurfaceFrame):
    """Acquire one or more documents without inventing a file/profile mapping."""

    paths_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent=parent)
        self.setObjectName("wb_file_batch_source_area")
        self.setMinimumHeight(76)
        self.setAutoFillBackground(False)
        self._accepted_suffixes = (".docx",)
        self._dialog_label = "Word 文档"
        self._manifest = DocumentInputManifest()
        self._policy = self._build_policy()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(17, 17, 17, 17)
        layout.setSpacing(10)
        self._icon = QLabel(self)
        self._icon.setFixedSize(36, 36)
        self._icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        self._title = QLabel(self)
        self._hint = QLabel(self)
        self._hint.setWordWrap(False)
        text_column.addWidget(self._title)
        text_column.addWidget(self._hint)
        layout.addLayout(text_column, 1)

        self._clear_button = QPushButton("清空", self)
        self._clear_button.clicked.connect(self.clear)
        self._clear_button.setVisible(False)
        layout.addWidget(self._clear_button, 0, Qt.AlignVCenter)
        self._files_button = QPushButton("选择文件", self)
        self._files_button.clicked.connect(self._pick_files)
        layout.addWidget(self._files_button, 0, Qt.AlignVCenter)
        self._folder_button = QPushButton("选择文件夹", self)
        self._folder_button.clicked.connect(self._pick_folder)
        layout.addWidget(self._folder_button, 0, Qt.AlignVCenter)

        self._drop_controller = attach_path_drop(
            parent=self,
            surface=self,
            policy=self._policy,
            on_paths=self._on_paths_dropped,
        )
        bind_theme(self, self._apply_theme)
        self._apply_theme()
        self._refresh()

    def _build_policy(self) -> PathAcceptancePolicy:
        return PathAcceptancePolicy(
            path_kind="either",
            suffixes=self._accepted_suffixes,
            cardinality="multiple",
            dialog_label=self._dialog_label,
            include_all_files=False,
        )

    def configure_file_acceptance(
        self,
        *,
        suffixes: Iterable[str],
        dialog_label: str,
    ) -> None:
        normalized = tuple(
            suffix if str(suffix).startswith(".") else f".{suffix}"
            for suffix in (
                str(value or "").strip().casefold()
                for value in suffixes
            )
            if suffix
        )
        self._accepted_suffixes = normalized or (".docx",)
        self._dialog_label = str(dialog_label or "支持的文件").strip()
        self._policy = self._build_policy()
        self._drop_controller.set_policy(self._policy)
        self.set_paths(self._manifest.requested_paths)

    def paths(self) -> tuple[str, ...]:
        return self._manifest.paths()

    def manifest(self) -> DocumentInputManifest:
        return self._manifest

    def title_text(self) -> str:
        return self._title.text()

    def hint_text(self) -> str:
        return self._hint.text()

    def set_paths(self, paths: Iterable[str]) -> tuple[str, ...]:
        manifest = discover_document_inputs(
            paths,
            accepted_suffixes=self._accepted_suffixes,
        )
        if manifest == self._manifest:
            return self.paths()
        self._manifest = manifest
        self._refresh()
        self.paths_changed.emit(self.paths())
        return self.paths()

    def clear(self) -> None:
        self.set_paths(())

    def _on_paths_dropped(self, paths: object) -> None:
        self.set_paths(
            (*self._manifest.requested_paths, *tuple(paths or ()))
        )

    def _pick_files(self) -> None:
        paths, _selected = QFileDialog.getOpenFileNames(
            self,
            "选择待处理文档",
            "",
            self._policy.dialog_filter,
        )
        if paths:
            self.set_paths((*self._manifest.requested_paths, *paths))

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择待处理文件夹",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if folder:
            self.set_paths((*self._manifest.requested_paths, folder))

    def _refresh(self) -> None:
        paths = self.paths()
        if paths:
            count_label = (
                f"至少 {len(paths)}"
                if self._manifest.truncated
                else str(len(paths))
            )
            self._title.setText(f"已识别 {count_label} 个文档")
            names = [Path(path).name for path in paths]
            preview = "、".join(names[:3])
            if len(names) > 3:
                preview += f" 等 {len(names)} 个"
            preview += f" · 来自 {len(self._manifest.roots)} 个位置"
            if self._manifest.issues:
                preview += f" · {len(self._manifest.issues)} 项提示"
            self._hint.setText(preview)
            self._hint.setToolTip(
                "\n".join((*paths, *self._manifest.issues))
            )
        else:
            if self._manifest.requested_paths and self._manifest.issues:
                issue_count = len(self._manifest.issues)
                self._title.setText("未识别到可处理文档")
                self._hint.setText(
                    self._manifest.issues[0]
                    + (
                        f" · 另有 {issue_count - 1} 项"
                        if issue_count > 1
                        else ""
                    )
                )
                self._hint.setToolTip("\n".join(self._manifest.issues))
            elif self._manifest.roots:
                folder_roots = tuple(
                    root
                    for root in self._manifest.roots
                    if root.kind == "folder"
                )
                folder_count = len(folder_roots)
                self._title.setText(
                    f"已选择 {folder_count} 个文件夹"
                )
                suffix_text = " / ".join(self._accepted_suffixes)
                folder_names = "、".join(
                    root.label for root in folder_roots[:3]
                )
                self._hint.setText(
                    f"{folder_names} · 暂未发现支持的 {suffix_text} 文档"
                )
                self._hint.setToolTip(
                    "\n".join(root.path for root in folder_roots)
                )
            else:
                suffix_text = " / ".join(self._accepted_suffixes)
                self._title.setText("拖拽文件或文件夹至此处")
                self._hint.setText(
                    f"支持 {suffix_text}；文件夹将包含子文件夹"
                )
                self._hint.setToolTip("")
        has_selection = bool(self._manifest.requested_paths)
        self._clear_button.setVisible(has_selection)
        self._files_button.setVisible(not has_selection)
        self._folder_button.setVisible(not has_selection)
        self._refresh_surface()

    def _apply_theme(self) -> None:
        for button in (
            self._clear_button,
            self._files_button,
            self._folder_button,
        ):
            apply_size_class(button, "md")
            apply_button_variant(button, "secondary")
        self._refresh_surface()

    def _refresh_surface(self) -> None:
        theme = get_theme()
        selected = bool(self._manifest.roots)
        source_kind = self._source_kind()
        icon_name = (
            "folder-open"
            if source_kind == "folder"
            else "file-text"
            if selected
            else "file-input"
        )
        foreground = (
            theme.text_on_primary if selected else theme.text_primary
        )
        hint_color = (
            theme_rgba(theme.text_on_primary, 0.85)
            if selected
            else theme.text_hint
        )
        icon_color = (
            theme.text_on_primary if selected else theme.primary
        )
        icon_background = (
            theme_rgba(theme.text_on_primary, 0.20)
            if selected
            else theme_rgba(theme.primary, 0.06)
        )

        self._icon.setProperty("sourceKind", source_kind)
        self._icon.setAccessibleName(
            {
                "folder": "文件夹来源",
                "file": "文件来源",
                "idle": "文件或文件夹来源",
            }[source_kind]
        )
        self._icon.setPixmap(
            get_icon(icon_name, 18, icon_color).pixmap(18, 18)
        )
        self._icon.setStyleSheet(
            f"background: {icon_background}; "
            f"border-radius: {theme.radius_sm}px;"
        )
        self._title.setStyleSheet(
            f"font-size: {theme.font_size_md}px; "
            f"font-weight: {theme.font_weight_emphasis}; "
            f"color: {foreground}; background: transparent;"
        )
        self._hint.setStyleSheet(
            f"font-size: {theme.font_size_sm}px; color: {hint_color}; "
            "background: transparent;"
        )
        self.configure_surface(
            background=theme.primary if selected else theme.bg_card,
            radius=theme.radius_sm,
            border_color=theme.primary if selected else theme.border,
            border_width=1.0,
        )
        self.update()

    def _source_kind(self) -> str:
        """Return the visual source kind, prioritizing folder semantics."""

        for requested_path in self._manifest.requested_paths:
            try:
                if Path(requested_path).expanduser().is_dir():
                    return "folder"
            except OSError:
                continue
        if any(root.kind == "folder" for root in self._manifest.roots):
            return "folder"
        if self._manifest.roots:
            return "file"
        return "idle"


def _source_badge(source_type: object) -> tuple[str, str]:
    return (
        ("内置", "builtin")
        if str(source_type or "").strip() == "builtin"
        else ("自定", "user")
    )


class FileBatchExecutionDetail(QWidget):
    """Execute one shared plan independently across a selected file set."""

    binding_changed = Signal(object, str)
    execute_requested = Signal()
    cancel_requested = Signal()
    summary_changed = Signal()
    paths_changed = Signal(object)

    def __init__(
        self,
        parent=None,
        *,
        source_area: FileBatchSourceArea | None = None,
        include_source_area: bool = True,
        include_shared_chrome: bool = True,
        defer_context_build: bool = False,
    ) -> None:
        super().__init__(parent)
        self._include_shared_chrome = bool(include_shared_chrome)
        self._context_built = False
        self._context_initialized = False
        self.setObjectName("wb_file_batch_execution_detail")
        self.setMinimumWidth(320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._scene = SceneWorkspace(scene_id="default")
        self._work_mode_id = "custom"
        self._plan_label = "未绑定方案"
        self._template_label = "未绑定模板"
        self._binding_signal_blocked = False
        self._material_selection: MaterialRunSelection | None = None
        self._material_preview: MaterialPreviewSnapshot | None = None
        self._runtime_template_overrides: dict[str, object] = {}
        self._custom_output_dir = ""
        self._execution_running = False
        self._actions_enabled = True
        self._last_result_status = "idle"
        self._preflight_confirmation_key = ""

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(get_theme().template_detail_section_gap)

        self._source_area = source_area or FileBatchSourceArea(self)
        if self._source_area.parent() is None:
            self._source_area.setParent(self)
        self._source_area.paths_changed.connect(self._on_paths_changed)
        if include_source_area:
            self._layout.addWidget(self._source_area)

        if not defer_context_build:
            self.ensure_context_built()

        bind_theme(self, self._apply_theme)
        if self._context_built and self._include_shared_chrome:
            self._populate_scene_options()
            self._populate_template_options()
        self._context_initialized = True
        self._apply_theme()
        self._refresh_projection()

    def ensure_context_built(self) -> None:
        if self._context_built:
            return
        if self._include_shared_chrome:
            self._build_binding_card()
        self._build_material_card()
        if self._include_shared_chrome:
            self._build_output_card()
            self._build_execution_card()
        self._layout.addStretch(1)
        self._context_built = True
        if self._context_initialized:
            self._apply_theme()
            self._refresh_projection()

    def _build_binding_card(self) -> None:
        self._binding_card = Card(parent=self)
        self._binding_card.set_header("处理方案与模板", icon_name="boxes")

        row = QWidget(self._binding_card)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._scene_label = QLabel("处理方案", row)
        layout.addWidget(self._scene_label)
        self._scene_combo = StyledComboBox(row)
        self._scene_combo.set_full_width_mode(True)
        self._scene_combo.currentIndexChanged.connect(self._on_scene_changed)
        layout.addWidget(self._scene_combo, 1)

        layout.addSpacing(10)
        self._template_label_widget = QLabel("模板", row)
        layout.addWidget(self._template_label_widget)
        self._template_combo = StyledComboBox(row)
        self._template_combo.set_full_width_mode(True)
        self._template_combo.currentIndexChanged.connect(self._on_template_changed)
        layout.addWidget(self._template_combo, 1)

        self._binding_card.add_widget(row)
        self._layout.addWidget(self._binding_card)

    def _build_material_card(self) -> None:
        self._material_card = Card(parent=self)
        self._material_card.set_header("共享资料", icon_name="database")
        self._material_summary = QLabel(self._material_card)
        self._material_summary.setWordWrap(True)
        self._material_card.add_widget(self._material_summary)
        self._layout.addWidget(self._material_card)

    def _build_output_card(self) -> None:
        self._output_card = Card(parent=self)
        self._output_card.set_header(
            "输出目录",
            icon_name="square-arrow-out-up-right",
        )

        row = QWidget(self._output_card)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._output_mode_group = QButtonGroup(self)
        self._output_mode_group.setExclusive(True)
        self._output_default_radio = ThemedRadioButton("默认", row)
        self._output_custom_radio = ThemedRadioButton("自定义", row)
        self._output_mode_group.addButton(self._output_default_radio, 0)
        self._output_mode_group.addButton(self._output_custom_radio, 1)
        self._output_default_radio.setChecked(True)
        self._output_custom_radio.toggled.connect(self._on_output_mode_changed)
        layout.addWidget(self._output_default_radio)
        layout.addWidget(self._output_custom_radio)

        self._output_browse_button = QPushButton("选择目录", row)
        self._output_browse_button.clicked.connect(self._pick_output_dir)
        self._output_browse_button.setVisible(False)
        apply_size_class(self._output_browse_button, "md")
        layout.addWidget(self._output_browse_button, 1)
        layout.addStretch(1)

        self._output_card.add_widget(row)
        self._layout.addWidget(self._output_card)

    def _build_execution_card(self) -> None:
        self._execution_card = Card(parent=self)
        self._execution_card.set_header("执行与结果", icon_name="terminal")

        row = QWidget(self._execution_card)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._status_label = QLabel(row)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label, 1)

        self._cancel_button = QPushButton("取消", row)
        self._cancel_button.clicked.connect(self.cancel_requested.emit)
        self._cancel_button.setVisible(False)
        apply_size_class(self._cancel_button, "lg")
        layout.addWidget(self._cancel_button)

        self._execute_button = QPushButton(row)
        self._execute_button.clicked.connect(self.execute_requested.emit)
        apply_size_class(self._execute_button, "lg")
        layout.addWidget(self._execute_button)

        self._execution_card.add_widget(row)

        self._progress_bar = QProgressBar(self._execution_card)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setVisible(False)
        self._execution_card.add_widget(self._progress_bar)

        self._result_log = QTextEdit(self._execution_card)
        self._result_log.setReadOnly(True)
        self._result_log.setMinimumHeight(110)
        self._result_log.setMaximumHeight(220)
        self._result_log.setVisible(False)
        self._execution_card.add_widget(self._result_log)

        self._layout.addWidget(self._execution_card)

    def selected_paths(self) -> tuple[str, ...]:
        return self._source_area.paths()

    def set_selected_paths(self, paths) -> tuple[str, ...]:
        return self._source_area.set_paths(paths)

    def input_manifest(self) -> DocumentInputManifest:
        return self._source_area.manifest()

    def output_roots_by_path(self) -> dict[str, str]:
        return self.input_manifest().output_roots(self.output_dir())

    def output_dir(self) -> str:
        return self._custom_output_dir

    def current_template_id(self) -> str:
        if not self._include_shared_chrome:
            return str(self._scene.template_id or "").strip()
        return str(self._template_combo.currentData() or "").strip()

    def runtime_template_overrides(self) -> dict[str, object]:
        return dict(self._runtime_template_overrides)

    def set_runtime_template_overrides(
        self,
        overrides: dict[str, object] | None,
    ) -> None:
        self._runtime_template_overrides = dict(overrides or {})

    def set_material_selection(
        self,
        selection: MaterialRunSelection | None,
        *,
        preview: MaterialPreviewSnapshot | None = None,
    ) -> None:
        self._material_selection = (
            selection
            if isinstance(selection, MaterialRunSelection)
            else None
        )
        self._material_preview = (
            preview
            if isinstance(preview, MaterialPreviewSnapshot)
            else None
        )
        self.clear_preflight_confirmation()
        self._refresh_projection()

    def set_work_mode(self, mode_id: str) -> None:
        mode = str(mode_id or "").strip() or "custom"
        if mode == self._work_mode_id and (
            not self._include_shared_chrome or self._scene_combo.count()
        ):
            return
        self._work_mode_id = mode
        if self._include_shared_chrome:
            self._binding_signal_blocked = True
            try:
                self._populate_scene_options(current_scene_id=self._scene.scene_id)
                self._populate_template_options(
                    current_template_id=self._scene.template_id
                )
            finally:
                self._binding_signal_blocked = False
        self._configure_source_acceptance()
        self.clear_preflight_confirmation()
        self._refresh_projection()

    def set_scene_context(self, scene: SceneWorkspace | None) -> None:
        self._scene = (
            scene
            if isinstance(scene, SceneWorkspace)
            else SceneWorkspace(scene_id="default")
        )
        scene_mode = str(getattr(self._scene, "mode_id", "") or "").strip()
        if scene_mode:
            self._work_mode_id = scene_mode
        if self._include_shared_chrome:
            self._binding_signal_blocked = True
            try:
                self._populate_scene_options(current_scene_id=self._scene.scene_id)
                self._populate_template_options(
                    current_template_id=self._scene.template_id
                )
            finally:
                self._binding_signal_blocked = False
        self._configure_source_acceptance()
        self.clear_preflight_confirmation()
        self._refresh_projection()

    def set_strategy_context(
        self,
        *,
        plan_label: str,
        template_label: str,
        template_id: str = "",
    ) -> None:
        self._plan_label = str(plan_label or "").strip() or "未绑定方案"
        self._template_label = str(template_label or "").strip() or "未绑定模板"
        target = str(template_id or "").strip()
        if target and self._include_shared_chrome:
            index = self._template_combo.findData(target)
            if index >= 0:
                blocked = self._template_combo.blockSignals(True)
                self._template_combo.setCurrentIndex(index)
                self._template_combo.blockSignals(blocked)
        self._refresh_projection()

    def _configure_source_acceptance(self) -> None:
        if scene_uses_exam_paper_surface(
            self._scene,
            mode_id=self._work_mode_id,
        ):
            self._source_area.configure_file_acceptance(
                suffixes=(".md", ".markdown"),
                dialog_label="Markdown 文件",
            )
            return
        self._source_area.configure_file_acceptance(
            suffixes=(".docx",),
            dialog_label="Word 文档",
        )

    def _populate_scene_options(self, *, current_scene_id: str = "") -> None:
        target = str(current_scene_id or self._scene.scene_id or "").strip()
        blocked = self._scene_combo.blockSignals(True)
        try:
            self._scene_combo.clear()
            selected = -1
            for option in plan_selector_options(
                self._work_mode_id,
                include_source_prefix=False,
            ):
                badge_text, badge_kind = _source_badge(option.source_type)
                index = self._scene_combo.add_badged_item(
                    option.label,
                    option.value,
                    badge_text=badge_text,
                    badge_kind=badge_kind,
                )
                if option.tooltip:
                    self._scene_combo.setItemData(index, option.tooltip, Qt.ToolTipRole)
                if option.value == target:
                    selected = index
            if selected >= 0:
                self._scene_combo.setCurrentIndex(selected)
        finally:
            self._scene_combo.blockSignals(blocked)

    def _populate_template_options(self, *, current_template_id: str = "") -> None:
        compatible = list(self._scene.compatible_template_ids or [])
        if not compatible and self._scene.template_id:
            compatible = [self._scene.template_id]
        target = str(current_template_id or self._scene.template_id or "").strip()
        blocked = self._template_combo.blockSignals(True)
        try:
            self._template_combo.clear()
            selected = -1
            for option in template_selector_options(
                self._work_mode_id,
                template_ids=compatible or None,
                include_source_prefix=False,
            ):
                badge_text, badge_kind = _source_badge(option.source_type)
                index = self._template_combo.add_badged_item(
                    option.label,
                    option.value,
                    badge_text=badge_text,
                    badge_kind=badge_kind,
                )
                if option.tooltip:
                    self._template_combo.setItemData(index, option.tooltip, Qt.ToolTipRole)
                if option.value == target:
                    selected = index
            if selected >= 0:
                self._template_combo.setCurrentIndex(selected)
        finally:
            self._template_combo.blockSignals(blocked)

    def _on_scene_changed(self, index: int) -> None:
        if self._binding_signal_blocked or index < 0:
            return
        scene_id = str(self._scene_combo.itemData(index) or "").strip()
        if not scene_id:
            return
        try:
            scene = load_scene_from_library(
                scene_id,
                mode_id=self._work_mode_id,
            )
        except (KeyError, OSError, TypeError, ValueError):
            self._populate_scene_options(current_scene_id=self._scene.scene_id)
            return
        self._scene = scene
        self._plan_label = strip_source_prefix(self._scene_combo.currentText())
        self._populate_template_options(current_template_id=scene.template_id)
        self._configure_source_acceptance()
        self.clear_preflight_confirmation()
        self._last_result_status = "idle"
        self._refresh_projection()
        self.binding_changed.emit(scene, self.current_template_id())

    def _on_template_changed(self, index: int) -> None:
        if self._binding_signal_blocked or index < 0:
            return
        template_id = str(self._template_combo.itemData(index) or "").strip()
        if not template_id:
            return
        self._template_label = strip_source_prefix(
            self._template_combo.currentText()
        )
        self.clear_preflight_confirmation()
        self._last_result_status = "idle"
        self._refresh_projection()
        self.binding_changed.emit(self._scene, template_id)

    def _on_paths_changed(self, paths: object) -> None:
        self.clear_preflight_confirmation()
        self.reset_execution_feedback()
        self.paths_changed.emit(tuple(paths or ()))
        self.summary_changed.emit()

    def _on_output_mode_changed(self, custom: bool) -> None:
        self._output_browse_button.setVisible(bool(custom))
        if not custom:
            self._custom_output_dir = ""
            self._output_browse_button.setText("选择目录")
        self.clear_preflight_confirmation()
        self._last_result_status = "idle"
        self._refresh_projection()

    def _pick_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择批量输出目录",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if not folder:
            return
        self._custom_output_dir = str(folder)
        self._output_browse_button.setText(Path(folder).name or folder)
        choose = path_action_presentation(PathAction.CHOOSE_DIRECTORY)
        self._output_browse_button.setIcon(
            get_icon(choose.icon_name, 16, get_theme().icon_primary)
        )
        self.clear_preflight_confirmation()
        self._refresh_projection()

    def preflight_confirmation_matches(self, key: str) -> bool:
        return bool(key) and self._preflight_confirmation_key == str(key)

    def set_preflight_confirmation(self, key: str, message: str) -> None:
        self._preflight_confirmation_key = str(key or "").strip()
        if not self._include_shared_chrome:
            return
        self._status_label.setText(str(message or "请确认后继续"))
        self._execute_button.setText("确认并批量处理")
        self._result_log.setVisible(False)

    def clear_preflight_confirmation(self) -> None:
        self._preflight_confirmation_key = ""

    def set_execute_enabled(self, enabled: bool) -> None:
        self._actions_enabled = bool(enabled)
        self._refresh_execution_actions()

    def has_local_execution_surface(self) -> bool:
        return self._include_shared_chrome

    def reset_execution_feedback(self) -> None:
        self._execution_running = False
        self._last_result_status = "idle"
        if not self._include_shared_chrome:
            self._refresh_projection()
            return
        self._progress_bar.setVisible(False)
        self._progress_bar.setValue(0)
        self._cancel_button.setVisible(False)
        self._result_log.clear()
        self._result_log.setVisible(False)
        self._refresh_projection()

    def set_execution_progress(self, state: ExecutionProgressState) -> None:
        self._execution_running = True
        if not self._include_shared_chrome:
            self.summary_changed.emit()
            return
        self._status_label.setText(str(state.stage_text or "正在批量处理"))
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(max(0, min(100, int(state.percent or 0))))
        self._cancel_button.setVisible(True)
        self._refresh_execution_actions()
        self.summary_changed.emit()

    def set_execution_result(self, state: ExecutionResultState) -> None:
        self._execution_running = False
        self._last_result_status = str(state.status or "failed")
        self.clear_preflight_confirmation()
        if not self._include_shared_chrome:
            self.summary_changed.emit()
            return
        presentation = build_execution_result_presentation(state)
        self._status_label.setText(
            presentation.summary or presentation.status_text
        )
        self._result_log.setPlainText(
            "\n".join(entry.message for entry in presentation.log_entries)
        )
        self._result_log.setVisible(bool(presentation.log_entries))
        self._progress_bar.setVisible(False)
        self._cancel_button.setVisible(False)
        self._refresh_execution_actions()
        self.summary_changed.emit()

    def finish_execution(self) -> None:
        self._execution_running = False
        if not self._include_shared_chrome:
            self._refresh_projection()
            return
        self._progress_bar.setVisible(False)
        self._cancel_button.setVisible(False)
        self._refresh_projection()

    def navigation_snapshot(self) -> dict[str, str]:
        count = len(self.selected_paths())
        if self._execution_running:
            badge_text, badge_variant = "执行中", "info"
        elif self._last_result_status == "success":
            badge_text, badge_variant = "已完成", "success"
        elif self._last_result_status in {"failed", "partial_success"}:
            badge_text, badge_variant = "需查看", "warning"
        else:
            badge_text, badge_variant = ("就绪", "success") if count else ("待补充", "neutral")
        return {
            "subtitle": (
                f"{count} 个文档 · {self._template_label}"
                if count
                else "尚未选择文档"
            ),
            "badge_text": badge_text,
            "badge_variant": badge_variant,
        }

    def _refresh_projection(self) -> None:
        if not self._context_built:
            self.summary_changed.emit()
            return
        count = len(self.selected_paths())
        if self._material_selection is None:
            self._material_summary.setText(
                f"暂无共享资料；方案和模板将分别应用于 {count or '所选'} 个文档"
            )
        else:
            name = (
                (
                    self._material_preview.package_name
                    if self._material_preview is not None
                    else ""
                )
                or self._material_selection.package_ref.package_id
            )
            self._material_summary.setText(
                f"{name} · 将共享应用于 {count or '所选'} 个文档"
            )
        if (
            self._include_shared_chrome
            and not self._execution_running
            and not self._preflight_confirmation_key
        ):
            self._status_label.setText(
                "已就绪，按文件分别输出"
                if count
                else "请选择文件或文件夹"
            )
        self._refresh_execution_actions()
        self.summary_changed.emit()

    def _refresh_execution_actions(self) -> None:
        if not self._include_shared_chrome:
            return
        count = len(self.selected_paths())
        enabled = (
            self._actions_enabled
            and not self._execution_running
            and count > 0
        )
        self._execute_button.setEnabled(enabled)
        self._execute_button.setVisible(not self._execution_running)
        if not self._preflight_confirmation_key:
            self._execute_button.setText(
                f"批量处理 {count} 个文档" if count else "批量处理"
            )

    def _apply_theme(self) -> None:
        theme = get_theme()
        if not self._context_built:
            return
        self._material_summary.setStyleSheet(
            f"font-size: {theme.font_size_md}px; "
            f"color: {theme.text_secondary}; background: transparent;"
        )
        if not self._include_shared_chrome:
            return
        for label in (
            self._scene_label,
            self._template_label_widget,
            self._status_label,
        ):
            label.setStyleSheet(
                f"font-size: {theme.font_size_md}px; "
                f"color: {theme.text_secondary}; background: transparent;"
            )
        apply_button_variant(self._execute_button, "primary")
        apply_button_variant(self._cancel_button, "secondary")
        apply_button_variant(self._output_browse_button, "secondary")


__all__ = ["FileBatchExecutionDetail", "FileBatchSourceArea"]
