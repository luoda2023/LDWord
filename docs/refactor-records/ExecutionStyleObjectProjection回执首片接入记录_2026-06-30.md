# ExecutionStyleObjectProjection 回执首片接入记录

日期：2026-06-30

## 1. 本轮目标

前两轮已经完成：

```text
StyleObjectProjection 首片
-> 模板正文详情接入
-> 场景分区样式接入
-> projection builder 下沉
```

但执行后回执仍然停留在旧链路：

```text
ExecutionCenter / RecentRunPanel
  -> effective_style_source_envelope(...)
  -> StyleReceiptSlotFrame.apply_envelope(...)
  -> StyleDifferenceSummarySlot.apply_projection(...)
```

也就是说，执行后样式事实还没有进入 `StyleObjectProjection`。本轮目标是把执行回执的首个真实消费点接入统一投影。

## 2. Builder 扩展

文件：

```text
src/ui/panels/style_object_projection_builders.py
```

新增：

```python
build_execution_style_projection(
    style_source_envelope=None,
    style_source_summary="",
    difference=None,
)
```

输出：

```text
kind = execution_style
object_label = 样式回执
source_label = 本次使用
scope_label = 执行结果
edit_state_label = 只读
receipt = StylePresentationEnvelope(execution_receipt)
difference = StyleDifferenceSummaryProjection | None
```

同时新增内部 helper：

```python
_effective_execution_receipt_envelope(...)
```

它保留原有回退逻辑：

- 优先使用 `style_source_envelope`。
- 如果 envelope 为空，则使用 `style_source_summary` 生成回执。
- 如果二者都为空，则 receipt 为空，回执行隐藏。

## 3. ExecutionCenter 接入

文件：

```text
src/ui/panels/workbench/execution_center.py
```

旧链路：

```text
_style_receipt_slot.apply_envelope(...)
_style_difference_slot.apply_projection(...)
```

新链路：

```text
build_execution_style_projection(...)
-> _style_receipt_block.apply_style_object_projection(...)
```

差异 slot 的可见性仍由 `ExecutionCenter` 控制：

```python
_style_difference_slot.setVisible(style_projection.difference is not None)
```

原因是 `StyleManagementBlock` 需要兼容场景分区样式。场景里的 difference slot 即使 projection 为空，也可能需要显示“选择分区”等空态；执行回执则应该无差异时隐藏。

## 4. RecentRunPanel 接入

文件：

```text
src/ui/panels/workbench/recent_run_panel.py
```

同样从旧链路：

```text
effective_style_source_envelope(...)
_style_receipt_slot.apply_envelope(...)
_style_difference_slot.apply_projection(...)
```

迁移为：

```text
build_execution_style_projection(...)
-> _style_review_block.apply_style_object_projection(...)
```

这样“执行中心”和“最近结果”两个执行后阅读面板，都开始使用同一种样式对象投影。

## 5. 测试更新

### 5.1 Builder 行为覆盖

文件：

```text
tests/test_small_widget_architecture.py
```

扩展：

```text
test_style_object_projection_builders_cover_template_and_scene_styles
```

新增断言：

- `build_execution_style_projection(...)` 输出 `kind == "execution_style"`。
- `object_label == "样式回执"`。
- `source_label == "本次使用"`。
- `scope_label == "执行结果"`。
- `edit_state_label == "只读"`。
- receipt summary 保持“样式来源：...”格式。
- difference 状态保留。

### 5.2 ExecutionCenter 行为与边界

文件：

```text
tests/test_workbench_execution_center.py
```

新增源码边界测试：

```text
test_execution_center_routes_style_receipt_through_style_object_projection
```

锁定：

- 必须调用 `build_execution_style_projection`。
- 必须调用 `apply_style_object_projection(style_projection)`。
- 不再直接调用 `effective_style_source_envelope`。
- 不再直接调用 `_style_receipt_slot.apply_envelope`。
- 不再直接调用 `_style_difference_slot.apply_projection`。

行为测试新增断言：

- `_style_receipt_block.property("style_object_kind") == "execution_style"`。
- `_style_receipt_block.property("style_object_label") == "样式回执"`。
- `_style_receipt_block.property("style_object_source_label") == "本次使用"`。
- `_style_receipt_block.property("style_object_scope_label") == "执行结果"`。
- `_style_receipt_block.property("style_object_edit_state_label") == "只读"`。

### 5.3 RecentRunPanel 行为与边界

文件：

```text
tests/test_recent_run_panel.py
```

新增源码边界测试：

```text
test_recent_run_panel_routes_style_receipt_through_style_object_projection
```

锁定同样的执行后回执链路。

## 6. 本轮验证

已执行语法检查：

```powershell
python -X utf8 -m py_compile src\ui\panels\style_object_projection_builders.py src\ui\panels\workbench\execution_center.py src\ui\panels\workbench\recent_run_panel.py tests\test_small_widget_architecture.py tests\test_workbench_execution_center.py tests\test_recent_run_panel.py
```

结果：通过。

已执行聚焦测试：

```powershell
python -X utf8 -m pytest tests\test_workbench_execution_center.py::test_execution_center_routes_style_receipt_through_style_object_projection tests\test_recent_run_panel.py::test_recent_run_panel_routes_style_receipt_through_style_object_projection tests\test_small_widget_architecture.py::test_style_object_projection_builders_cover_template_and_scene_styles tests\test_workbench_execution_center.py::test_execution_center_result_state_renders_style_source_receipt tests\test_workbench_execution_center.py::test_execution_center_hides_receipt_block_without_style_source tests\test_workbench_execution_center.py::test_execution_center_shows_style_difference_without_receipt tests\test_recent_run_panel.py::test_recent_run_panel_accepts_style_source_envelope tests\test_recent_run_panel.py::test_recent_run_panel_hides_receipt_slot_without_style_source -q
```

结果：

```text
8 passed
```

追加执行相关完整回归：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py tests\test_workbench_execution_center.py tests\test_recent_run_panel.py -q
```

结果：

```text
139 passed
```

追加执行执行前复核相邻架构回归：

```powershell
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py -q
```

结果：

```text
47 passed in 54.58s
```

## 7. 当前未完成

本轮不把以下事项视为完成：

1. `QuickExecutionDetail` 的执行前复核仍然直接使用 `StyleSourceCompactRow` 和 difference slot。
2. `execution_prereview` 还没有统一进入 `StyleObjectProjection`。
3. `effective_style_source_envelope(...)` 仍保留在 Workbench state 中，供未迁移路径兼容。
4. 执行回执尚未纳入 `receipt + difference + preview` 的完整三端视图。
5. `StylePolicyControlDeck` 和 `StylePreviewSurface` 尚未落地。

## 8. 下一步建议

下一步应接 `QuickExecutionDetail` 的执行前复核：

```text
build_execution_prereview_style_projection(...)
-> source/scope/difference
-> StyleManagementBlock(execution_prereview)
```

这能把执行前和执行后都接到统一投影：

```text
执行前：模板基线 / 分区覆盖 / 差异
执行后：本次实际使用 / 差异 / 回执
```

等执行前也接入后，再考虑清理 `effective_style_source_envelope(...)` 的兼容路径。

## 9. 本轮结论

本轮完成了执行后回执的统一投影首片：

```text
ExecutionCenter
RecentRunPanel
  -> build_execution_style_projection(...)
  -> StyleObjectProjection
  -> StyleManagementBlock.apply_style_object_projection(...)
```

用户可见行为保持不变，但底层链路继续向统一样式对象收敛。这样后续要做模板/场景/执行三端一致的样式预览与回执，会更容易继续推进。
