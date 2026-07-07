# 第 42 步：订阅漂移批量失败恢复 Persistent Worker Queue Artifact/Record 服务化记录
日期：2026-07-06

## 目标

在第 41 步 queue projection 服务化之后，继续把 persistent worker queue 中不写文件的 artifact payload、manifest markdown、status fields、queue items 和最终 history record builder 下沉到 `src/services/material_assets/question_library.py`。

本步仍然不让 service 写 JSON/Markdown 文件。面板只负责文件写入，然后把 artifact result 注入 service record builder。

## 新增服务 API

- `question_figure_remote_writeback_task_policy_record_fields`
- `question_figure_master_subscription_drift_batch_failure_recovery_persistent_worker_queue_status_fields`
- `question_figure_master_subscription_drift_batch_failure_recovery_persistent_worker_queue_items`
- `question_figure_master_subscription_drift_batch_failure_recovery_persistent_worker_queue_artifact_id`
- `question_figure_master_subscription_drift_batch_failure_recovery_persistent_worker_queue_artifact_payload`
- `question_figure_master_subscription_drift_batch_failure_recovery_persistent_worker_queue_artifact_markdown`
- `build_question_figure_library_master_subscription_drift_batch_failure_recovery_persistent_worker_queue_record`

同时保留旧私有 alias，兼容面板与历史测试。

## 职责变化

service 现在负责：

- 归一化 task policy record fields。
- 推导 queue status、retry scheduler status、worker item status、next step。
- 生成 lock key。
- 生成 queue items。
- 生成 queue artifact id。
- 组装 queue artifact payload 和 markdown。
- 根据 artifact result 构造最终 persistent worker queue history record。
- 在 manifest 写入失败时把 queue record 状态转为 attention required。

`AssetsPanel` 现在负责：

- 调用 service 生成 status fields 和 queue items。
- 写 queue JSON/Markdown manifest。
- 把 artifact result 注入 service record builder。
- 追加 history、写回 profile metadata、保存 archive、刷新 UI。

## 边界原则

这一步把 queue 链路进一步拆为：

- service：状态、payload、markdown、record 的纯构造。
- panel：本地文件写入与 UI 编排。
- tests：用模拟 artifact result 验证 record builder，不依赖真实 manifest 文件。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- status fields 能推导 `scheduled` / `scheduled`。
- queue items 能继承 queue id 和 item status。
- artifact id 稳定生成。
- artifact payload 固化 queue status 和 item count。
- artifact markdown 包含 batch id 和 queue status。
- record builder 使用注入 artifact result 生成完整 queue record。
- record lookup、items_from_record、entries recorded 状态仍兼容。
- 聚合导出和旧私有 alias 指向同一实现。

## 下一步建议

第 43 步建议进入 durable worker monitor：

- 先拆 durable worker monitor 的 signature、entries、actions、items_from_record。
- 再拆 monitor artifact payload/markdown/record builder。
- 面板继续保留 manifest 写入、dead-letter 操作编排和 UI 刷新。
