# 第 35 步：订阅漂移批量失败恢复 Auto Execution 服务化记录

日期：2026-07-06

## 目标

把题图素材库“跨包主数据订阅漂移”链路中 batch failure recovery auto execution 的纯数据逻辑，从 `AssetsPanel` 下沉到 `src/services/material_assets/question_library.py`。

本步只移动不触碰文件系统的部分：签名、记录 ID、历史记录查找、entries 投影和 actions。实际 trace repair artifact 的 JSON/Markdown 写入、profile metadata 写回和 append 编排仍留在面板层，后续单独拆成执行产物服务。

## 新增服务 API

- `question_figure_master_subscription_drift_batch_failure_recovery_auto_execution_signature`
- `question_figure_master_subscription_drift_batch_failure_recovery_auto_execution_record_id`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_auto_execution_record_for`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_auto_execution_entries`
- `question_figure_master_subscription_drift_batch_failure_recovery_auto_execution_actions`

同时保留旧私有 alias，供现有面板调用和历史测试兼容。

## 数据职责

auto execution 负责把 follow-up 治理记录继续投影为可执行状态：

- 读取已记录的 follow-up record。
- 合并 rollback、compensation、historical output review 的最终要求。
- 结合 historical output targets 生成稳定 auto execution signature。
- 生成 `qfig-master-batch-recovery-auto-exec-*` record id。
- 判断当前 batch + signature 是否已有自动执行记录。
- 生成待执行、已执行或需定位报告的按钮动作。
- 生成表格需要的 execution status、label、tooltip 和 latest record 快照。

## 面板边界

`AssetsPanel` 继续保留：

- auto execution 表格刷新、选择和按钮事件。
- `_question_figure_master_subscription_drift_batch_failure_recovery_auto_execution_artifact`。
- `_question_figure_library_master_subscription_drift_batch_failure_recovery_auto_execution_record`。
- `_append_question_figure_library_master_subscription_drift_batch_failure_recovery_auto_execution_record`。
- `_apply_question_figure_master_subscription_drift_batch_failure_recovery_auto_execution_metadata_to_profile`。

这些函数仍然会写 artifact 文件、追加 profile history 或改写 asset metadata，不属于纯数据服务。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- follow-up record 后可生成 auto execution entry。
- entry 能继承 rollback、compensation、historical output review 和 historical output targets。
- 未记录时 actions 为 `execute_trace_repair` / `locate_report`。
- record id 以 `qfig-master-batch-recovery-auto-exec-` 开头。
- record lookup 能按 batch id + auto execution signature 命中。
- 已有 auto execution record 后 entries 能识别 `auto_execution_recorded=True` 并读取 latest record。
- `material_assets` 聚合导出和 `question_library` 私有 alias 指向同一实现。

## 下一步建议

第 36 步建议继续拆 auto execution 的副作用层：

- 把 trace repair artifact payload、markdown 和路径规划拆成纯 planner。
- 把真实文件写入封装为 artifact writer。
- 让面板 append 流程只负责编排和保存 archive。
- 为 artifact 写入失败、重复写入和路径生成补更窄的服务测试。
