# ExecutionPrereviewStyleObjectProjection 接入记录

日期：2026-06-30

## 1. 本轮目标

上一轮已经把执行后样式回执接入统一投影：

```text
ExecutionCenter / RecentRunPanel
-> build_execution_style_projection(...)
-> StyleObjectProjection
-> StyleManagementBlock.apply_style_object_projection(...)
```

但执行前复核仍然是旧链路：

```text
QuickExecutionDetail
-> build_style_source_projection(...)
-> StyleSourceCompactRow.apply_projection(...)
-> build_style_difference_summary_projection(...)
-> StyleDifferenceSummarySlot.apply_projection(...)
```

本轮目标是把 `QuickExecutionDetail` 的 `execution_prereview` 也纳入 `StyleObjectProjection`。

## 2. StyleObjectProjection 扩展 source slot

文件：

```text
src/shared/ui/style_object_projection.py
src/shared/ui/style_management_block.py
```

`StyleObjectProjection` 新增：

```python
source: object | None = None
```

`StyleManagementBlock.apply_style_object_projection(...)` 新增 source slot 应用：

```text
style_object.source
-> source_slot.apply_projection(...)
```

考虑到 `QuickExecutionDetail` 的 source slot 是一个容器：

```text
QWidget(source_slot)
  -> 场景/模板选择行
  -> StyleSourceCompactRow
```

所以 `StyleManagementBlock` 的 helper 会先尝试当前 source slot，再查找子控件里第一个支持 `apply_projection(...)` 的对象。这样不需要让业务页面再直接持有并更新 `StyleSourceCompactRow`。

## 3. execution_prereview builder

文件：

```text
src/ui/panels/style_object_projection_builders.py
```

新增：

```python
build_execution_prereview_style_projection(scene, template, template_label="")
```

它统一组合：

- `build_style_source_projection(..., view_mode="execution_review")`
- `build_style_difference_summary_projection(...)`
- `StyleObjectProjection(kind="execution_prereview_style")`

输出语义：

```text
kind = execution_prereview_style
object_label = 执行前复核
source = StyleSourceProjection
difference = StyleDifferenceSummaryProjection | None
edit_state_label = 只读
```

## 4. QuickExecutionDetail 迁移

文件：

```text
src/ui/panels/workbench/quick_execution_detail.py
```

旧链路：

```text
_style_source_row.apply_projection(...)
_sync_style_difference_slot(...)
_style_difference_slot.apply_projection(...)
```

新链路：

```text
build_execution_prereview_style_projection(...)
-> _scene_card.apply_style_object_projection(...)
```

差异 slot 是否可见仍由 `QuickExecutionDetail` 控制：

```python
_style_difference_slot.setVisible(style_projection.difference is not None)
```

因为执行前复核没有独立分区时，difference 区应隐藏，而不是显示空态。

## 5. 测试更新

### 5.1 Builder 行为

文件：

```text
tests/test_small_widget_architecture.py
```

扩展：

```text
test_style_object_projection_builders_cover_template_and_scene_styles
```

新增覆盖：

- `build_execution_prereview_style_projection(...)` 输出 `kind == "execution_prereview_style"`。
- `object_label == "执行前复核"`。
- `source.view_mode == "execution_review"`。
- 有独立分区时 `difference` 非空。
- `edit_state_label == "只读"`。

### 5.2 QuickExecutionDetail 行为和源码边界

文件：

```text
tests/test_quick_execution_detail_architecture.py
```

新增/更新断言：

- `_scene_card.property("style_object_kind") == "execution_prereview_style"`。
- `_scene_card.property("style_object_label") == "执行前复核"`。
- `_scene_card.property("style_object_edit_state_label") == "只读"`。
- 源码必须调用 `build_execution_prereview_style_projection`。
- 源码必须调用 `apply_style_object_projection(style_projection)`。
- 源码不再直接调用 `build_style_source_projection`。
- 源码不再直接调用 `build_style_difference_summary_projection`。
- 源码不再直接调用 `_style_source_row.apply_projection`。
- 源码不再直接调用 `_style_difference_slot.apply_projection`。

## 6. 本轮验证

已执行语法检查：

```powershell
python -X utf8 -m py_compile src\shared\ui\style_object_projection.py src\shared\ui\style_management_block.py src\ui\panels\style_object_projection_builders.py src\ui\panels\workbench\quick_execution_detail.py tests\test_small_widget_architecture.py tests\test_quick_execution_detail_architecture.py
```

结果：通过。

已执行聚焦测试：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_object_projection_builders_cover_template_and_scene_styles tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_hides_style_difference_without_independent_sections -q
```

结果：

```text
3 passed
```

追加执行相关共享小控件、执行中心、最近结果回归：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py tests\test_workbench_execution_center.py tests\test_recent_run_panel.py -q
```

结果：

```text
139 passed
```

追加执行执行前详情架构完整回归：

```powershell
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py -q
```

结果：

```text
47 passed in 55.18s
```

追加执行 whitespace 检查：

```powershell
git diff --check -- src\shared\ui\style_object_projection.py src\shared\ui\style_management_block.py src\ui\panels\style_object_projection_builders.py src\ui\panels\workbench\quick_execution_detail.py tests\test_small_widget_architecture.py tests\test_quick_execution_detail_architecture.py docs\refactor-records\ExecutionPrereviewStyleObjectProjection接入记录_2026-06-30.md
```

结果：无 whitespace error；仅提示部分 Python 文件下次由 Git 触碰时 LF 会替换为 CRLF。

## 7. 当前未完成

本轮不把以下事项视为完成：

1. `StylePreviewSurface` 尚未落地。
2. `StylePolicyControlDeck` 尚未从 `StyleRuleControlDeck` 抽象出来。
3. 执行前复核仍没有 preview，只覆盖 source/scope/difference。
4. `effective_style_source_envelope(...)` 的兼容路径仍存在。
5. 场景概览首屏工程信息下沉仍未完成。

## 8. 本轮结论

本轮把执行前复核也接进了统一样式对象：

```text
QuickExecutionDetail
-> build_execution_prereview_style_projection(...)
-> StyleObjectProjection(source + difference)
-> StyleManagementBlock.apply_style_object_projection(...)
```

至此，模板正文、场景分区、执行前复核、执行后回执都已经开始使用同一种投影入口。

这还不是最终优秀设计，但它让后续真正做视觉和控件规划时，有了更稳的对象边界。
