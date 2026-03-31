from __future__ import annotations

from datetime import datetime

from src.qt_api import QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget, Signal
from src.shared.ui.button_style import apply_button_variant
from src.shared.ui.card import Card
from src.shared.ui.config_list_widget import ConfigListWidget
from src.shared.ui.theme import bind_theme, get_theme


class ConfigManagementDetail(QWidget):
    """Workbench V2 configuration-management detail pane."""

    summary_changed = Signal()

    def __init__(self, strategy_summary_card: QWidget | None = None, parent=None):
        super().__init__(parent)
        self._config_counter = 2
        self._loaded_config_name = ""

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(16)

        self._intro = QLabel(
            "\u5728\u8fd9\u91cc\u4fdd\u5b58\u3001\u641c\u7d22\u3001\u52a0\u8f7d\u548c\u5220\u9664\u6267\u884c\u914d\u7f6e\u3002"
        )
        self._intro.setWordWrap(True)
        self._layout.addWidget(self._intro)

        if strategy_summary_card is not None:
            self._layout.addWidget(strategy_summary_card)

        self._build_save_card()
        self._build_list_card()
        self._layout.addStretch(1)

        self._seed_configs()
        self._emit_summary_changed()

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _build_save_card(self) -> None:
        self._save_card = Card("\u4fdd\u5b58\u5f53\u524d\u914d\u7f6e", parent=self)

        self._name_input = QLineEdit(self._save_card)
        self._name_input.setPlaceholderText("\u914d\u7f6e\u540d\u79f0")
        self._desc_input = QTextEdit(self._save_card)
        self._desc_input.setPlaceholderText("\u914d\u7f6e\u63cf\u8ff0\uff08\u53ef\u9009\uff09")
        self._desc_input.setMaximumHeight(88)

        self._save_btn = QPushButton("\u4fdd\u5b58\u914d\u7f6e", self._save_card)
        apply_button_variant(self._save_btn, "primary")
        self._save_btn.clicked.connect(self._save_current_config)

        self._save_status = QLabel("\u6682\u672a\u65b0\u589e\u914d\u7f6e\u3002", self._save_card)

        self._save_card.add_widget(self._name_input)
        self._save_card.add_widget(self._desc_input)
        self._save_card.add_widget(self._save_btn)
        self._save_card.add_widget(self._save_status)
        self._layout.addWidget(self._save_card)

    def _build_list_card(self) -> None:
        self._list_card = Card("\u5df2\u4fdd\u5b58\u7684\u914d\u7f6e", parent=self)
        self._config_list = ConfigListWidget(self._list_card)
        self._config_list.config_loaded.connect(self._on_config_loaded)
        self._config_list.config_deleted.connect(self._on_config_deleted)
        self._list_status = QLabel("\u53ef\u4ece\u5217\u8868\u76f4\u63a5\u52a0\u8f7d\u6216\u5220\u9664\u3002", self._list_card)

        self._list_card.add_widget(self._config_list)
        self._list_card.add_widget(self._list_status)
        self._layout.addWidget(self._list_card)

    def _seed_configs(self) -> None:
        self._config_list.add_config(
            "cfg-1",
            "\u9ed8\u8ba4\u914d\u7f6e",
            "\u9002\u7528\u4e8e\u901a\u7528\u6587\u6863\u683c\u5f0f\u5316\u3002",
            "2026-03-31 10:00",
        )
        self._config_list.add_config(
            "cfg-2",
            "\u6280\u672f\u6587\u6863\u914d\u7f6e",
            "\u5305\u542b\u6807\u9898\u7f16\u53f7\u3001\u76ee\u5f55\u4e0e\u8f93\u51fa\u8981\u6c42\u3002",
            "2026-03-31 14:30",
        )

    def _save_current_config(self) -> None:
        name = self._name_input.text().strip()
        if not name:
            self._save_status.setText("\u8bf7\u5148\u8f93\u5165\u914d\u7f6e\u540d\u79f0\u3002")
            return

        self._config_counter += 1
        config_id = f"cfg-{self._config_counter}"
        description = self._desc_input.toPlainText().strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._config_list.add_config(config_id, name, description, timestamp)
        self._name_input.clear()
        self._desc_input.clear()
        self._save_status.setText(f"\u5df2\u4fdd\u5b58\u914d\u7f6e\uff1a{name}")
        self._emit_summary_changed()

    def _on_config_loaded(self, config_id: str) -> None:
        self._loaded_config_name = self._config_list.config_name(config_id) or config_id
        self._list_status.setText(f"\u5df2\u52a0\u8f7d\u914d\u7f6e\uff1a{self._loaded_config_name}")
        self._emit_summary_changed()

    def _on_config_deleted(self, config_id: str) -> None:
        deleted_name = self._config_list.config_name(config_id) or config_id
        self._config_list.remove_config(config_id)
        if deleted_name == self._loaded_config_name:
            self._loaded_config_name = ""
        self._list_status.setText(f"\u5df2\u5220\u9664\u914d\u7f6e\uff1a{deleted_name}")
        self._emit_summary_changed()

    def navigation_snapshot(self) -> dict[str, str]:
        count = self._config_list.config_count()
        if self._loaded_config_name:
            subtitle = f"{self._loaded_config_name} · {count} \u4e2a\u5df2\u4fdd\u5b58"
            badge_text = "\u5df2\u52a0\u8f7d"
            badge_variant = "success"
        else:
            subtitle = f"{count} \u4e2a\u5df2\u4fdd\u5b58\u914d\u7f6e"
            badge_text = str(count)
            badge_variant = "neutral"
        return {
            "subtitle": subtitle,
            "badge_text": badge_text,
            "badge_variant": badge_variant,
        }

    def _emit_summary_changed(self) -> None:
        self.summary_changed.emit()

    def _apply_theme(self) -> None:
        t = get_theme()
        self._intro.setStyleSheet(
            f"font-size: {t.font_size_md}px; color: {t.text_secondary};"
        )
        self._save_status.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_secondary};"
        )
        self._list_status.setStyleSheet(
            f"font-size: {t.font_size_sm}px; color: {t.text_hint};"
        )
