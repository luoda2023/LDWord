# StylePolicyToggleList 泛化与旧 Override 兼容记录

日期：2026-06-30

后续进展：`policy_toggled`、`set_policy_checked(...)`、`set_policy_row_visible(...)`、`policy_toggle_for_key(...)`、`has_policy_key(...)` 已进入主链路，详见 `docs/audits/样式策略PolicyAPI主链路迁移记录_2026-06-30.md`。

## 1. 本轮目标

上一轮已经把场景样式的 `summary_items`、`policy`、`difference`、`preview` 收束到同一份 `StyleObjectProjection`。

剩下一个明显语义问题：

```text
StylePolicyControlDeck
-> StyleOverrideToggleList
```

通用策略控制区仍依赖带有“override / 覆盖”含义的列表类名。这个名字适合早期的“场景分区独立样式”，但不适合后续模板管理、执行前复核、只读策略摘要等更通用的策略区。

本轮目标是新增通用命名：

```text
StylePolicyToggleList
StylePolicyToggleOption
```

并让旧名继续兼容。

## 2. 新结构

新增文件：

```text
src/shared/ui/style_policy_toggle_list.py
```

负责真正实现：

- 标题
- 选项行
- `ToggleSwitch`
- `toggled = Signal(str, bool)`
- checked 同步
- row visible 同步
- theme 应用

兼容文件：

```text
src/shared/ui/style_override_toggle_list.py
```

现在只保留：

```text
StyleOverrideToggleOption(StylePolicyToggleOption)
StyleOverrideToggleList(StylePolicyToggleList)
```

也就是说，旧 import 不会断，但主实现已经转移到 policy 命名。

## 3. 主链路迁移

### 3.1 StylePolicyControlDeck

文件：

```text
src/shared/ui/style_policy_control_deck.py
```

已从：

```text
StyleOverrideToggleList
StyleOverrideToggleOption
```

迁移到：

```text
StylePolicyToggleList
StylePolicyToggleOption
```

内部 objectName 也从：

```text
{prefix}_override_list
```

调整为：

```text
{prefix}_policy_list
```

### 3.2 StyleRuleControlDeck

文件：

```text
src/shared/ui/style_rule_control_deck.py
```

场景规则 deck 仍是场景专用薄包装，但输入类型改为通用：

```text
Sequence[StylePolicyToggleOption]
```

### 3.3 SceneStyleOverrideSection

文件：

```text
src/ui/panels/scene_style_override_sections.py
```

构造分区开关时也改为使用：

```text
StylePolicyToggleOption
StylePolicyToggleList
```

场景层仍保留 `override_toggled` 信号，这是兼容语义；但控件实现不再依赖 override 命名。

### 3.4 shared ui 导出

文件：

```text
src/shared/ui/__init__.py
```

新增导出：

```text
StylePolicyToggleList
StylePolicyToggleOption
```

后续新代码应该优先使用这两个名字。

## 4. 对一致性和可读性的意义

这一步不是视觉微调，而是边界语义修正。

旧含义：

```text
这个列表只属于“分区样式覆盖”
```

新含义：

```text
这个列表属于“任意样式策略开关”
```

它让后续 UI 规划更自然：

- 场景分区样式：独立样式策略
- 模板管理：模板策略或锁定策略
- 执行前复核：只读策略摘要
- 输出设置：策略确认项

都可以复用同一个列表控件，而不需要接受“override”这个场景专属词。

## 5. 当前保留的兼容边界

以下内容仍保留：

```text
StyleOverrideToggleList
StyleOverrideToggleOption
override_toggled
override_toggle_for_variant(...)
set_override_checked(...)
set_override_row_visible(...)
```

保留原因：

1. 场景分区样式本身仍是“独立样式覆盖模板”的业务语义。
2. 旧测试和导航 API 仍使用 override 术语。
3. 一次性删除会扩大风险，当前阶段只把通用控件主实现迁走。

建议后续分两步处理：

```text
第一步：新增 policy_toggled / policy_toggle_for_key 等通用 API
第二步：把 override API 标成场景兼容层
```

## 6. 测试更新

更新文件：

```text
tests/test_small_widget_architecture.py
tests/test_scene_panel_architecture.py
tests/test_ui_exports.py
```

新增或更新守门点：

- `StylePolicyToggleList` 能管理行、信号、checked 和 visible。
- `StyleOverrideToggleList` 是 `StylePolicyToggleList` 的兼容子类。
- `StyleOverrideToggleOption` 是 `StylePolicyToggleOption` 的兼容子类。
- `StylePolicyControlDeck` 内部必须使用 `StylePolicyToggleList`。
- `SceneStyleOverrideSection` 内部必须使用 `StylePolicyToggleList` / `StylePolicyToggleOption`。
- 旧 `style_override_toggle_list.py` 不再承载 `ToggleSwitch(row...)` 实现，只做兼容包装。
- `src.shared.ui` 导出 `StylePolicyToggleList` 和 `StylePolicyToggleOption`。

## 7. 本轮验证

已执行语法检查：

```powershell
python -X utf8 -m py_compile src\shared\ui\style_policy_toggle_list.py src\shared\ui\style_override_toggle_list.py src\shared\ui\style_policy_control_deck.py src\shared\ui\style_rule_control_deck.py src\ui\panels\scene_style_override_sections.py src\shared\ui\__init__.py tests\test_small_widget_architecture.py tests\test_scene_panel_architecture.py tests\test_ui_exports.py
```

结果：通过。

已执行兼容探针：

```powershell
python -X utf8 -c "from src.shared.ui.style_policy_toggle_list import StylePolicyToggleList, StylePolicyToggleOption; from src.shared.ui.style_override_toggle_list import StyleOverrideToggleList, StyleOverrideToggleOption; print(StylePolicyToggleOption('a','A')); print(issubclass(StyleOverrideToggleList, StylePolicyToggleList)); print(issubclass(StyleOverrideToggleOption, StylePolicyToggleOption))"
```

结果：

```text
StylePolicyToggleOption(key='a', label='A', tooltip='')
True
True
```

已执行焦点测试：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_policy_toggle_list_manages_rows_signals_and_override_alias tests\test_small_widget_architecture.py::test_style_rule_control_deck_groups_toggles_comparison_and_batch_actions tests\test_small_widget_architecture.py::test_style_policy_control_deck_accepts_generic_policy_copy tests\test_ui_exports.py::test_shared_ui_exports_include_unified_controls -q
```

结果：

```text
4 passed in 0.89s
```

已执行场景焦点测试：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py::test_scene_panel_uses_shared_card_header_and_flow_scope_layout tests\test_scene_panel_architecture.py::test_scene_panel_scope_style_override_editor_writes_section_styles -q
```

结果：

```text
2 passed in 4.76s
```

已执行共享小控件与导出回归：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py tests\test_ui_exports.py -q
```

结果：

```text
46 passed in 1.95s
```

已执行完整场景架构回归：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py -q
```

结果：

```text
59 passed in 64.83s (0:01:04)
```

备注：当前 `.git` worktree 元数据仍指向旧的 `C:\Users\Administrator\...` 路径，`git status` 会被该陈旧指针拦截；本轮验证以源码检查、兼容探针和 pytest 输出为准。

## 8. 下一步建议

下一轮可以开始做可见文案减法：

```text
场景概览卡片
分区样式策略区
执行前复核样式区
```

重点删除或迁移：

```text
内部策略描述
调试式数量说明
英文 key
大段解释型风险文案
```

旧 override API 仍作为场景兼容别名保留，但新代码应继续优先使用 policy API。
