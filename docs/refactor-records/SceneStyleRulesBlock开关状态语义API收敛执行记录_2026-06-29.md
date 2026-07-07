# SceneStyleRulesBlock 开关状态语义 API 收敛执行记录

日期：2026-06-29

## 1. 本轮目标

上一轮已经新增 `SceneStyleRulesBlock`，让场景页不再直接持有 `SceneStyleOverrideSection`。本轮继续收窄边界：把 `_StyleRulesDetail` 里对底层 `ToggleSwitch` 几何细节的直接操作，下沉到 `SceneStyleRulesBlock`。

目标是让页面层只表达业务意图：

```text
把某个分区的独立样式开关设为开 / 关
```

而不是继续知道：

```text
TRACK_W
THUMB_D
THUMB_MARGIN
thumb_position
```

这些属于开关控件的视觉实现，不应该出现在场景业务页。

## 2. 原问题

改动前，`_StyleRulesDetail._set_variant_toggle_checked(...)` 会直接操作：

```python
toggle.setChecked(bool(checked))
target = (
    toggle.TRACK_W - toggle.THUMB_D - toggle.THUMB_MARGIN
    if checked
    else toggle.THUMB_MARGIN
)
toggle.thumb_position = float(target)
toggle.update()
```

这带来两个问题：

- 场景页知道 `ToggleSwitch` 的绘制常量，边界不清。
- 后续如果开关控件内部尺寸或动画实现改变，场景页也会被迫跟着改。

从模板管理一致性的角度看，这属于页面层过度了解控件实现。模板管理页应管理对象和状态，控件细节应被共享控件或对象 block 吸收。

## 3. 本轮代码变更

### 3.1 SceneStyleRulesBlock 增加语义 API

文件：`src/ui/panels/scene_style_rules_block.py`

新增：

```python
set_override_checked(variant_key: str, checked: bool) -> bool
```

职责：

- 根据 `variant_key` 找到对应独立样式开关。
- 设置 checked 状态。
- 同步开关 thumb 的视觉位置。
- 找不到开关时返回 `False`。

这样 `_StyleRulesDetail` 不需要知道开关的内部尺寸常量。

### 3.2 _StyleRulesDetail 改为调用语义 API

文件：`src/ui/panels/scene_panel.py`

调整：

- `set_scene(...)` 中不再先取 `toggle` 再判断。
- `_set_variant_toggle_checked(...)` 改为：

```python
self._style_rules_block.set_override_checked(variant_key, checked)
```

页面层仍然保留 `_set_variant_toggle_checked(...)` 这个业务方法，是为了让恢复当前分区、全部跟随模板、撤销恢复等流程不发生行为变化。

## 4. 测试护栏

文件：`tests/test_scene_panel_architecture.py`

更新 `test_scene_style_rules_block_wraps_override_section_as_stable_object`：

- 验证 `block.set_override_checked("references_body", True)` 返回 `True`。
- 验证 checked 状态变为 `True`。
- 验证 thumb 位置同步到打开位置。
- 验证设回 `False` 后 thumb 回到关闭位置。
- 验证未知 key 返回 `False`。

更新 `test_scene_panel_controls_follow_template_management_contract`：

- `scene_panel.py` 中不能出现 `TRACK_W`。
- `scene_panel.py` 中不能出现 `THUMB_D`。
- `scene_panel.py` 中不能出现 `thumb_position`。
- `scene_panel.py` 必须通过 `set_override_checked(...)` 进入 block API。

这把“页面层不得操作开关几何细节”变成测试契约。

## 5. 验证结果

目标交互测试：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py::test_scene_style_rules_block_wraps_override_section_as_stable_object tests\test_scene_panel_architecture.py::test_scene_panel_controls_follow_template_management_contract tests\test_scene_panel_architecture.py::test_scene_panel_scope_style_override_editor_writes_section_styles tests\test_scene_panel_architecture.py::test_scene_panel_restore_all_section_styles_returns_every_partition_to_template -q
```

结果：

```text
4 passed in 37.20s
```

完整场景面板架构测试：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py -q
```

结果：

```text
58 passed in 256.95s (0:04:16)
```

布局守门测试：

```powershell
python -X utf8 -m pytest tests\test_ui_layout_hardening.py::test_template_and_scene_style_shells_keep_summary_preview_surface_order tests\test_ui_layout_hardening.py::test_scene_style_management_block_collapses_readonly_surface -q
```

结果：

```text
2 passed in 1.28s
```

补充检查：

```powershell
git diff --check -- src\ui\panels\scene_style_rules_block.py src\ui\panels\scene_panel.py tests\test_scene_panel_architecture.py
```

结果：

```text
无空白错误；仅有 Windows 行尾提示。
```

## 6. 当前边界变化

本轮之后：

```text
_StyleRulesDetail
  说：references_body 的独立样式开关应为 True / False

SceneStyleRulesBlock
  做：找到开关，设置 checked，同步 thumb 位置

ToggleSwitch
  管：绘制开关本身
```

这比之前更符合模板管理的复用原则：页面层表达业务状态，共享对象区处理控件状态，原子控件处理视觉实现。

## 7. 后续继续执行点

下一轮可以继续收窄：

1. 把 `focus_navigation_field(...)` 中的 `self._variant_toggles.get(...)` 下沉为 `SceneStyleRulesBlock.override_toggle_for_variant(...)` 或 `highlight_target_for_field(...)`。
2. 把 `self._section_style_editor.widget_for_field(...)` 下沉为 `SceneStyleRulesBlock.editor_widget_for_field(...)`。
3. 把 `_section_style_editor.apply_to_style(...)` 改成 block 级 API，例如 `apply_editor_to_style(style)`。

这样 `_StyleRulesDetail` 会逐步只关心场景业务和样式投影，不再知道内部控件树。

## 8. 本轮结论

本轮没有改变视觉，但继续把场景页从“知道控件实现”推向“调用对象区语义 API”。这是一小步，但方向正确：`SceneStyleRulesBlock` 正在从简单包装层变成真正的场景样式规则对象区。
