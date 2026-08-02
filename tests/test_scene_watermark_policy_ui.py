from src.config.scene import SceneWorkspace
from src.qt_api import QApplication
from src.ui.panels.scene_watermark_rules import SceneWatermarkRulesCard


def _app():
    return QApplication.instance() or QApplication([])


def test_scene_watermark_card_preserves_text_while_disabled_and_updates_scene():
    _app()
    scene = SceneWorkspace()
    scene.watermark.enabled = False
    scene.watermark.text = "内部传阅"
    card = SceneWatermarkRulesCard()
    try:
        card.set_scene(scene)

        assert card._watermark_enabled.isChecked() is False
        assert card._watermark_text.text() == "内部传阅"
        assert card._watermark_text.isEnabled() is False

        card._watermark_enabled.click()
        card._watermark_text.setText("审阅版本")

        assert card._watermark_text.isEnabled() is True
        assert scene.watermark.enabled is True
        assert scene.watermark.text == "审阅版本"

        card._watermark_enabled.click()

        assert scene.watermark.enabled is False
        assert scene.watermark.text == "审阅版本"
        assert card._watermark_text.isEnabled() is False
    finally:
        card.close()


def test_scene_watermark_card_exposes_navigation_targets():
    _app()
    card = SceneWatermarkRulesCard()
    try:
        card.set_scene(SceneWorkspace())

        assert card.focus_navigation_field("scene.watermark.enabled") is True
        assert card.focus_navigation_field("scene.watermark.text") is True
        assert card.focus_navigation_field("unknown") is False
    finally:
        card.close()
