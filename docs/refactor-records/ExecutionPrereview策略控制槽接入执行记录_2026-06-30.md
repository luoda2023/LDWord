# ExecutionPrereview 策略控制槽接入执行记录

日期：2026-06-30

## 1. 本轮判断

上一轮已经把执行前复核接入了统一样式对象链路：

```text
build_execution_prereview_style_projection(...)
-> StyleObjectProjection
-> StyleManagementBlock.apply_style_object_projection(...)
-> source / difference / preview slots
```

但它仍然缺少 `rule_control`：

```text
模板管理 / 场景分区样式：有稳定控件槽位和投影协议
执行前复核：只看来源、差异、预览，没有策略状态区
```

这会造成两个问题：

1. 用户在执行前只知道“有独立样式”，但看不到哪些分区开了独立样式。
2. 场景分区样式已经使用 `StylePolicyControlDeck`，执行前复核却没有使用同一套策略控件，样式和控件语言仍不一致。

所以本轮不再继续加解释文字，而是补真实链路：

```text
场景样式策略投影
-> 执行前复核 StyleObjectProjection.policy
-> StyleManagementBlock.rule_control
-> StylePolicyControlDeck.apply_projection(...)
```

## 2. 控件边界

执行前复核不是编辑页，因此不能直接复用场景编辑页的交互语义。

本轮采用的边界是：

| 信息 | 位置 | 原因 |
| --- | --- | --- |
| 样式来源 | `StyleSourceSlot` | 保持“模板 + 场景分区”统一入口 |
| 独立样式状态 | `StylePolicyControlDeck(read_only=True)` | 复用场景策略控件，但禁止误操作 |
| 差异摘要 | 顶层 `StyleDifferenceSummarySlot` | 避免策略 deck 内部再重复显示差异 |
| 样式预览 | `StylePreviewSurface` | 与模板概览、场景分区预览共用 surface 协议 |

关键选择：

```python
StylePolicyControlDeck(
    object_name_prefix="wb_execution_prereview_policy",
    toggle_title="独立样式",
    show_difference=False,
    read_only=True,
)
```

这不是新增一套“执行前策略摘要 UI”，而是让执行前复核使用同一个策略 deck，只把可编辑能力关闭。

## 3. 本轮代码改动

### 3.1 `StylePolicyControlDeck`

文件：

```text
src/shared/ui/style_policy_control_deck.py
```

新增两个可复用参数：

```python
show_difference: bool = True
read_only: bool = False
```

作用：

- `show_difference=False`：允许调用方隐藏 deck 内部差异槽，避免和页面级 difference slot 重复。
- `read_only=True`：保留策略状态展示，但关闭 toggle 和批量动作按钮。
- `style_policy_show_difference` / `style_policy_control_read_only`：提供可测试、可巡检的 UI property。

这让同一个 deck 可以服务两类入口：

| 入口 | deck 模式 |
| --- | --- |
| 场景分区样式 | 可编辑，显示内部 difference |
| 执行前复核 | 只读，隐藏内部 difference |

### 3.2 `build_execution_prereview_style_projection`

文件：

```text
src/ui/panels/style_object_projection_builders.py
```

执行前复核 projection 现在带上：

```python
policy=build_scene_section_style_policy_projection(
    scene,
    template,
    preview_variant_key,
)
```

这意味着页面不需要自己拼策略状态，也不需要知道场景样式内部怎么统计 override。

### 3.3 `QuickExecutionDetail`

文件：

```text
src/ui/panels/workbench/quick_execution_detail.py
```

执行前复核新增：

```python
self._style_prereview_policy_deck = StylePolicyControlDeck(...)
```

并传给共享 block：

```python
StyleManagementBlock(
    mode="execution_prereview",
    source_slot=...,
    scope_slot=...,
    rule_control=self._style_prereview_policy_deck,
    difference_slot=...,
    preview_slot=...,
)
```

