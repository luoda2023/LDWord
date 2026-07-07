# 第 30 步：订阅漂移批量失败队列服务化记录
日期：2026-07-06

## 目标

把题图素材库“跨包主数据订阅漂移”链路中 batch failure queue 的纯数据逻辑，从 `AssetsPanel` 下沉到 `src/services/material_assets/question_library.py`。

本步不移动实际 retry、skip、locate 的 UI 事件，也不移动 recovery report 和后续恢复执行链路。面板继续负责用户交互和 profile metadata 写入，service 负责失败队列视图、治理记录、重试次数和稳定 id。

## 本次新增服务 API

- `question_figure_library_master_subscription_drift_batch_failure_queue_entries`
- `question_figure_master_subscription_drift_batch_failure_issue_label`
- `question_figure_master_subscription_drift_batch_failure_status_label`
- `question_figure_master_subscription_drift_batch_failure_next_step`
- `question_figure_master_subscription_drift_batch_failure_queue_actions`
- `question_figure_library_master_subscription_drift_batch_failure_queue_governance_for`
- `build_question_figure_library_master_subscription_drift_batch_failure_queue_governance_record`
- `question_figure_master_subscription_drift_batch_failure_queue_id`
- `question_figure_master_subscription_drift_batch_failure_retry_attempt`
- `question_figure_remote_writeback_task_policy_item_fields`

同时保留旧私有 alias，供现有面板调用和历史测试兼容。

## 数据职责

batch failure queue 负责把 batch decision execution 中失败的 result item 投影为前台可处理队列：

- 从 profile history 中收集 `partial` 或 `blocked` 的 batch execution record。
- 解析 `subscription_drift_batch_decision_result_items`，筛出 `result_status=failed` 的项目。
- 过滤已经 `recovered` 或 `skipped` 的 failure queue governance record，避免重复入队。
- 通过当前仍待执行的 decision execution entries 判断是否允许 retry。
- 生成 issue、status、next step、tooltip、actions 等前台队列行。
- 生成 `question_figure_library_cross_package_master_subscription_drift_conflict_batch_failure_queue_governance` 治理记录。
- 生成稳定 `qfig-master-batch-failure-*` queue id。
- 根据历史治理记录计算下一次 retry attempt。

## 面板边界

`AssetsPanel` 仍保留：

- batch failure queue 的按钮渲染、点击事件、定位和刷新。
- retry / skip 触发后的 profile metadata 写入。
- recovery report entries 以及后续 file recovery、historical docx repair、word xml media repair 链路。
- 远程写回主流程中的本地 helper 和 policy 常量。服务层新增的 policy item helper 仅服务于本步 failure queue governance record，远程写回本体后续单独拆分。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- failed-only batch record 进入 `blocked` / `batch_failure_queue`。
- failure queue entries 生成 master key、issue、status、retry flag 和 action tuple。
- governance record 生成 queue id、connector、resolution action、next step 和 task policy item 字段。
- governance lookup 能按 batch id、master key、queue status 命中记录。
- retry attempt 能根据历史 retry governance record 递增。
- recovered / skipped 后 failure queue entries 不再重复出现。
- material_assets 聚合出口和 question_library 旧私有 alias 指向同一实现。

## 下一步建议

第 31 步建议拆 batch failure recovery report 数据层：

- recovery report entries。
- recovery report status、issue、next step、action tuple。
- recovery report governance lookup/record/id。
- 与 batch failure queue governance record 的前后置关系。

仍建议把实际文件恢复、历史 docx 修复和 Word XML media 深修的 profile mutation 留在面板侧，等 recovery report 的数据层稳定后再继续拆后续执行链路。
