# 第 26 步：订阅漂移决策计划服务化记录

日期：2026-07-06

## 目标

把题图素材库“跨包主数据订阅漂移”链路中的 decision plan 纯数据逻辑，从 `AssetsPanel` 下沉到 `src/services/material_assets/question_library.py`。

本步骤只移动无 UI 副作用的函数：从已审批的 triage 记录生成待执行的字段裁决计划、查询已 planned 的记录、生成计划记录、生成计划项和 plan id。面板仍保留 `_apply_question_figure_master_subscription_drift_decision_plan_metadata_to_profile`，负责把计划状态写回当前 profile 的 asset metadata。

## 本次新增服务 API

- `question_figure_library_master_subscription_drift_decision_plan_entries`
- `question_figure_library_master_subscription_drift_decision_plan_for`
- `question_figure_library_master_subscription_drift_decision_plan_record_for_profiles`
- `build_question_figure_library_master_subscription_drift_decision_plan_record`
- `question_figure_master_subscription_drift_decision_plan_id`
- `subscription_drift_decision_plan_fields`
- `subscription_drift_decision_plan_items`
- `subscription_drift_decision_plan_recommendation`
- `subscription_drift_decision_plan_selected_decision`
- `subscription_drift_decision_plan_impact_summary`

同时保留同名旧私有 alias，供既有面板调用和旧测试兼容。

## 数据职责

decision plan 负责把“已入队、已分诊、已审批”的订阅漂移记录转成可执行计划：

- 读取 `subscription_change_diff_fields`，去重并生成字段级计划项。
- 为版本、etag、更新时间默认选择 `accept_remote`。
- 为 alt text、reference 等内容字段保留 `field_merge` 选项。
- 生成 `qfig-master-decision-*` 幂等 plan id。
- 产出 `question_figure_library_cross_package_master_subscription_drift_conflict_decision_plan` 治理记录。
- 过滤已存在 `planned` 状态的 master key，避免重复生成计划。

## 面板边界

`AssetsPanel` 只保留两类职责：

- 用户交互：表格刷新、定位题图、按钮动作、状态提示。
- 状态落盘：把生成后的 plan record 写回命中的 profile metadata/history。

计划生成、计划查询、计划项构造和摘要文案全部由 service 提供。

## 验证

新增/扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- queue -> triage approval -> decision plan 的连续服务链路。
- plan items 字段集合、默认裁决、`field_merge` 选项。
- plan record 的状态、id、next step、queue id 继承和远程/本地字段透传。
- `..._for`、`..._record_for_profiles` 查询函数。
- 已 planned 后不再重复生成 entries。
- material_assets 包入口和旧私有 alias 指向同一实现。

## 下一步建议

第 27 步可以继续下沉“订阅漂移裁决执行”中的纯数据函数。建议仍保留实际 metadata 写回和批量 profile mutation 在面板侧，先抽离：

- execution entries / lookup。
- execution record 构造。
- 字段裁决结果摘要。
- 单项执行结果 payload。
- 后续审计/失败队列所需的只读聚合。
