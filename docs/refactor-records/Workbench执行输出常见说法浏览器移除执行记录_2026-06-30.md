# Workbench 执行输出常见说法浏览器移除执行记录

日期：2026-06-30

## 1. 本轮结论

快速执行页的“执行输出”卡片不再展示“常见说法”浏览器。

移除内容包括：

- `常见说法` 标题
- `全部说法` 筛选下拉
- `4 条说法` 数量提示
- `打开依据` 按钮
- 常见说法列表
- 双击打开依据文件的交互

这不是隐藏，而是从 Workbench 快速执行页面结构、刷新逻辑、主题样式和测试合同中删除。

## 2. 为什么移除

快速执行页的执行输出区域应该只承担：

1. 执行按钮。
2. 执行状态。
3. 运行前问题处理。
4. 执行日志。
5. 生成结果与错误反馈。

“常见说法”属于场景覆盖与样本依据管理。它放在执行输出区会造成三个问题：

- 用户正在准备生成文档，却被迫看到一组场景建设证据。
- `打开依据` 像执行前必须操作，实际并不是生成文档的必需步骤。
- 它和场景管理页的依据浏览功能重复，职责边界不清。

因此，快速执行保留摘要里的守门状态即可；需要看依据时，应回到场景页。

## 3. 删除边界

| 位置 | 本轮处理 |
| --- | --- |
| Workbench 快速执行 / 执行输出 | 移除常见说法浏览器 |
| Workbench 快速执行 / 场景摘要 | 保留常见说法守门摘要 |
| 场景管理页 | 保留常见说法列表、筛选、打开依据 |
| 底层 `scene_summary_projection` | 保留 projection、过滤、文案和依据状态函数 |

这样快速执行页只显示执行相关内容；场景页继续承担依据浏览和覆盖审计。

## 4. 实现变更

### 4.1 `QuickExecutionDetail`

文件：`src/ui/panels/workbench/quick_execution_detail.py`

已删除：

- `_request_cell_panel`
- `_request_cell_filter`
- `_request_cell_count_label`
- `_request_cell_list`
- `_open_request_cell_fixture_btn`
- `_request_cell_specs`
- `_sample_fixture_output_dir`
- `current_request_cell_items(...)`
- `_refresh_request_cell_list(...)`
- `_selected_request_cell_id(...)`
- `_selected_request_cell(...)`
- `_selected_request_cell_fixture_docx_path(...)`
- `_sync_selected_request_cell_state(...)`
- `_open_request_cell_fixture_file(...)`
- Workbench 里的 `_format_request_cell_tooltip(...)`

同时移除对应 imports：

- `DEFAULT_SCENE_SAMPLE_FIXTURE_DIR`
- `scene_request_cell_count_text`
- `scene_request_cell_count_tooltip`
- `scene_request_cell_evidence_status_text`
- `scene_request_cell_evidence_status_tooltip`
- `scene_request_cell_filter_options`
- `scene_request_cell_fixture_specs_for_scene`
- `scene_request_cell_list_item_projection`
- `scene_request_cell_matches_filter`

保留：

- `build_scene_request_cell_summary_text(...)`

原因：摘要仍用于快速执行的场景概览，但浏览和打开依据不再属于快速执行输出。

### 4.2 测试合同

文件：`tests/test_quick_execution_detail_architecture.py`

旧合同：

- 快速执行页必须展示常见说法浏览器。
- 支持筛选常见说法。
- 支持打开依据 docx。

新合同：

- 快速执行页不创建 `_request_cell_panel`。
- 不创建 `_request_cell_filter`。
- 不创建 `_request_cell_list`。
- 不创建 `_request_cell_count_label`。
- 不创建 `_open_request_cell_fixture_btn`。
- 不暴露 `current_request_cell_items(...)`。
- 源码中不得出现 `wb_v2_request_cell_panel`、`wb_v2_request_cell_list`、`打开依据`。
- 仍保留 `build_scene_request_cell_summary_text(...)`。

文件：`tests/test_ui_copy_guardrails.py`

旧合同：

- 场景页和 Workbench 都要提供 request-cell tooltip helper。

新合同：

- 只在场景页守护常见说法 tooltip 文案。
- Workbench 不再提供 request-cell tooltip helper。

## 5. 验证记录

已通过：

```powershell
python -X utf8 -m py_compile src\ui\panels\workbench\quick_execution_detail.py tests\test_quick_execution_detail_architecture.py tests\test_ui_copy_guardrails.py
```

```powershell
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py::test_quick_execution_output_does_not_embed_request_cell_browser tests\test_quick_execution_detail_architecture.py::test_quick_execution_scene_summary_includes_profile_contracts -q
```

结果：`2 passed`

```powershell
python -X utf8 -m pytest tests\test_ui_copy_guardrails.py::test_request_cell_tooltips_use_reader_labels_in_scene_panel tests\test_ui_copy_guardrails.py::test_request_cell_list_item_projection_unifies_disambiguation_copy tests\test_ui_copy_guardrails.py::test_request_cell_filter_projection_is_readable_and_complete -q
```

结果：`3 passed`

```powershell
python -X utf8 -m pytest tests\test_quick_execution_detail_architecture.py -q
```

结果：`46 passed`

```powershell
python -X utf8 -m pytest tests\test_ui_copy_guardrails.py -q
```

结果：`15 passed`

## 6. 后续建议

快速执行页不建议再放任何“依据浏览器”。

如果确实需要提示用户场景依据状态，应该只保留一行摘要，并通过场景配置入口查看详情，而不是在执行输出区嵌入筛选列表和文件打开按钮。
