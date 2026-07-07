# SceneStyleRulesBlock 导航目标语义 API 收敛执行记录

日期：2026-06-29

## 1. 本轮目标

上一轮已经把分区样式开关的 checked/视觉 thumb 同步下沉到 `SceneStyleRulesBlock.set_override_checked(...)`。本轮继续收窄 `_StyleRulesDetail` 对内部控件树的认知，把导航高亮需要的 widget 查找也下沉到 `SceneStyleRulesBlock`。

目标是让 `_StyleRulesDetail` 保持业务语义：

```text
当前导航目标属于哪个分区、哪个字段
```

而不是直接访问：

```text
_variant_toggles.get(...)
_section_style_editor.widget_for_field(...)
```

## 2. 原问题

改动前，`_StyleRulesDetail.focus_navigation_field(...)` 里直接做了两类控件查找：

```python
toggle = self._variant_toggles.get(variant_key)
widget = self._section_style_editor.widget_for_field(editor_field)
```

这让页面层继续知道：

- 独立样式开关存放在 `_variant_toggles` 字典里。
- 字段控件来自 `_section_style_editor.widget_for_field(...)`。
- 当分区没有开启独立样式时，应该高亮开关而不是字段。

这些判断和 `SceneStyleRulesBlock` 的对象边界更接近，不应该散在场景页面层。

## 3. 本轮代码变更

### 3.1 SceneStyleRulesBlock 增加导航辅助 API

文件：`src/ui/panels/scene_style_rules_block.py`

新增：

```python
has_variant(variant_key: str) -> bool
override_toggle_for_variant(variant_key: str) -> QWidget | None
editor_widget_for_field(field_id: str) -> QWidget | None
navigation_widget_for_field(
    field_id: str,
    *,
    variant_key: str = "",
    prefer_toggle: bool = False,
    prefer_toggle_when_unchecked: bool = False,
) -> QWidget | None
```

这些 API 的职责：

- 由 block 判断某个分区 key 是否存在。
- 由 block 找到对应开关。
- 由 block 找到字段编辑控件。
- 由 block 根据“优先高亮开关”或“未开启时高亮开关”的规则返回最终高亮 widget。

### 3.2 _StyleRulesDetail 改为调用 block

文件：`src/ui/panels/scene_panel.py`

调整：

- `focus_navigation_field(...)` 不再直接调用 `_variant_toggles.get(...)`。
- `focus_navigation_field(...)` 不再直接调用 `_section_style_editor.widget_for_field(...)`。
- `_style_navigation_target(...)` 不再通过 `_variant_toggles` 判断分区是否存在，而是调用：

```python
self._style_rules_block.has_variant(parts[0])
```

现在页面层仍负责：

- 解析字段 ID。
- 同步当前编辑分区。
- 判断当前场景是否已开启独立样式。
- 调用 `_highlight_navigation_widget(...)`。

但控件树查找已经由 `SceneStyleRulesBlock` 接管。

## 4. 测试护栏

文件：`tests/test_scene_panel_architecture.py`

更新 `test_scene_style_rules_block_wraps_override_section_as_stable_object`：

- 验证 `has_variant(...)`。
- 验证 `override_toggle_for_variant(...)`。
- 验证 `editor_widget_for_field(...)`。
- 验证 `navigation_widget_for_field(...)` 在不同偏好下返回开关或字段控件。

更新 `test_scene_panel_controls_follow_template_management_contract`：

- 禁止 `scene_panel.py` 出现 `_variant_toggles.get`。
- 禁止 `scene_panel.py` 直接调用 `_section_style_editor.widget_for_field(...)`。
- 要求 `scene_panel.py` 使用 `navigation_widget_for_field(...)`。
- 要求 `scene_panel.py` 使用 `editor_widget_for_field(...)`。
- 要求 `scene_panel.py` 使用 `has_variant(...)`。

这把“页面层不直接查内部控件树”变成了结构测试。

## 5. 验证结果

目标测试：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py::test_scene_style_rules_block_wraps_override_section_as_stable_object tests\test_scene_panel_architecture.py::test_scene_panel_controls_follow_template_management_contract tests\test_scene_panel_architecture.py::test_scene_panel_scope_style_override_editor_writes_section_styles tests\test_scene_panel_architecture.py::test_scene_panel_restore_all_section_styles_returns_every_partition_to_template -q
```

结果：

```text
4 passed in 37.47s
```

完整场景面板架构测试：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py -q
```

结果：

```text
58 passed in 257.02s (0:04:17)
```

布局守门测试：

```powershell
python -X utf8 -m pytest tests\test_ui_layout_hardening.py::test_template_and_scene_style_shells_keep_summary_preview_surface_order tests\test_ui_layout_hardening.py::test_scene_style_management_block_collapses_readonly_surface -q
```

结果：

```text
2 passed in 1.22s
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
  解析导航字段
  判断当前场景状态
  调用 block 获取应该高亮的 widget

SceneStyleRulesBlock
  知道分区开关在哪里
  知道字段编辑控件在哪里
  根据偏好返回最终导航目标

StyleEditingSection / ParagraphStyleEditor
  继续负责字段控件本身
```

这比上一轮更进一步：`_StyleRulesDetail` 不再直接查询控件树，而是调用对象区的语义 API。

## 7. 后续继续执行点

下一轮可以继续收窄编辑应用逻辑：

- 把 `_section_style_editor.set_editable(...)` 下沉为 `SceneStyleRulesBlock.set_editor_editable(...)`。
- 把 `_section_style_editor.apply_to_style(style)` 下沉为 `SceneStyleRulesBlock.apply_editor_to_style(style)`。
- 逐步减少 `_StyleRulesDetail` 中保留的兼容字段，例如 `_section_font_cn`、`_section_line_value` 等。

中期目标：

```text
_StyleRulesDetail
  只处理 scene/template/projection/action

SceneStyleRulesBlock
  处理所有 UI 控件定位、状态同步和字段表面入口
```

## 8. 本轮结论

本轮继续把场景样式规则从“页面知道控件树”推进为“页面调用对象区语义 API”。这有助于后续删除冗余文本、重排页面结构时不再破坏模板管理与场景样式规则的一致性。
