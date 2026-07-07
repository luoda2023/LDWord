# ExecutionPrereview 策略行当前态闭环执行记录

日期：2026-06-30

## 1. 本轮判断

上一轮已经打通：

```text
点击策略项
-> 预览切换到对应分区
-> 仍可跳转到场景分区样式修正入口
```

但还缺一个直接影响可读性的反馈：

```text
预览区已经切到“致谢”
策略区却没有显示“致谢”这一行是当前预览对象
```

这会让用户需要靠记忆判断“当前预览对应哪一项”。本轮补的是当前态，而不是再加说明文字。

## 2. 设计边界

当前态不能和开关状态混在一起：

| 状态 | 含义 | 例子 |
| --- | --- | --- |
| checked | 是否启用独立样式 | 参考文献开启独立样式 |
| current | 当前预览/当前焦点对象 | 预览区正在看致谢 |
| activated | 用户点了一行 | 用户点击致谢行 |

因此本轮新增的是：

```text
current_policy_key
style_policy_row_current
```

而不是复用 toggle checked。

## 3. 本轮代码改动

### 3.1 `StylePolicyToggleList`

文件：

```text
src/shared/ui/style_policy_toggle_list.py
```

新增：

```python
current_policy_key()
set_current_policy_key(key) -> bool
```

每个 row 和 label 现在带：

```text
style_policy_row_key
style_policy_row_current
```

列表自身带：

```text
style_policy_current_key
```

当前行会使用主题色：

```text
background = theme.bg_selected
border = theme.border_focus
label color = theme.primary
label weight = theme.font_weight_emphasis
```

### 3.2 `StylePolicyControlDeck`

文件：

```text
src/shared/ui/style_policy_control_deck.py
```

新增透传：

```python
current_policy_key()
set_current_policy_key(policy_key) -> bool
```

deck 自身也同步：

```text
style_policy_current_key
```

调用方不需要拿内部 `toggle_list`。

### 3.3 `QuickExecutionDetail`

文件：

```text
src/ui/panels/workbench/quick_execution_detail.py
```

执行前复核每次重新应用样式投影后，都会从当前 preview projection 取出分区 key：

```python
preview_key = getattr(style_projection.preview_projection, "variant_key", "")
self._style_prereview_preview_variant_key = preview_key
self._style_prereview_policy_deck.set_current_policy_key(preview_key)
```

所以：

- 初始预览“参考文献”时，参考文献行是当前态。
- 点击“致谢”后，预览切到致谢，致谢行变成当前态。
- checked 状态不受影响。

## 4. 链路结果

当前执行前复核链路变成：

```text
policy_selected("acknowledgment_body")
-> build_execution_prereview_style_projection(preview_variant_key="acknowledgment_body")
-> preview_projection.variant_key == "acknowledgment_body"
-> StylePreviewSurface.style_presentation_variant_key == "acknowledgment_body"
-> StylePolicyControlDeck.style_policy_current_key == "acknowledgment_body"
-> row["acknowledgment_body"].style_policy_row_current == True
```

这让用户看到三处一致：

| 区域 | 当前对象 |
| --- | --- |
| 策略行高亮 | 致谢 |
| 预览区标题 | 致谢 |
| 修正定位 | `acknowledgment_body` |

## 5. 测试覆盖

新增或更新的断言：

- `StylePolicyToggleList.set_current_policy_key("references_body")` 成功。
- 当前行 `style_policy_row_current is True`。
- 非当前行 `style_policy_row_current is False`。
- 无效 key 返回 `False`，清空当前态返回 `True`。
- `StylePolicyControlDeck` 透传 `current_policy_key`。
- 执行前复核初始当前策略项是默认预览分区。
- 点击“致谢”后，当前策略项切到 `acknowledgment_body`。
- 参考文献行从当前态恢复为非当前态。

已通过焦点验证：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_policy_toggle_list_manages_rows_signals_and_override_alias tests\test_small_widget_architecture.py::test_style_policy_control_deck_supports_readonly_without_internal_difference tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_policy_selection_switches_style_preview -q
```

结果：

```text
4 passed
```

随后追加共享链路回归：

```powershell
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py tests\test_small_widget_architecture.py tests\test_scene_panel_architecture.py tests\test_ui_exports.py tests\test_ui_layout_hardening.py tests\test_workbench_issue_navigation.py tests\test_field_display_names.py -q
```

结果：

```text
208 passed in 98.10s
```

## 6. 仍未完成

本轮闭合的是策略行当前态，不声明以下事项完成：

1. 尚未做截图级视觉验收，当前只通过 property 和样式代码验证。
2. 当前态是单选状态，不是多分区对比预览。
3. 当前态还没有键盘导航语义；目前主要由点击策略行驱动。
4. 跳转到 ScenePanel 后的高亮效果仍未做端到端截图验证。
5. 执行报告仍没有记录执行前当前复核分区。

## 7. 下一步

下一轮更适合继续处理端到端可见反馈：

```text
执行前复核当前策略行
-> 跳转到 ScenePanel
-> ScenePanel 高亮同一分区样式控件
-> 返回后仍保持当前预览分区
```

做到这一步，执行前复核才会更像一个连续的修正路径，而不是一组状态卡片。
