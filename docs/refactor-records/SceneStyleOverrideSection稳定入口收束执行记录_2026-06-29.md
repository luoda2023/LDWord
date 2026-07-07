# SceneStyleOverrideSection 稳定入口收束执行记录

日期：2026-06-29

## 1. 本轮目标

上一轮已经把 `StyleManagementBlock` 的规则控制区从自由 `management_widgets` 收束为命名 slot：

```text
StyleManagementBlock(rule_control=StyleRuleControlDeck)
```

但场景分区样式仍有一个历史问题：`SceneStyleOverrideSection` 暴露了大量字段级兼容属性，例如：

- `toggle_list`
- `toggles`
- `rows`
- `comparison_strip`
- `owner_toolbar`
- `selector`
- `preview`
- `style_surface`
- `editor`
- `unit_labels`

这些属性短期方便测试和旧调用，但会让外部把 `SceneStyleOverrideSection` 当成“控件仓库”，而不是一个稳定的样式管理组合块。

本轮目标不是一次性删除旧属性，而是先建立三个稳定入口，并把真实调用和测试重心迁过去：

```text
management_block
rule_control_deck
editing_section
```

## 2. 本轮代码落点

### 2.1 新增 management_block 公开入口

文件：

- `src/ui/panels/scene_style_override_sections.py`

新增：

```python
@property
def management_block(self) -> StyleManagementBlock:
    return self._style_management_block
```

意义：

外部需要摘要卡、摘要网格、mode、规则控制 slot 时，不再读取私有 `_style_management_block`。

### 2.2 _StyleRulesDetail 改为从稳定入口取值

文件：

- `src/ui/panels/scene_panel.py`

变更前，初始化时直接从 section 拆字段级兼容属性：

```python
self._style_override_toggle_list = self._style_override_section.toggle_list
self._variant_toggles = self._style_override_section.toggles
self._style_owner_toolbar = self._style_override_section.owner_toolbar
self._style_variant_combo = self._style_override_section.selector
self._style_surface = self._style_override_section.style_surface
self._section_style_editor = self._style_override_section.editor
```

变更后，先取得稳定组合对象：

```python
management_block = self._style_override_section.management_block
rule_deck = self._style_override_section.rule_control_deck
editing_section = self._style_override_section.editing_section
```

再从稳定对象取值：

```python
self._style_override_summary = management_block.summary
self._variant_toggles = rule_deck.toggles
self._style_owner_toolbar = editing_section.owner_toolbar
self._style_variant_combo = editing_section.selector
self._style_surface = editing_section.style_surface
self._section_style_editor = editing_section.editor
```

这一步没有删除 `_StyleRulesDetail` 里的旧别名。原因是这些别名仍被当前类的后续方法使用，直接删除会放大改动面。本轮先迁移来源，降低字段级出口继续扩散的风险。

## 3. 测试守门

更新文件：

- `tests/test_scene_panel_architecture.py`
- `tests/test_ui_layout_hardening.py`

新增/调整验证点：

- `section.management_block.property("style_management_mode") == "scene_section_rules"`。
- `section.management_block.rule_control is section.rule_control_deck`。
- `scene_panel.py` 必须出现：
  - `management_block = self._style_override_section.management_block`
  - `rule_deck = self._style_override_section.rule_control_deck`
  - `editing_section = self._style_override_section.editing_section`
- `scene_panel.py` 不应再出现：
  - `self._style_override_section.toggle_list`
  - `self._style_override_section.editor`
  - `self._style_override_section.style_surface`
- 布局测试改为通过 `editing_section` 和 `rule_control_deck` 做几何断言。

## 4. 已验证

语法检查：

```powershell
python -X utf8 -m py_compile src/ui/panels/scene_style_override_sections.py src/ui/panels/scene_panel.py tests/test_scene_panel_architecture.py tests/test_ui_layout_hardening.py
```

结果：通过。

焦点回归：

```powershell
python -X utf8 -m pytest tests/test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface tests/test_scene_panel_architecture.py::test_scene_panel_controls_follow_template_management_contract tests/test_ui_layout_hardening.py::test_template_and_scene_style_shells_keep_summary_preview_surface_order tests/test_ui_layout_hardening.py::test_scene_style_management_block_collapses_readonly_surface -q
```

结果：

```text
4 passed
```

宽回归：

```powershell
python -X utf8 -m pytest tests/test_scene_panel_architecture.py tests/test_ui_layout_hardening.py tests/test_small_widget_architecture.py tests/test_template_style_detail.py -q
```

结果：

```text
138 passed
```

## 5. 当前边界

本轮仍保留 `SceneStyleOverrideSection` 的字段级兼容属性。原因：

- 旧测试和调试代码仍可能直接读取这些属性。
- 真实业务类 `_StyleRulesDetail` 内部仍保留旧别名，用于降低一次性改动风险。
- 直接删除会把风险扩散到布局测试、场景面板行为测试和历史兼容路径。

但新规则已经明确：

```text
新业务调用优先使用 management_block / rule_control_deck / editing_section。
字段级属性只作为兼容层保留，不再作为主访问路径。
```

## 6. 后续建议

下一步可以继续推进：

1. 把 `_StyleRulesDetail` 内部旧别名按能力分组，例如 `_style_rules_controls`、`_style_rules_editor`。
2. 给 `SceneStyleOverrideSection` 的字段级属性加“compat”注释或迁移测试，减少新代码误用。
3. 当测试和业务调用都不再依赖字段级属性后，再逐步删除 `toggle_list`、`editor`、`style_surface` 等兼容出口。

## 7. 本轮判断

这轮不改变用户可见界面，但它继续把分区样式从“很多控件堆在一起”推进为“稳定组合块”。

现在场景分区样式的内部依赖关系更清楚：

```text
SceneStyleOverrideSection
-> management_block: 摘要、mode、样式管理结构
-> rule_control_deck: 独立样式开关、差异、批量动作
-> editing_section: owner、预览、字段表单
```

这能让后续删除冗余文本、统一预览 envelope、继续和模板管理保持一致时，不再被一堆字段级兼容出口拖住。
