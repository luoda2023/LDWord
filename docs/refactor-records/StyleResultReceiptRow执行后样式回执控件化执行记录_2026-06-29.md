# StyleResultReceiptRow 执行后样式回执控件化执行记录

日期：2026-06-29

后续进展：

- 回执行已从 `set_summary(...)` 纯文本入口升级为优先消费 `StylePresentationEnvelope`：`ExecutionResultState` / `RecentRunState` 已携带 `style_source_envelope`，执行中心与最近结果面板改为 `apply_envelope(...)`，旧 `set_summary(...)` 仅作为兼容入口保留，详见 `docs/refactor-records/Workbench样式回执Envelope状态链路执行记录_2026-06-29.md`。

## 1. 本轮目标

上一轮已经把执行报告中的 `style_source` 回流到 Workbench UI，但展示方式仍是把 `style_source_summary` 拼进执行摘要文本。这样虽然能看到内容，却仍然有两个问题：

```text
1. 样式来源和普通执行摘要混在一起，不像一个可复用回执。
2. 执行中心、最近结果、后续可能的执行历史容易继续各自拼字。
```

本轮目标是把执行后的样式来源抽成只读共享控件，让“本次按哪个模板、哪些分区独立样式”成为独立回执行，而不是普通 summary 文本的一部分。

## 2. 本轮代码落点

### 2.1 新增共享回执行

文件：

- `src/shared/ui/style_result_receipt_row.py`

新增：

- `StyleResultReceiptRow`

职责：

| 能力 | 说明 |
| --- | --- |
| 标题 | 固定显示 `样式来源` |
| 正文 | 展示执行后的样式来源摘要 |
| 前缀清理 | 自动把 `样式来源：...` 拆成标题和正文，避免重复 |
| 空态 | 无摘要时自动隐藏 |
| 视觉 | 使用浅信息底色、边框和 `type-outline` 图标 |

接口：

```python
row.set_summary("样式来源：本次按模板“默认格式”处理；参考文献（行距）使用场景独立样式。")
row.summary_text()
row.detail.text()
```

### 2.2 执行中心接入

文件：

- `src/ui/panels/workbench/execution_center.py`

变更：

- 新增 `_style_receipt_row = StyleResultReceiptRow(...)`。
- 放在 `执行摘要` 标题和 summary 文本框之间。
- `set_result_state(...)` 不再把 `state.style_source_summary` 拼入 `QTextEdit`。
- 样式来源改由 `_style_receipt_row.set_summary(...)` 渲染。

结果：

```text
执行摘要：本次执行已完成
样式来源：本次按模板“默认格式”处理；参考文献（行距）使用场景独立样式。
```

两者在 UI 结构上分离。

### 2.3 最近结果接入

文件：

- `src/ui/panels/workbench/recent_run_panel.py`

变更：

- 新增 `_style_receipt_row = StyleResultReceiptRow(...)`。
- 放在最近结果 summary 下方、产物 meta 上方。
- `set_state(...)` 不再把 `state.style_source_summary` 拼入 `_summary`。
- 样式来源改由 `_style_receipt_row.set_summary(...)` 渲染。

### 2.4 共享 UI 导出

文件：

- `src/shared/ui/__init__.py`

新增导出：

- `StyleResultReceiptRow`

## 3. 本轮测试

新增/扩展：

- `tests/test_small_widget_architecture.py::test_style_result_receipt_row_projects_readonly_style_source_summary`
- `tests/test_workbench_execution_center.py::test_execution_center_result_state_renders_style_source_receipt`
- `tests/test_recent_run_panel.py::test_recent_run_panel_includes_style_source_summary`

验证点：

- 回执行空摘要时隐藏。
- 回执行会清理 `样式来源：` 前缀。
- 执行中心 summary 文本不再包含样式来源。
- 最近结果 summary 文本不再包含样式来源。
- 执行中心和最近结果都通过同一个回执行展示样式来源。

已运行：

```powershell
python -X utf8 -m py_compile src/shared/ui/style_result_receipt_row.py src/shared/ui/__init__.py src/ui/panels/workbench/execution_center.py src/ui/panels/workbench/recent_run_panel.py tests/test_small_widget_architecture.py tests/test_workbench_execution_center.py tests/test_recent_run_panel.py
```

结果：通过。

```powershell
python -X utf8 -m pytest tests/test_small_widget_architecture.py::test_style_result_receipt_row_projects_readonly_style_source_summary tests/test_workbench_execution_center.py::test_execution_center_result_state_renders_style_source_receipt tests/test_recent_run_panel.py::test_recent_run_panel_includes_style_source_summary tests/test_ui_exports.py -q
```

结果：

```text
4 passed
```

宽一点的相关回归：

```powershell
python -X utf8 -m pytest tests/test_workbench_execution_center.py tests/test_recent_run_panel.py tests/test_small_widget_architecture.py tests/test_ui_exports.py -q
```

结果：

```text
121 passed
```

## 4. 当前边界

本轮只做“执行后样式来源回执行”，不是完整执行报告 UI：

- 不展示所有 `style_source.sections` 结构化明细。
- 不提供跳转动作。
- 不替代 JSON/Markdown 报告。
- 快速执行日志仍保留一条文本日志，作为执行流记录。

后续如果需要更强能力，可以把 `StyleResultReceiptRow` 扩展为：

```text
StyleResultReceiptRow
-> compact mode：一行回执
-> detail mode：展开分区差异
-> action mode：打开报告 / 查看模板 / 查看分区
```

## 5. 本轮判断

这一轮让执行后的样式来源从“拼进摘要的一句文本”变成了可复用 UI 单元。它和执行前的 `StyleSourceCompactRow` 形成更清楚的分工：

```text
执行前：StyleSourceCompactRow，回答“将按什么样式执行？”
执行后：StyleResultReceiptRow，回答“刚才实际按什么样式执行？”
```

这进一步减少了 Workbench 与模板/场景样式链路之间的表达分叉。
