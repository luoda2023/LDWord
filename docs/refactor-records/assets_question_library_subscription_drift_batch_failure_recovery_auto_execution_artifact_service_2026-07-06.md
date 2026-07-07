# 第 36 步：订阅漂移批量失败恢复 Auto Execution Artifact 服务化记录

日期：2026-07-06

## 目标

继续拆第 35 步留下的 auto execution trace repair 产物逻辑，把 artifact 的稳定规划能力下沉到 `src/services/material_assets/question_library.py`，让 `AssetsPanel` 不再同时负责 artifact id、payload、markdown 和路径规则。

本步采用 report drilldown 的现有模式：service 负责可测试的数据规划，面板保留实际 `mkdir` 和 `write_text` 副作用。

## 新增服务 API

- `question_figure_master_subscription_drift_trace_repair_output_dir`
- `question_figure_master_subscription_drift_batch_failure_recovery_auto_execution_artifact_id`
- `question_figure_master_subscription_drift_batch_failure_recovery_auto_execution_artifact_paths`
- `question_figure_master_subscription_drift_batch_failure_recovery_auto_execution_artifact_payload`
- `question_figure_master_subscription_drift_batch_failure_recovery_auto_execution_artifact_markdown`

同时保留旧私有 alias，避免面板和历史测试发生大范围重命名。

## 职责变化

service 现在负责：

- 基于 execution id、batch id、auto execution signature 生成 trace repair artifact id。
- 规划默认输出目录和 JSON/Markdown 文件路径。
- 生成 trace repair payload。
- 生成 trace repair markdown。
- 统一 artifact summary、historical output targets 和 trace rows 的结构。

`AssetsPanel` 现在只负责：

- 调用 service helper 取得 payload、markdown 和路径。
- 创建输出目录。
- 写入 JSON/Markdown 文件。
- 把写入结果合并进 auto execution record。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- artifact id 以 `qfig-master-batch-recovery-trace-repair-` 开头。
- `output_dir` 参数能控制路径规划，测试不会写入真实项目目录。
- payload 与路径规划复用同一个 artifact id。
- payload summary 能记录 historical output target count。
- trace rows 能保存 historical output trace repair status。
- markdown 能包含 batch id 和 master key。
- `material_assets` 聚合导出和 `question_library` 私有 alias 指向同一实现。

## 下一步建议

第 37 步可以继续拆 auto execution record builder：

- 把 execution status、rollback status、compensation status、historical output trace repair status 的决策函数下沉。
- 把 execution items 构造下沉。
- 把完整 auto execution record 构造下沉到 service，并通过注入 artifact result 避免 service 隐式写文件。
- 面板最终只做“生成 artifact result、追加 history、保存 archive、刷新 UI”。
