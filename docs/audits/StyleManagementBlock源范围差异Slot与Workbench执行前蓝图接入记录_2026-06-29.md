# StyleManagementBlock 源范围差异 Slot 与 Workbench 执行前蓝图接入记录

日期：2026-06-29

## 1. 本轮目标

上一轮已经把 Workbench 执行前差异摘要接到“场景与模板”卡里，但当时仍有一个边界没有闭合：

```text
Workbench 执行前只有 style_management_mode = execution_prereview 的属性标记，
真实容器仍是普通 Card。
```

这意味着它还没有真正进入 `StyleManagementBlock` 的页面蓝图，也没有真实 `source_slot / scope_slot / difference_slot`。

本轮目标：

1. 给 `StyleManagementBlock` 增加 `source_slot`、`scope_slot`、`difference_slot`。
2. 将 Workbench 执行前“场景与模板”从普通 `Card` 迁移为 `StyleManagementBlock(mode="execution_prereview")`。
3. 保持界面不重复展示“分区范围”，先让 `StyleSourceCompactRow` 所在组合槽同时声明为 source 和 scope。

## 2. 共享块接口变化

文件：

```text
src/shared/ui/style_management_block.py
```

新增参数：

```python
source_slot: QWidget | None = None
scope_slot: QWidget | None = None
difference_slot: QWidget | None = None
```

新增属性：

```python
block.source_slot
block.scope_slot
block.difference_slot
```

新增运行时审计属性：

```text
style_management_has_source_slot
style_management_has_scope_slot
style_management_has_difference_slot
style_management_has_preview_slot
style_management_has_receipt_slot
```

内容计划同步规则：

| slot | 影响 |
| --- | --- |
| `source_slot` | 开启 `source` 板块 |
| `scope_slot` | 开启 `scope` 板块 |
| `difference_slot` | 开启 `difference` 板块 |
| `preview_slot` | 开启 `preview` 板块 |
| `receipt_slot` | 开启 `receipt` 板块 |

保留：

```text
management_widgets
```

仍作为 legacy 兼容入口存在，但业务代码守门继续要求新链路不要使用它。

## 3. Workbench 执行前迁移

文件：

```text
src/ui/panels/workbench/quick_execution_detail.py
```

迁移前：

```text
Card("场景与模板")
-> 场景/模板选择行
-> StyleSourceCompactRow
-> StyleDifferenceSummarySlot
```

迁移后：

```text
StyleManagementBlock(mode="execution_prereview")
-> source_slot / scope_slot:
     场景/模板选择行
     StyleSourceCompactRow
-> difference_slot:
     StyleDifferenceSummarySlot
```

真实代码结构：

```python
self._scene_card = StyleManagementBlock(
    self,
    title="场景与模板",
    icon_name="boxes",
    object_name_prefix="wb_execution_prereview",
    mode="execution_prereview",
    source_slot=self._style_prereview_source_slot,
    scope_slot=self._style_prereview_source_slot,
    difference_slot=self._style_difference_slot,
)
```

这里 `source_slot` 与 `scope_slot` 暂时指向同一个组合 widget。

原因：

```text
当前 StyleSourceCompactRow 已经同时展示“模板”和“分区”两行。
如果立刻拆出独立 scope_slot，会在界面上重复出现分区信息。
```

这不是最终形态限制，而是这一轮的谨慎迁移：

```text
先让蓝图和命名 slot 成立，
再通过截图审计判断是否需要把范围拆成独立可视行。
```

## 4. 用户体验影响

对用户来说，这轮不应增加额外复杂度。

仍然看到：

```text
场景与模板选择
样式来源
必要时显示差异摘要
```

但工程上已经从：

```text
普通 Card + 临时控件
```

升级为：

```text
StyleManagementBlock(execution_prereview)
```

这意味着 Workbench 执行前与模板管理、场景分区、执行后回执进入同一套样式管理语义。

## 5. 测试更新

### 5.1 StyleManagementBlock slot 守门

文件：

```text
tests/test_small_widget_architecture.py
```

更新：

```text
test_style_management_block_named_slots_update_plan
```

验证：

