# StyleReceiptSlotFrame 无卡片回执槽位执行记录

日期：2026-06-29

## 1. 本轮结论

上一轮已经把 Workbench 执行中心的样式回执接入：

```text
StyleManagementBlock(mode="execution_receipt_review", receipt_slot=...)
```

但 `RecentRunPanel` 仍然不能直接套 `StyleManagementBlock`，原因是它本身已经是 `Card`。如果直接嵌入完整 block，会形成卡片套卡片：

```text
RecentRunPanel(Card)
  StyleManagementBlock
    DetailSummaryCard
      StyleResultReceiptRow
```

本轮新增无卡片嵌入式回执槽位：

```text
StyleReceiptSlotFrame
```

它只负责：

1. 持有 `StyleResultReceiptRow`。
2. 同步有回执/无回执显隐。
3. 暴露 `style_management_content_plan = receipt` 等语义属性。
4. 不创建 Card，不增加额外标题卡片。

这样最近结果面板也进入了统一 receipt 边界，同时避免视觉层级变重。

## 2. 代码落点

### 2.1 新增 cardless receipt frame

文件：

```text
src/shared/ui/style_receipt_slot_frame.py
```

新增：

```text
StyleReceiptSlotFrame
```

关键行为：

```text
初始隐藏
内部创建 StyleResultReceiptRow
apply_envelope(...) 后同步显示/隐藏
set_summary(...) 后同步显示/隐藏
has_receipt() 返回当前是否有可见回执
```

语义属性：

```text
style_management_mode = execution_receipt_review
style_management_content_plan = receipt
style_management_has_receipt = True
style_management_has_editor = False
style_receipt_slot_surface = embedded
```

### 2.2 导出共享控件

文件：

```text
src/shared/ui/__init__.py
```

新增导出：

```text
StyleReceiptSlotFrame
```

### 2.3 执行中心改用 frame

文件：

```text
src/ui/panels/workbench/execution_center.py
```

当前结构：

```text
_style_receipt_slot = StyleReceiptSlotFrame(...)
_style_receipt_row = _style_receipt_slot.receipt_row

_style_receipt_block = StyleManagementBlock(
    mode="execution_receipt_review",
    receipt_slot=_style_receipt_slot,
)
```

执行中心仍保留完整 `StyleManagementBlock` 外壳，因为它不是 Card，适合展示“样式回执”这一块。

### 2.4 最近结果接入 frame

文件：

```text
src/ui/panels/workbench/recent_run_panel.py
```

原结构：

```text
_style_receipt_row = StyleResultReceiptRow(...)
add_widget(_style_receipt_row)
```

新结构：

```text
_style_receipt_slot = StyleReceiptSlotFrame(...)
_style_receipt_row = _style_receipt_slot.receipt_row
add_widget(_style_receipt_slot)
```

最近结果仍显示同一条 `StyleResultReceiptRow`，但外层已经具备 receipt 语义和显隐同步。

## 3. 为什么不把 RecentRunPanel 改成 StyleManagementBlock

`StyleManagementBlock` 的职责是完整的页面级样式管理区，内部有 `DetailSummaryCard`。它适合：

| 场景 | 是否适合完整 block |
| --- | --- |
| 模板正文详情 | 适合 |
| 场景分区样式 | 适合 |
| 模板概览页面级预览 | 适合 |
| Workbench 执行中心 | 适合 |
| Workbench 最近结果卡片内部 | 不适合 |

`RecentRunPanel` 已经是一张结果卡。它需要的是“卡内一条语义回执”，不是“卡内再嵌一张样式管理卡”。

因此本轮将边界拆成：

```text
StyleManagementBlock：完整样式管理块
StyleReceiptSlotFrame：已有容器内的轻量 receipt 槽位
StyleResultReceiptRow：具体回执行
```

## 4. 用户体验含义

用户看到的内容没有变复杂：

```text
样式来源：本次按模板“默认格式”处理；参考文献（行距）使用场景独立样式。
```

但内部链路变得更清楚：

```text
执行中心：作为独立块显示样式回执
最近结果：作为结果卡内部回执行显示样式来源
```

