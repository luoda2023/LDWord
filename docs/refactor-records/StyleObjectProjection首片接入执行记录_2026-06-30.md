# StyleObjectProjection 首片接入执行记录

日期：2026-06-30

## 1. 本轮目标

上一轮规划判断，模板管理、场景分区样式、模板预览和执行回执要真正高度复用，不能只停留在共享字段控件或共享卡片外壳。它们还需要同一种“样式对象投影”：

```text
当前对象是谁
来源是什么
影响范围是什么
是否可编辑
摘要是什么
差异是什么
预览是什么
回执是什么
```

本轮先落 P0 的第一片：新增统一投影对象，并让它真实穿过模板正文详情和场景分区样式两条链路。

## 2. 新增对象

新增文件：

```text
src/shared/ui/style_object_projection.py
```

新增：

```python
StyleObjectProjection
```

它把现有已经分散存在的三类信息合并成一个对象：

- `StyleOwnerViewState`：来源、范围、编辑状态、字段区状态。
- `SummaryGridItem`：摘要卡片内容。
- `StylePresentationEnvelope`：预览和执行回执语义。

同时预留：

- `preview_projection`
- `difference`
- `receipt`
- `empty_preview_text`

这让后续不需要每个页面分别调用：

```text
apply_owner_state(...)
apply_preview_projection(...)
apply_comparison_projection(...)
set_summary_items(...)
```

而是可以先构造一个样式对象投影，再一次性交给共享块。

## 3. StyleManagementBlock 接入

文件：

```text
src/shared/ui/style_management_block.py
```

新增：

```python
apply_style_object_projection(...)
```

它统一负责：

1. 写入 `style_object_kind`。
2. 写入 `style_object_label`。
3. 写入 `style_object_source_label`。
4. 写入 `style_object_scope_label`。
5. 写入 `style_object_edit_state_label`。
6. 同步 summary items。
7. 同步 owner state。
8. 同步 difference slot。
9. 同步 preview。
10. 同步 receipt slot。

同时扩展：

```python
apply_preview_projection(..., envelope=None)
```

这样 preview 可以接收统一的 `StylePresentationEnvelope`，而不是只能由页面层单独传 projection。

本轮还补了一个小的状态安全点：当新的样式对象没有差异、预览或回执时，对应 slot 会清空，避免旧状态残留。

## 4. 模板正文详情接入

文件：

```text
src/ui/panels/template_style_detail.py
```

新增内部方法：

```python
_template_body_style_projection()
```

现在模板正文详情的同步路径变成：

```text
StyleDetail
-> _template_body_style_projection()
-> StyleObjectProjection.from_owner_state(...)
-> StyleManagementBlock.apply_style_object_projection(...)
```

原来的事实仍然保留：

- 未选择模板时，摘要显示“当前状态 / 未选择模板”。
- 选择模板后，摘要继续来自 `build_template_detail_summary_items(..., "tpl_style")`。
- 字段区状态继续来自 `template_body_style_owner_state(...)`。

区别是这些信息不再由模板详情分别推给不同控件，而是先合成一个样式对象投影。

## 5. 场景分区样式接入

文件：

```text
src/ui/panels/scene_panel.py
src/ui/panels/scene_style_rules_block.py
src/ui/panels/scene_style_override_sections.py
```

`SceneStyleRulesBlock` 和 `SceneStyleOverrideSection` 新增转发方法：

```python
apply_style_object_projection(...)
```

`_StyleRulesDetail._sync_style_editor()` 现在不再分别调用三条路径：

```text
apply_comparison_projection(...)
apply_preview_projection(...)
apply_owner_state(...)
```

而是先组装：

```python
StyleObjectProjection.from_owner_state(
    kind="scene_section_style",
    object_label=variant.label,
    owner_state=owner_state,
    preview_projection=preview_projection,
    difference=comparison_projection,
    empty_preview_text="选择分区后预览样式",
)
```

再交给：

```python
SceneStyleRulesBlock.apply_style_object_projection(...)
```

这一步的意义是：场景分区样式的来源、范围、只读折叠、差异摘要和预览已经开始由同一个对象驱动。

## 6. 导出与测试

文件：

```text
src/shared/ui/__init__.py
tests/test_ui_exports.py
```

`StyleObjectProjection` 已加入共享 UI 导出。

新增测试：

```text
tests/test_small_widget_architecture.py::test_style_management_block_applies_unified_style_object_projection
```

覆盖：

