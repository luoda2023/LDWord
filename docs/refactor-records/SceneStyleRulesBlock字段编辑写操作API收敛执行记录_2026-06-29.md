# SceneStyleRulesBlock 字段编辑写操作 API 收敛执行记录

日期：2026-06-29

## 1. 本轮目标

前两轮已经把分区样式开关状态、导航高亮控件查找下沉到 `SceneStyleRulesBlock`。本轮继续处理 `_StyleRulesDetail` 对字段编辑器的直接写操作，把 `set_editable(...)` 和 `apply_to_style(...)` 也收进 block 语义 API。

目标是让 `_StyleRulesDetail` 更接近业务协调层：

```text
同步场景状态
计算投影
触发恢复 / 保存
通知 scene edited
```

而不是继续直接操作字段编辑器内部方法。

## 2. 原问题

改动前，`_StyleRulesDetail` 仍直接调用：

```python
self._section_style_editor.set_editable(enabled)
self._section_style_editor.apply_to_style(style)
```

这说明虽然字段控件和导航查找已经逐步下沉，但页面层仍知道“字段编辑器如何切换可编辑状态”和“字段编辑器如何写回 StyleConfig”。从模板管理一致性的角度看，这两个操作应该属于 `SceneStyleRulesBlock` 对外提供的样式规则对象能力。

## 3. 本轮代码变更

### 3.1 SceneStyleRulesBlock 增加字段编辑写操作 API

文件：`src/ui/panels/scene_style_rules_block.py`

新增：

```python
set_editor_editable(enabled: bool) -> None
apply_editor_to_style(style) -> None
```

这两个方法目前是薄转发：

- `set_editor_editable(...)` 调用 `self.editor.set_editable(...)`。
- `apply_editor_to_style(...)` 调用 `self.editor.apply_to_style(...)`。

它们的价值不是减少代码行，而是把“页面层直接碰字段编辑器”的边界收进 block。

### 3.2 _StyleRulesDetail 改为调用 block

文件：`src/ui/panels/scene_panel.py`

调整：

```python
self._style_rules_block.set_editor_editable(enabled)
self._style_rules_block.apply_editor_to_style(style)
```

保留 `_set_style_editor_enabled(...)` 和 `_on_style_editor_edited(...)` 的业务入口不变，避免影响当前信号链路。

## 4. 测试护栏

文件：`tests/test_scene_panel_architecture.py`

更新 `test_scene_style_rules_block_wraps_override_section_as_stable_object`：

- 调用 `block.set_editor_editable(False)` 后验证 `font_cn` 控件不可用。
- 调用 `block.set_editor_editable(True)` 后验证 `font_cn` 控件可用。
- 修改 `bold_switch` 后调用 `block.apply_editor_to_style(target_style)`，验证 `target_style.bold` 被写回。

更新 `test_scene_panel_controls_follow_template_management_contract`：

- 禁止 `scene_panel.py` 出现 `_section_style_editor.set_editable(...)`。
- 禁止 `scene_panel.py` 出现 `_section_style_editor.apply_to_style(...)`。
- 要求 `scene_panel.py` 使用 `set_editor_editable(...)`。
- 要求 `scene_panel.py` 使用 `apply_editor_to_style(...)`。
- 要求 `scene_style_rules_block.py` 暴露这两个 API。

## 5. 验证结果

目标测试：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py::test_scene_style_rules_block_wraps_override_section_as_stable_object tests\test_scene_panel_architecture.py::test_scene_panel_controls_follow_template_management_contract tests\test_scene_panel_architecture.py::test_scene_panel_scope_style_override_editor_writes_section_styles tests\test_scene_panel_architecture.py::test_scene_panel_restore_all_section_styles_returns_every_partition_to_template -q
```

结果：

```text
4 passed in 37.38s
```

完整场景面板架构测试：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py -q
```

结果：

```text
58 passed in 257.28s (0:04:17)
```

布局守门测试：

```powershell
python -X utf8 -m pytest tests\test_ui_layout_hardening.py::test_template_and_scene_style_shells_keep_summary_preview_surface_order tests\test_ui_layout_hardening.py::test_scene_style_management_block_collapses_readonly_surface -q
```

结果：

```text
2 passed in 1.21s
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
  判断何时可编辑
  判断何时写回 style
  调用 block API

SceneStyleRulesBlock
  切换字段编辑器可编辑状态
  把当前字段控件值写回 StyleConfig

ParagraphStyleEditor
  执行真实字段控件同步
```

这让 `SceneStyleRulesBlock` 更接近完整对象区，而不只是 `SceneStyleOverrideSection` 的简单包装。

## 7. 后续继续执行点

下一轮可以继续减少兼容字段：

- `_section_font_cn`
- `_section_font_en`
- `_section_size_combo`
- `_section_bold_switch`
- `_section_line_value`
- `_section_space_before`
- `_section_space_after`

这些字段现在主要服务测试和导航断言。更好的方向是：

```text
测试面向 SceneStyleRulesBlock 的公开 API
页面层不暴露 paragraph editor 内部字段
```

同时可以考虑让 `SceneStyleRulesBlock` 承接更多同步入口，例如：

- `set_current_scene_style_state(...)`
- `apply_preview_and_owner_state(...)`
- `sync_variant_rows(...)`

但这些会牵涉业务投影，建议分小步继续。

## 8. 本轮结论

本轮没有改变用户可见行为，但继续把场景分区样式从“页面层操作字段编辑器”推进到“页面层调用对象区 API”。这对后续删除冗余文案、重排功能区、和模板管理保持一致非常重要。
