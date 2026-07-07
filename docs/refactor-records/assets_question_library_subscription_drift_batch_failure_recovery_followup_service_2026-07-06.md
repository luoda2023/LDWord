# 第 34 步：订阅漂移批量失败恢复 Follow-up 服务化记录
日期：2026-07-06

## 目标

把题图素材库“跨包主数据订阅漂移”链路中 batch failure recovery follow-up 的纯数据逻辑，从 `AssetsPanel` 下沉到 `src/services/material_assets/question_library.py`。

本步只移动 rollback、compensation、historical output review 的判断、行投影、动作和治理 record 构造。实际写回 profile metadata、自动执行和历史输出 trace repair 仍留在面板侧或后续步骤。

## 本次新增服务 API

- `question_figure_master_subscription_drift_batch_failure_recovery_followup_signature`
- `question_figure_master_subscription_drift_batch_failure_recovery_followup_record_id`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_followup_record_for`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_followup_entries`
- `question_figure_master_subscription_drift_batch_failure_recovery_followup_actions`
- `build_question_figure_library_master_subscription_drift_batch_failure_recovery_followup_record`
- `question_figure_master_subscription_drift_batch_failure_recovery_followup_items_from_record`

同时保留旧私有 alias，供现有面板调用和历史测试兼容。

## 数据职责

follow-up 负责把 SLA center 的结果继续展开为后续治理判断：

- 基于 SLA center entries 生成 follow-up rows。
- 判断是否需要 rollback review。
- 判断是否需要 compensation 或 compensation review。
- 判断是否需要 historical output review。
- 生成稳定 follow-up signature 和 `qfig-master-batch-recovery-followup-*` record id。
- 判断当前 follow-up 是否已经写入治理记录。
- 生成 follow-up actions 和 follow-up governance record。
- 从 follow-up record 中解析固化 items。

## 面板边界

`AssetsPanel` 仍保留：

- follow-up 表格刷新、选择和按钮事件。
- `_append_question_figure_library_master_subscription_drift_batch_failure_recovery_followup_record` 的 profile 写入编排。
- `_apply_question_figure_master_subscription_drift_batch_failure_recovery_followup_metadata_to_profile`。
- 自动 rollback / compensation / historical output trace repair 执行链路。
- trace repair artifact 的文件写入和后续审计。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- SLA record 后可生成 follow-up entry。
- recovered 项会触发 rollback review 和 historical output review。
- closed 且无 skipped/unresolved 时 compensation 为 not required。
- follow-up actions 在未记录时生成 record_followup / locate_drilldown。
- follow-up record 生成 id、status、next step 和固化 items。
- follow-up lookup 能按 batch id + signature 命中。
- 已记录 follow-up 后 entries 能识别 `followup_recorded=True`。
- material_assets 聚合出口和 question_library 旧私有 alias 指向同一实现。

## 下一步建议

第 35 步建议继续拆 batch failure recovery auto execution 数据层：

- auto execution signature / record id。
- auto execution record lookup。
- auto execution entries 和 actions。
- 不含真实文件写入的 execution status / trace row 规划。

实际 trace repair artifact 写文件建议继续保留到单独的执行/产物服务拆分步骤。
