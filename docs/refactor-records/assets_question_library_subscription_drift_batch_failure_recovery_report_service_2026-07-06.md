# 第 31 步：订阅漂移批量失败恢复报告服务化记录
日期：2026-07-06

## 目标

把题图素材库“跨包主数据订阅漂移”链路中 batch failure recovery report 的纯数据逻辑，从 `AssetsPanel` 下沉到 `src/services/material_assets/question_library.py`。

本步继续保留实际文件写入、按钮事件、定位动作和 profile metadata mutation 在面板侧。service 负责恢复报告、报告明细 payload、artifact 投影和前台表格行。

## 本次新增服务 API

- `question_figure_library_master_subscription_drift_batch_failure_recovery_report_entries`
- `question_figure_master_subscription_drift_batch_failure_recovery_report_items`
- `question_figure_master_subscription_drift_batch_failure_recovery_report_signature`
- `question_figure_master_subscription_drift_batch_failure_recovery_report_id`
- `question_figure_master_subscription_drift_batch_failure_recovery_policy_fields_from_items`
- `question_figure_master_subscription_drift_batch_failure_recovery_report_actions`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_report_for`
- `build_question_figure_library_master_subscription_drift_batch_failure_recovery_report_record`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_report_drilldown_artifact_for`
- `question_figure_master_subscription_drift_batch_failure_recovery_report_drilldown_artifact_id`
- `question_figure_master_subscription_drift_batch_failure_recovery_report_drilldown_row_id`
- `question_figure_master_subscription_drift_batch_failure_recovery_report_drilldown_payload`
- `question_figure_master_subscription_drift_batch_failure_recovery_report_drilldown_markdown`
- `question_figure_master_subscription_drift_batch_failure_recovery_report_drilldown_payload_from_record`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_report_drilldown_entries`
- `question_figure_master_subscription_drift_batch_failure_recovery_report_drilldown_actions`
- `question_figure_master_subscription_drift_batch_failure_recovery_report_items_from_record`

同时保留旧私有 alias，供现有面板调用和历史测试兼容。

## 数据职责

batch failure recovery report 负责把失败队列治理结果汇总为可审计的恢复报告：

- 从 batch execution record 中识别 failed result item。
- 关联 batch failure queue governance record，判断 recovered、skipped、retry_failed、open。
- 汇总 recovered/skipped/retry_failed/open/unresolved 计数。
- 生成稳定 report signature 和 `qfig-master-batch-recovery-report-*` report id。
- 判断当前恢复状态是否已经生成过同签名报告。
- 判断已生成报告是否已经有 drilldown artifact。
- 生成 report record 和 report actions。
- 生成 drilldown payload、row id、artifact id、drilldown rows 和 drilldown actions。
- 从 report record / artifact record 解析 JSON payload，供面板和后续后台任务复用。

## 面板边界

`AssetsPanel` 仍保留：

- 表格刷新、按钮渲染、选择、定位和用户事件。
- `_question_figure_master_subscription_drift_batch_failure_recovery_report_write_drilldown_artifact` 的实际文件写入。
- `_question_figure_library_master_subscription_drift_batch_failure_recovery_report_drilldown_artifact_record` 的写文件编排。
- `_apply_question_figure_master_subscription_drift_batch_failure_recovery_report_metadata_to_profile`。
- `_apply_question_figure_master_subscription_drift_batch_failure_recovery_report_drilldown_artifact_metadata_to_profile`。
- 后续 file recovery、historical docx repair、Word XML media deep repair 等恢复执行链路。

## 附带修正

`question_figure_library_master_subscription_drift_batch_decision_execution_for` 原先只返回 `applied` / `partial` batch execution record。恢复报告消费的是 `blocked` batch，因此本步把 `blocked` 纳入可查询状态，保证 drilldown payload 能回填失败批次状态。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- recovered governance record 生成 recovery report entries。
- report actions 在未生成报告、已生成报告、已生成 drilldown artifact 三种状态下正确变化。
- report record 生成 id、status、summary、policy fields 和 report items。
- report lookup 能按 batch id 和 signature 命中。
- drilldown payload 能关联 blocked batch execution record。
- drilldown artifact lookup、payload parser、drilldown entries 和 drilldown actions 可用。
- material_assets 聚合出口和 question_library 旧私有 alias 指向同一实现。

## 下一步建议

第 32 步建议拆 batch failure recovery background task 数据层：

- background task entries。
- batch/queue/report/drilldown stage row。
- task status、next step、action tuple。
- task policy source 和 durable task record。

实际后台任务执行、文件系统写入和 profile mutation 仍建议继续留在面板侧，等后台任务纯投影稳定后再拆执行链路。
