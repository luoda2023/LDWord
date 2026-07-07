# SceneStyleDifferenceSlot 显式登记执行记录

日期：2026-06-29

## 1. 本轮目标

上一轮已经给 `StyleManagementBlock` 增加了：

```text
source_slot
scope_slot
difference_slot
preview_slot
receipt_slot
```

并把 Workbench 执行前迁入：

```text
StyleManagementBlock(mode="execution_prereview")
```

但场景分区样式还留着一个语义缺口：

```text
StyleDifferenceSummarySlot 已经存在于 StyleRuleControlDeck 内部，
用户也能看到差异摘要，
但 StyleManagementBlock 并不知道真实 difference_slot 是哪一个。
```

这会让 `scene_section_rules` 的内容计划仍有一点“声明强于证据”的味道：

```text
content_plan = source|scope|rules|difference|editor|preview
```

其中 `difference=True`，但 `style_management_has_difference_slot=False`。

本轮目标是把场景分区样式也接入真实 `difference_slot` 契约。

## 2. 关键实现

### 2.1 StyleManagementBlock 支持嵌套 slot 登记

文件：

```text
src/shared/ui/style_management_block.py
```

新增逻辑：

```text
如果 difference_slot 已经是 rule_control 的子孙控件，
StyleManagementBlock 只登记它，不重新 add_widget。
```

原因：

```text
StyleRuleControlDeck 内部结构是：

toggle_list
-> difference_slot
-> restore / undo actions
```

如果 `StyleManagementBlock` 再把 `difference_slot` 直接 add 到 card，
Qt 会把它从 `StyleRuleControlDeck` 里 reparent 出来，破坏 deck 内部布局。
```

因此新增：

```python
_slot_is_descendant_of(widget, ancestor)
```

用于区分：

| 情况 | 行为 |
| --- | --- |
| 独立 slot | add 到 `DetailSummaryCard` |
| 已嵌套在 rule_control 内 | 只登记，不重排 |

### 2.2 SceneStyleOverrideSection 显式传入 difference_slot

文件：

```text
src/ui/panels/scene_style_override_sections.py
```

更新：

```python
StyleManagementBlock(
    ...,
    rule_control=self._rule_control_deck,
    difference_slot=self._rule_control_deck.difference_slot,
)
```

这让真实场景分区页面满足：

```text
section.management_block.difference_slot is section.rule_control_deck.difference_slot
```

同时保持：

```text
section.difference_slot.parentWidget() is section.rule_control_deck
```

也就是说，block 知道这个 slot，deck 仍然拥有这个 slot。

## 3. 用户体验影响

本轮不改变用户可见界面。

用户仍看到：

```text
独立样式开关
模板基线 / 当前分区 / 差异摘要
全部跟随模板 / 撤销恢复
字段编辑
段落预览
```

变化在工程边界：

```text
差异摘要不再只是 RuleControlDeck 里的内部控件，
而是 StyleManagementBlock 能识别的 difference slot。
```

这为后续统一模板管理、场景配置、Workbench 复核和执行回执提供更强的运行时证据。

## 4. 测试更新

### 4.1 小组件测试

文件：

```text
tests/test_small_widget_architecture.py
```

更新：

```text
test_style_management_block_named_modes_project_shared_contracts
```

新增断言：

- `scene_block.difference_slot is rule_deck.difference_slot`
- `style_management_has_difference_slot is True`
- `rule_deck.difference_slot.parentWidget() is rule_deck`

这证明 `StyleManagementBlock` 能登记嵌套 slot，但不会把它重排出 `StyleRuleControlDeck`。

### 4.2 场景面板架构测试

文件：

```text
tests/test_scene_panel_architecture.py
```

更新：

```text
test_scene_panel_uses_shared_card_header_and_flow_scope_layout
test_scene_style_override_section_wraps_owner_preview_and_surface
```

新增断言：

- 源码包含 `difference_slot=self._rule_control_deck.difference_slot`
- `section.management_block.difference_slot is section.difference_slot`
- `style_management_has_difference_slot is True`
- `section.difference_slot.parentWidget() is section.rule_control_deck`

## 5. 已运行验证

语法检查：

```powershell
python -X utf8 -m py_compile src\shared\ui\style_management_block.py src\ui\panels\scene_style_override_sections.py tests\test_small_widget_architecture.py tests\test_scene_panel_architecture.py
```

结果：通过。

焦点回归：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_management_block_named_modes_project_shared_contracts tests\test_small_widget_architecture.py::test_style_management_block_named_slots_update_plan tests\test_scene_panel_architecture.py::test_scene_panel_uses_shared_card_header_and_flow_scope_layout tests\test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface -q
```

结果：

```text
4 passed
```

## 6. 当前链路状态

| 阶段 | difference slot 状态 |
| --- | --- |
| 场景分区样式 | 已显式登记，slot 嵌套在 `StyleRuleControlDeck` 内 |
| Workbench 执行前复核 | 已显式挂入 `StyleManagementBlock(execution_prereview)` |
| Workbench 执行后回执 | 目前仍以 receipt 为主，difference slot 尚未闭合 |

## 7. 下一步

继续推进：

1. 给执行后回执补可选 `difference_slot`，让执行前差异摘要和执行后实际回执闭环。
2. 评估是否需要独立 `StyleScopeSummarySlot`，把 source/scope 从 `StyleSourceCompactRow` 中拆开。
3. 继续清理主界面冗余文案和内部 key。

## 8. 本轮判断

这轮是一次边界补强。

之前是：

```text
看得见 difference，但 block 不知道 difference slot。
```

现在是：

```text
看得见 difference，block 也能登记真实 difference slot。
```

这让 `StyleManagementContentPlan` 从“声明有哪些板块”继续接近“每个板块都有真实 slot 证据”。
