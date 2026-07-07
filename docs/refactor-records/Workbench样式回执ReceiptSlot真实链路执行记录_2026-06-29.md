# Workbench 样式回执 ReceiptSlot 真实链路执行记录

日期：2026-06-29

## 1. 本轮结论

上一轮已经把模板概览的页面级样式预览接入 `StyleManagementBlock(preview_slot=...)`。本轮继续推进 Workbench 执行后的样式回执链路。

审计后发现 Workbench 有两个回执入口：

| 入口 | 当前容器 | 原状态 | 本轮处理 |
| --- | --- | --- | --- |
| 执行中心 `ExecutionCenter` | 普通 `QWidget` | 直接挂 `StyleResultReceiptRow` | 已接入 `StyleManagementBlock(receipt_slot=...)` |
| 最近结果 `RecentRunPanel` | 已经是 `Card` | 直接挂 `StyleResultReceiptRow` | 后续已通过 `StyleReceiptSlotFrame` 接入无卡片 receipt 边界 |

本轮完成了执行中心的真实链路迁移：

```text
ExecutionCenter
  StyleManagementBlock(mode="execution_receipt_review")
    receipt_slot = StyleReceiptSlotFrame
      receipt_row = StyleResultReceiptRow
```

这意味着执行后的样式来源不再只是一个散落在 Workbench 的独立行，而是进入了样式管理体系的命名 `receipt` 板块。

## 2. 为什么新增 execution_receipt_review

已有模式里有：

```text
readonly_review = source|scope|preview|receipt
```

但 Workbench 执行中心的样式回执不应该展示这么多内容。执行结束后，用户只需要确认：

```text
这次实际用了哪套模板和哪些场景覆盖。
```

如果把 `readonly_review` 直接用于执行中心，会带来多余板块：

| 板块 | 是否需要 | 原因 |
| --- | --- | --- |
| source | 不需要 | 回执行自己已经包含来源标题和摘要 |
| scope | 不需要 | 执行摘要里已有处理范围，回执不重复 |
| preview | 不需要 | 执行后不是预览阶段 |
| editor | 不需要 | 执行结果不可编辑 |
| receipt | 需要 | 样式来源的最终结果确认 |

因此本轮新增：

```text
execution_receipt_review = receipt
```

它是一个只读、只回执的模式，不带预览、不带编辑、不带规则控制。

## 3. 代码落点

### 3.1 共享模式

文件：

```text
src/shared/ui/style_management_block.py
```

新增契约：

```text
execution_receipt_review
  show_owner_toolbar = False
  show_owner_status = False
  show_preview = False
  collapse_surface_when_readonly = True
```

新增内容计划：

```text
source = False
scope = False
rules = False
editor = False
preview = False
receipt = True
```

最终编码：

```text
style_management_content_plan = receipt
```

### 3.2 执行中心接入 receipt_slot

文件：

```text
src/ui/panels/workbench/execution_center.py
```

原结构：

```text
layout.addWidget(self._style_receipt_row)
```

新结构：

```text
self._style_receipt_slot = StyleReceiptSlotFrame(...)
self._style_receipt_row = self._style_receipt_slot.receipt_row

self._style_receipt_block = StyleManagementBlock(
    title="样式回执",
    icon_name="type-outline",
    object_name_prefix="wb_execution_style_receipt",
    mode="execution_receipt_review",
    receipt_slot=self._style_receipt_slot,
)

layout.addWidget(self._style_receipt_block)
```

并新增显隐同步：

```text
没有样式来源回执：隐藏整个 block
有样式来源回执：显示 block 和内部 row
```

这样不会出现空的“样式回执”卡片。

## 4. 用户体验含义

本轮不是增加更多说明文字，而是调整结构：

```text
执行摘要：告诉用户这次执行总体结果。
样式回执：告诉用户这次实际采用的样式来源。
```

这比把样式来源混在长摘要文本里更清楚，也比裸露一行 `StyleResultReceiptRow` 更像一套稳定产品语言。

页面上仍保留短文案：

```text
样式回执
样式来源：...
```

不会展示内部模式名 `execution_receipt_review`。

## 5. 最近结果的后续补充

`RecentRunPanel` 当前继承自 `Card`：

```text
class RecentRunPanel(Card):
```

而 `StyleManagementBlock` 内部会创建 `DetailSummaryCard`。如果直接把它塞进 `RecentRunPanel`，就会形成：

```text
Card 最近结果
  DetailSummaryCard 样式回执
    StyleResultReceiptRow
```

