from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.config.library import is_scene_library_path, is_template_library_path
from src.config.loader import save_scene, save_template
from src.qt_api import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.config_list_widget import ConfigListWidget
from src.shared.ui.theme import bind_theme, get_theme

from .diagnostics import log_best_effort_state_sync_failure


class _SceneExportSection(QWidget):
    changed = Signal()

    def __init__(self, bridge=None, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._current_scene = None
        self._scene_dirty = bool(bridge.is_scene_dirty()) if bridge is not None else False
        self._scene_id = ""
        self._scene_name = ""
        self._scene_path = ""
        self._scene_source = ""
        self._last_scene_save_path = ""

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        self._scene_status = QLabel("", self)
        self._scene_status.setWordWrap(True)
        self._layout.addWidget(self._scene_status)

        self._scene_export_card = Card(parent=self)
        self._scene_export_card.set_header("保存当前场景", icon_name="save")

        actions = QWidget(self._scene_export_card)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(10)

        self._scene_save_btn = QPushButton("保存场景文件", actions)
        apply_button_variant(self._scene_save_btn, "primary")
        self._scene_save_btn.clicked.connect(self._save_scene_file)
        actions_layout.addWidget(self._scene_save_btn, 1)

        self._scene_save_as_btn = QPushButton("场景另存为", actions)
        apply_button_variant(self._scene_save_as_btn, "secondary")
        self._scene_save_as_btn.clicked.connect(self._save_scene_as)
        actions_layout.addWidget(self._scene_save_as_btn, 1)

        self._scene_export_status = QLabel("当前还没有可保存的场景。", self._scene_export_card)
        self._scene_export_status.setWordWrap(True)

        self._scene_path_label = QLabel("", self._scene_export_card)
        self._scene_path_label.setWordWrap(True)

        self._scene_export_card.add_widget(actions)
        self._scene_export_card.add_widget(self._scene_export_status)
        self._scene_export_card.add_widget(self._scene_path_label)
        self._layout.addWidget(self._scene_export_card)

        if self._bridge is not None:
            self._bridge.scene_dirty_changed.connect(self._on_scene_dirty_changed)

        self._refresh_state()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_current_scene(self, scene) -> None:
        self._current_scene = scene
        self._scene_name = str(getattr(scene, "name", "") or "").strip()
        self._scene_id = str(getattr(scene, "scene_id", "") or "").strip()
        self._sync_context_from_bridge()
        self._refresh_state()
        self.changed.emit()

    def is_scene_dirty(self) -> bool:
        return self._scene_dirty

    def navigation_snapshot(self) -> dict[str, str]:
        scene_label = self._scene_name or self._scene_id or "当前场景"
        return {
            "subtitle": f"{scene_label} 有未保存的更改",
            "badge_text": "未保存",
            "badge_variant": "warning",
        }

    def save_current_scene_to_path(self, path: str | Path) -> Path:
        if self._current_scene is None:
            raise RuntimeError("no current scene is available to save")

        saved_path = save_scene(self._current_scene, path)
        self._last_scene_save_path = str(saved_path)
        self._scene_path = str(saved_path)
        self._scene_source = "library" if is_scene_library_path(saved_path) else "file"
        self._scene_id = str(getattr(self._current_scene, "scene_id", "") or "").strip() or saved_path.stem
        try:
            self._current_scene.scene_id = self._scene_id
        except Exception as exc:
            log_best_effort_state_sync_failure("scene export section", "scene_id assignment", exc)

        self._scene_export_status.setText(f"已保存当前场景：{saved_path.name}")
        self._scene_path_label.setText(f"保存到：{saved_path}")

        if self._bridge is not None:
            self._bridge.set_current_scene(
                self._current_scene,
                config_id=self._scene_id,
                path=self._scene_path,
                source=self._scene_source,
            )
            self._bridge.clear_scene_dirty()
        else:
            self._scene_dirty = False
            self._refresh_state()

        self.changed.emit()
        return saved_path

    def _default_scene_save_path(self) -> str:
        if self._scene_path:
            return self._scene_path
        if self._last_scene_save_path:
            return self._last_scene_save_path
        scene_name = self._scene_name or self._scene_id or "scene_config"
        return str(Path.cwd() / f"{_safe_file_stem(scene_name)}.json")

    def _save_scene_file(self) -> None:
        if self._current_scene is None:
            self._scene_export_status.setText("当前还没有可保存的场景。")
            return

        if self._scene_path:
            self.save_current_scene_to_path(self._scene_path)
            return

        self._save_scene_as()

    def _save_scene_as(self) -> None:
        if self._current_scene is None:
            self._scene_export_status.setText("当前还没有可保存的场景。")
            return

        file_path, _selected = QFileDialog.getSaveFileName(
            self,
            "保存场景配置",
            self._default_scene_save_path(),
            "Config Files (*.json *.yaml *.yml);;JSON Files (*.json);;YAML Files (*.yaml *.yml)",
        )
        file_path = str(file_path or "").strip()
        if not file_path:
            return
        if not Path(file_path).suffix:
            file_path += ".json"
        self.save_current_scene_to_path(file_path)

    def _sync_context_from_bridge(self) -> None:
        if self._bridge is None:
            return
        self._scene_id = self._bridge.current_scene_id() or self._scene_id
        self._scene_path = self._bridge.current_scene_path() or self._scene_path
        self._scene_source = self._bridge.current_scene_source() or self._scene_source

    def _on_scene_dirty_changed(self, dirty: bool) -> None:
        self._scene_dirty = bool(dirty)
        self._sync_context_from_bridge()
        self._refresh_state()
        self.changed.emit()

    def _refresh_state(self) -> None:
        scene_label = self._scene_name or self._scene_id or "当前场景"

        if self._current_scene is None:
            self._scene_save_btn.setEnabled(False)
            self._scene_save_as_btn.setEnabled(False)
            self._scene_status.setText("当前会话还没有载入可编辑场景。")
        elif self._scene_dirty:
            self._scene_save_btn.setEnabled(True)
            self._scene_save_as_btn.setEnabled(True)
            self._scene_status.setText(f"{scene_label} 有未保存的更改，可在确认后保存场景文件。")
        else:
            self._scene_save_btn.setEnabled(True)
            self._scene_save_as_btn.setEnabled(True)
            self._scene_status.setText(f"{scene_label} 当前没有未保存的更改。")

        self._scene_path_label.setText(f"路径：{self._scene_path}" if self._scene_path else "")
        self._apply_theme()

    def _apply_theme(self) -> None:
        t = get_theme()
        self._scene_status.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.warning if self._scene_dirty else t.text_secondary};"
        )
        self._scene_export_status.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        )
        self._scene_path_label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
        )


