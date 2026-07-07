# 第 28 步：订阅漂移字段合并执行服务化记录

日期：2026-07-06

## 目标

把题图素材库“跨包主数据订阅漂移”链路中 field merge execution 的纯数据逻辑，从 `AssetsPanel` 下沉到 `src/services/material_assets/question_library.py`。

本步骤不移动用户弹窗、不移动 profile metadata 写回，也不移动 batch execution/失败队列/审计链路。面板继续负责交互和 mutation，service 负责生成可验证的字段合并数据与治理记录。

## 本次新增服务 API

- `question_figure_library_master_subscription_drift_field_merge_execution_entries`
- `question_figure_library_master_subscription_drift_field_merge_execution_for`
- `question_figure_library_master_subscription_drift_field_merge_execution_record_for_profiles`
- `build_question_figure_library_master_subscription_drift_field_merge_execution_record`
- `question_figure_master_subscription_drift_field_merge_execution_id`
- `subscription_drift_field_merge_decision_items`
- `subscription_drift_field_merge_sources`
- `subscription_drift_field_merge_sources_label`
- `subscription_drift_field_merge_execution_items`
- `subscription_drift_field_merge_execution_record_items`

同时保留旧私有 alias，供现有面板调用和历史测试兼容。

## 数据职责

field merge execution 负责处理 planned decision plan 中支持字段合并的内容字段：

- 从 decision items 中筛出支持 `field_merge` 的 `alt_text` 和 `reference`。
- 校验每个待合并字段的 source 选择，只允许 `local` 或 `remote`。
- 生成 `field=source` 的稳定摘要，用于幂等 id。
- 生成 `qfig-master-merge-*` execution id。
- 产出 `question_figure_library_cross_package_master_subscription_drift_conflict_field_merge_decision_execution` 治理记录。
- 解析 field merge executed-items，供面板把结果应用回当前 profile metadata。
- 过滤已 applied 的 field merge execution，避免重复生成待处理行。

## 面板边界

`AssetsPanel` 仍保留：

- 字段合并 source 选择弹窗。
- 表格选择、定位题图、按钮动作和状态提示。
- `_apply_question_figure_master_subscription_drift_field_merge_execution_to_profile`。
- metadata 字段写入策略，例如 `reference` 映射到现有 URL/cache/reference 键。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- queue -> triage approval -> decision plan -> decision execution -> field merge execution 的连续服务链路。
- `field_merge` 字段筛选。
- source 选择规范化和非法 source 拦截。
- field merge execution record 的 status、connector、id、plan id、fields、changed fields 和 sources。
- executed items 的 applied value、field source 和 value_changed。
- `..._for`、`..._record_for_profiles` 查询函数。
- material_assets 包入口和旧私有 alias 指向同一实现。

## 下一步建议

第 29 步建议拆 batch decision execution：

- batch entries。
- batch id。
- batch result item。
- batch execution record。
- batch result items parser。
- batch fields summary。

仍建议把实际批量 metadata 写回留在面板侧，等 batch 和失败队列数据层都服务化后，再判断是否需要独立 mutation service。