这符合“删除冗余文本描述”的方向：不加长说明，而是让结构负责表达层级。

## 5. 新增与更新测试

### 5.1 共享控件测试

文件：

```text
tests/test_small_widget_architecture.py
```

新增：

```text
test_style_receipt_slot_frame_wraps_receipt_row_without_card_chrome
```

断言：

```text
初始隐藏
content_plan == receipt
surface == embedded
apply_envelope 后显示
set_summary("") 后隐藏
```

### 5.2 最近结果真实页面测试

文件：

```text
tests/test_recent_run_panel.py
```

新增/更新断言：

```text
panel._style_receipt_slot 是 StyleReceiptSlotFrame
panel._style_receipt_slot.receipt_row is panel._style_receipt_row
style_management_content_plan == receipt
style_receipt_slot_surface == embedded
有样式来源时 slot 显示
无样式来源时 slot 隐藏
```

### 5.3 执行中心真实页面测试

文件：

```text
tests/test_workbench_execution_center.py
```

更新断言：

```text
center._style_receipt_slot 是 StyleReceiptSlotFrame
center._style_receipt_block.receipt_slot is center._style_receipt_slot
center._style_receipt_slot.receipt_row is center._style_receipt_row
```

### 5.4 导出测试

文件：

```text
tests/test_ui_exports.py
```

新增断言：

```text
StyleReceiptSlotFrame.__name__ == "StyleReceiptSlotFrame"
```

## 6. 验证

已执行精确回归：

```powershell
python -X utf8 -m py_compile src/shared/ui/style_receipt_slot_frame.py src/shared/ui/__init__.py src/ui/panels/workbench/execution_center.py src/ui/panels/workbench/recent_run_panel.py tests/test_recent_run_panel.py tests/test_workbench_execution_center.py tests/test_small_widget_architecture.py tests/test_ui_exports.py
python -X utf8 -m pytest tests/test_small_widget_architecture.py::test_style_receipt_slot_frame_wraps_receipt_row_without_card_chrome tests/test_workbench_execution_center.py::test_execution_center_defaults_to_canonical_readiness_state tests/test_workbench_execution_center.py::test_execution_center_result_state_renders_style_source_receipt tests/test_workbench_execution_center.py::test_execution_center_hides_receipt_block_without_style_source tests/test_recent_run_panel.py::test_recent_run_panel_default_summary_text tests/test_recent_run_panel.py::test_recent_run_panel_includes_style_source_summary tests/test_recent_run_panel.py::test_recent_run_panel_accepts_style_source_envelope tests/test_recent_run_panel.py::test_recent_run_panel_hides_receipt_slot_without_style_source tests/test_ui_exports.py::test_shared_ui_exports_include_unified_controls -q
```

结果：

```text
9 passed in 2.18s
```

静态证据：

```text
src/ui/panels/workbench/recent_run_panel.py
  add_widget(self._style_receipt_slot)
  不再 add_widget(self._style_receipt_row)

src/ui/panels/workbench/execution_center.py
  StyleManagementBlock.receipt_slot = self._style_receipt_slot
```

## 7. 当前链路状态

| 链路 | 状态 |
| --- | --- |
| 模板正文编辑 | `StyleManagementBlock(template_baseline_edit)` |
| 场景分区样式 | `StyleManagementBlock(scene_section_rules)` |
| 模板概览页面级预览 | `StyleManagementBlock(template_overview_preview, preview_slot=...)` |
| Workbench 执行中心样式回执 | `StyleManagementBlock(execution_receipt_review, receipt_slot=StyleReceiptSlotFrame)` |
| Workbench 最近结果样式回执 | `StyleReceiptSlotFrame` |

## 8. 下一轮建议

下一步可以继续处理“差异摘要”：

```text
StyleDifferenceReceipt / StyleDifferenceSummarySlot
```

它应该服务：

1. 场景分区样式详情。
2. Workbench 执行前复核。
3. Workbench 执行后报告。

目标是把“相对模板改了什么”从散落字段变成可复用、可回执、可测试的语义块。
