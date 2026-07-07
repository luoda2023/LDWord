# ExecutionPrereview StylePreviewSurface 接入记录

日期：2026-06-30

后续进展：`StylePolicyControlDeck` 已作为通用策略控制外壳落地，`StyleRuleControlDeck` 已变为场景分区样式薄包装，详见 `docs/refactor-records/StylePolicyControlDeck抽象接入记录_2026-06-30.md`。

后续进展：`StylePolicyProjection` 已完成首片接入，详见 `docs/refactor-records/StylePolicyProjection首片接入记录_2026-06-30.md`。

后续进展：`StyleObjectProjection.policy` 已接入统一样式对象链路，详见 `docs/audits/样式策略投影与模板管理同构链路打通记录_2026-06-30.md`。

后续进展：场景样式摘要已并入同一份样式对象 projection，详见 `docs/audits/场景样式摘要与策略投影同源化记录_2026-06-30.md`。

后续进展：策略开关列表已泛化为 `StylePolicyToggleList`，详见 `docs/refactor-records/StylePolicyToggleList泛化与旧Override兼容记录_2026-06-30.md`。

后续进展：样式策略主链路已迁移到 `policy_*` API，详见 `docs/audits/样式策略PolicyAPI主链路迁移记录_2026-06-30.md`。

## 1. 本轮目标

上一轮已经把模板概览和场景分区样式接入 `StylePreviewSurface`：

```text
模板页面预览 -> StylePreviewSurface -> TemplateStylePreview
场景段落预览 -> StylePreviewSurface(show_metadata=False) -> StylePreview
```

但 Workbench 执行前复核仍只回答：

```text
本次用哪个模板
哪些分区有独立样式
与模板差异是什么
```

还没有回答用户更直觉的问题：

```text
执行前大概会长什么样？
```

本轮目标是给执行前复核补上轻量段落预览，并继续走统一样式对象链路：

```text
build_execution_prereview_style_projection(...)
-> StyleObjectProjection(preview + preview_projection)
-> StyleManagementBlock.apply_style_object_projection(...)
-> StylePreviewSurface.apply_preview_projection(...)
-> StylePreview
```

## 2. 预览口径

执行前复核不是编辑页面，不能把所有分区都展开成预览列表。当前采用一个保守口径：

```text
有独立样式：预览第一个独立样式分区
没有独立样式：预览默认分区的模板跟随效果
```

当前默认分区来自 `STYLE_VARIANTS[0]`，也就是 `references_body / 参考文献`。

这样做的好处：

- 不增加首屏复杂度。
- 不新造预览数据模型。
- 复用 `scene_section_style_preview_projection(...)` 的真实有效样式计算。
- 能在执行前给用户一个直观样式反馈。

## 3. Builder 接入

涉及文件：

```text
src/ui/panels/style_object_projection_builders.py
```

`build_execution_prereview_style_projection(...)` 现在额外输出：

```python
preview=StylePresentationEnvelope.from_preview_projection(preview_projection)
preview_projection=preview_projection
empty_preview_text="选择场景后预览样式"
```

新增 helper：

```python
_execution_prereview_variant_key(...)
```

选择顺序：

1. `source_projection.section_differences` 中的第一个 `variant_key`。
2. `scene.section_styles` 中第一个已知 `STYLE_VARIANTS` key。
3. `STYLE_VARIANTS[0].key`。
4. 没有可用 variant 时返回空。

## 4. StyleManagementBlock 接入

涉及文件：

```text
src/shared/ui/style_management_block.py
```

`apply_style_object_projection(...)` 现在在发现 preview 信息时，会同时驱动：

```text
preview_slot
editing_section.preview
```

其中 preview slot 优先调用：

```text
apply_preview_projection(...)
```

如果 slot 没有该方法，再退回：

```text
apply_envelope(...)
```

这让 `StyleManagementBlock.preview_slot` 不再只是静态容器，而可以消费 `StyleObjectProjection` 里的预览投影。

## 5. StylePreviewSurface 接入

涉及文件：

```text
src/shared/ui/style_preview_surface.py
```

新增方法：

```python
apply_preview_projection(projection, envelope=None, empty_text="")
```