class _TemplateExportSection(QWidget):
    changed = Signal()

    def __init__(self, bridge=None, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._current_template = None
        self._template_dirty = bool(bridge.is_template_dirty()) if bridge is not None else False
        self._template_id = ""
        self._template_name = ""
        self._template_path = ""
        self._template_source = ""
        self._last_template_save_path = ""

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        self._template_status = QLabel("", self)
        self._template_status.setWordWrap(True)
        self._layout.addWidget(self._template_status)

        self._template_export_card = Card(parent=self)
        self._template_export_card.set_header("保存当前模板", icon_name="save")

        actions = QWidget(self._template_export_card)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(10)

        self._template_export_btn = QPushButton("保存模板文件", self._template_export_card)
        apply_button_variant(self._template_export_btn, "primary")
        self._template_export_btn.clicked.connect(self._save_template_file)
        actions_layout.addWidget(self._template_export_btn, 1)

        self._template_save_as_btn = QPushButton("模板另存为", self._template_export_card)
        apply_button_variant(self._template_save_as_btn, "secondary")
        self._template_save_as_btn.clicked.connect(self._save_template_as)
        actions_layout.addWidget(self._template_save_as_btn, 1)

        self._template_export_status = QLabel("当前还没有可保存的模板。", self._template_export_card)
        self._template_export_status.setWordWrap(True)

        self._last_save_path_label = QLabel("", self._template_export_card)
        self._last_save_path_label.setWordWrap(True)

        self._template_export_card.add_widget(actions)
        self._template_export_card.add_widget(self._template_export_status)
        self._template_export_card.add_widget(self._last_save_path_label)
        self._layout.addWidget(self._template_export_card)

        if self._bridge is not None:
            self._bridge.template_dirty_changed.connect(self._on_template_dirty_changed)

        self._refresh_state()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_current_template(self, template) -> None:
        self._current_template = template
        self._template_name = str(getattr(template, "name", "") or "").strip()
        self._sync_context_from_bridge()
        self._refresh_state()
        self.changed.emit()

    def is_template_dirty(self) -> bool:
        return self._template_dirty

    def navigation_snapshot(self) -> dict[str, str]:
        template_label = self._template_name or self._template_id or "当前模板"
        return {
            "subtitle": f"{template_label} 有未保存的更改",
            "badge_text": "未保存",
            "badge_variant": "warning",
        }

    def save_current_template_to_path(self, path: str | Path) -> Path:
        if self._current_template is None:
            raise RuntimeError("no current template is available to save")

        saved_path = save_template(self._current_template, path)
        self._last_template_save_path = str(saved_path)
        self._template_path = str(saved_path)
        self._template_source = "library" if is_template_library_path(saved_path) else "file"
        self._template_id = self._template_id or saved_path.stem

        self._template_export_status.setText(f"已保存当前模板：{saved_path.name}")
        self._last_save_path_label.setText(f"保存到：{saved_path}")

        if self._bridge is not None:
            self._bridge.set_current_template(
                self._current_template,
                config_id=self._template_id or saved_path.stem,
                path=self._template_path,
                source=self._template_source,
            )
            self._bridge.clear_template_dirty()
        else:
            self._template_dirty = False
            self._refresh_state()

        self.changed.emit()
        return saved_path

    def _default_template_save_path(self) -> str:
        if self._template_path:
            return self._template_path
        if self._last_template_save_path:
            return self._last_template_save_path
        template_name = self._template_name or self._template_id or "template_config"
        return str(Path.cwd() / f"{_safe_file_stem(template_name)}.json")

    def _save_template_file(self) -> None:
        if self._current_template is None:
            self._template_export_status.setText("当前还没有可保存的模板。")
            return

        if self._template_path:
            self.save_current_template_to_path(self._template_path)
            return

        self._save_template_as()

    def _save_template_as(self) -> None:
        if self._current_template is None:
            self._template_export_status.setText("当前还没有可保存的模板。")
            return

        file_path, _selected = QFileDialog.getSaveFileName(
            self,
            "保存模板配置",
            self._default_template_save_path(),
            "Config Files (*.json *.yaml *.yml);;JSON Files (*.json);;YAML Files (*.yaml *.yml)",
        )
        file_path = str(file_path or "").strip()
        if not file_path:
            return
        if not Path(file_path).suffix:
            file_path += ".json"
        self.save_current_template_to_path(file_path)

    def _sync_context_from_bridge(self) -> None:
        if self._bridge is None:
            return
        self._template_id = self._bridge.current_template_id() or self._template_id
        self._template_path = self._bridge.current_template_path() or self._template_path
        self._template_source = self._bridge.current_template_source() or self._template_source

    def _on_template_dirty_changed(self, dirty: bool) -> None:
        self._template_dirty = bool(dirty)
        self._sync_context_from_bridge()
        self._refresh_state()
        self.changed.emit()

    def _refresh_state(self) -> None:
        template_label = self._template_name or self._template_id or "当前模板"

        if self._current_template is None:
            self._template_export_btn.setEnabled(False)
            self._template_save_as_btn.setEnabled(False)
            self._template_status.setText("当前会话还没有载入可编辑模板。")
        elif self._template_dirty:
            self._template_export_btn.setEnabled(True)
            self._template_save_as_btn.setEnabled(True)
            self._template_status.setText(f"{template_label} 有未保存的更改，可在确认后保存模板文件。")
        else:
            self._template_export_btn.setEnabled(True)
            self._template_save_as_btn.setEnabled(True)
            self._template_status.setText(f"{template_label} 当前没有未保存的更改。")

        self._last_save_path_label.setText(f"路径：{self._template_path}" if self._template_path else "")
        self._apply_theme()

    def _apply_theme(self) -> None:
        t = get_theme()
        self._template_status.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.warning if self._template_dirty else t.text_secondary};"
        )
        self._template_export_status.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        )
        self._last_save_path_label.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
        )


