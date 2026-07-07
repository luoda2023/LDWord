# 第 29 步：订阅漂移批量裁决执行服务化记录

日期：2026-07-06

## 目标

把题图素材库“跨包主数据订阅漂移”链路中 batch decision execution 的纯数据逻辑，从 `AssetsPanel` 下沉到 `src/services/material_assets/question_library.py`。

本步骤不移动实际批量 metadata 写回，也不移动失败队列、恢复报告、SLA、跟进和审计链路。面板继续负责 mutation 和用户交互，service 负责生成批量执行视图与治理记录。

## 本次新增服务 API

- `question_figure_library_master_subscription_drift_batch_decision_execution_entries`
- `question_figure_library_master_subscription_drift_batch_decision_execution_for`
- `question_figure_library_master_subscription_drift_batch_decision_execution_record_for_profiles`
- `build_question_figure_library_master_subscription_drift_batch_decision_execution_result_item`
- `build_question_figure_library_master_subscription_drift_batch_decision_execution_record`
- `question_figure_master_subscription_drift_batch_decision_execution_id`
- `subscription_drift_batch_decision_execution_result_items`
- `subscription_drift_batch_fields_summary`

同时保留旧私有 alias，供现有面板调用和历史测试兼容。

## 数据职责

batch decision execution 负责把当前所有待执行的普通 decision execution entries 汇总成批次：

- 基于待执行 entries 生成稳定 `qfig-master-batch-*` batch id。
- 汇总 accept remote / keep local 字段摘要。
- 生成批量执行表格 row。
- 为每个单项执行结果生成 result item。
- 汇总 result items，产出 batch execution record。
- 根据 result items 计算 `applied`、`partial`、`blocked` 状态。
- 解析 batch record 中的 result items，供失败队列和后续审计链路复用。
- 过滤已存在 `applied` 或 `partial` 的 batch record，避免重复生成批次。

## 面板边界

`AssetsPanel` 仍保留：

- 批量执行按钮、定位、刷新和状态提示。
- `_apply_question_figure_master_subscription_drift_batch_decision_execution_metadata_to_profile`。
- 单项执行过程中对 profile 的实际 mutation。
- batch failure queue、recovery report、SLA、follow-up、audit 等后续治理链路。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- queue -> triage approval -> decision plan -> decision execution -> batch decision execution 的连续服务链路。
- batch entries、batch id 和字段摘要。
- result item 的 execution id、plan id、字段摘要和 affected count。
- batch record 的 status、connector、counts、next step 和 result item parser。
- failed-only batch record 进入 `blocked` / `batch_failure_queue`。
- `..._for`、`..._record_for_profiles` 查询函数。
- material_assets 包入口和旧私有 alias 指向同一实现。

## 下一步建议

第 30 步建议拆 batch failure queue 数据层：

- failure queue entries。
- failure issue/status/next-step labels。
- queue action tuples。
- failure queue governance lookup/record/id。
- retry attempt 计算。

仍建议把实际 recovery、retry 和 metadata 写回留在面板侧，直到失败恢复链路的数据层全部服务化。
