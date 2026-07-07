# 第 32 步：订阅漂移批量失败恢复后台任务服务化记录
日期：2026-07-06

## 目标

把题图素材库“跨包主数据订阅漂移”链路中 batch failure recovery background task 的纯投影逻辑，从 `AssetsPanel` 下沉到 `src/services/material_assets/question_library.py`。

本步只移动后台任务表的数据行、状态文案和动作 tuple。实际按钮处理、定位、刷新、文件写入和 profile metadata mutation 仍留在面板侧。

## 本次新增服务 API

- `question_figure_library_master_subscription_drift_batch_failure_recovery_background_task_entries`
- `question_figure_master_subscription_drift_batch_failure_recovery_background_task_batch_row`
- `question_figure_master_subscription_drift_batch_failure_recovery_background_task_queue_row`
- `question_figure_master_subscription_drift_batch_failure_recovery_background_task_report_row`
- `question_figure_master_subscription_drift_batch_failure_recovery_background_task_drilldown_row`
- `question_figure_master_subscription_drift_batch_failure_recovery_background_task_actions`
- `question_figure_master_subscription_drift_batch_failure_recovery_background_task_status_label`
- `question_figure_remote_writeback_task_policy_governance_suffix`

同时保留旧私有 alias，供现有面板调用和历史测试兼容。

## 数据职责

background task 投影负责把恢复链路当前状态压缩成前台后台任务表：

- 从 recovery report entries 生成任务行。
- 根据 batch execution record 生成 batch execution 阶段 row。
- 根据 failure recovery 汇总生成 queue governance 阶段 row。
- 根据 recovery report record 生成 report 固化阶段 row。
- 根据 drilldown artifact record 生成 artifact 复核阶段 row。
- 按 batch id、stage order、changed_at 排序并限制前台展示数量。
- 根据 action 字段生成定位动作 tuple。
- 根据状态码生成状态文案。
- 把 task policy summary 拼接成治理说明后缀。

## 面板边界

`AssetsPanel` 仍保留：

- 后台任务表刷新、按钮渲染和点击处理。
- 定位到 batch、failure queue、report、drilldown 的 UI 行为。
- report/drilldown artifact 实际写文件。
- report/drilldown metadata 写回 profile。
- 后续 SLA、follow-up、durable task、repair execution 等链路。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- 带 report 和 drilldown artifact 的历史记录能生成四个后台任务阶段。
- stage order 为 batch execution -> failure recovery -> recovery report -> drilldown artifact。
- 每个阶段 action 正确指向 locate_batch / locate_report / locate_drilldown。
- status label 能从 `blocked` 生成“已阻塞”。
- background task actions 能为 drilldown 行生成定位动作。
- task policy governance suffix 可从 policy record 生成策略摘要。
- material_assets 聚合出口和 question_library 旧私有 alias 指向同一实现。

## 下一步建议

第 33 步建议继续拆 batch failure recovery SLA center 数据层：

- SLA age/signature/record id。
- SLA center entries。
- SLA center record lookup/record。
- SLA status、escalation、actions 和 follow-up 入口投影。

仍建议把真正的跨 archive mutation、通知、自动升级和外部系统动作留在面板或后续专门服务中，先完成纯数据投影下沉。