这会违反当前前端设计边界：

```text
不要把 UI cards 放进其他 cards。
```

因此本轮没有强行把完整 `StyleManagementBlock` 塞进最近结果。后续已按本节建议抽出更小的：

```text
StyleReceiptSlotFrame
```

并让 `ExecutionCenter` 和 `RecentRunPanel` 共用。详见：

```text
docs/refactor-records/StyleReceiptSlotFrame无卡片回执槽位执行记录_2026-06-29.md
```

## 6. 新增守门测试

### 6.1 共享模式守门

文件：

```text
tests/test_small_widget_architecture.py
```

新增断言：

```text
style_management_content_plan("execution_receipt_review").sections() == ("receipt",)
execution_receipt_block.property("style_management_content_plan") == "receipt"
execution_receipt_block.property("style_management_has_editor") is False
execution_receipt_block.property("style_management_has_receipt") is True
execution_receipt_block.receipt_slot is receipt_slot
execution_receipt_block.preview is None
editing_section 不进入主布局
```

### 6.2 执行中心真实页面守门

文件：

```text
tests/test_workbench_execution_center.py
```

新增断言：

```text
center._style_receipt_block 是 StyleManagementBlock
style_management_mode == execution_receipt_review
style_management_content_plan == receipt
receipt_slot is center._style_receipt_slot
center._style_receipt_slot.receipt_row is center._style_receipt_row
style_management_has_editor is False
```

同时验证：

```text
没有样式来源：receipt block 隐藏
有样式来源：receipt block 显示，原 summary_text/detail 行为不变
```

### 6.3 导出守门

文件：

```text
tests/test_ui_exports.py
```

新增断言：

```text
style_management_content_plan("execution_receipt_review").sections() == ("receipt",)
```

## 7. 验证

已执行精确回归：

```powershell
python -X utf8 -m pytest tests/test_workbench_execution_center.py::test_execution_center_defaults_to_canonical_readiness_state tests/test_workbench_execution_center.py::test_execution_center_result_state_renders_status_and_summary tests/test_workbench_execution_center.py::test_execution_center_result_state_renders_style_source_receipt tests/test_workbench_execution_center.py::test_execution_center_hides_receipt_block_without_style_source tests/test_small_widget_architecture.py::test_style_management_block_named_modes_project_shared_contracts tests/test_ui_exports.py::test_shared_ui_exports_include_unified_controls -q
```

结果：

```text
6 passed in 3.28s
```

中范围回归时发现 `DetailSummaryCard` 的 queued height sync 可能在 Qt C++ widget 删除后继续触发，导致后续无关 widget 测试被过期事件打断。本轮已在：

```text
src/shared/ui/template_summary_card.py
```

为 `_run_queued_content_height_sync` 增加销毁后 `RuntimeError` 防护。随后重新执行：

```powershell
python -X utf8 -m py_compile src/shared/ui/template_summary_card.py src/shared/ui/style_management_block.py src/ui/panels/workbench/execution_center.py
python -X utf8 -m pytest tests/test_workbench_execution_center.py tests/test_recent_run_panel.py tests/test_small_widget_architecture.py tests/test_ui_exports.py -q
```

结果：

```text
131 passed in 10.47s
```

静态证据：

```text
src/ui/panels/workbench/execution_center.py
  不再直接 layout.addWidget(self._style_receipt_row)
  改为 layout.addWidget(self._style_receipt_block)
```

## 8. 当前链路状态

| 链路 | 状态 |
| --- | --- |
| 模板正文编辑 | 已进入 `StyleManagementBlock(template_baseline_edit)` |
| 场景分区样式 | 已进入 `StyleManagementBlock(scene_section_rules)` |
| 模板概览页面级预览 | 已进入 `StyleManagementBlock(template_overview_preview, preview_slot=...)` |
| Workbench 执行中心样式回执 | 已进入 `StyleManagementBlock(execution_receipt_review, receipt_slot=StyleReceiptSlotFrame)` |
| Workbench 最近结果样式回执 | 已进入 `StyleReceiptSlotFrame` |

## 9. 下一轮建议

下一轮可继续处理样式差异摘要。建议优先设计：

```text
StyleDifferenceReceipt / StyleDifferenceSummarySlot
```

验收标准：

1. 场景分区样式详情能展示“相对模板改了什么”。
2. Workbench 执行前能复核将应用的样式差异。
3. 执行后报告能回执实际使用的样式差异。
4. 测试能读取稳定的差异摘要属性。
