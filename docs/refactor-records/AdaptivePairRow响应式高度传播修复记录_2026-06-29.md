# AdaptivePairRow 响应式高度传播修复记录

日期：2026-06-29

## 1. 背景

在把 `StyleManagementContentPlan` 守门推进到真实页面后，宽回归暴露了一个既有布局问题：

- 模板正文详情在宽屏下的表单行高度可能被分配为 88，而不是应有的 44。
- 参考文献详情在 480px 窄屏下应堆叠的字体/字号行没有稳定堆叠。

根因不在 content plan，而在响应式表单尺寸传播：

1. `AdaptivePairRow.minimumSizeHint()` 为了支持窄屏堆叠，会返回堆叠高度，但宽屏 inline 状态也可能被父布局按双行高度分配。
2. `TemplateFormGrid` 和 `InspectorForm` 没有显式汇总内部响应式子项的 `sizeHint()` / `heightForWidth()`。
3. `DesignSystemCard` 使用自绘 frame 后，卡片自身没有显式转发内部 layout 的 `sizeHint()`。
4. `ReferenceDetail` 独立样式卡显示时没有先预留内容高度，可能先以头部高度进入布局。

## 2. 本轮修复

### 2.1 AdaptivePairRow

文件：

```text
src/shared/ui/adaptive_pair_row.py
```

修复：

- 支持 `hasHeightForWidth()` / `heightForWidth(...)`。
- `sizeHint()` 根据当前方向返回 inline 或 stacked 高度。
- `minimumSizeHint()` 保持窄屏可收缩宽度，但高度根据当前方向返回单行或堆叠高度。
- 方向切换后刷新父级布局链。

### 2.2 TemplateFormGrid

文件：

```text
src/shared/ui/template_form_layout.py
```

修复：

- 保存内部 `AdaptivePairRow` 列表。
- 显式汇总 `sizeHint()` / `minimumSizeHint()`。
- 支持 `heightForWidth(...)`。

### 2.3 InspectorForm

文件：

```text
src/shared/ui/inspector_form.py
```

修复：

- 显式汇总内部表单项尺寸。
- 支持 `heightForWidth(...)`，把响应式高度继续向上传递。

### 2.4 DesignSystemCard

文件：

```text
src/shared/ui/design_system_card.py
```

修复：

- `sizeHint()` / `minimumSizeHint()` 显式转发内部主 layout。

### 2.5 ReferenceDetail

文件：

```text
src/ui/panels/template_reference_detail.py
```

修复：

- 独立样式卡显示时调用 `reserve_visible_height(...)`，避免先以头部高度参与布局。

## 3. 验证

已执行：

```powershell
python -X utf8 -m py_compile src/shared/ui/adaptive_pair_row.py src/shared/ui/template_form_layout.py src/shared/ui/inspector_form.py src/shared/ui/design_system_card.py src/ui/panels/template_reference_detail.py
```

结果：通过。

```powershell
python -X utf8 -m pytest tests/test_ui_layout_hardening.py::test_adaptive_pair_row_stacks_when_narrow tests/test_ui_layout_hardening.py::test_reference_detail_pairs_stack_when_editor_width_is_narrow tests/test_ui_layout_hardening.py::test_style_detail_uses_global_stacked_spacing_and_compact_emphasis -q
```

结果：

```text
3 passed
```

## 4. 结论

这次修复让共享响应式表单链路更稳：

- 宽屏 inline 行保持单行高度。
- 窄屏 stacked 行能稳定获得堆叠高度。
- 高度能从 `AdaptivePairRow` 经 `TemplateFormGrid`、`InspectorForm`、`DesignSystemCard` 正确传递到页面。

这对后续继续做模板管理和场景样式的一致化很重要，因为共享控件不仅要语义一致，也要在不同宽度下保持稳定布局。
