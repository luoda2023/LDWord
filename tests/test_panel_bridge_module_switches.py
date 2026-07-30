from __future__ import annotations

from src.config.scene import SceneWorkspace
from src.ui.bridge import PanelBridge


def test_bridge_module_switch_update_is_copy_on_write_and_emits_once():
    bridge = PanelBridge()
    original = SceneWorkspace(scene_id="custom")
    bridge.set_current_scene(original, emit_signal=False)
    scenes = []
    dirty_states = []
    bridge.scene_changed.connect(scenes.append)
    bridge.scene_dirty_changed.connect(dirty_states.append)

    assert bridge.update_current_scene_module_switches({"page_setup": False}) is True

    updated = bridge.current_scene()
    assert updated is not original
    assert original.module_switches["page_setup"] is True
    assert updated.module_switches["page_setup"] is False
    assert scenes == [updated]
    assert dirty_states == [True]


def test_bridge_module_switch_noop_does_not_emit_or_dirty_scene():
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom")
    bridge.set_current_scene(scene, emit_signal=False)
    scenes = []
    bridge.scene_changed.connect(scenes.append)

    assert bridge.update_current_scene_module_switches(
        {"page_setup": scene.module_switches["page_setup"]}
    ) is False
    assert bridge.current_scene() is scene
    assert bridge.is_scene_dirty() is False
    assert scenes == []


def test_bridge_preserves_requested_state_for_dependency_selection():
    bridge = PanelBridge()
    scene = SceneWorkspace(scene_id="custom")
    scene.module_switches["heading_recognition"] = False
    scene.module_switches["toc"] = False
    bridge.set_current_scene(scene, emit_signal=False)

    bridge.update_current_scene_module_switches({"toc": True})

    assert bridge.current_scene().module_switches["toc"] is True
