# 交付名称 PresetLabel 运行时归一执行记录

日期：2026-06-30

## 本轮结论

上一轮把交付版本显示名目录下沉，并让场景族推荐、输出设置页、场景摘要、快速执行详情共用同一套名称。本轮继续把这条链路推进到真正执行阶段：`{preset_label}` 在核心 Pipeline 输出路径和 Workbench 报告路径里，也会使用共享显示名。

这意味着历史场景或外部配置里如果仍写着 `Student version`、`Answer key`，只要它们通过 `{preset_label}` 参与文件名或报告目录渲染，运行时也会输出“学生版”“答案版”，不会在最后一步重新露出英文模板名。

## 原问题

上轮修完 UI 后，仍有两处运行时入口直接读取 `preset.label`：

- `src/pipeline/runner.py` 的 `_render_delivery_template()`。
- `src/ui/panels/workbench/execution_runtime.py` 的 `_delivery_report_stem()` 和 `_delivery_report_dir()`。

因此链路仍不完全：

1. 输出设置预览显示 `review/审阅稿`。
2. 实际 Pipeline 如果读取历史 `preset.label="Review copy"`，仍可能按英文生成文件名。
3. Workbench 报告 JSON/Markdown 路径也可能继续使用英文 label。

这会让“预览”和“真实产物”不一致。

## 本轮实现

涉及文件：

- `src/pipeline/runner.py`
- `src/ui/panels/workbench/execution_runtime.py`
- `tests/test_output_runtime_semantics.py`

主要变更：

- Pipeline 的 `{preset_label}` 渲染改为 `delivery_preset_display_name(preset)`。
- Workbench 报告 stem 的 `{preset_label}` 渲染改为 `delivery_preset_display_name(preset)`。
- Workbench 报告目录的 `{preset_label}` 渲染改为 `delivery_preset_display_name(preset)`。
- 新增测试覆盖标准英文 label 和用户自定义 label 的边界。

## 边界保持

本轮只改变 `{preset_label}` 的显示语义，不改变 `{preset_id}`：

- `{preset_id}` 继续是稳定技术编号，适合路径稳定引用。
- `{preset_label}` 代表用户可读交付名称，运行时应该和 UI 预览一致。
- 标准英文模板 label 会翻译，例如 `Answer key` -> “答案版”。
- 用户自定义 label 保留，例如 `Review package` 仍输出 `Review package`。

这和模板管理的“显示名优先，技术 ID 留作锚点”保持一致。

## 测试覆盖

新增测试：

- `test_pipeline_renders_preset_label_with_shared_display_name`
- `test_workbench_report_templates_render_preset_label_with_shared_display_name`

覆盖内容：

- 核心 Pipeline 中 `filename_template="{stem}_{preset_label}"` 且 `label="Student version"` 时，输出文件为 `source_学生版.docx`。
- Workbench 报告 stem 中 `label="Answer key"` 时，报告 stem 为 `source_答案版`。
- Workbench 报告目录中 `output_dir_template="{preset_label}"` 且 `label="Answer key"` 时，目录为 `答案版`。
- 自定义 `label="Review package"` 仍按自定义名称渲染。

已执行验证：

```text
python -X utf8 -m py_compile src\pipeline\runner.py src\ui\panels\workbench\execution_runtime.py tests\test_output_runtime_semantics.py
python -X utf8 -m pytest tests\test_output_runtime_semantics.py::test_pipeline_renders_preset_label_with_shared_display_name tests\test_output_runtime_semantics.py::test_workbench_report_templates_render_preset_label_with_shared_display_name -q
python -X utf8 -m pytest tests\test_output_runtime_semantics.py -q
python -X utf8 -m pytest tests\test_scene_panel_architecture.py tests\test_quick_execution_detail_architecture.py -q
```

结果：

```text
2 passed in 0.72s
25 passed in 6.95s
110 passed in 93.07s
```

## 后续建议

1. 输出区“交付名称”字段应补充 tooltip，明确它会影响 `{preset_label}` 和界面显示；“交付编号”则影响 `{preset_id}` 和稳定路径。
2. 执行报告 payload 中若还有直接展示 `preset.label` 的字段，可以继续改为同时输出 `preset_label_display` 与 `preset_id`，避免报告读者混淆。
3. 历史场景迁移可考虑只在显示/运行时投影，不强行改用户文件，保持兼容。