- `StyleManagementBlock` 能消费 `StyleObjectProjection`。
- 样式对象属性能写入 block。
- 摘要能同步。
- owner status 能同步。
- 只读状态能折叠字段区。
- preview 能同步 presentation envelope。
- difference slot 能同步。

架构测试也补充了源码约束：

- 模板正文详情必须引用 `StyleObjectProjection`。
- 模板正文详情必须调用 `apply_style_object_projection(...)`。
- 场景页必须引用 `StyleObjectProjection`。
- 场景样式 block/section 必须暴露 `apply_style_object_projection(...)`。

## 7. 本轮验证

已执行语法检查：

```powershell
python -X utf8 -m py_compile src\shared\ui\style_object_projection.py src\shared\ui\style_management_block.py src\shared\ui\__init__.py src\ui\panels\template_style_detail.py src\ui\panels\scene_style_override_sections.py src\ui\panels\scene_style_rules_block.py src\ui\panels\scene_panel.py tests\test_small_widget_architecture.py tests\test_template_style_detail.py tests\test_scene_panel_architecture.py tests\test_ui_exports.py
```

结果：通过。

已执行聚焦测试：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_management_block_applies_unified_style_object_projection tests\test_small_widget_architecture.py::test_style_management_block_named_modes_project_shared_contracts tests\test_ui_exports.py::test_shared_ui_exports_include_unified_controls -q
```

结果：

```text
3 passed
```

已执行模板和场景对象区测试：

```powershell
python -X utf8 -m pytest tests\test_template_style_detail.py::test_style_detail_reuses_shared_controls tests\test_template_style_detail.py::test_style_detail_updates_summary_grid_with_current_body_settings tests\test_scene_panel_architecture.py::test_scene_panel_uses_shared_card_header_and_flow_scope_layout tests\test_scene_panel_architecture.py::test_scene_style_override_section_wraps_owner_preview_and_surface tests\test_scene_panel_architecture.py::test_scene_style_rules_block_wraps_override_section_as_stable_object -q
```

结果：

```text
5 passed
```

追加执行共享小控件、模板详情和导出回归：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py tests\test_template_style_detail.py tests\test_ui_exports.py -q
```

结果：

```text
57 passed
```

追加执行完整场景架构回归：

```powershell
python -X utf8 -m pytest tests\test_scene_panel_architecture.py -q
```

结果：

```text
59 passed in 244.80s (0:04:04)
```

已执行格式检查：

```powershell
git diff --check -- src\shared\ui\style_object_projection.py src\shared\ui\style_management_block.py src\shared\ui\__init__.py src\ui\panels\template_style_detail.py src\ui\panels\scene_style_override_sections.py src\ui\panels\scene_style_rules_block.py src\ui\panels\scene_panel.py tests\test_small_widget_architecture.py tests\test_template_style_detail.py tests\test_scene_panel_architecture.py tests\test_ui_exports.py docs\refactor-records\StyleObjectProjection首片接入执行记录_2026-06-30.md
```

结果：无空白错误；命令只输出当前工作区已有的 LF/CRLF 提示。

## 8. 当前未完成

这轮只是 P0 首片，不把以下事项视为完成：

1. 还没有新增专门的 `StylePreviewSurface`。
2. 模板正文详情还没有显示同规格段落预览。
3. `StyleRuleControlDeck` 还没有升级为更通用的 `StylePolicyControlDeck`。
4. 执行前复核和执行后回执还没有完全改为 `StyleObjectProjection`。
5. 模板详情和场景详情仍保留一部分内部控件别名。
6. 场景概览首屏工程信息下沉还没有完成。

## 9. 下一步建议

下一轮应继续推进 P0，而不是马上跳到视觉大改：

```text
build_template_body_style_projection(...)
build_scene_section_style_projection(...)
build_execution_style_projection(...)
```

也就是说，把本轮临时在页面内组装的 projection，继续下沉成稳定 builder。等 builder 稳定后，再做 `StylePreviewSurface` 和策略控件归一，界面重排会更稳。

## 10. 本轮结论

本轮把“样式对象投影”从规划推进为可运行的首片：

```text
模板正文详情 -> StyleObjectProjection -> StyleManagementBlock
场景分区样式 -> StyleObjectProjection -> SceneStyleRulesBlock -> StyleManagementBlock
```

这一步不直接改变视觉，但它改变了后续优化的工作方式：以后不必在模板页、场景页、执行页分别拼来源、范围、差异和预览，而是让共享样式管理块消费同一种对象。
