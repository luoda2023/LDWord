"""Scene-owned document watermark status editor."""

from __future__ import annotations

from src.config.scene import SceneWorkspace
from src.qt_api import QLineEdit, Qt, QVBoxLayout, QWidget, Signal
from src.shared.ui.card import Card
from src.shared.ui.template_form_layout import template_form_row
from src.shared.ui.toggle_switch import ToggleSwitch


class SceneWatermarkRulesCard(QWidget):
    """Edit the business watermark switch/text owned by a scene."""

    scene_edited = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_scene: SceneWorkspace | None = None
        self._is_syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        card = Card(parent=self)
        card.set_header("文档水印", icon_name="shield-check")

        self._watermark_enabled = ToggleSwitch(self, checked=False)
        self._watermark_enabled.toggled_signal.connect(self._on_edited)
        self._watermark_text = QLineEdit(self)
        self._watermark_text.setPlaceholderText("例如：内部传阅")
        self._watermark_text.textChanged.connect(self._on_edited)
        card.add_widget(
            template_form_row(
                "启用文字水印",
                self._watermark_enabled,
                parent=card,
            )
        )
        card.add_widget(
            template_form_row("水印文本", self._watermark_text, parent=card)
        )
        layout.addWidget(card)

    def set_scene(self, scene: SceneWorkspace) -> None:
        self._current_scene = scene
        self._is_syncing = True
        try:
            self._watermark_enabled.setChecked(bool(scene.watermark.enabled))
            self._watermark_text.setText(str(scene.watermark.text or ""))
            self._sync_watermark_text_state()
        finally:
            self._is_syncing = False

    def _sync_watermark_text_state(self) -> None:
        enabled = self._watermark_enabled.isChecked()
        self._watermark_text.setEnabled(enabled)

    def _on_edited(self, *_args) -> None:
        self._sync_watermark_text_state()
        if self._is_syncing or self._current_scene is None:
            return
        self._current_scene.watermark.enabled = self._watermark_enabled.isChecked()
        self._current_scene.watermark.text = self._watermark_text.text()
        self.scene_edited.emit()

    def focus_navigation_field(self, field_id: str) -> bool:
        target = str(field_id or "").strip()
        controls = {
            "watermark": self._watermark_enabled,
            "watermark.enabled": self._watermark_enabled,
            "scene.watermark.enabled": self._watermark_enabled,
            "watermark.text": self._watermark_text,
            "scene.watermark.text": self._watermark_text,
        }
        control = controls.get(target)
        if control is None:
            return False
        control.setFocus(Qt.OtherFocusReason)
        return True


__all__ = ["SceneWatermarkRulesCard"]
