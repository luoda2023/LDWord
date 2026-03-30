# Task 3 Consistency Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep WorkbenchPanel consistently caching the last-known template and scene so bridge updates reuse the cached data, clean up the adapter, and add a regression test.

**Architecture:** WorkbenchPanel tracks `_current_template`/`_current_scene`, renders via `WorkbenchStrategyAdapter`, and proxies bridge signals. We'll update `set_strategy_summary` to update the caches before delegating to the adapter, remove the stray return, and add a regression test exercising the mixed manual/bridge path.

**Tech Stack:** Python 3.12, PySide6/PyQt, pytest.

---

### Task 1: Re-sync WorkbenchPanel summary cache

**Files:**
- Modify: `src/ui/panels/workbench/panel.py:23-37`

- [ ] Step 1: Update `WorkbenchPanel.set_strategy_summary` so it updates `_current_template` and `_current_scene` when a non-`None` value arrives, then always builds the summary from the cached values before delegating to the strategy card.

```python
    def set_strategy_summary(self, template: TemplateConfig | None, scene: SceneWorkspace | None) -> None:
        if template is not None:
            self._current_template = template
        if scene is not None:
            self._current_scene = scene
        state = self._strategy_adapter.build_summary(self._current_template, self._current_scene)
        self._strategy_card.set_state(state)
```

### Task 2: Remove duplicate return in the adapter

**Files:**
- Modify: `src/ui/adapters/workbench_strategy_adapter.py:21-34`

- [ ] Step 1: Ensure `build_summary` only returns once by deleting the dead `return state` at the end of the function so the final summary is produced from the single state instance.

### Task 3: Test the mixed manual + bridge update

**Files:**
- Modify: `tests/test_workbench_layout.py`

- [ ] Step 1: Add a regression test similar to this structure to prove the cached template survives a later bridge-only scene update.

```python
def test_workbench_panel_preserves_cached_template_when_bridge_updates_scene():
    _app()
    bridge = PanelBridge()
    panel = WorkbenchPanel(bridge)
    try:
        template = TemplateConfig(name="混合模板")
        scene = SceneWorkspace(
            name="初始场景",
            description="初始描述",
            category_label="初始分类",
            strict_mode=False,
        )
        for module_name in list(scene.module_switches.keys()):
            scene.module_switches[module_name] = False
        scene.module_switches["page_setup"] = True

        panel.set_strategy_summary(template, scene)

        updated_scene = SceneWorkspace(
            name="后续场景",
            description="后续描述",
            category_label="后续分类",
            strict_mode=True,
        )
        for module_name in list(updated_scene.module_switches.keys()):
            updated_scene.module_switches[module_name] = False
        updated_scene.module_switches["page_setup"] = True

        bridge.scene_changed.emit(updated_scene)

        assert panel._strategy_card._scene_value.text() == "后续描述"
        assert panel._strategy_card._template_value.text() == "混合模板"
        assert "1" in panel._strategy_card._modules_value.text()
    finally:
        panel.close()
```

### Task 4: Run targeted tests

**Files:**
- Test: `tests/test_workbench_strategy_card.py`, `tests/test_workbench_layout.py`

- [ ] Step 1: Run `pytest tests/test_workbench_strategy_card.py tests/test_workbench_layout.py -v` and expect both files to pass with the new test added.
