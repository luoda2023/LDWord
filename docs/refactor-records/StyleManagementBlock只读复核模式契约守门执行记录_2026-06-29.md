# StyleManagementBlock 只读复核模式契约守门执行记录

日期：2026-06-29

## 1. 本轮目标

上一轮文档已经确认：场景页和模板管理的差异不在底层字段控件，而在样式管理块的“成品结构”和页面任务边界。要继续往 `SceneStyleRulesBlock`、`SampleEvidenceBlock` 这种稳定对象区推进，第一步必须先保证 `StyleManagementBlock` 的模式契约不会漂移。

本轮选择落地 P0 护栏：补齐 `readonly_review` 模式的结构测试。

## 2. 为什么补 readonly_review

当前共享样式管理块已经有多种 mode：

| Mode | 用途 | 已有价值 |
| --- | --- | --- |
| `template_baseline_edit` | 模板正文排版编辑 | 模板管理主编辑入口 |
| `scene_section_rules` | 场景分区样式规则 | 场景页样式覆盖入口 |
| `template_overview_preview` | 模板概览预览 | 页面级预览槽位 |
| `execution_receipt_review` | 执行后样式回执 | Workbench / 最近结果复核 |
| `execution_prereview` | 执行前样式复核 | Workbench 执行前蓝图 |
| `readonly_review` | 只读样式复核 | 后续可承载只读预览和回执 |

已有测试已经覆盖了前几个主要模式，但 `readonly_review` 没有进入同一张契约测试。它恰好是“只读但需要预览/来源/回执”的边界模式，如果不加护栏，后续很容易出现两种分叉：

- 只读复核误挂字段编辑器，导致用户以为可以编辑。
- 只读复核缺少来源/预览/回执 slot，导致它不像模板管理，也不像 Workbench 回执。

## 3. 本轮代码变更

文件：`tests/test_small_widget_architecture.py`

在 `test_style_management_block_named_modes_project_shared_contracts` 中新增：

- `style_management_contract("readonly_review")` 的契约断言。
- `style_management_content_plan("readonly_review")` 的 slot 顺序断言。
- `StyleManagementBlock(mode="readonly_review")` 实例化断言。

新增守门点：

| 守门点 | 期望 |
| --- | --- |
| owner toolbar | 不显示 |
| owner status | 显示 |
| preview | 显示 |
| editor | 不在 content plan 中 |
| surface | 隐藏 |
| receipt | 保留命名 slot |
| layout | 不把 `editing_section` 作为主布局编辑区挂出 |

这相当于把“只读复核不是编辑页”写进测试，而不是靠约定记忆。

## 4. 验证结果

先跑新增目标测试：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_management_block_named_modes_project_shared_contracts -q
```

结果：

```text
1 passed in 0.79s
```

随后跑相关共享 UI 与面板结构测试：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py tests\test_ui_exports.py tests\test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface tests\test_template_style_detail.py::test_style_detail_reuses_shared_controls tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row -q
```

结果：

```text
42 passed in 2.06s
```

中途有一次按语义猜测测试名的命令未收集到用例；随后通过 `pytest --collect-only` 定位真实用例名并重新执行，最终验证通过。

## 5. 对模板管理一致性的意义

这一轮没有改视觉，但它让样式管理块的模式边界更硬：

- 模板编辑：可以编辑，有字段表面。
- 场景样式规则：可以在独立样式开启后编辑，有差异和预览。
- 执行前复核：只看来源、范围、差异，不编辑。
- 执行后回执：只看结果和证据，不编辑。
- 只读复核：可看来源、预览和回执，不编辑。

这样后续页面改造时，不需要每个调用方都自己判断“要不要显示 owner、preview、字段表面、回执”。调用方应该选择 mode，结构由 `StyleManagementBlock` 负责。

## 6. 后续继续执行点

### P1：抽 `SceneStyleRulesBlock`

下一步可以把 `_StyleRulesDetail` 中大量直接透传的内部控件收进 `SceneStyleRulesBlock`，让场景页只面向稳定对象：

```text
SceneStyleRulesBlock
  set_scene(...)
  focus_navigation_field(...)
  style_rules_changed
```

页面层不应继续知道 `rule_deck`、`editing_section`、`comparison_strip`、`style_surface` 的内部组合。

### P2：处理范围和样式规则继续切开

`scn_scope` 只回答“处理哪些内容”，`scn_style_rules` 只回答“样式跟模板还是独立覆盖”。这能自然删除大量解释性文字。

### P3：把核对依据做成 `SampleEvidenceBlock`

样本文件、请求说法、证据路径、生成状态和打开动作应成为一个对象化 block，避免继续散在场景概览的高级区里。

## 7. 本轮结论

本轮完成了一个小但关键的结构守门：`readonly_review` 已经和其它样式管理 mode 一样进入测试契约。后续真正重排场景页时，可以更放心地依赖 `StyleManagementBlock` 的模式语义，而不是继续靠页面层手工拼控件。
