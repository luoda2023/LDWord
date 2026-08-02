# 样式策略 Policy API 主链路迁移记录

日期：2026-06-30

## 1. 本轮目标

上一轮已经完成：

```text
StylePolicyToggleList
StylePolicyToggleOption
```

并让旧的：

```text
StyleOverrideToggleList
StyleOverrideToggleOption
```

退为兼容包装。

但主链路仍存在旧 API 语义：

```text
override_toggled
set_override_checked(...)
set_override_row_visible(...)
override_toggle_for_variant(...)
has_variant(...)
```

这些名字适合“场景分区独立样式覆盖模板”，但不适合通用策略控件。 本轮目标是新增并迁移到：

```text
policy_toggled
set_policy_checked(...)
set_policy_row_visible(...)
policy_toggle_for_key(...)
has_policy_key(...)
```

旧 override API 保留为场景兼容别名。

## 2. 新增 API

### 2.1 StylePolicyControlDeck

文件：

```text
src/shared/ui/style_policy_control_deck.py
```

新增：

```text
has_policy_key(policy_key)
policy_toggle_for_key(policy_key)
set_policy_row_visible(policy_key, visible)
set_policy_checked(policy_key, checked)
```

兼容：

```text
set_override_row_visible(variant_key, visible)
```

现在只是转发到：

```text
set_policy_row_visible(...)
```

`apply_projection(...)` 内部也改为使用：

```text
set_policy_row_visible(...)
set_policy_checked(...)
```

### 2.2 SceneStyleOverrideSection

文件：

```text
src/ui/panels/scene_style_override_sections.py
```

新增信号：

```text
policy_toggled
```

新增方法：

```text
set_policy_row_visible(...)
set_policy_checked(...)
has_policy_key(...)
policy_toggle_for_key(...)
```

保留：

```text
override_toggled
set_override_row_visible(...)
```

作为场景兼容入口。

### 2.3 SceneStyleRulesBlock

文件：

```text
src/ui/panels/scene_style_rules_block.py
```

新增信号：

```text
policy_toggled
```

新增方法：

```text
set_policy_row_visible(...)
set_policy_checked(...)
has_policy_key(...)
policy_toggle_for_key(...)
```

旧方法仍保留：

```text
set_override_row_visible(...)
set_override_checked(...)
has_variant(...)
override_toggle_for_variant(...)
```

但现在这些旧方法都转发到 policy API。

## 3. 主链路迁移

文件：

```text
src/ui/panels/scene_panel.py
```

主链路已从：

```text
override_toggled
has_variant(...)
set_override_row_visible(...)
set_override_checked(...)
```

迁移为：

```text
policy_toggled
has_policy_key(...)
set_policy_row_visible(...)
set_policy_checked(...)
```

这意味着场景面板不再直接依赖旧 override API，旧 API 的职责只剩兼容。

## 4. 一致性收益

目前样式策略链路的主语已经统一为：

```text
policy
```

包括：

```text
StylePolicyProjection
StylePolicyControlDeck
StylePolicyToggleList
policy_toggled
set_policy_checked
policy_toggle_for_key
```

场景层仍然可以把业务叫做“独立样式”或“跟随模板”，但控件层不再被“override”这个场景专属词绑住。

这对后续复用很关键：

- 模板管理可以使用策略开关，不需要接受 override 命名。
- 执行前复核可以使用只读策略投影，不需要继承场景覆盖语义。
- 输出或批处理策略可以复用同一套 policy API。

## 5. 当前仍保留的兼容层

仍保留：

```text
override_toggled
set_override_checked(...)
set_override_row_visible(...)
has_variant(...)
override_toggle_for_variant(...)
```

保留原因：

1. 旧测试和外部调用可能仍在使用。
2. 场景分区样式业务本身仍可以称为 override。
3. 本轮目标是迁移主链路，不是一次性删除兼容 API。

建议后续把这些旧 API 文档化为：

```text
scene compatibility aliases
```

再逐步减少新代码调用。

## 6. 测试更新

更新文件：

```text
tests/test_small_widget_architecture.py
tests/test_scene_panel_architecture.py
```

新增或调整守门点：

- `StylePolicyControlDeck` 暴露 `has_policy_key(...)`。
- `StylePolicyControlDeck` 暴露 `policy_toggle_for_key(...)`。
- `StylePolicyControlDeck` 暴露 `set_policy_checked(...)`。
- `StyleRuleControlDeck` 优先监听 `policy_toggled`。
- `SceneStyleOverrideSection` 优先监听 `policy_toggled`。
- `SceneStyleRulesBlock` 优先使用 `set_policy_*` 和 `policy_toggle_for_key(...)`。
- `scene_panel.py` 不应再调用 `set_override_checked(...)`。
- `scene_panel.py` 不应再调用 `has_variant(...)`。
- `scene_panel.py` 应调用 `policy_toggled`、`has_policy_key(...)`、`set_policy_row_visible(...)`、`set_policy_checked(...)`。
- 旧 override API 仍通过少量兼容断言覆盖。

## 7. 本轮验证

已执行语法检查：

```powershell
python -X utf8 -m py_compile src\shared\ui\style_policy_control_deck.py src\ui\panels\scene_style_override_sections.py src\ui\panels\scene_style_rules_block.py src\ui\panels\scene_panel.py tests\test_small_widget_architecture.py tests\test_scene_panel_architecture.py
```

结果：通过。

已执行焦点测试：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_rule_control_deck_groups_toggles_comparison_and_batch_actions tests\test_small_widget_architecture.py::test_style_policy_control_deck_accepts_generic_policy_copy tests\test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface tests\test_scene_panel_architecture.py::test_scene_style_rules_block_wraps_override_section_as_stable_object -q
```

结果：

```text
4 passed in 1.50s
```

已执行共享小控件与导出回归：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py tests\test_ui_exports.py -q
```

结果：

```text
46 passed in 1.82s
```

已执行完整场景架构回归：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py -q
```

结果：

```text
59 passed in 59.71s
```

备注：当前 `.git` worktree 元数据仍指向旧的 `<LOCAL_PATH>` 路径，`git status` 会被该陈旧指针拦截；本轮验证以源码检查和 pytest 输出为准。

## 8. 下一步建议

下一轮可以开始做可见文案减法。

建议优先检查：

```text
场景概览卡片
分区样式策略区
执行前复核样式区
```

删除或迁移这类文本：

- 内部策略描述
- 调试式数量说明
- 英文 key
- 大段解释型风险文案

界面正文只保留：

```text
状态
动作
结果
必要边界
```
