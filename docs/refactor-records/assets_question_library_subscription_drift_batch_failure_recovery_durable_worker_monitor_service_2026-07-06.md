# 第 43 步：订阅漂移批量失败恢复 Durable Worker Monitor 投影服务化记录

日期：2026-07-06

## 目标

在 persistent worker queue 已完成服务化之后，继续把 durable worker monitor 中可纯计算的投影逻辑下沉到 `src/services/material_assets/question_library.py`。

本步只迁移：

- monitor signature
- monitor record id
- monitor record lookup
- monitor entries
- monitor actions
- monitor items_from_record

本步不迁移：

- monitor manifest JSON/Markdown 文件写入
- durable worker monitor artifact 组装
- 最终 durable worker monitor history record builder
- dead-letter 操作编排和 UI 刷新

## 新增服务 API

- `question_figure_master_subscription_drift_batch_failure_recovery_durable_worker_monitor_signature`
- `question_figure_master_subscription_drift_batch_failure_recovery_durable_worker_monitor_record_id`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_durable_worker_monitor_record_for`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_durable_worker_monitor_entries`
- `question_figure_master_subscription_drift_batch_failure_recovery_durable_worker_monitor_actions`
- `question_figure_master_subscription_drift_batch_failure_recovery_durable_worker_monitor_items_from_record`

同时补齐 `src/services/material_assets/__init__.py` 聚合导出和 `question_library.py` 中的旧私有 alias，保持面板旧调用路径兼容。

## 职责变化

service 现在负责：

- 从 persistent worker queue record 投影 durable worker monitor 行
- 计算 durable worker monitor 幂等 signature
- 按 batch id、signature、record kind 查找最新 monitor record
- 推导 pending / ready_to_resume / paused / blocked / dead-letter 相关状态
- 生成 monitor 操作按钮所需的 action 元组
- 从 monitor record 中解析 monitor items

`AssetsPanel` 现在只保留薄包装：

- 统计本地 DOCX target 数并注入 service
- 转调 service 生成 monitor rows/actions/signature/id
- 继续保留 manifest 写入、history 写回、profile metadata 回填和 UI 刷新

## 边界原则

这一步的边界是“状态投影先服务化，副作用留在面板”。

这样可以先减少面板中的重复治理投影代码，同时避免一次性迁移 artifact/record builder 导致文件系统副作用和 UI 操作交织过深。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

新增覆盖：

- durable monitor entries 能从已有 persistent worker queue record 继续投影
- 未记录状态生成 `record_worker_monitor` 和 `locate_queue` 动作
- monitor signature 和 record id 稳定生成
- monitor record lookup 支持 batch id、signature、record kind
- monitor items_from_record 能解析 record 中的 items JSON
- 已记录状态能回显 monitor/resume/dead-letter 状态
- dead-letter 候选状态生成 `register_dead_letter` 和 `locate_monitor` 动作
- 聚合导出和旧私有 alias 指向同一服务实现

## 下一步建议

第 44 步继续处理 durable worker monitor artifact/record：

- 把 monitor artifact id、payload、markdown 下沉到 service
- 把最终 durable worker monitor record builder 下沉到 service
- 面板继续只负责写 JSON/Markdown 文件，并把 artifact result 注入 record builder
- 测试中用模拟 artifact result 覆盖 ready、blocked、dead-letter 三类状态
