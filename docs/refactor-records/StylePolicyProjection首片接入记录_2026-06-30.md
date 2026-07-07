# StylePolicyProjection 首片接入记录

日期：2026-06-30

后续进展：`StyleObjectProjection.policy` 与 `StyleManagementBlock` 分发链路已接入，场景分区样式 builder 已能产出 policy，详见 `docs/audits/样式策略投影与模板管理同构链路打通记录_2026-06-30.md`。

后续进展：场景样式 `summary_items` 已并入同一份 projection，详见 `docs/audits/场景样式摘要与策略投影同源化记录_2026-06-30.md`。

后续进展：`StylePolicyToggleList` 已完成泛化，详见 `docs/refactor-records/StylePolicyToggleList泛化与旧Override兼容记录_2026-06-30.md`。

后续进展：样式策略主链路已迁移到 `policy_*` API，详见 `docs/audits/样式策略PolicyAPI主链路迁移记录_2026-06-30.md`。

## 1. 本轮目标

上一轮已经抽出：

```text
StylePolicyControlDeck
```

并让：

```text
StyleRuleControlDeck -> StylePolicyControlDeck
```

但它当时仍然只是“可配置文案控件”。状态仍由调用方分散写入：

```text
set_restore_all_enabled(...)
set_undo_restore_all_enabled(...)
apply_comparison_projection(...)
toggle_list.set_checked(...)
```

这和现在已经形成的样式对象链路不一致：

```text
StyleObjectProjection
StyleSourceSlot.apply_projection(...)
StylePreviewSurface.apply_preview_projection(...)
```

本轮目标是新增：

```text
StylePolicyProjection
```

并让 `StylePolicyControlDeck` 支持：

```text
apply_projection(...)
```

## 2. 新增投影对象

涉及文件：

```text
src/shared/ui/style_policy_control_deck.py
```

新增三个 dataclass：

```python
StylePolicyToggleProjection
StylePolicyActionProjection
StylePolicyProjection
```

### 2.1 StylePolicyToggleProjection

描述一个策略开关：

```text
key
label
checked
visible
tooltip
```

### 2.2 StylePolicyActionProjection

描述一个动作按钮：

```text
label
enabled
labels
tooltip
```

其中 `labels` 继续用于拼接“将恢复：正文”这类批量动作 tooltip。

### 2.3 StylePolicyProjection

描述整个策略区：

```text
kind
title
toggles
difference
restore_all
undo_restore_all
```

每个 projection 都提供 `from_object(...)`，方便后续 builder 用普通对象或 dataclass 逐步迁移。

## 3. StylePolicyControlDeck.apply_projection

新增方法：

```python
StylePolicyControlDeck.apply_projection(projection)
```

它会同步：

- 策略类型：`style_policy_kind`
- 标题：`style_policy_title`
- 开关数量：`style_policy_toggle_count`
- 已开启数量：`style_policy_checked_count`
- 开关项：创建或更新 `StyleOverrideToggleList`
- 差异摘要：`StyleDifferenceSummarySlot.apply_projection(...)`
- 全部恢复动作
- 撤销恢复动作

程序化同步开关状态时，会同时更新 `ToggleSwitch.thumb_position`，避免视觉 thumb 和 checked 状态错位。

## 4. 当前兼容边界

本轮没有删除旧方法：

```text
set_restore_all_enabled(...)
set_undo_restore_all_enabled(...)
apply_comparison_projection(...)
set_override_row_visible(...)
```

原因是场景分区样式现有业务链路仍稳定使用这些 API。

当前边界是：

```text
新链路：apply_projection(...)
旧链路：继续可用
```

这让后续可以逐步迁移场景业务调用，而不是一次性改动所有状态同步代码。

## 5. 测试更新

更新文件：

```text
tests/test_small_widget_architecture.py
tests/test_scene_panel_architecture.py
tests/test_ui_exports.py
```

新增覆盖点：

- `StylePolicyProjection` 可以创建策略区状态。
- `StylePolicyControlDeck.apply_projection(...)` 可自动创建开关项。
- projection 能驱动开关 checked/visible。
- projection 能驱动恢复/撤销按钮 label、enabled 和 tooltip。
- `style_policy_toggle_count`、`style_policy_checked_count` 属性正确。
- `StylePolicyProjection`、`StylePolicyToggleProjection`、`StylePolicyActionProjection` 通过 `src.shared.ui` 导出。
- 场景架构守门确认 `StylePolicyControlDeck` 具备 `apply_projection`。

## 6. 本轮验证

已执行语法检查：

```powershell
python -X utf8 -m py_compile src\shared\ui\style_policy_control_deck.py src\shared\ui\__init__.py tests\test_small_widget_architecture.py tests\test_scene_panel_architecture.py tests\test_ui_exports.py
```

结果：通过。

已执行聚焦测试：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_policy_control_deck_applies_policy_projection tests\test_small_widget_architecture.py::test_style_policy_control_deck_accepts_generic_policy_copy tests\test_scene_panel_architecture.py::test_scene_panel_uses_shared_card_header_and_flow_scope_layout tests\test_ui_exports.py::test_shared_ui_exports_include_unified_controls -q
```

结果：

```text
4 passed in 1.44s
```

已执行共享小控件和导出回归：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py tests\test_ui_exports.py -q
```

结果：

```text
46 passed in 1.65s
```

已执行完整场景架构回归：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py -q
```

结果：

```text
59 passed in 61.11s (0:01:01)
```

## 7. 当前未完成

本轮仍不声明以下事项完成：

1. 场景分区业务层仍主要调用旧 API，还没有改成构造 `StylePolicyProjection`。
2. `StylePolicyToggleList` 和 `policy_*` API 已落地，旧 override API 仍作为兼容层存在。
3. `StyleObjectProjection.policy` 和场景样式 summary 已接入同一份 projection。
4. `SceneStyleRulesBlock` / `SceneStyleOverrideSection` 的旧 setter 仍作为兼容 API 保留。

## 8. 下一步建议

下一轮可以继续做可见文案减法：

```text
状态
动作
结果
必要边界
```

把内部策略描述、英文 key 和调试式数量说明继续移出界面正文。