class _SessionConfigSection(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config_counter = 0
        self._loaded_config_name = ""

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(16)

        self._build_save_card()
        self._build_list_card()

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def navigation_snapshot(self) -> dict[str, str]:
        count = self._config_list.config_count()

        if self._loaded_config_name:
            subtitle = f"{self._loaded_config_name} · {count} 项已保存"
            badge_text = "已加载"
            badge_variant = "success"
        elif count:
            subtitle = f"{count} 项配置"
            badge_text = str(count)
            badge_variant = "neutral"
        else:
            subtitle = "暂无已保存的配置"
            badge_text = "暂无"
            badge_variant = "warning"

        return {
            "subtitle": subtitle,
            "badge_text": badge_text,
            "badge_variant": badge_variant,
        }

    def _build_save_card(self) -> None:
        self._save_card = Card(parent=self)
        self._save_card.set_header("保存会话配置", icon_name="save")

        self._name_input = QLineEdit(self._save_card)
        self._name_input.setPlaceholderText("配置名称")

        self._desc_input = QTextEdit(self._save_card)
        self._desc_input.setPlaceholderText("描述（可选）")
        self._desc_input.setMaximumHeight(88)

        self._save_btn = QPushButton("保存配置", self._save_card)
        apply_button_variant(self._save_btn, "primary")
        self._save_btn.clicked.connect(self._save_current_config)

        self._save_status = QLabel("还没有保存任何会话配置。", self._save_card)

        self._save_card.add_widget(self._name_input)
        self._save_card.add_widget(self._desc_input)
        self._save_card.add_widget(self._save_btn)
        self._save_card.add_widget(self._save_status)

        self._layout.addWidget(self._save_card)

    def _build_list_card(self) -> None:
        self._list_card = Card(parent=self)
        self._list_card.set_header("会话配置", icon_name="scroll-text")

        self._config_list = ConfigListWidget(self._list_card)
        self._config_list.config_loaded.connect(self._on_config_loaded)
        self._config_list.config_deleted.connect(self._on_config_deleted)

        self._list_status = QLabel(
            "会话配置当前仅保存在内存中，后续可接入持久化存储。",
            self._list_card,
        )

        self._list_card.add_widget(self._config_list)
        self._list_card.add_widget(self._list_status)
        self._layout.addWidget(self._list_card)

    def _save_current_config(self) -> None:
        name = self._name_input.text().strip()
        if not name:
            self._save_status.setText("请先输入配置名称。")
            return

        self._config_counter += 1
        config_id = f"cfg-{self._config_counter}"
        description = self._desc_input.toPlainText().strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        self._config_list.add_config(config_id, name, description, timestamp)
        self._name_input.clear()
        self._desc_input.clear()
        self._save_status.setText(f"已保存配置：{name}")
        self.changed.emit()

    def _on_config_loaded(self, config_id: str) -> None:
        self._loaded_config_name = self._config_list.config_name(config_id) or config_id
        self._list_status.setText(f"已载入配置：{self._loaded_config_name}")
        self.changed.emit()

    def _on_config_deleted(self, config_id: str) -> None:
        deleted_name = self._config_list.config_name(config_id) or config_id
        self._config_list.remove_config(config_id)
        if deleted_name == self._loaded_config_name:
            self._loaded_config_name = ""
        self._list_status.setText(f"已删除配置：{deleted_name}")
        self.changed.emit()

    def _apply_theme(self) -> None:
        t = get_theme()
        self._save_status.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        )
        self._list_status.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
        )


