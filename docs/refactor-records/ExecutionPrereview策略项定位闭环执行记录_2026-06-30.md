# ExecutionPrereview 策略项定位闭环执行记录

日期：2026-06-30

## 1. 本轮判断

上一轮已经把执行前复核接入只读 `StylePolicyControlDeck`：

```text
StyleObjectProjection.policy
-> StyleManagementBlock.rule_control
-> StylePolicyControlDeck.apply_projection(...)
```

但链路仍不完整：

```text
用户能看到“参考文献开了独立样式”
但不能直接从这一项回到对应场景设置
```

这会让执行前复核停留在“展示状态”，不是“发现问题 -> 定位 -> 修正 -> 回流复核”的闭环。

本轮目标是补上策略项定位协议，而不是继续增加解释文案。

## 2. 设计边界

策略控件里有两种动作，必须分开：

| 动作 | 信号 | 含义 |
| --- | --- | --- |
| 开关改变 | `toggled` / `policy_toggled` | 用户修改策略状态 |
| 策略项激活 | `activated` / `policy_selected` | 用户想定位这一项 |

执行前复核是只读页，因此：

- toggle 仍然禁用，不能改状态。
- row/label 可以点击，用来定位到场景分区样式。
- 定位不冒充字段编辑，不伪造 `line_spacing_pt` 等具体字段。
- 裸 variant key 交给已有 `workbench_issue_navigation` 归一化。

## 3. 本轮代码改动

### 3.1 `StylePolicyToggleList`

文件：

```text
src/shared/ui/style_policy_toggle_list.py
```

新增：

```python
activated = Signal(str)
activate_policy(key) -> bool
```

并给每个 row / label：

```python
row.setProperty("style_policy_row_key", key)
row.mousePressEvent = lambda ...: self.activate_policy(key)
label.mousePressEvent = lambda ...: self.activate_policy(key)
```

这样点击文字区域也能定位，不要求用户点一个被禁用的开关。

### 3.2 `StylePolicyControlDeck`

文件：

```text
src/shared/ui/style_policy_control_deck.py
```

新增：

```python
policy_selected = Signal(str)
activate_policy(policy_key) -> bool
```

并透传列表层：

```python
self._toggle_list.activated.connect(self.policy_selected.emit)
```

调用方只依赖 deck，不需要知道内部 list 的存在。

### 3.3 `QuickExecutionDetail`

文件：

```text
src/ui/panels/workbench/quick_execution_detail.py
```

执行前复核接入：

```python
self._style_prereview_policy_deck.policy_selected.connect(
    self._on_style_policy_selected
)
```

定位时发出：

```python
self.issue_repair_requested.emit("scene_style_field", policy_key)
```

其中 `policy_key` 是 `references_body` 这类分区样式 key。已有导航适配会把它识别为：

```text
focus_kind = style_variant_toggle
normalized_key = scene.section_styles.references_body
```

### 3.4 显示名修正

文件：

```text
src/ui/adapters/field_display_names.py
```

修正裸分区样式 key 的用户可读名：

```text
scene.section_styles.references_body -> 参考文献正文
```

避免定位提示显示技术路径。

## 4. 链路结果

现在执行前复核的策略区链路变为：

```text
build_execution_prereview_style_projection(...)
-> policy: scene section style policy
-> StylePolicyControlDeck(read_only=True)
-> 用户点击“参考文献”
-> policy_selected("references_body")
-> issue_repair_requested("scene_style_field", "references_body")
-> Workbench navigation
-> ScenePanel scn_style_rules
-> focus style_variant_toggle
```

这比上一轮多打通了两件事：

1. 策略状态不只是能看，还能作为定位入口。
2. 执行前复核不需要知道 ScenePanel 内部控件，只发语义化目标。

## 5. 测试覆盖

新增或更新的断言：

- `StylePolicyToggleList.activate_policy("references_body")` 会发 `activated`。
- toggle 点击仍只发 `toggled`，不会混成定位信号。
- `StylePolicyControlDeck.activate_policy(...)` 会发 `policy_selected`。
- 只读 deck 的 toggle 仍禁用，但 row 激活仍可用。
- 执行前复核策略项激活会发出 `("scene_style_field", "references_body")`。
- `workbench_scene_field_focus_projection("scene_style_field", "references_body")` 可定位到 `style_variant_toggle`。
- `field_display_name("scene.section_styles.references_body") == "参考文献正文"`。

已通过焦点验证：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_policy_toggle_list_manages_rows_signals_and_override_alias tests\test_small_widget_architecture.py::test_style_policy_control_deck_supports_readonly_without_internal_difference tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row tests\test_workbench_issue_navigation.py::test_workbench_scene_field_focus_projection_normalizes_reusable_controls tests\test_field_display_names.py::test_field_display_name_translates_scene_and_template_paths -q
```

结果：

```text
5 passed
```

随后追加共享链路回归：

```powershell
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py tests\test_small_widget_architecture.py tests\test_scene_panel_architecture.py tests\test_workbench_issue_navigation.py tests\test_field_display_names.py tests\test_ui_exports.py -q
```

结果：

```text
170 passed in 77.20s
```

## 6. 仍未完成

本轮闭合的是“策略项能定位”，不声明以下事项完成：

1. 点击策略项后的跨面板导航视觉验收还没有用浏览器/截图验证。
2. 执行前复核策略项驱动预览已在后续闭合，详见 `docs/refactor-records/ExecutionPrereview策略项驱动预览闭环执行记录_2026-06-30.md`；但它仍不是多分区预览列表。
3. 策略项定位到的是分区样式开关，不是具体字段；如果后续有“差异字段列表”，应进一步定位到具体字段。
4. 执行报告还没有沉淀执行前策略状态。
5. 模板管理暂未引入模板级策略区，因为当前没有明确模板级策略对象。

## 7. 下一步

后续已经处理“预览粒度”的第一层：

```text
策略项选中/激活
-> 预览区同步显示该分区样式
```

详见：

```text
docs/refactor-records/ExecutionPrereview策略项驱动预览闭环执行记录_2026-06-30.md
```

后续仍可继续完善这条路径：

```text
看见独立样式
-> 点某个分区
-> 预览这个分区
-> 必要时跳去修改
-> 回来复核
```
