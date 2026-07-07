# Workbench 执行前样式策略开关主路径移除执行记录

日期：2026-06-30

## 1. 结论

本轮按用户指出的统一设计问题继续处理：快速执行页“场景与模板”主路径不再放置只读的“独立样式”策略开关列表。

这次不是隐藏，而是从 Workbench 快速执行页的执行前复核链路中移除 `StylePolicyControlDeck`。保留的信息是：

```text
样式来源摘要
看模板
调分区
差异摘要
样式预览
```

移除的信息是：

```text
独立样式开关列表
撤销恢复
禁用态分区 toggle
点击策略行切换预览
```

原因：

- 快速执行页是“本次运行复核”，不是场景分区样式编辑页。
- 禁用 toggle 看起来像可操作控件，实际不能操作，会造成误导。
- “撤销恢复”属于场景分区样式编辑行为，不属于执行前主路径。
- 用户需要修改时，应通过“调分区”进入场景分区样式页。

## 2. 代码改动

### 2.1 快速执行页

文件：`src/ui/panels/workbench/quick_execution_detail.py`

已删除：

- `StylePolicyControlDeck` 导入。
- `_style_prereview_policy_deck` 创建。
- `policy_selected.connect(...)`。
- `rule_control=self._style_prereview_policy_deck`。
- `_style_prereview_policy_deck.set_current_policy_key(...)`。
- `_on_style_policy_selected(...)`。

保留：

- `_style_prereview_source_slot`
- `_style_difference_slot`
- `_style_prereview_preview_slot`
- `_style_prereview_preview`
- `_scene_card = StyleManagementBlock(mode="execution_prereview")`

当前执行前复核 slot 计划为：

```text
source|scope|difference|preview
```

不再是：

```text
source|scope|policy|difference|preview
```

### 2.2 投影层

文件：`src/ui/panels/style_object_projection_builders.py`

已删除 `build_execution_prereview_style_projection(...)` 中的：

```text
policy=build_scene_section_style_policy_projection(...)
```

这样执行前复核投影不再暗示 Workbench 主路径需要策略开关。

## 3. 测试守门

文件：`tests/test_quick_execution_detail_architecture.py`

已更新：

- 不再导入 `StylePolicyControlDeck`。
- `detail._scene_card.rule_control is None`。
- `style_management_content_plan == "source|scope|difference|preview"`。
- `style_management_slot_plan == "source|scope|difference|preview"`。
- `style_management_has_policy is False`。
- `style_management_has_policy_slot is False`。
- `style_management_rule_control_protocol == "none"`。
- `QuickExecutionDetail` 不应拥有 `_style_prereview_policy_deck`。
- 源码中不得出现：

```text
StylePolicyControlDeck(
policy_selected.connect
_on_style_policy_selected
rule_control=self._style_prereview_policy_deck
```

原来的“点击策略行切换预览”测试改为：

- 执行前复核使用样式来源摘要。
- 不展示 policy toggle。
- “调分区”仍发出 `scene_style_field` 修复请求。
- 样式预览继续展示默认受影响分区。

## 4. 验证

已运行：

```text
python -X utf8 -m py_compile src\ui\panels\workbench\quick_execution_detail.py src\ui\panels\style_object_projection_builders.py tests\test_quick_execution_detail_architecture.py
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_hides_style_difference_without_independent_sections tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_style_prereview_uses_summary_without_policy_toggles -q
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py -q
```

结果：

```text
py_compile 通过
3 passed in 2.59s
48 passed in 18.81s
```

## 5. 统一边界

当前统一口径：

| 位置 | 是否放策略开关 | 原因 |
| --- | --- | --- |
| 模板正文排版 | 否 | 只编辑模板默认样式 |
| Workbench 快速执行 | 否 | 只复核本次运行，不编辑覆盖 |
| 场景分区样式 | 是 | 唯一负责跟随模板/独立样式的操作入口 |

如果后续需要展示更多场景覆盖细节，应进入：

- 场景规划的“分区样式”
- 场景概览的“核对依据”
- 执行报告或问题详情

不应回到：

- 模板正文排版主编辑区
- Workbench 快速执行主路径
- 禁用态 toggle 列表