class ConfigManagementDetail(QWidget):
    """Workbench V2 configuration-management detail pane."""

    summary_changed = Signal()

    def __init__(self, strategy_summary_card: QWidget | None = None, bridge=None, parent=None):
        super().__init__(parent)
        self._bridge = bridge

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(16)

        self._intro = QLabel(
            "集中管理当前场景文件、模板文件和会话内执行草稿。",
            self,
        )
        self._intro.setWordWrap(True)
        self._layout.addWidget(self._intro)

        if strategy_summary_card is not None:
            self._layout.addWidget(strategy_summary_card)

        self._scene_export_section = _SceneExportSection(bridge=bridge, parent=self)
        self._template_export_section = _TemplateExportSection(bridge=bridge, parent=self)
        self._session_config_section = _SessionConfigSection(self)

        self._scene_export_section.changed.connect(self._emit_summary_changed)
        self._template_export_section.changed.connect(self._emit_summary_changed)
        self._session_config_section.changed.connect(self._emit_summary_changed)

        self._layout.addWidget(self._scene_export_section)
        self._layout.addWidget(self._template_export_section)
        self._layout.addWidget(self._session_config_section)
        self._layout.addStretch(1)

        self._template_status = self._template_export_section._template_status
        self._template_export_btn = self._template_export_section._template_export_btn
        self._template_export_status = self._template_export_section._template_export_status
        self._last_save_path_label = self._template_export_section._last_save_path_label

        self._save_card = self._session_config_section._save_card
        self._name_input = self._session_config_section._name_input
        self._desc_input = self._session_config_section._desc_input
        self._save_btn = self._session_config_section._save_btn
        self._save_status = self._session_config_section._save_status
        self._list_card = self._session_config_section._list_card
        self._config_list = self._session_config_section._config_list
        self._list_status = self._session_config_section._list_status

        self._emit_summary_changed()
        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def set_current_scene(self, scene) -> None:
        self._scene_export_section.set_current_scene(scene)

    def set_current_template(self, template) -> None:
        self._template_export_section.set_current_template(template)

    def save_current_scene_to_path(self, path: str | Path) -> Path:
        return self._scene_export_section.save_current_scene_to_path(path)

    def save_current_template_to_path(self, path: str | Path) -> Path:
        return self._template_export_section.save_current_template_to_path(path)

    def is_scene_dirty(self) -> bool:
        return self._scene_export_section.is_scene_dirty()

    def is_template_dirty(self) -> bool:
        return self._template_export_section.is_template_dirty()

    def navigation_snapshot(self) -> dict[str, str]:
        scene_dirty = self._scene_export_section.is_scene_dirty()
        template_dirty = self._template_export_section.is_template_dirty()

        if scene_dirty and template_dirty:
            return {
                "subtitle": "当前场景与模板均有未保存更改",
                "badge_text": "2 项未保存",
                "badge_variant": "warning",
            }
        if scene_dirty:
            return self._scene_export_section.navigation_snapshot()
        if template_dirty:
            return self._template_export_section.navigation_snapshot()
        return self._session_config_section.navigation_snapshot()

    def _emit_summary_changed(self) -> None:
        self.summary_changed.emit()

    def _apply_theme(self) -> None:
        t = get_theme()
        self._intro.setStyleSheet(
            f"font-size: {t.font_size_md}px; color: {t.text_secondary};"
        )


def _safe_file_stem(value: str) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join(ch if ch not in forbidden else "_" for ch in str(value or "").strip())
    cleaned = cleaned.strip(" ._")
    return cleaned or "config"