- `source_slot`、`scope_slot`、`difference_slot`、`preview_slot`、`receipt_slot` 都可接入。
- slot parent 都落在 `DetailSummaryCard`。
- 内容计划同步为 `source|scope|difference|editor|preview|receipt`。
- 新增 `style_management_has_*_slot` 属性为 True。

### 5.2 Workbench 执行前架构守门

文件：

```text
tests/test_quick_execution_detail_architecture.py
```

更新：

```text
test_quick_execution_detail_uses_shared_style_source_row
```

新增断言：

- `_scene_card` 是 `StyleManagementBlock`。
- `source_slot` 和 `scope_slot` 指向 `_style_prereview_source_slot`。
- `difference_slot` 指向 `_style_difference_slot`。
- `style_management_content_plan = source|scope|difference`。
- `style_management_has_source_slot / scope_slot / difference_slot` 均为 True。

### 5.3 设计系统架构测试

文件：

```text
tests/test_design_system_refactor.py
```

更新：

```text
test_quick_execution_plain_card_headers_use_design_system_card_slots
```

旧断言要求：

```text
self._scene_card.set_header("场景与模板", icon_name="boxes")
```

新断言要求：

```text
StyleManagementBlock(... title="场景与模板", mode="execution_prereview")
source_slot=self._style_prereview_source_slot
difference_slot=self._style_difference_slot
```

## 6. 已运行验证

语法检查：

```powershell
python -X utf8 -m py_compile src\shared\ui\style_management_block.py src\ui\panels\workbench\quick_execution_detail.py tests\test_small_widget_architecture.py tests\test_quick_execution_detail_architecture.py tests\test_design_system_refactor.py
```

结果：通过。

焦点回归：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_management_block_named_slots_update_plan tests\test_small_widget_architecture.py::test_style_management_block_named_modes_project_shared_contracts tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_hides_style_difference_without_independent_sections tests\test_design_system_refactor.py::test_quick_execution_plain_card_headers_use_design_system_card_slots -q
```

结果：

```text
5 passed
```

## 7. 当前链路状态

| 页面/阶段 | 入口 |
| --- | --- |
| 模板正文编辑 | `StyleManagementBlock(mode="template_baseline_edit")` |
| 场景分区样式 | `StyleManagementBlock(mode="scene_section_rules", rule_control=...)` |
| 模板概览预览 | `StyleManagementBlock(mode="template_overview_preview", preview_slot=...)` |
| Workbench 执行前复核 | `StyleManagementBlock(mode="execution_prereview", source_slot=..., scope_slot=..., difference_slot=...)` |
| Workbench 执行后回执 | `StyleManagementBlock(mode="execution_receipt_review", receipt_slot=...)` |

这比上一轮更进一步：

```text
Workbench 执行前不再只是带有属性的普通 Card，
而是真正进入了 StyleManagementBlock 蓝图。
```

## 8. 当前边界

本轮仍未新建独立的可视 `StyleScopeSummarySlot`。

原因：

```text
StyleSourceCompactRow 当前已经展示“模板”和“分区”两行。
立即再放一个范围 slot 会造成界面重复。
```

后续如果截图审计确认来源行过载，可以拆成：

```text
StyleSourceSlot：只讲模板来源
StyleScopeSummarySlot：只讲分区范围
StyleDifferenceSummarySlot：只讲差异
```

但这应基于视觉审计，而不是为了代码纯度强行拆。

## 9. 下一步

建议继续推进：

1. 对 Workbench 执行前页面做截图审计，确认组合 source/scope slot 是否可读。
2. 如果来源行信息过密，再拆出 `StyleScopeSummarySlot`。
3. 将执行后回执补上可选 `difference_slot`，让执行前与执行后差异摘要闭环。
4. 继续清理主界面冗余文案，确保 `execution_prereview` 不出现内部 key 和长审计说明。

## 10. 本轮判断

这一轮的价值不是多显示了一个控件，而是把复用层级继续向上推了一层：

```text
从“共享控件”
到“共享 slot”
再到“共享页面蓝图”。
```

Workbench 执行前现在已经和模板管理、场景分区、执行后回执站在同一套 `StyleManagementBlock` 结构里。后续优化可以围绕 slot 的可读性继续打磨，而不是再从零组织页面。
