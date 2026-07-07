# 第 41 步：订阅漂移批量失败恢复 Persistent Worker Queue Projection 服务化记录
日期：2026-07-06

## 目标

继续拆分 batch failure recovery 链路，把 persistent worker queue 中不触碰文件系统的 projection/lookup/action/parser helper 下沉到 `src/services/material_assets/question_library.py`。

本步不移动 queue manifest artifact 写入，也不移动最终 queue record builder。它们仍然会写 JSON/Markdown manifest，保留在 `AssetsPanel`。

## 新增服务 API

- `question_figure_master_subscription_drift_batch_failure_recovery_persistent_worker_queue_signature`
- `question_figure_master_subscription_drift_batch_failure_recovery_persistent_worker_queue_record_id`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_persistent_worker_queue_record_for`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_persistent_worker_queue_entries`
- `question_figure_master_subscription_drift_batch_failure_recovery_persistent_worker_queue_actions`
- `question_figure_master_subscription_drift_batch_failure_recovery_persistent_worker_queue_items_from_record`

同时保留旧私有 alias，供面板和历史测试兼容。

## 职责变化

service 现在负责：

- 基于 Word media rewrite record 生成 persistent worker queue 待登记行。
- 生成 queue signature 和 queue id。
- 按 batch id + signature 查找已有 queue record。
- 投影 recorded 状态、queue status、lock status、retry scheduler status。
- 生成 queue 操作 action。
- 从 queue record 中解析固化的 queue items。

`AssetsPanel` 现在负责：

- 扫描历史输出目标中的本地 DOCX 数量，并注入 service entries。
- 写 persistent worker queue JSON/Markdown manifest。
- 构造带 artifact result 的最终 queue record。
- 追加 history、写回 profile metadata、保存 archive、刷新 UI。

## 边界原则

这一步把“表格状态投影”和“真实 manifest 写入”分开：

- service：可测试、无文件副作用的 queue projection。
- panel：文件写入、history 追加和 UI 编排。
- tests：用手工 queue record 验证 lookup、recorded 状态和 items parser，不依赖实际 manifest 文件。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- 未登记 queue 时能从 Word media rewrite record 生成待登记行。
- queue signature 和 queue id 稳定生成。
- 未登记 action 为 `register_worker_queue` / `locate_manifest`。
- queue record lookup 能按 batch id + signature 命中。
- items_from_record 能解析固化 queue items。
- 已登记 queue 时 entries 能投影 `scheduled`、`acquired`、`scheduled` 状态。
- 已登记 action 为 `locate_queue`。
- 聚合导出和旧私有 alias 指向同一实现。

## 下一步建议

第 42 步建议拆 persistent worker queue artifact/record builder：

- 下沉不写文件的 queue artifact payload/markdown/record status/items 构造。
- 面板继续保留 manifest JSON/Markdown 写入。
- record builder 通过 artifact result 参数接收写入结果，和 auto execution、Word media rewrite 的模式对齐。
