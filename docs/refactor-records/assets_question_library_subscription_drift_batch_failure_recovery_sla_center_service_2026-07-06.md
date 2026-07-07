# 第 33 步：订阅漂移批量失败恢复 SLA Center 服务化记录
日期：2026-07-06

## 目标

把题图素材库“跨包主数据订阅漂移”链路中 batch failure recovery SLA center 的纯数据逻辑，从 `AssetsPanel` 下沉到 `src/services/material_assets/question_library.py`。

本步只移动 SLA 行、SLA record、状态判断、签名和解析函数。实际表格选择、按钮处理、跨 archive 写回 profile metadata 仍留在面板侧。

## 本次新增服务 API

- `question_figure_master_subscription_drift_batch_failure_recovery_sla_age_hours`
- `question_figure_master_subscription_drift_batch_failure_recovery_sla_signature`
- `question_figure_master_subscription_drift_batch_failure_recovery_sla_record_id`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_sla_center_record_for`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_sla_center_entries`
- `question_figure_master_subscription_drift_batch_failure_recovery_sla_center_actions`
- `build_question_figure_library_master_subscription_drift_batch_failure_recovery_sla_center_record`
- `question_figure_master_subscription_drift_batch_failure_recovery_sla_items_from_record`
- `question_figure_remote_writeback_parse_expiry_datetime`

同时保留旧私有 alias，供现有面板调用和历史测试兼容。

## 数据职责

SLA center 负责把恢复报告状态映射成跨归档治理视图：

- 读取 archive.profiles 中的 recovery report entries。
- 计算 SLA age、SLA status、escalation status 和 owner。
- 根据 archive scope、batch id、report signature、SLA 状态和计数生成稳定 signature。
- 判断当前 SLA 状态是否已经写入过治理记录。
- 生成 SLA center row、actions 和治理 record。
- 解析 SLA record 中固化的 report items。
- 生成稳定 `qfig-master-batch-recovery-sla-*` record id。

## 面板边界

`AssetsPanel` 仍保留：

- SLA center 表格刷新、选择和按钮事件。
- `_append_question_figure_library_master_subscription_drift_batch_failure_recovery_sla_center_record` 的 profile 写入编排。
- `_apply_question_figure_master_subscription_drift_batch_failure_recovery_sla_center_metadata_to_profile`。
- 后续 follow-up、rollback、compensation、historical output review 和自动执行链路。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- SLA age helper 能按固定 now 计算小时数。
- ISO 时间解析 helper 可解析 `Z` 结尾时间。
- archive-like object 可生成 SLA center entry，不依赖 UI 类型。
- closed SLA entry 生成 record_sla / locate_drilldown 动作。
- SLA record 生成 id、status、archive id、next step 和 items。
- SLA record lookup 能按 batch id + signature 命中。
- 已记录 SLA 后 entries 能识别 `sla_recorded=True`。
- material_assets 聚合出口和 question_library 旧私有 alias 指向同一实现。

## 下一步建议

第 34 步建议继续拆 batch failure recovery follow-up 数据层：

- follow-up signature / record id。
- follow-up record lookup。
- follow-up entries。
- rollback、compensation、historical output review 状态判断和 actions。
- follow-up record builder。

实际 rollback、补偿、历史输出追溯和自动执行仍建议保留在面板或后续专门执行服务中。
