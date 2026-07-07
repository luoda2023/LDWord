# Workbench 执行前样式差异摘要接入执行记录

日期：2026-06-29

## 1. 本轮目标

上一份规划文档已经确认：Workbench 执行前是样式链路的明显断点。

已有状态：

```text
模板管理：能看模板基线和页面级预览
场景配置：能编辑分区独立样式，并显示与模板差异
Workbench 执行后：能显示样式回执
Workbench 执行前：只能显示样式来源，不能显示将应用的分区差异
```

本轮先补这个断点：

```text
在 Workbench “场景与模板”卡中，样式来源行下方显示执行前差异摘要。
没有独立样式时隐藏；有独立样式时显示。
```

这不是完整的页面蓝图重排，而是把已经存在的数据链路接到可见 UI，避免用户运行前只能看到“有独立样式”，却不知道主要差异是什么。

## 2. 新增语义层

文件：

```text
src/config/style_difference_projection.py
```

新增：

```text
StyleDifferenceSummaryProjection
build_style_difference_summary_projection(...)
```

输入：

```text
Sequence[StyleDifferenceProjection]
```

输出：

```text
template_status
current_status
difference_status
detail
variant
section_count
changed_section_count
pending_section_count
```

规则：

| 情况 | 输出 |
| --- | --- |
| 无独立分区 | `None`，UI 不显示差异摘要 |
| 单个独立分区 | 保留该分区的模板/当前/差异/详情 |
| 多个分区有字段差异 | 聚合为 `N 个分区已调整` |
| 多个分区待比较 | 聚合为 `待比较`，提示需要模板基线后比较 |
| 多个独立分区但字段未变 | 聚合为 `未改字段` |

这样聚合逻辑位于 config/projection 层，后续场景页、Workbench、报告都能复用。

## 3. Workbench 接入

文件：

```text
src/ui/panels/workbench/quick_execution_detail.py
```

新增导入：

```text
StyleDifferenceSummarySlot
build_style_difference_summary_projection
```

接入位置：

```text
场景与模板卡
-> 场景/模板选择行
-> StyleSourceCompactRow
-> StyleDifferenceSummarySlot
```

同步逻辑：

```text
build_style_source_projection(...)
-> projection.section_differences
-> build_style_difference_summary_projection(...)
-> StyleDifferenceSummarySlot.apply_projection(...)
```

显示规则：

```text
summary_projection is None -> 隐藏 difference slot
summary_projection exists -> 显示 difference slot
```

同时给场景卡打上轻量语义属性：

```text
style_management_mode = execution_prereview
style_management_content_plan = source|scope|difference
```

这一步不是说 `Card` 已经等同 `StyleManagementBlock`，而是先把 Workbench 执行前的语义标出来，方便后续完整蓝图替换。

## 4. StyleManagementBlock 模式契约

文件：

```text
src/shared/ui/style_management_block.py
```

新增模式：

```text
execution_prereview
```

内容计划：

```text
source|scope|difference
```

契约：

```text
show_owner_toolbar = False
show_owner_status = False
show_preview = False
collapse_surface_when_readonly = True
```

意义：

```text
执行前复核只读，不应该出现编辑器、恢复按钮或规则开关。
它回答的是：这次将按哪个模板和哪些分区差异执行。
```

## 5. 用户体验变化

### 无独立样式

用户只看到样式来源：

```text
模板：默认格式
分区：全部分区跟随模板
```

差异摘要隐藏，不增加空话。

### 有独立样式但没有模板基线

用户看到：

```text
模板基线：模板基线
当前分区：参考文献 独立样式
差异：待比较
```

tooltip/detail：

```text
需要模板基线后比较字段差异。
```

### 多个分区有字段差异

聚合语义为：

```text
当前分区：3 个分区独立样式
差异：2 个分区已调整
详情：不同：参考文献改了行距；致谢改了字号、中文字体
```

主界面只放摘要；完整证据后续可进入报告。

## 6. 测试更新

### 6.1 差异 projection 测试

文件：

```text
tests/test_style_difference_projection.py
```

新增：

```text
test_style_difference_summary_projection_returns_none_without_overrides
test_style_difference_summary_projection_keeps_single_section_readable
test_style_difference_summary_projection_aggregates_multiple_sections
test_style_difference_summary_projection_aggregates_pending_compare_sections
```

验证：

- 无独立分区不生成摘要。
- 单分区摘要保留可读分区名称。
- 多分区字段差异能聚合。
- 待比较状态能聚合。

### 6.2 Workbench 架构测试

文件：

```text
tests/test_quick_execution_detail_architecture.py
```

更新：

```text
test_quick_execution_detail_uses_shared_style_source_row
```

新增断言：

- `_style_difference_slot` 是 `StyleDifferenceSummarySlot`
- 场景卡具备 `execution_prereview` 内容计划属性
- 有独立分区时差异 slot 显示
- 差异状态为 `待比较`

新增：

```text
test_quick_execution_detail_hides_style_difference_without_independent_sections
```

验证：

- 无独立分区时差异 slot 隐藏
- `style_difference_has_projection` 为 `False`

### 6.3 StyleManagementBlock 模式测试

文件：

```text
tests/test_small_widget_architecture.py
```

更新：

```text
test_style_management_block_named_modes_project_shared_contracts
```

验证：

- `execution_prereview` 正式存在
- 内容计划为 `source|scope|difference`
- 不显示 editor / preview / owner toolbar

## 7. 已运行验证

语法检查：

```powershell
python -X utf8 -m py_compile src\config\style_difference_projection.py src\ui\panels\style_difference_projection.py src\ui\panels\workbench\quick_execution_detail.py tests\test_style_difference_projection.py tests\test_quick_execution_detail_architecture.py
```

结果：通过。

差异 projection：

```powershell
python -X utf8 -m pytest tests\test_style_difference_projection.py -q
```

结果：

```text
8 passed
```

Workbench 执行前聚焦测试：

```powershell
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_hides_style_difference_without_independent_sections -q
```

结果：

```text
2 passed
```

模式契约 + 聚合 + Workbench 合并聚焦回归：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_management_block_named_modes_project_shared_contracts tests\test_style_difference_projection.py tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_hides_style_difference_without_independent_sections -q
```

结果：

```text
11 passed
```

## 8. 当前边界

本轮没有把 Workbench 的“场景与模板”卡整体替换成 `StyleManagementBlock`。

原因：

- 当前 `StyleManagementBlock` 还没有正式 `source_slot` / `scope_slot`。
- 直接替换会扩大 Workbench 布局风险。
- 本轮目标是先把执行前差异复核链路接通。

当前真实状态：

```text
Workbench 执行前已有 execution_prereview 语义属性。
差异摘要已真实显示。
完整 StyleManagementBlueprint 仍未完成。
```

## 9. 下一步

继续推进 P0：

1. 给 `StyleManagementBlock` 增加 `source_slot`、`scope_slot`、独立 `difference_slot`。
2. 将 Workbench 的执行前复核卡从普通 `Card` 迁移到完整 `StyleManagementBlock(mode="execution_prereview")`。
3. 将执行后回执加入可选差异摘要，形成：

```text
执行前将应用什么
-> 执行后实际使用什么
```

4. 继续清理主界面冗余文本，尤其是内部 key、成熟度代号和长边界说明。

## 10. 本轮判断

这轮把 Workbench 执行前从“只显示来源”推进为“来源 + 差异复核”。

用户现在能在运行前看到：

```text
当前模板是什么
哪些分区独立
独立分区是否已经知道差异
```

这比继续写更多说明文字更有效，因为它把用户真正需要判断的信息放到了运行前的决策位置。
