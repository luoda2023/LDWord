# 交付报告 Preset 显示名与 Raw 标签分层执行记录

日期：2026-06-30

## 本轮结论

上一轮已经把 `{preset_label}` 的真实输出路径打通到共享显示名。本轮继续处理报告链路：输出目标预检和结构化中间产物现在也能区分“用户可读显示名”和“原始 label”。

当前边界是：

- 输出目标预检面向用户，`label` 直接使用显示名，例如“答案版”。
- 结构化中间产物需要兼容和可追溯，所以保留 raw `label`，同时新增 `display_label`。

这样报告读者不会再只看到 `Answer key`，而排查时也还能看到历史 raw label。

## 原问题

上一轮修完运行时 `{preset_label}` 后，仍有两个报告入口没有完全归一：

- `OutputTargetPreflightItem.label` 仍从 `preset.label` 读取。
- 结构化中间产物里的 `preset` payload 只有 `label`，没有可读显示名字段。

这会造成一个微妙断点：

1. 输出文件名：`source_答案版.docx`
2. 报告路径：`答案版/source_答案版_changes.json`
3. 预检或中间产物：仍可能显示 `Answer key`

用户会以为这是两个不同的交付版本。

## 本轮实现

涉及文件：

- `src/pipeline/runner.py`
- `src/ui/panels/workbench/execution_runtime.py`
- `tests/test_output_runtime_semantics.py`

主要变更：

- `_planned_output_targets()` 创建 `OutputTargetPreflightItem` 时，`label` 改为 `delivery_preset_display_name(preset)`。
- `_delivery_preset_payload()` 保留 `label`，新增 `display_label`。
- 新增测试覆盖输出目标预检和结构化中间产物 payload。

## 字段边界

报告字段现在按用途分层：

- `preset_id`：稳定技术编号，用于定位和路径稳定性。
- `label`：原始 label，保留历史配置和用户输入。
- `display_label`：用户可读显示名，用于报告阅读和 UI 展示。

举例：

```json
{
  "preset_id": "answer_key",
  "label": "Answer key",
  "display_label": "答案版"
}
```

自定义 label 仍保留：

```json
{
  "preset_id": "review",
  "label": "Review package",
  "display_label": "Review package"
}
```

这保证了“标准模板名可翻译，自定义名称不覆盖”的边界。

## 测试覆盖

新增测试：

- `test_pipeline_output_target_preflight_uses_shared_delivery_display_label`
- `test_workbench_delivery_preset_payload_keeps_raw_and_display_labels`

覆盖内容：

- 输出目标预检中 `label="Answer key"` 的交付版本显示为“答案版”。
- 中间产物 preset payload 中 raw `label` 保留 `Answer key`。
- 同一 payload 中新增 `display_label="答案版"`。

已执行验证：

```text
python -X utf8 -m py_compile src\pipeline\runner.py src\ui\panels\workbench\execution_runtime.py tests\test_output_runtime_semantics.py
python -X utf8 -m pytest tests\test_output_runtime_semantics.py::test_pipeline_output_target_preflight_uses_shared_delivery_display_label tests\test_output_runtime_semantics.py::test_workbench_delivery_preset_payload_keeps_raw_and_display_labels tests\test_output_runtime_semantics.py::test_pipeline_renders_preset_label_with_shared_display_name tests\test_output_runtime_semantics.py::test_workbench_report_templates_render_preset_label_with_shared_display_name -q
python -X utf8 -m pytest tests\test_output_runtime_semantics.py -q
python -X utf8 -m pytest tests\test_scene_panel_architecture.py tests\test_quick_execution_detail_architecture.py -q
```

结果：

```text
4 passed in 0.74s
27 passed in 6.28s
110 passed in 82.31s
```

## 后续建议

1. Markdown/JSON 报告展示层如果直接渲染 `preset.label`，后续应优先展示 `display_label`，并在详情中保留 raw `label`。
2. Workbench 最近结果里的多版本产物列表目前多按 `preset_id` 标注，后续可以用 `display_label + preset_id tooltip` 的模式继续人话化。
3. 输出设置页“交付名称”字段仍值得补 tooltip，解释它和 `{preset_label}` 的关系。
