# StyleDifferenceSummarySlot 差异摘要边界执行记录

日期：2026-06-29

## 1. 本轮结论

模板预览和 Workbench 样式回执已经分别进入：

```text
preview_slot
receipt_slot
StyleReceiptSlotFrame
```

但“相对模板改了什么”仍然只有 `StyleComparisonStrip` 这一条 UI 呈现，语义上还附着在 `rules` 里。用户看到的是同一行对比，但工程边界不够清楚：

```text
rules：是否启用独立样式、是否全部跟随模板
difference：模板基线、当前分区、字段差异
preview：段落最终效果
```

本轮新增无卡片差异摘要槽位：

```text
StyleDifferenceSummarySlot
```

并把 `scene_section_rules` 的内容计划从：

```text
source|scope|rules|editor|preview
```

升级为：

```text
source|scope|rules|difference|editor|preview
```

这让“规则控制”和“差异摘要”在内容边界上分开，但不增加额外解释文本，也不改变原有对比条的用户阅读方式。

## 2. 当前差异链路

已有数据层：

```text
src/config/style_difference_projection.py
  StyleDifferenceProjection
  build_style_difference_projection(...)
  build_scene_style_difference_projections(...)
```

已有展示层：

```text
src/shared/ui/style_comparison_strip.py
  StyleComparisonStrip
```

已有真实页面：

```text
SceneStyleOverrideSection
  StyleRuleControlDeck
    StyleComparisonStrip
```

问题是 `StyleComparisonStrip` 更像一个 UI 零件，不像一个可被场景页、Workbench、报告共同识别的“差异摘要板块”。本轮的 `StyleDifferenceSummarySlot` 就是给它补上这层语义。

## 3. 代码落点

### 3.1 新增差异摘要 slot

文件：

```text
src/shared/ui/style_difference_summary_slot.py
```

新增：

```text
StyleDifferenceSummarySlot
```

它内部仍然使用：

```text
StyleComparisonStrip
```

暴露属性：

```text
style_difference_content_plan = difference
style_difference_slot_surface = embedded
style_difference_has_projection
style_difference_template_status
style_difference_current_status
style_difference_status
style_difference_detail
```

含义：

```text
StyleComparisonStrip 负责画出来。
StyleDifferenceSummarySlot 负责声明“这是差异摘要”。
```

### 3.2 StyleRuleControlDeck 接入

文件：

```text
src/shared/ui/style_rule_control_deck.py
```

原结构：

```text
toggle_list
comparison_strip
restore_all / undo_restore_all
```

新结构：

```text
toggle_list
difference_slot
  comparison_strip
restore_all / undo_restore_all
```

对外仍保留：

```text
deck.comparison_strip
```

避免破坏已有测试和调用。同时新增：

```text
deck.difference_slot
```

### 3.3 SceneStyleOverrideSection 暴露 difference_slot

文件：

```text
src/ui/panels/scene_style_override_sections.py
```

新增：

```text
section.difference_slot
```

它指向：

```text
section.rule_control_deck.difference_slot
```

### 3.4 StyleManagementContentPlan 新增 difference

文件：

```text
src/shared/ui/style_management_block.py
```

`StyleManagementContentPlan` 新增字段：

```text
difference: bool = False
```

`scene_section_rules` 当前计划：

```text
source=True
scope=True
rules=True
difference=True
editor=True
preview=True
receipt=False
```

最终编码：

```text
source|scope|rules|difference|editor|preview
```

## 4. 用户体验含义

本轮没有新增长说明文字。页面上的对比条仍然是：

```text
模板基线：...
当前分区：...
差异：...
```

但内部不再把这条信息当作 `rules` 的附属内容。新的边界是：

| 板块 | 用户问题 | 组件 |
| --- | --- | --- |
| rules | 哪些分区要独立设置，是否全部恢复模板 | `StyleRuleControlDeck` / `StyleOverrideToggleList` |
| difference | 当前分区相对模板改了什么 | `StyleDifferenceSummarySlot` |
| preview | 最终段落效果是什么样 | `StylePreview` |

这比继续加“说明文字”更清楚，也更利于后续 Workbench 复核和执行后报告复用。

## 5. 新增与更新测试

### 5.1 共享小组件

文件：

```text
tests/test_small_widget_architecture.py
```

新增：

```text
test_style_difference_summary_slot_wraps_comparison_strip_with_semantic_role
```

验证：

```text
slot.content_plan == difference
slot.surface == embedded
apply_projection 后同步 template/current/difference/detail 属性
comparison_strip 仍正常显示
```

更新：

```text
test_style_rule_control_deck_groups_toggles_comparison_and_batch_actions
```

验证：

```text
deck.difference_slot 存在
deck.difference_slot.comparison_strip is deck.comparison_strip
```

### 5.2 共享内容计划

文件：

```text
tests/test_small_widget_architecture.py
```

更新：

```text
style_management_content_plan("scene_section_rules").sections()
```

从：

```text
source|scope|rules|editor|preview
```

改为：

```text
source|scope|rules|difference|editor|preview
```

### 5.3 真实场景页面

文件：

```text
tests/test_scene_panel_architecture.py
```

新增/更新断言：

```text
style_management_content_plan == source|scope|rules|difference|editor|preview
style_management_has_difference is True
section.difference_slot is section.rule_control_deck.difference_slot
style_difference_content_plan == difference
```

### 5.4 导出

文件：

```text
tests/test_ui_exports.py
```

新增：

```text
StyleDifferenceSummarySlot
```

## 6. 验证

已执行精确回归：

```powershell
python -X utf8 -m py_compile src/shared/ui/style_difference_summary_slot.py src/shared/ui/style_rule_control_deck.py src/shared/ui/style_management_block.py src/shared/ui/__init__.py src/ui/panels/scene_style_override_sections.py tests/test_small_widget_architecture.py tests/test_scene_panel_architecture.py tests/test_ui_exports.py
python -X utf8 -m pytest tests/test_small_widget_architecture.py::test_style_difference_summary_slot_wraps_comparison_strip_with_semantic_role tests/test_small_widget_architecture.py::test_style_rule_control_deck_groups_toggles_comparison_and_batch_actions tests/test_small_widget_architecture.py::test_style_management_block_named_modes_project_shared_contracts tests/test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface tests/test_ui_exports.py::test_shared_ui_exports_include_unified_controls -q
```

结果：

```text
5 passed in 2.47s
```

## 7. 当前链路状态

| 链路 | 状态 |
| --- | --- |
| 模板正文编辑 | `source|scope|editor` |
| 场景分区样式 | `source|scope|rules|difference|editor|preview` |
| 模板概览页面级预览 | `preview` |
| Workbench 执行中心样式回执 | `receipt` |
| Workbench 最近结果样式回执 | `receipt` |

## 8. 下一步

下一轮可以把 `StyleDifferenceSummarySlot` 推到 Workbench 执行前复核或执行后报告：

1. Workbench 执行前：显示将应用哪些分区差异。
2. Workbench 执行后：回执实际使用了哪些分区差异。
3. 报告 JSON/Markdown：继续复用 `StyleDifferenceProjection`，避免 UI 和报告各写一套差异摘要。
