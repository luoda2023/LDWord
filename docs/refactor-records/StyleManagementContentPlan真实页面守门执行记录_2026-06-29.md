# StyleManagementContentPlan 真实页面守门执行记录

日期：2026-06-29

## 1. 背景

上一轮已经让 `StyleManagementBlock` 自身具备内容计划：

```text
source / scope / rules / editor / preview / receipt
```

并且把 `management_widgets` 降级为 legacy 兼容入口。但这还只证明共享控件本身有能力，不足以证明真实业务页面真的遵守这套内容边界。

本轮目标是把 content plan 守门推进到真实页面：

- 模板正文详情
- 场景分区样式

## 2. 本轮新增断言

### 2.1 模板正文详情

文件：

```text
tests/test_template_style_detail.py
```

新增断言：

```text
style_management_content_plan = source|scope|editor
style_management_has_rules = False
style_management_has_preview = False
style_management_has_legacy_widgets = False
```

含义：

- 模板正文详情只负责模板基线的来源、影响范围和字段编辑。
- 不混入规则控制。
- 不混入段落预览。
- 不使用 legacy 自由插入。

### 2.2 场景分区样式

文件：

```text
tests/test_scene_panel_architecture.py
```

新增断言：

```text
style_management_content_plan = source|scope|rules|difference|editor|preview
style_management_has_rules = True
style_management_has_preview = True
style_management_has_legacy_widgets = False
```

含义：

- 场景分区样式明确包含来源、范围、规则、编辑、预览。
- 规则控制走 `rule_control`。
- 段落预览走内置 preview。
- 不使用 legacy 自由插入。

## 3. 对设计一致性的意义

这一步把“模板管理和场景样式应该共享结构”从抽象描述变成真实页面证据：

| 页面 | 内容计划 | 用户心智 |
| --- | --- | --- |
| 模板正文详情 | `source|scope|editor` | 编辑模板基线 |
| 场景分区样式 | `source|scope|rules|difference|editor|preview` | 管理场景覆盖 |

这能防止两个页面继续只是在控件层复用、内容层却分叉。

## 4. 验证

已执行：

```powershell
python -X utf8 -m py_compile tests/test_template_style_detail.py tests/test_scene_panel_architecture.py
```

结果：通过。

```powershell
python -X utf8 -m pytest tests/test_template_style_detail.py::test_style_detail_syncs_widget_values_from_template tests/test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface -q
```

结果：

```text
2 passed
```

追加回归时发现并修复了共享响应式表单高度传播问题，详见：

```text
docs/refactor-records/AdaptivePairRow响应式高度传播修复记录_2026-06-29.md
```

聚焦验证：

```powershell
python -X utf8 -m pytest tests/test_ui_layout_hardening.py::test_adaptive_pair_row_stacks_when_narrow tests/test_ui_layout_hardening.py::test_reference_detail_pairs_stack_when_editor_width_is_narrow tests/test_ui_layout_hardening.py::test_style_detail_uses_global_stacked_spacing_and_compact_emphasis -q
```

结果：

```text
3 passed
```

## 5. 后续

下一步可以继续把 content plan 推到更多页面：

- 模板概览里的页面级预览可进入 `preview_slot`。
- Workbench 执行后样式来源可进入 `receipt_slot`。
- 只读复核态可使用 `readonly_review` 计划。

到那一步，来源、范围、规则、编辑、预览、回执就不只是共享 block 的字段，而是贯穿模板、场景和执行链路的统一信息架构。
