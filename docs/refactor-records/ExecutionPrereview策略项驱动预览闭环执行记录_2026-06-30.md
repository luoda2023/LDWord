# ExecutionPrereview 策略项驱动预览闭环执行记录

日期：2026-06-30

## 1. 本轮判断

上一轮已经把执行前复核的策略项变成可定位入口：

```text
StylePolicyControlDeck.policy_selected("references_body")
-> issue_repair_requested("scene_style_field", "references_body")
-> ScenePanel 分区样式开关
```

但用户路径仍然有一个断点：

```text
点了“致谢”
-> 可以跳去修
-> 但当前预览仍停留在默认代表分区
```

这会让策略区和预览区看起来不是同一个对象系统。真正合理的链路应该是：

```text
点哪个策略项
-> 预览哪个分区
-> 必要时跳去修改同一个分区
```

## 2. 设计边界

本轮没有让页面直接操作 `StylePreview`，而是继续走统一投影：

```text
QuickExecutionDetail selected variant key
-> build_execution_prereview_style_projection(..., preview_variant_key=...)
-> StyleObjectProjection.preview_projection
-> StyleManagementBlock.apply_style_object_projection(...)
-> StylePreviewSurface.apply_preview_projection(...)
```

这样做的原因：

1. 执行前复核仍然不认识预览控件内部结构。
2. 预览切换和来源、策略、差异一起由同一份 `StyleObjectProjection` 更新。
3. 后续如果模板管理或其他只读复核也需要“选项驱动预览”，可以复用 builder 参数和 preview slot 协议。

## 3. 本轮代码改动

### 3.1 builder 支持指定预览分区

文件：

```text
src/ui/panels/style_object_projection_builders.py
```

`build_execution_prereview_style_projection(...)` 新增：

```python
preview_variant_key: str = ""
```

内部选择逻辑变为：

```text
优先使用 preview_variant_key
-> 否则使用第一个有差异的分区
-> 否则使用第一个 section_styles 分区
-> 否则使用 STYLE_VARIANTS[0]
```

并且 policy 的 difference 也同步使用这个选中的分区：

```python
policy=build_scene_section_style_policy_projection(
    scene,
    template,
    selected_preview_variant_key,
)
```

### 3.2 执行前复核记录当前预览分区

文件：

```text
src/ui/panels/workbench/quick_execution_detail.py
```

新增状态：

```python
self._style_prereview_preview_variant_key = ""
```

场景切换时重置，策略项选择时更新：

```python
self._style_prereview_preview_variant_key = target
self._sync_style_source_row()
self.issue_repair_requested.emit("scene_style_field", target)
```

于是策略项选择同时完成两件事：

- 本地预览切换到该分区。
- 发出修正定位请求。

### 3.3 预览控件暴露当前分区 key

文件：

```text
src/shared/ui/style_preview.py
src/shared/ui/style_preview_surface.py
```

新增可观测 property：

```text
style_presentation_variant_key
```

`StylePreviewSurface` 和内部 `StylePreview` 都会同步该属性。这样测试和后续 UI 联动不用依赖文本标题推断当前预览对象。

## 4. 链路结果

当前执行前复核链路：

```text
策略区显示：
  参考文献：独立样式
  致谢：独立样式

用户点击“致谢”
-> policy_selected("acknowledgment_body")
-> _style_prereview_preview_variant_key = "acknowledgment_body"
-> build_execution_prereview_style_projection(preview_variant_key="acknowledgment_body")
-> preview_projection.variant_key == "acknowledgment_body"
-> StylePreviewSurface.style_presentation_variant_key == "acknowledgment_body"
-> StylePreview.title == "致谢"
-> issue_repair_requested("scene_style_field", "acknowledgment_body")
```

这让执行前复核里的三个区域开始指向同一对象：

| 区域 | 当前对象 |
| --- | --- |
| 策略项 | `acknowledgment_body` |
| 预览 | `acknowledgment_body` |
| 修正定位 | `acknowledgment_body` |

## 5. 测试覆盖

新增或更新的断言：

- builder 支持 `preview_variant_key="acknowledgment_body"`。
- 指定分区后 `preview_projection.variant_key == "acknowledgment_body"`。
- 指定分区后 preview title 是“致谢”。
- policy difference 也跟随选中的分区。
- 执行前复核点击策略项后 `_style_prereview_preview_variant_key` 更新。
- `StylePreviewSurface` 和内部 `StylePreview` 都暴露 `style_presentation_variant_key`。
- 点击策略项仍继续发出 `("scene_style_field", "acknowledgment_body")` 修正定位。

已通过焦点验证：

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_object_projection_builders_cover_template_and_scene_styles tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_policy_selection_switches_style_preview tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row -q
```

结果：

```text
3 passed
```

随后追加共享链路回归：

```powershell
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py tests\test_small_widget_architecture.py tests\test_scene_panel_architecture.py tests\test_ui_exports.py tests\test_ui_layout_hardening.py tests\test_workbench_issue_navigation.py tests\test_field_display_names.py -q
```

结果：

```text
208 passed in 103.29s
```

## 6. 仍未完成

本轮闭合的是策略项驱动预览，不声明以下事项完成：

1. 尚未做跨面板视觉验收：点击策略项后跳到 ScenePanel 的实际高亮效果还没有截图验证。
2. 执行前复核仍不是多分区预览列表，只是“选中哪个预览哪个”。
3. 预览区还没有显式展示“当前预览：致谢”这类轻量元信息，因为当前 `show_metadata=False`。
4. 执行报告仍没有沉淀执行前策略状态和当前复核分区。
5. 目录、题注、表格等专用预览仍未统一进入 `StylePreviewSurface`。

## 7. 下一步

后续已经补上“策略行当前态”：

```text
策略项选中
-> 预览切换
-> 策略行选中态/当前态
```

详见：

```text
docs/refactor-records/ExecutionPrereview策略行当前态闭环执行记录_2026-06-30.md
```

下一步仍适合继续做跨面板可见反馈：

```text
当前策略行
-> 跳转后 ScenePanel 高亮同一分区
```
