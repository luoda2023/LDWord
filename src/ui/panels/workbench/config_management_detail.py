from __future__ import annotations

from datetime import datetime

from pathlib import Path

from src.config.loader import save_template

from src.qt_api import QFileDialog, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget, Signal

from src.shared.ui.button_style import apply_button_variant

from src.shared.ui.card import Card

from src.shared.ui.config_list_widget import ConfigListWidget

from src.shared.ui.theme import bind_theme, get_theme

class _TemplateExportSection(QWidget):

    changed = Signal()

    def __init__(self, bridge=None, parent=None):

        super().__init__(parent)

        self._bridge = bridge

        self._current_template = None

        self._template_dirty = bool(bridge.is_template_dirty()) if bridge is not None else False

        self._template_name = ""

        self._last_template_save_path = ""

        self._layout = QVBoxLayout(self)

        self._layout.setContentsMargins(0, 0, 0, 0)

        self._layout.setSpacing(12)

        self._template_status = QLabel("", self)

        self._template_status.setWordWrap(True)

        self._layout.addWidget(self._template_status)

        self._template_export_card = Card("Save Current Template", parent=self)

        self._template_export_btn = QPushButton("Save As Template File", self._template_export_card)

        apply_button_variant(self._template_export_btn, "primary")

        self._template_export_btn.clicked.connect(self._save_template_as)

        self._template_export_status = QLabel("No template is currently available to save.", self._template_export_card)

        self._template_export_status.setWordWrap(True)

        self._last_save_path_label = QLabel("", self._template_export_card)

        self._last_save_path_label.setWordWrap(True)

        self._template_export_card.add_widget(self._template_export_btn)

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

        self._refresh_state()

        self.changed.emit()

    def is_template_dirty(self) -> bool:

        return self._template_dirty

    def navigation_snapshot(self) -> dict[str, str]:

        template_label = self._template_name or "Current Template"

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

        self._template_export_status.setText(f"Saved current template: {saved_path.name}")

        self._last_save_path_label.setText(f"Saved to: {saved_path}")

        if self._bridge is not None:

            self._bridge.clear_template_dirty()

        else:

            self._template_dirty = False

            self._refresh_state()

        self.changed.emit()

        return saved_path

    def _default_template_save_path(self) -> str:

        if self._last_template_save_path:

            return self._last_template_save_path

        template_name = self._template_name or "template_config"

        forbidden = '<>:"/\\\\|?*'

        safe_name = "".join(ch if ch not in forbidden else "_" for ch in template_name).strip() or "template_config"

        return str(Path.cwd() / f"{safe_name}.json")

    def _save_template_as(self) -> None:

        if self._current_template is None:

            self._template_export_status.setText("No template is currently available to save.")

            return

        file_path, _selected = QFileDialog.getSaveFileName(

            self,

            "Save Template Config",

            self._default_template_save_path(),

            "Config Files (*.json *.yaml *.yml);;JSON Files (*.json);;YAML Files (*.yaml *.yml)",

        )

        file_path = str(file_path or "").strip()

        if not file_path:

            return

        if not Path(file_path).suffix:

            file_path += ".json"

        self.save_current_template_to_path(file_path)

    def _on_template_dirty_changed(self, dirty: bool) -> None:

        self._template_dirty = bool(dirty)

        self._refresh_state()

        self.changed.emit()

    def _refresh_state(self) -> None:

        template_label = self._template_name or "Current Template"

        if self._current_template is None:

            self._template_export_btn.setEnabled(False)

            self._template_status.setText("No editable template has been loaded into the current session yet.")

        elif self._template_dirty:

            self._template_export_btn.setEnabled(True)

            self._template_status.setText(f"{template_label} has unsaved changes. Save a template file when you are ready.")

        else:

            self._template_export_btn.setEnabled(True)

            self._template_status.setText(f"{template_label} currently has no unsaved changes.")

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

        self._save_card = Card("Save Session Config", parent=self)

        self._name_input = QLineEdit(self._save_card)

        self._name_input.setPlaceholderText("Config name")

        self._desc_input = QTextEdit(self._save_card)

        self._desc_input.setPlaceholderText("Description (optional)")

        self._desc_input.setMaximumHeight(88)

        self._save_btn = QPushButton("Save Config", self._save_card)

        apply_button_variant(self._save_btn, "primary")

        self._save_btn.clicked.connect(self._save_current_config)

        self._save_status = QLabel("No session config has been saved yet.", self._save_card)

        self._save_card.add_widget(self._name_input)

        self._save_card.add_widget(self._desc_input)

        self._save_card.add_widget(self._save_btn)

        self._save_card.add_widget(self._save_status)

        self._layout.addWidget(self._save_card)

    def _build_list_card(self) -> None:

        self._list_card = Card("Session Configs", parent=self)

        self._config_list = ConfigListWidget(self._list_card)

        self._config_list.config_loaded.connect(self._on_config_loaded)

        self._config_list.config_deleted.connect(self._on_config_deleted)

        self._list_status = QLabel("Session configs currently live only in memory; persistent storage can be added later.", self._list_card)

        self._list_card.add_widget(self._config_list)

        self._list_card.add_widget(self._list_status)

        self._layout.addWidget(self._list_card)

    def _save_current_config(self) -> None:

        name = self._name_input.text().strip()

        if not name:

            self._save_status.setText("Please enter a config name first.")

            return

        self._config_counter += 1

        config_id = f"cfg-{self._config_counter}"

        description = self._desc_input.toPlainText().strip()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        self._config_list.add_config(config_id, name, description, timestamp)

        self._name_input.clear()

        self._desc_input.clear()

        self._save_status.setText(f"Saved config: {name}")

        self.changed.emit()

    def _on_config_loaded(self, config_id: str) -> None:

        self._loaded_config_name = self._config_list.config_name(config_id) or config_id

        self._list_status.setText(f"Loaded config: {self._loaded_config_name}")

        self.changed.emit()

    def _on_config_deleted(self, config_id: str) -> None:

        deleted_name = self._config_list.config_name(config_id) or config_id

        self._config_list.remove_config(config_id)

        if deleted_name == self._loaded_config_name:

            self._loaded_config_name = ""

        self._list_status.setText(f"Deleted config: {deleted_name}")

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

            "Save, search, load, and delete in-session execution config drafts, and export the current template to a real config file.",

            self,

        )

        self._intro.setWordWrap(True)

        self._layout.addWidget(self._intro)

        if strategy_summary_card is not None:

            self._layout.addWidget(strategy_summary_card)

        self._template_export_section = _TemplateExportSection(bridge=bridge, parent=self)

        self._session_config_section = _SessionConfigSection(self)

        self._template_export_section.changed.connect(self._emit_summary_changed)

        self._session_config_section.changed.connect(self._emit_summary_changed)

        self._layout.addWidget(self._template_export_section)

        self._layout.addWidget(self._session_config_section)

        self._layout.addStretch(1)

        # Backward-compatible attribute aliases used by tests / local probes.

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

    def set_current_template(self, template) -> None:

        self._template_export_section.set_current_template(template)

    def save_current_template_to_path(self, path: str | Path) -> Path:

        return self._template_export_section.save_current_template_to_path(path)

    def is_template_dirty(self) -> bool:

        return self._template_export_section.is_template_dirty()

    def navigation_snapshot(self) -> dict[str, str]:

        if self._template_export_section.is_template_dirty():

            return self._template_export_section.navigation_snapshot()

        return self._session_config_section.navigation_snapshot()

    def _emit_summary_changed(self) -> None:

        self.summary_changed.emit()

    def _apply_theme(self) -> None:

        t = get_theme()

        self._intro.setStyleSheet(

            f"font-size: {t.font_size_md}px; color: {t.text_secondary};"

        )
