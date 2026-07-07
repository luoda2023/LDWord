# StyleRuleControlDeck 分区样式控制区抽取执行记录

日期：2026-06-29

## 1. 本轮目标

上一轮已经把 `StyleManagementBlock` 接入模式契约，让模板正文和场景分区样式不再靠散落布尔参数定义主结构。本轮继续推进 P1：场景分区样式页内部仍然直接创建并管理：

- `StyleOverrideToggleList`
- `StyleComparisonStrip`
- `全部跟随模板` 按钮
- `撤销恢复` 按钮

这些控件都属于同一件事：

```text
当前场景的分区样式规则：哪些分区独立、和模板差在哪、是否批量恢复模板。
```

所以本轮目标是抽出共享控制区 `StyleRuleControlDeck`，让 `SceneStyleOverrideSection` 不再直接拼这组控件。

## 2. 本轮代码落点

### 2.1 新增共享控制区

文件：

- `src/shared/ui/style_rule_control_deck.py`

新增：

- `StyleRuleControlDeck`

职责：

| 能力 | 说明 |
| --- | --- |
| 独立样式开关 | 内部持有 `StyleOverrideToggleList` |
| 模板/当前/差异对照 | 内部持有 `StyleComparisonStrip` |
| 全部跟随模板 | 内部持有 `restore_all_button` |
| 撤销恢复 | 内部持有 `undo_restore_all_button` |
| 信号转发 | `override_toggled`、`restore_all_requested`、`undo_restore_all_requested` |
| 状态方法 | `set_override_row_visible()`、`apply_comparison_projection()`、`set_restore_all_enabled()`、`set_undo_restore_all_enabled()` |

对象命名保持兼容：

```text
{prefix}_override_list
{prefix}_comparison
{prefix}_restore_all_template
{prefix}_undo_restore_all_template
```

这样不破坏现有测试、导航定位和调试习惯。

### 2.2 场景分区样式接入 deck

文件：

- `src/ui/panels/scene_style_override_sections.py`

变更：

- 不再直接创建 `StyleOverrideToggleList`。
- 不再直接创建 `StyleComparisonStrip`。
- 不再直接创建两个批量恢复按钮。
- 新增 `self._rule_control_deck = StyleRuleControlDeck(...)`。
- `StyleManagementBlock(..., rule_control=self._rule_control_deck)`。
- 对外兼容属性仍保留：
  - `toggle_list`
  - `toggles`
  - `rows`
  - `toggle_labels`
  - `comparison_strip`
  - `restore_all_button`
  - `undo_restore_all_button`

判断：

这让场景页仍然能保持原交互，但控件所有权更清楚。后续如果模板管理要展示“哪些场景覆盖了此模板”的只读控制区，也能复用 deck 或扩展其只读模式。

### 2.3 共享 UI 导出

文件：

- `src/shared/ui/__init__.py`

新增导出：

- `StyleRuleControlDeck`

## 3. 本轮测试

新增/扩展：

- `tests/test_small_widget_architecture.py::test_style_rule_control_deck_groups_toggles_comparison_and_batch_actions`
- `tests/test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface`

验证点：

- Deck 统一创建独立样式开关、差异条和两个批量动作按钮。
- Deck 能转发开关、全部恢复、撤销恢复信号。
- Deck 能更新差异条状态。
- Deck 能隐藏单个分区开关行。
- Deck 维护与旧实现一致的 objectName。
- `SceneStyleOverrideSection` 实际通过 `rule_control_deck` 暴露这些控件。

已运行：

```powershell
python -X utf8 -m py_compile src/shared/ui/style_rule_control_deck.py src/shared/ui/__init__.py src/ui/panels/scene_style_override_sections.py tests/test_small_widget_architecture.py tests/test_scene_panel_architecture.py
```

结果：通过。

```powershell
python -X utf8 -m pytest tests/test_small_widget_architecture.py::test_style_rule_control_deck_groups_toggles_comparison_and_batch_actions tests/test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface tests/test_ui_exports.py -q
```

结果：

```text
3 passed
```

宽一点的相关回归：

```powershell
python -X utf8 -m pytest tests/test_small_widget_architecture.py tests/test_scene_panel_architecture.py tests/test_ui_exports.py -q
```

结果：

```text
85 passed
```

## 4. 当前边界

本轮抽取的是控制区所有权，不是重新设计布局。也就是说：

- 批量恢复按钮仍显示在 `StyleManagementBlock` 的 header action 区。
- `StyleRuleControlDeck` 目前服务场景分区样式，尚未接入模板管理的只读引用列表。
- 差异条仍使用 `StyleComparisonStrip`，尚未升级为更完整的差异预览控件。

这些边界是有意保留的，避免本轮同时改变控件结构和用户视觉位置。

## 5. 后续建议

下一步可以继续推进：

1. 给 `StyleRuleControlDeck` 增加只读模式，用于模板管理展示“哪些场景有分区独立样式”。
2. 将 `StyleDifferenceProjection` 更直接地喂给 deck，让 deck 自身能渲染简短差异摘要。
3. 把批量恢复前影响范围做成确认态，而不是只靠 tooltip。
4. 做截图审计，确认 deck 抽取后分区样式页高度和间距没有回退。

## 6. 本轮判断

这一轮让“分区样式规则”从场景页里的散装控件变成了一个可复用 deck。它不是最终优秀设计的全部，但它把边界又往前推了一步：场景页不再直接管理独立样式开关、差异条和批量恢复动作，这些都归入样式规则控制区。
