# 第 27 步：订阅漂移裁决执行服务化记录

日期：2026-07-06

## 目标

把题图素材库“跨包主数据订阅漂移”链路中普通 decision execution 的纯数据逻辑，从 `AssetsPanel` 下沉到 `src/services/material_assets/question_library.py`。

本步骤不移动实际 profile mutation。`AssetsPanel` 继续负责 `_apply_question_figure_master_subscription_drift_decision_execution_to_profile`，也继续保留 field merge、batch execution、失败队列和审计链路的本地实现，后续分步拆分。

## 本次新增服务 API

- `question_figure_library_master_subscription_drift_decision_execution_entries`
- `question_figure_library_master_subscription_drift_decision_execution_for`
- `question_figure_library_master_subscription_drift_decision_execution_record_for_profiles`
- `build_question_figure_library_master_subscription_drift_decision_execution_record`
- `question_figure_master_subscription_drift_decision_execution_id`
- `subscription_drift_decision_execution_plan_items`
- `subscription_drift_decision_execution_items`
- `subscription_drift_decision_execution_record_items`

同时保留旧私有 alias，供现有面板调用和历史测试兼容。

## 数据职责

decision execution 负责把 planned decision plan 转成 applied execution record：

- 读取 `subscription_drift_decision_plan_items` 并补齐默认 `selected_decision`。
- 过滤已经 `applied` 的 master key，避免重复执行。
- 生成待执行表格 rows，包含 accept remote / keep local 摘要。
- 把计划项归一化为 executed items。
- 计算 changed fields、accept remote fields、keep local fields、merged fields。
- 生成 `qfig-master-exec-*` 幂等 execution id。
- 产出 `question_figure_library_cross_package_master_subscription_drift_conflict_decision_execution` 治理记录。

## 面板边界

`AssetsPanel` 仍保留：

- 用户触发执行、定位题图和刷新表格。
- 将 execution record 应用到命中的 profile metadata。
- batch execution、field merge 和后续失败队列/审计链路。

这样 service 只负责“应该执行什么、执行记录长什么样”，面板负责“把执行结果应用到当前 UI 工作集”。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- queue -> triage approval -> decision plan -> decision execution 的连续服务链路。
- execution entries 对 planned record 的读取和 applied record 的重复过滤。
- execution record 的 status、connector、id、next step、plan id 继承。
- executed items 的 applied value 和 value_changed。
- `..._for`、`..._record_for_profiles` 查询函数。
- material_assets 包入口和旧私有 alias 指向同一实现。

## 下一步建议

第 28 步建议拆 field merge execution：

- field merge entries。
- merge field sources / labels。
- field merge execution record。
- field merge execution id。
- field merge executed-items / record-items。

仍建议把实际 profile metadata 写回留在面板侧，等 field merge 和 batch 都服务化后再统一评估是否需要独立 mutation service。
