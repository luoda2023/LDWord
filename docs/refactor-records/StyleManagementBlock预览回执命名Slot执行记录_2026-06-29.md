# StyleManagementBlock 预览与回执命名 Slot 执行记录

日期：2026-06-29

## 1. 背景

上一轮已经新增 `StyleManagementContentPlan`，让样式管理区可以声明：

```text
source / scope / rules / editor / preview / receipt
```

但当时只是内容计划，`StyleManagementBlock` 仍然只有：

- `rule_control`
- `management_widgets`

其中 `rule_control` 已经是命名 slot，但 `preview` 和 `receipt` 还没有正式入口。后续如果模板页、场景页或 Workbench 想放页面级预览、只读回执，很容易继续塞进 `management_widgets`，又回到“共享 block 被当普通容器”的问题。

本轮目标是先补齐 `preview_slot` 和 `receipt_slot`，不强制现有页面迁移，但给后续布局重排一个明确 API。

## 2. 本轮改动

`StyleManagementBlock` 新增参数：

```python
preview_slot: QWidget | None = None
receipt_slot: QWidget | None = None
```

新增属性：

```python
block.preview_slot
block.receipt_slot
```

行为：

- 传入 `preview_slot` 时，widget 被加入摘要卡内容区。
- 传入 `receipt_slot` 时，widget 被加入摘要卡内容区。
- `StyleManagementContentPlan` 会自动打开对应板块：
  - `preview_slot is not None` -> `style_management_has_preview = True`
  - `receipt_slot is not None` -> `style_management_has_receipt = True`

## 3. 为什么先做命名 slot

优秀设计需要的不是“所有东西都能塞进去”，而是“每类东西有明确归属”。

当前归属变成：

| 板块 | 命名入口 |
| --- | --- |
| `rules` | `rule_control` |
| `preview` | `preview_slot` 或内置 preview |
| `receipt` | `receipt_slot` |
| 兼容临时内容 | `management_widgets` |

`management_widgets` 仍然保留，是为了避免破坏历史调用方；但新页面应该优先使用命名 slot。

## 4. 和内容计划的关系

示例：

```python
StyleManagementBlock(
    mode="template_baseline_edit",
    preview_slot=preview_widget,
    receipt_slot=receipt_widget,
)
```

虽然 `template_baseline_edit` 默认计划是：

```text
source|scope|editor
```

但因为传入了命名槽位，运行时计划会变成：

```text
source|scope|editor|preview|receipt
```

这让“页面实际包含哪些板块”能被 Qt 属性和测试观察到，而不是只靠开发者记忆。

## 5. 测试守门

新增：

```python
tests/test_small_widget_architecture.py::test_style_management_block_named_preview_and_receipt_slots_update_plan
```

锁定：

- `block.preview_slot` 指向传入 widget。
- `block.receipt_slot` 指向传入 widget。
- 两个 widget 都进入 `DetailSummaryCard`。
- content plan 会变成 `source|scope|editor|preview|receipt`。
- `style_management_has_preview` 和 `style_management_has_receipt` 为 `True`。

## 6. 验证

已执行：

```powershell
python -X utf8 -m py_compile src/shared/ui/style_management_block.py tests/test_small_widget_architecture.py
```

结果：通过。

```powershell
python -X utf8 -m pytest tests/test_small_widget_architecture.py::test_style_management_block_named_modes_project_shared_contracts tests/test_small_widget_architecture.py::test_style_management_block_named_preview_and_receipt_slots_update_plan -q
```

结果：

```text
2 passed
```

## 7. 后续

下一步可以继续做两件事：

1. 把新页面或复核页里的页面级预览、执行回执逐步迁到 `preview_slot` / `receipt_slot`。
2. 给 `management_widgets` 增加更强的静态守门：允许历史兼容，但禁止新增业务页面继续使用自由插入承载规则、预览或回执。

## 8. 本轮结论

样式管理区的内容计划已经开始有真实 API 支撑。

`rules`、`preview`、`receipt` 不再只是文档里的板块名，而是可以通过命名 slot 进入共享 block，并同步为可测试的运行时属性。这是后续真正重排内容、减少冗余说明、保持模板管理一致性的前置条件。

## 9. 追加记录：management_widgets legacy 守门

追加日期：2026-06-29

`management_widgets` 继续保留为兼容入口，但已降级为可审计 legacy：

- `StyleManagementBlock.legacy_management_widgets`
- `style_management_has_legacy_widgets`

新增守门：

- `tests/test_small_widget_architecture.py::test_style_management_block_legacy_widgets_are_auditable`
- `tests/test_small_widget_architecture.py::test_style_management_block_business_code_uses_named_slots`

现在 `src/shared` 和 `src/ui` 的业务调用方不得再使用 `management_widgets=`。后续新入口应走 `rule_control`、`preview_slot` 或 `receipt_slot`。
