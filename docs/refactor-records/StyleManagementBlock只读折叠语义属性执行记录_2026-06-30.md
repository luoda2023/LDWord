# StyleManagementBlock 只读折叠语义属性执行记录

日期：2026-06-30

## 1. 本轮目标

前几轮已经把场景分区样式区逐步收敛到 `SceneStyleRulesBlock`，并删除了 `ScenePanel` 对段落编辑器内部控件的兼容别名。本轮继续往用户可见体验推进一小步：让“未启用独立样式时折叠字段编辑区”不再只是底层控件的 `hide/show`，而是成为 `StyleManagementBlock` 对外可观察的语义状态。

旧判断方式偏实现：

```python
section.editing_section.style_surface.isHidden()
```

新判断方式偏产品语义：

```python
section.management_block.property("style_management_editor_collapsed_by_readonly")
```

这让测试和后续页面逻辑能表达“编辑区因为只读而折叠”，而不是表达“某个子控件刚好隐藏了”。

## 2. 本轮代码调整

### 2.1 StyleManagementBlock 统一编辑区可见状态

文件：`src/shared/ui/style_management_block.py`

新增内部方法：

```python
_set_editor_surface_visible(visible: bool) -> None
```

它统一负责：

1. 控制 `editing_section.style_surface` 是否可见。
2. 同步 `style_management_editor_available`。
3. 同步 `style_management_editor_visible`。
4. 同步 `style_management_editor_collapsed`。
5. 同步 `style_management_editor_collapsed_by_readonly`。

现在初始化阶段和 `apply_owner_state(...)` 中的只读折叠都走这个方法，避免编辑区可见状态散落在不同位置。

### 2.2 语义属性

新增属性语义如下：

| 属性 | 含义 |
| --- | --- |
| `style_management_editor_available` | 当前 content plan 是否包含字段编辑区 |
| `style_management_editor_visible` | 字段编辑区当前是否展开显示 |
| `style_management_editor_collapsed` | 字段编辑区存在，但当前被折叠 |
| `style_management_editor_collapsed_by_readonly` | 字段编辑区因为只读/跟随模板状态被折叠 |

这些属性让后续样式管理区可以继续按“来源、范围、规则、差异、编辑、预览”的语义规划，而不需要外部直接检查底层控件。

## 3. 测试更新

### 3.1 布局烟测增加语义断言

文件：`tests/test_ui_layout_hardening.py`

更新 `test_scene_style_management_block_collapses_readonly_surface`：

只读/跟随模板时：

```text
style_management_editor_available == True
style_management_editor_visible == False
style_management_editor_collapsed == True
style_management_editor_collapsed_by_readonly == True
```

启用独立样式后：

```text
style_management_editor_available == True
style_management_editor_visible == True
style_management_editor_collapsed == False
style_management_editor_collapsed_by_readonly == False
```

### 3.2 架构守门测试增加约束

文件：`tests/test_scene_panel_architecture.py`

新增约束：

```text
StyleManagementBlock 必须包含 _set_editor_surface_visible(...)
StyleManagementBlock 必须同步 style_management_editor_visible
StyleManagementBlock 必须同步 style_management_editor_collapsed_by_readonly
不允许重新出现 style_surface.setVisible(editable) 这种散落写法
```

## 4. 对用户体验的意义

用户之前觉得“不说人话”，其中一个原因是：界面把禁用态字段直接铺出来，让用户必须读提示文字才知道“为什么灰掉”。现在已有的折叠机制可以减少这种负担，而本轮让这个折叠机制变成稳定语义。

后续可见 UI 可以继续沿着这个方向走：

```text
跟随模板
  只显示来源、差异结论、预览和启用入口
  不展示大面积灰色字段控件

已独立覆盖
  展开字段编辑区
  展示差异字段和恢复动作
```

这比继续增加说明文字更接近优秀设计：结构本身告诉用户当前能做什么。

## 5. 与模板管理一致性的关系

模板管理编辑的是“基线样式”，字段区天然可编辑；场景分区样式编辑的是“覆盖层”，字段区只有在启用独立样式后才可编辑。

因此两者不需要完全相同布局，但需要相同语义：

```text
是否有编辑区
编辑区是否展开
为什么不能编辑
当前来源是谁
当前对象是谁
```

本轮把“编辑区是否展开、是否因为只读折叠”变成 `StyleManagementBlock` 的公共语义，有利于模板管理、场景样式、执行回执继续共享同一个样式管理骨架。

## 6. 后续建议

### P0：将主界面长说明继续下沉

折叠状态有语义属性后，可以进一步清理主界面文案：

- 未启用独立样式时只保留短状态。
- 详细原因进入 tooltip 或状态 strip。
- 字段区折叠时不再靠长句解释。

### P1：把来源/规则/编辑/预览的可见性也语义化

后续可继续给 `StyleManagementBlock` 补类似属性：

```text
style_management_source_visible
style_management_rules_visible
style_management_difference_visible
style_management_preview_visible
```

这样“页面板块规划”会越来越像产品结构，而不是一堆控件拼装。

## 7. 本轮验证

已执行：

```powershell
python -X utf8 -m py_compile src\shared\ui\style_management_block.py
```

结果：通过。

已执行：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py::test_scene_panel_uses_shared_card_header_and_flow_scope_layout tests\test_scene_panel_architecture.py::test_scene_panel_controls_follow_template_management_contract tests\test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface tests\test_ui_layout_hardening.py::test_scene_style_management_block_collapses_readonly_surface -q
```

结果：

```text
4 passed in 2.74s
```

## 8. 本轮结论

本轮没有改变大量 UI，但把“只读时折叠字段编辑区”从控件实现状态提升成了 `StyleManagementBlock` 的可观察语义。这是继续减少冗余解释文字、提高可读性、并让场景样式管理和模板管理保持同一套产品语言的必要小步。
