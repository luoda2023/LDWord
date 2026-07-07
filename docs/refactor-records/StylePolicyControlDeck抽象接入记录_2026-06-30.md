# StylePolicyControlDeck 抽象接入记录

日期：2026-06-30

后续进展：`StylePolicyProjection` 已完成首片接入，`StylePolicyControlDeck` 已支持 `apply_projection(...)`，详见 `docs/refactor-records/StylePolicyProjection首片接入记录_2026-06-30.md`。

后续进展：`StyleObjectProjection.policy` 与 `StyleManagementBlock` 分发链路已接入，详见 `docs/audits/样式策略投影与模板管理同构链路打通记录_2026-06-30.md`。

后续进展：场景样式摘要也已并入同一份 projection，详见 `docs/audits/场景样式摘要与策略投影同源化记录_2026-06-30.md`。

后续进展：`StylePolicyToggleList` 已落地，旧 `StyleOverrideToggleList` 改为兼容包装，详见 `docs/refactor-records/StylePolicyToggleList泛化与旧Override兼容记录_2026-06-30.md`。

后续进展：样式策略主链路已迁移到 `policy_*` API，详见 `docs/audits/样式策略PolicyAPI主链路迁移记录_2026-06-30.md`。

## 1. 本轮目标

前几轮已经完成：

```text
StyleSourceSlot：统一样式来源槽位
StylePreviewSurface：统一样式预览外壳
ExecutionPrereview preview：执行前复核接入轻量预览
```

剩下拖住“模板管理、场景分区、执行前复核高度复用”的核心控件之一，是 `StyleRuleControlDeck`。

它虽然已经是共享控件，但语义仍强绑定场景分区样式：

```text
独立样式
全部跟随模板
撤销恢复
将关闭独立样式：...
恢复独立样式：...
```

这些文案适合场景分区，但不适合作为更通用的策略控制外壳。本轮目标是把真实实现下沉到：

```text
StylePolicyControlDeck
```

让 `StyleRuleControlDeck` 成为场景分区样式的薄包装。

## 2. 新增共享控件

新增文件：

```text
src/shared/ui/style_policy_control_deck.py
```

新增类：

```python
StylePolicyControlDeck
```

它承接真实结构：

```text
StylePolicyControlDeck
-> StyleOverrideToggleList
-> StyleDifferenceSummarySlot
-> restore_all_button
-> undo_restore_all_button
```

并提供可配置文案：

- `toggle_title`
- `restore_all_label`
- `restore_all_disabled_tooltip`
- `restore_all_enabled_tooltip`
- `restore_all_enabled_labels_prefix`
- `undo_restore_all_label`
- `undo_restore_all_disabled_tooltip`
- `undo_restore_all_enabled_tooltip`
- `undo_restore_all_enabled_labels_prefix`

这样后续如果模板管理或执行复核需要策略区，不必复用写死“独立样式”的场景控件。

## 3. StyleRuleControlDeck 变为薄包装

涉及文件：

```text
src/shared/ui/style_rule_control_deck.py
```

迁移前：

```text
StyleRuleControlDeck
-> 创建 StyleOverrideToggleList
-> 创建 StyleDifferenceSummarySlot
-> 创建全部跟随模板按钮
-> 创建撤销恢复按钮
```

迁移后：

```text
class StyleRuleControlDeck(StylePolicyControlDeck)
```

它只负责传入场景分区样式文案：

```text
toggle_title="独立样式"
restore_all_label="全部跟随模板"
restore_all_enabled_labels_prefix="将关闭独立样式："
undo_restore_all_enabled_labels_prefix="恢复独立样式："
```

保留了原有：

- objectName：`{prefix}_rule_control_deck`
- `override_toggled`
- `restore_all_requested`
- `undo_restore_all_requested`
- `toggle_list`
- `difference_slot`
- `restore_all_button`
- `undo_restore_all_button`
- `set_restore_all_enabled(...)`
- `set_undo_restore_all_enabled(...)`

所以场景页不需要改调用方式。

## 4. API 边界

`StylePolicyControlDeck` 同时提供：

```text
policy_toggled
override_toggled
```

`policy_toggled` 是新语义，给未来通用策略区使用。

`override_toggled` 是兼容语义，保证 `StyleRuleControlDeck` 和既有场景分区样式不用重连信号。

这属于过渡期设计：先抽出通用外壳，再逐步把调用方从“override”语义迁移到“policy”语义。

## 5. 测试更新

更新文件：

```text
tests/test_small_widget_architecture.py
tests/test_scene_panel_architecture.py
tests/test_ui_exports.py
```

覆盖点：

- `StyleRuleControlDeck` 是 `StylePolicyControlDeck` 子类。
- `StylePolicyControlDeck` 承接 `StylePolicyToggleList`。
- `StylePolicyControlDeck` 承接 `StyleDifferenceSummarySlot`。
- `StyleRuleControlDeck` 仍保持原 objectName 和 tooltip 行为。
- `StylePolicyControlDeck` 可使用通用策略文案。
- `StylePolicyControlDeck.policy_toggled` 能发出开关变化。
- `StylePolicyControlDeck` 通过 `src.shared.ui` 导出。

## 6. 本轮验证

已执行语法检查：

```powershell
python -X utf8 -m py_compile src\shared\ui\style_policy_control_deck.py src\shared\ui\style_rule_control_deck.py src\shared\ui\__init__.py tests\test_small_widget_architecture.py tests\test_scene_panel_architecture.py tests\test_ui_exports.py
```

结果：通过。

已执行聚焦测试：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_rule_control_deck_groups_toggles_comparison_and_batch_actions tests\test_small_widget_architecture.py::test_style_policy_control_deck_accepts_generic_policy_copy tests\test_scene_panel_architecture.py::test_scene_panel_uses_shared_card_header_and_flow_scope_layout tests\test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface tests\test_ui_exports.py::test_shared_ui_exports_include_unified_controls -q
```

结果：

```text
5 passed in 1.66s
```

已执行共享小控件和导出回归：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py tests\test_ui_exports.py -q
```

结果：

```text
45 passed in 1.54s
```

已执行完整场景架构回归：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py -q
```

结果：

```text
59 passed in 53.80s
```

已执行布局守门：

```powershell
python -X utf8 -m pytest tests\test_ui_layout_hardening.py::test_template_and_scene_style_shells_keep_summary_preview_surface_order -q
```

结果：

```text
1 passed in 1.08s
```

## 7. 当前边界状态

已经改善：

- 真实策略控制实现从 `StyleRuleControlDeck` 下沉到 `StylePolicyControlDeck`。
- 场景分区样式仍通过 `StyleRuleControlDeck` 使用原文案和原 API。
- 后续模板、场景、执行前复核可以共享“策略区外壳”，而不必复用场景专属文案。

仍未完成：

1. `StylePolicyControlDeck` 已改用 `StylePolicyToggleList`。
2. 现有场景主链路已迁移到 `policy_toggled`，旧 `override_toggled` 仍作为兼容信号保留。
3. 执行前复核已在后续实际使用只读 `StylePolicyControlDeck`；模板管理是否需要策略区仍待模板级策略场景确认。
4. 场景样式 summary 和批量动作主链路已收束到 projection，但兼容 setter 仍保留。

## 8. 下一步建议

下一轮可以继续做：

```text
场景概览卡片
分区样式策略区
执行前复核样式区
```

重点做可见文案减法，避免结构已经统一但界面仍显示内部策略语言。