它负责：

- 从 projection 生成或读取 `StylePresentationEnvelope`。
- 把 envelope + projection 交给 renderer。
- 同步 surface 自身的 presentation 属性。

这样执行前复核可以把 `StylePreviewSurface` 当作标准 preview slot，而不是直接调用内部 `StylePreview`。

## 6. QuickExecutionDetail 接入

涉及文件：

```text
src/ui/panels/workbench/quick_execution_detail.py
```

新增结构：

```text
_style_prereview_preview_slot = StylePreviewSurface(show_metadata=False)
_style_prereview_preview = StylePreview(...)
_scene_card = StyleManagementBlock(..., preview_slot=_style_prereview_preview_slot)
```

执行前复核的 content plan 现在从：

```text
source|scope|difference
```

变为：

```text
source|scope|difference|preview
```

因为 `StylePreviewSurface(show_metadata=False)` 不显示额外摘要文本，所以 UI 不会多一层解释，只会多一个段落预览。

## 7. 测试更新

新增/更新测试：

```text
tests/test_small_widget_architecture.py
tests/test_quick_execution_detail_architecture.py
```

覆盖点：

- 执行前复核 projection 现在带 `preview_projection`。
- 执行前复核 projection 的 preview title 是当前预览分区，例如 `参考文献`。
- QuickExecutionDetail 拥有 `_style_prereview_preview_slot`。
- preview slot 是 `StylePreviewSurface`。
- 内部 renderer 是 `StylePreview`。
- `StyleManagementBlock.preview_slot` 指向该 slot。
- 执行前复核 content plan 包含 `preview`。
- preview renderer 能收到 `section_paragraph` envelope。

## 8. 本轮验证

已执行语法检查：

```powershell
python -X utf8 -m py_compile src\shared\ui\style_preview_surface.py src\shared\ui\style_management_block.py src\ui\panels\style_object_projection_builders.py src\ui\panels\workbench\quick_execution_detail.py tests\test_small_widget_architecture.py tests\test_quick_execution_detail_architecture.py
```

结果：通过。

已执行聚焦测试：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_object_projection_builders_cover_template_and_scene_styles tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_hides_style_difference_without_independent_sections -q
```

结果：

```text
3 passed in 1.75s
```

已执行执行前详情完整架构回归：

```powershell
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py -q
```

结果：

```text
47 passed in 14.56s
```

已执行共享小控件和导出回归：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py tests\test_ui_exports.py -q
```

结果：

```text
44 passed in 1.40s
```

已执行设计系统和布局守门：

```powershell
python -X utf8 -m pytest tests\test_design_system_refactor.py::test_quick_execution_plain_card_headers_use_design_system_card_slots tests\test_ui_layout_hardening.py::test_template_and_scene_style_shells_keep_summary_preview_surface_order -q
```

结果：

```text
2 passed in 1.25s
```

已执行执行中心和最近结果回归：

```powershell
python -X utf8 -m pytest tests\test_workbench_execution_center.py tests\test_recent_run_panel.py -q
```

结果：

```text
99 passed in 4.55s
```

## 9. 当前未完成

本轮不声明以下事项完成：

1. 执行前复核仍只展示一个代表性分区预览，不是多分区预览列表。
2. `StyleManagementBlock.preview_slot` 可以驱动 `StylePreviewSurface`，但尚未强制 preview slot 必须实现统一协议。
3. 预览选择口径还没有显示“正在预览哪个分区”的显式用户文案，因为当前 `show_metadata=False` 避免首屏变重。
4. 执行前复核的策略区已在后续通过只读 `StylePolicyControlDeck` 接入，详见 `docs/refactor-records/ExecutionPrereview策略控制槽接入执行记录_2026-06-30.md`。
5. 目录、题注等专用预览仍未统一进 `StylePreviewSurface`。

## 10. 下一步建议

下一轮更适合继续做控件边界，而不是继续堆文案：

```text
scene state changed
-> build_scene_section_style_projection(...)
-> StyleManagementBlock.apply_style_object_projection(...)
-> all slots update
```

这样模板管理、场景分区和执行前复核才能继续共享同一套对象语言，而不是每个入口维护一组控件状态。
