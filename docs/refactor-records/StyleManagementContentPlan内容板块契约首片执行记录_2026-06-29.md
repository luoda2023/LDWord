# StyleManagementContentPlan 内容板块契约首片执行记录

日期：2026-06-29

## 1. 背景

前几轮已经把样式链路的控件和展示语义逐步收束：

- `StyleManagementBlock` 统一模板正文和场景分区样式的页面级外壳。
- `StyleEditingSection` 统一 owner、状态、预览和字段编辑外壳。
- `StylePresentationEnvelope` 统一模板预览、分区预览、执行回执的展示语义。

但还有一个更靠近信息架构的问题：页面知道自己用了哪个控件，却没有明确声明自己应该包含哪些内容板块。

这会导致后续继续出现两类偏差：

1. 场景页容易重新把“来源、范围、规则、编辑、预览、回执”混在同一段说明里。
2. 模板页和场景页虽然用了同一个 block，但用户看到的结构仍然可能不一致。

本轮目标不是重排视觉，而是先把内容板块计划变成代码契约。

## 2. 新增契约

新增：

```python
StyleManagementContentPlan
style_management_content_plan(...)
```

位置：

```text
src/shared/ui/style_management_block.py
```

计划包含六个板块：

| 板块 | 用户问题 | 说明 |
| --- | --- | --- |
| `source` | 样式从哪里来？ | 模板基线、跟随模板、独立样式 |
| `scope` | 影响哪里？ | 模板全局、当前分区、场景分区 |
| `rules` | 是否覆盖模板？ | 独立样式开关、恢复模板、全部跟随 |
| `editor` | 当前能改什么？ | 字段编辑表面 |
| `preview` | 改完长什么样？ | 页面级或段落级预览 |
| `receipt` | 这次实际用了什么？ | 执行后只读回执 |

## 3. 当前模式计划

当前先给已有模式建立轻量计划：

| mode | content plan |
| --- | --- |
| `template_baseline_edit` | `source|scope|editor` |
| `scene_section_rules` | `source|scope|rules|difference|editor|preview` |
| `readonly_review` | `source|scope|preview|receipt` |
| `custom` | `source|scope|editor|preview` |

这不是最终视觉布局，只是先让每个共享 block 明确“自己包含哪些语义板块”。

## 4. Runtime 属性

`StyleManagementBlock` 现在会同步这些 Qt 属性：

```text
style_management_content_plan
style_management_has_source
style_management_has_scope
style_management_has_rules
style_management_has_editor
style_management_has_preview
style_management_has_receipt
```

作用：

- 测试可以直接验证模式边界。
- 后续视觉检查可以基于属性判断页面是否缺板块。
- 后续删除冗余文案时，可以用这些属性判断文案是否已经能由控件承担。

## 5. 当前不做什么

本轮刻意不做这些事：

1. 不重排模板页和场景页视觉布局。
2. 不新增 receipt slot。
3. 不删除主界面文案。
4. 不改变现有 owner/status/preview/editor 控件创建顺序。

原因是当前最重要的是先让“内容边界”可见、可测、可复用。视觉重排应该在这个契约稳定后再做。

## 6. 测试守门

新增或更新：

- `tests/test_small_widget_architecture.py::test_style_management_block_named_modes_project_shared_contracts`
- `tests/test_ui_exports.py::test_shared_ui_exports_include_unified_controls`

锁定内容：

- 模板正文模式必须是 `source|scope|editor`。
- 场景分区样式模式必须是 `source|scope|rules|difference|editor|preview`。
- `StyleManagementContentPlan` 和 `style_management_content_plan(...)` 必须从共享 UI 导出。

## 7. 验证

已执行：

```powershell
python -X utf8 -m py_compile src/shared/ui/style_management_block.py src/shared/ui/__init__.py tests/test_small_widget_architecture.py tests/test_ui_exports.py
```

结果：通过。

```powershell
python -X utf8 -m pytest tests/test_small_widget_architecture.py::test_style_management_block_named_modes_project_shared_contracts tests/test_ui_exports.py::test_shared_ui_exports_include_unified_controls -q
```

结果：

```text
2 passed
```

追加验证中发现并修复了两个场景导航图标漂移：

- `scn_evidence` 从 `file-text` 恢复为 `database`，与“核对依据”详情卡头保持一致。
- `scn_features` 从 `sliders-horizontal` 恢复为 `toggle-right`，与既有架构守门一致。

对应聚焦验证：

```powershell
python -X utf8 -m pytest tests/test_scene_panel_architecture.py::test_scene_panel_uses_shared_card_header_and_flow_scope_layout -q
```

结果：

```text
1 passed
```

## 8. 后续路线

下一步可以沿着 content plan 继续推进：

1. `rules`：把所有规则控制入口都收进命名 slot，禁止自由插入长说明。
2. `preview`：补正式 preview slot，使模板页面级预览、场景段落预览都能被 block 明确承认。
3. `receipt`：补只读 receipt slot，用于 Workbench 或执行复核态。
4. 文案减负：当 `source/scope/rules/editor/preview/receipt` 都有控件表达后，删除主界面里重复解释这些板块的长句。

## 9. 本轮结论

这轮把样式管理从“共享控件外壳”继续推进到“共享内容板块契约”。

用户还看不到大幅视觉变化，但代码已经能回答一个关键问题：模板正文、场景分区、只读复核分别应该有哪些内容板块。这是后续真正重排界面、删除冗余文本、保持模板管理一致性的基础。

## 10. 追加记录：preview / receipt 命名 slot

追加日期：2026-06-29

在 content plan 建立后，继续补齐 `preview` 和 `receipt` 的命名入口：

- `StyleManagementBlock(preview_slot=...)`
- `StyleManagementBlock(receipt_slot=...)`

追加效果：

- `preview_slot` 和 `receipt_slot` 会进入 `DetailSummaryCard` 内容区。
- `StyleManagementContentPlan` 会根据传入的命名 slot 自动打开 `preview` / `receipt` 板块。
- 新增 `tests/test_small_widget_architecture.py::test_style_management_block_named_preview_and_receipt_slots_update_plan` 锁定运行时属性。

这一步让 `preview` / `receipt` 不再只是计划字段，而是有明确 API 的样式管理板块。

## 11. 追加记录：真实页面守门

追加日期：2026-06-29

content plan 已推进到真实页面测试：

- `tests/test_template_style_detail.py::test_style_detail_syncs_widget_values_from_template`
- `tests/test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface`

当前锁定：

- 模板正文详情：`source|scope|editor`
- 场景分区样式：`source|scope|rules|difference|editor|preview`
- 两者都必须 `style_management_has_legacy_widgets=False`

这证明 content plan 不只是共享控件的小样例，而已经开始约束真实业务页面。
