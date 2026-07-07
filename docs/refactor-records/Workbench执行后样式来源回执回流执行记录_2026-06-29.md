# Workbench 执行后样式来源回执回流执行记录

日期：2026-06-29

后续进展：

- 本文记录的是 `style_source_summary` 回流阶段。后续已把 Workbench 状态链路升级为 `StylePresentationEnvelope` 优先：`ExecutionResultState` / `RecentRunState` 新增 `style_source_envelope`，执行中心与最近结果面板优先渲染 envelope，`style_source_summary` 保留为报告、日志和旧调用方兼容文本，详见 `docs/refactor-records/Workbench样式回执Envelope状态链路执行记录_2026-06-29.md`。

## 1. 本轮目标

上一份再审计文档确认了一个 P0 断点：执行前 Workbench 已能通过 `StyleSourceCompactRow` 看到样式来源，执行报告也已经写入 `style_source`，但执行完成后的 UI 状态对象没有保留样式来源，导致用户执行后无法直接确认：

```text
本次到底按哪个模板处理？
哪些分区使用了场景独立样式？
执行结果和报告里的样式来源是否一致？
```

本轮目标是打通：

```text
样式来源投影 -> 执行报告摘要 -> runtime payload -> ExecutionResultState -> RecentRunState -> Workbench 结果 UI
```

## 2. 本轮代码落点

### 2.1 状态对象增加样式来源回执

文件：

- `src/ui/panels/workbench/state.py`

新增字段：

- `ExecutionResultState.style_source`
- `ExecutionResultState.style_source_summary`
- `RecentRunState.style_source`
- `RecentRunState.style_source_summary`

判断：

结构化 payload 和可读摘要都保留。这样当前文本 UI 能直接展示摘要，后续如果要做专门的 `StyleResultReceiptRow`，也不需要从字符串反推。

### 2.2 Adapter 生成统一可读摘要

文件：

- `src/ui/adapters/workbench_execution_adapter.py`

新增能力：

- `build_result_state(..., style_source=..., style_source_summary=...)`
- `_style_source_receipt_summary(...)`
- `build_recent_run_state(...)` 同步样式来源字段

显示规则：

| 输入 | 输出 |
| --- | --- |
| `style_source.summary` 存在 | `样式来源：{summary}` |
| 只有 `template_label + section_status` | `样式来源：本次按模板“X”处理；{section_status}。` |
| 无样式来源 | 不展示 |

### 2.3 Runtime payload 带回 style_source

文件：

- `src/ui/panels/workbench/execution_runtime.py`
- `src/ui/panels/workbench/panel.py`

覆盖路径：

| 路径 | 当前处理 |
| --- | --- |
| 普通执行成功 | payload 增加 `style_source` |
| 普通执行失败 | payload 增加 `style_source` |
| 资料/资产预检失败 | `_failed_payload` 后补 `style_source` |
| 多交付目标执行 | `_run_delivery_target_groups` 接收并返回 `style_source` |
| 旧 Workbench runner | 成功/失败 payload 均增加 `style_source` |

这样执行报告和 UI 消费的是同一份 `build_style_source_report_summary(...)` 结果。

### 2.4 两条 Workbench 消费通道同步传递

文件：

- `src/ui/panels/workbench/execution_controller.py`
- `src/ui/panels/workbench/panel.py`

变更：

- V2 主执行通道从 payload 读取 `style_source` 并传入 adapter。
- 旧面板 `apply_execution_result(...)` 同步传入 `style_source`。

### 2.5 UI 展示接入

文件：

- `src/ui/panels/workbench/execution_center.py`
- `src/ui/panels/workbench/recent_run_panel.py`
- `src/ui/panels/workbench/quick_execution_detail.py`

展示位置：

| UI | 展示方式 |
| --- | --- |
| 执行中心 | 主 summary 下方空一行显示样式来源 |
| 最近结果 | 主 summary 下一行显示样式来源 |
| 快速执行详情日志 | 写入 info 级执行日志 |

当前保持轻量文本展示，不新增复杂控件。原因是本轮目标是闭合链路；后续再做 `StyleResultReceiptRow` 时可复用结构化 state。

## 3. 用户侧变化

执行前用户看到：

```text
样式来源
模板：默认格式
分区：参考文献（行距）
```

执行后用户能在执行摘要和最近结果中看到：

```text
样式来源：本次按模板“默认格式”处理；参考文献（行距）使用场景独立样式。
```

这让“配置 -> 执行 -> 报告”形成同一条叙事，不再要求用户打开报告文件才能知道实际样式来源。

## 4. 本轮测试

新增/扩展：

- `tests/test_workbench_execution_center.py::test_execution_adapter_builds_success_result_state`
- `tests/test_workbench_execution_center.py::test_execution_center_result_state_renders_style_source_receipt`
- `tests/test_recent_run_panel.py::test_recent_run_panel_includes_style_source_summary`

已运行：

```powershell
python -X utf8 -m py_compile src/ui/panels/workbench/state.py src/ui/adapters/workbench_execution_adapter.py src/ui/panels/workbench/execution_center.py src/ui/panels/workbench/recent_run_panel.py src/ui/panels/workbench/quick_execution_detail.py src/ui/panels/workbench/execution_runtime.py src/ui/panels/workbench/panel.py src/ui/panels/workbench/execution_controller.py tests/test_workbench_execution_center.py tests/test_recent_run_panel.py
```

结果：通过。

```powershell
python -X utf8 -m pytest tests/test_workbench_execution_center.py::test_execution_adapter_builds_success_result_state tests/test_workbench_execution_center.py::test_execution_center_result_state_renders_style_source_receipt tests/test_recent_run_panel.py::test_recent_run_panel_includes_style_source_summary tests/test_execution_worker.py::test_execution_worker_normalizes_report_paths_to_strings -q
```

结果：

```text
4 passed
```

宽一点的 Workbench 相关回归：

```powershell
python -X utf8 -m pytest tests/test_workbench_execution_center.py tests/test_recent_run_panel.py tests/test_execution_worker.py::test_execution_worker_normalizes_report_paths_to_strings -q
```

结果：

```text
93 passed
```

## 5. 仍待后续推进

本轮闭合的是数据与文本回执，不等于完成最终优秀设计。后续仍建议继续：

1. 抽 `StyleResultReceiptRow`，把执行后样式来源从普通文本升级为可扫描的小型回执控件。
2. 将 `StyleManagementBlock` 增加模式契约，避免模板正文和场景分区继续靠调用方各自拼装。
3. 抽 `StyleRuleControlDeck`，收束分区独立样式开关、差异条、批量恢复和撤销恢复。
4. 做真实窗口截图验证，确认中文字体下执行前/执行后样式来源都不溢出。

## 6. 本轮判断

这一轮完成了 P0 中最关键的一条链路：执行前看到的样式来源，执行后 UI 和报告都能追溯到同一份摘要。它让 Workbench 不再只是“执行按钮和产物列表”，而是能说清楚本次文档格式来自哪里、哪些分区偏离了模板。