因此实际 content plan 从：

```text
source|scope|difference|preview
```

变为：

```text
source|scope|rules|difference|preview
```

## 4. 一致性收益

本轮后，三个入口的复用关系更清晰：

| 入口 | 来源 | 策略 | 差异 | 预览 |
| --- | --- | --- | --- | --- |
| 模板管理 | `StyleSourceSlot` / baseline projection | 暂无必要 | summary/projection | `StylePreviewSurface` |
| 场景分区样式 | `StyleSourceSlot` | `StylePolicyControlDeck` 可编辑 | deck 内部 difference | `StylePreviewSurface` |
| 执行前复核 | `StyleSourceSlot` | `StylePolicyControlDeck` 只读 | 顶层 difference | `StylePreviewSurface` |

真正统一的是投影和槽位协议：

```text
StyleObjectProjection.source  -> source slot
StyleObjectProjection.policy  -> rule_control.apply_projection(...)
StyleObjectProjection.difference -> difference slot
StyleObjectProjection.preview_projection -> preview slot
```

## 5. 可读性收益

执行前复核不再只告诉用户：

```text
有独立样式
```

而是可以直接展示：

```text
正文：跟随模板
参考文献：独立样式
附录：未启用/不可见
```

同时删除了两个潜在噪声：

1. 不额外增加“策略说明文本”。
2. 不重复显示策略 deck 内部 difference，避免同一差异摘要出现两次。

## 6. 测试覆盖

新增或更新的断言：

- 执行前复核 `_scene_card.rule_control` 指向 `StylePolicyControlDeck`。
- `style_management_rule_control_protocol == "policy_projection"`。
- `style_management_content_plan == "source|scope|rules|difference|preview"`。
- 执行前复核策略 deck 是只读：`style_policy_control_read_only is True`。
- 执行前复核隐藏 deck 内部 difference：`style_policy_show_difference is False`。
- `build_execution_prereview_style_projection(...)` 现在携带 `policy`。
- 只读 deck 中 toggle 和批量动作不会响应点击。

已通过关键回归：

```powershell
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_hides_style_difference_without_independent_sections tests\test_small_widget_architecture.py::test_style_policy_control_deck_supports_readonly_without_internal_difference tests\test_small_widget_architecture.py::test_style_policy_control_deck_applies_policy_projection tests\test_small_widget_architecture.py::test_style_object_projection_builders_cover_template_and_scene_styles -q
```

结果：

```text
5 passed
```

随后追加共享链路回归：

```powershell
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py tests\test_small_widget_architecture.py tests\test_scene_panel_architecture.py tests\test_ui_exports.py -q
```

结果：

```text
156 passed in 76.33s
```

## 7. 仍未打通

本轮闭合的是执行前复核的策略槽，不声明以下事项完成：

1. 模板管理正文页仍没有自己的策略区。当前模板正文是 baseline 编辑，不一定需要策略 deck，但如果后续出现“模板级策略/禁用项/锁定项”，应走同一 `StylePolicyControlDeck`。
2. 执行前复核仍只展示代表性分区预览，不是多分区预览列表。
3. `StylePolicyControlDeck(read_only=True)` 的策略项定位已在后续闭合，详见 `docs/refactor-records/ExecutionPrereview策略项定位闭环执行记录_2026-06-30.md`。
4. 执行前复核没有把策略状态写入执行报告，当前只在 UI 复核面闭合。
5. 目录、题注、表格等专用预览仍未统一进入 `StylePreviewSurface`。

## 8. 下一步

下一轮更适合继续处理“复核链路完整性”，而不是继续加说明文案：

```text
StylePolicyControlDeck read-only state
-> policy_selected(current section)
-> ScenePanel 对应 style variant
-> 修改后回流执行前复核 projection
```

做到这一步后，用户看到的就不是一组抽象卡片，而是一条可确认、可跳转、可修正、再回来看结果的闭环。
