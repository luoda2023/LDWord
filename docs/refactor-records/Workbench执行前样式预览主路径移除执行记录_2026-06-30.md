# Workbench 执行前样式预览主路径移除执行记录

日期：2026-06-30

## 1. 本轮结论

快速执行页的“场景与模板”卡片不再承载样式预览。

被移除的是主路径中的这块内容：

- `参考文献样式预览`
- 示例文本 `中文、English、数字 123 与括号（示例）。`
- 由 `StylePreviewSurface + StylePreview` 组成的外部 preview slot
- 执行前复核 projection 中的 `preview_projection`

这不是隐藏控件，而是从页面结构、状态字段、投影 builder、测试合同四层移除。

## 2. 为什么不应该放在这里

用户在快速执行页的主任务是：

1. 选择输入文档。
2. 确认当前使用哪个场景。
3. 确认当前关联哪个模板。
4. 发现是否存在独立分区样式差异。
5. 必要时跳到模板管理或分区样式配置处理。
6. 执行生成。

“样式预览”属于查看格式效果，不属于快速执行前必须完成的决策。它放在这里会产生三个问题：

- 视觉上抢占主路径空间，让“场景与模板”卡片看起来像样式编辑器。
- 信息职责和模板管理重复，用户会困惑：到底在哪里看模板、在哪里改模板、在哪里执行？
- 预览只展示一个分区样例，容易让用户误以为当前快速执行会直接编辑该分区。

因此，快速执行页更适合显示“来源、范围、差异摘要、跳转入口”，而不是承载格式预览。

## 3. 删除后的职责边界

| 区域 | 保留职责 | 不再承担 |
| --- | --- | --- |
| 快速执行 / 场景与模板 | 场景选择、模板选择、样式来源摘要、分区差异摘要、跳转入口 | 样式效果预览、分区样式编辑、策略开关 |
| 模板管理 | 查看模板整体样式、查看模板预览、编辑模板参数 | 执行前配置汇总 |
| 场景分区样式 | 独立分区样式编辑、恢复/覆盖策略、分区预览 | 快速执行主链路 |

这样边界更清楚：快速执行只告诉用户“现在会用什么”，需要看效果就点“看模板”，需要改单独分区就点“调分区”。

## 4. 实现变更

### 4.1 `QuickExecutionDetail`

文件：`src/ui/panels/workbench/quick_execution_detail.py`

已移除：

- `StylePreview` import
- `StylePreviewSurface` import
- `_style_prereview_preview_variant_key`
- `_style_prereview_preview_slot`
- `_style_prereview_preview`
- `preview_slot=self._style_prereview_preview_slot`
- `_sync_style_source_row()` 中的 preview variant 传递与回写

保留：

- `StyleSourceSlot`
- `StyleDifferenceSummarySlot`
- `StyleManagementBlock(mode="execution_prereview")`
- “看模板”跳转
- “调分区”跳转

### 4.2 `build_execution_prereview_style_projection`

文件：`src/ui/panels/style_object_projection_builders.py`

执行前复核 projection 现在只输出：

- `kind`
- `object_label`
- `source_label`
- `scope_label`
- `edit_state_label`
- `source`
- `difference`

已移除：

- `preview_variant_key` 参数
- `_execution_prereview_variant_key(...)`
- `scene_section_style_preview_projection(...)` 的执行前复核调用
- `preview`
- `preview_projection`
- `empty_preview_text`

这保证即使未来页面误传 preview slot，也不会从执行前复核 builder 获得可渲染预览数据。

## 5. 测试合同变化

### 5.1 快速执行页结构合同

文件：`tests/test_quick_execution_detail_architecture.py`

新合同：

- 不存在 `_style_prereview_preview_slot`
- 不存在 `_style_prereview_preview`
- `StyleManagementBlock.preview_slot is None`
- `effective_preview_slot is None`
- `style_management_content_plan == "source|scope|difference"`
- `style_management_slot_plan == "source|scope|difference"`
- `style_management_has_preview_slot is False`
- 源码中不得出现 `StylePreviewSurface(` 和 `preview_slot=self._style_prereview_preview_slot`

同时继续验证：

- `StyleSourceSlot` 仍存在。
- `StyleDifferenceSummarySlot` 仍存在。
- “看模板”仍发出 template 跳转。
- “调分区”仍发出 `scene_style_field / scene.section_styles.*.line_spacing_pt` 跳转。

### 5.2 投影 builder 合同

文件：`tests/test_small_widget_architecture.py`

新合同：

- `build_execution_prereview_style_projection(...).preview_projection is None`
- `preview.is_empty() is True`
- `policy is None`
- `difference` 继续保留，并能随独立分区数量变化。

## 6. 验证记录

已通过：

```powershell
python -X utf8 -m py_compile src\ui\panels\workbench\quick_execution_detail.py src\ui\panels\style_object_projection_builders.py tests\test_quick_execution_detail_architecture.py tests\test_small_widget_architecture.py
```

```powershell
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_uses_shared_style_source_row tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_hides_style_difference_without_independent_sections tests\test_quick_execution_detail_architecture.py::test_quick_execution_detail_style_prereview_uses_summary_without_policy_or_preview -q
```

结果：`3 passed`

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_object_projection_builders_cover_template_and_scene_styles -q
```

结果：`1 passed`

```powershell
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py -q
```

结果：`48 passed`

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py::test_style_management_block_named_modes_project_shared_contracts tests\test_small_widget_architecture.py::test_style_management_block_named_slots_update_plan tests\test_small_widget_architecture.py::test_style_object_projection_builders_cover_template_and_scene_styles -q
```

结果：`3 passed`

```powershell
python -X utf8 -m pytest tests\test_small_widget_architecture.py -q
```

结果：`49 passed`

```powershell
python -X utf8 -m pytest tests\test_template_style_detail.py tests\test_template_panel_architecture.py -q
```

结果：`33 passed`

## 7. 后续建议

下一步不建议再把任何“效果预览”放回快速执行卡片。

如果用户需要确认样式效果，快速执行页应提供明确动作：

- `看模板`：进入模板管理预览。
- `调分区`：进入场景分区样式编辑。

如果后续仍需要一个更轻量的提示，可以只在差异摘要中显示“存在 1 个独立分区样式”，不要加入示例文本、预览框或额外解释段落。
