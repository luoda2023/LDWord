# 第 44 步：订阅漂移批量失败恢复 Durable Worker Monitor Artifact/Record 服务化记录

日期：2026-07-06

## 目标

在第 43 步 durable worker monitor 投影服务化之后，继续把 monitor artifact 和最终 history record 的纯构造逻辑下沉到 `src/services/material_assets/question_library.py`。

本步仍然不让 service 写文件。service 只产出 artifact id、payload、markdown、status fields、monitor items 和最终 record；`AssetsPanel` 继续负责本地 JSON/Markdown manifest 写入、history 追加、profile metadata 回填和 UI 刷新。

## 新增服务 API

- `question_figure_master_subscription_drift_batch_failure_recovery_durable_worker_monitor_status_fields`
- `question_figure_master_subscription_drift_batch_failure_recovery_durable_worker_monitor_items`
- `question_figure_master_subscription_drift_batch_failure_recovery_durable_worker_monitor_artifact_id`
- `question_figure_master_subscription_drift_batch_failure_recovery_durable_worker_monitor_artifact_payload`
- `question_figure_master_subscription_drift_batch_failure_recovery_durable_worker_monitor_artifact_markdown`
- `build_question_figure_library_master_subscription_drift_batch_failure_recovery_durable_worker_monitor_record`

同步补齐：

- `src/services/material_assets/__init__.py` 聚合导出
- `question_library.py` 旧私有 alias
- `AssetsPanel` 顶部本地兼容 alias

## 职责变化

service 现在负责：

- 根据 persistent worker queue record 推导 monitor execution/status/resume/dead-letter 状态
- 生成 heartbeat id/status
- 生成 monitor items
- 生成 monitor artifact id
- 组装 monitor artifact payload 和 markdown
- 根据 artifact result 构造最终 durable worker monitor history record
- 在 manifest 写入失败时把 record 转为 `attention_required` / `manifest_write_failed`

`AssetsPanel` 现在负责：

- 调用 service 生成 status fields 和 monitor items
- 写入 monitor JSON/Markdown manifest
- 将 artifact result 注入 service record builder
- 追加 history、回填 profile metadata、保存 archive、刷新 UI

## 边界原则

这一步继续保持副作用边界：

- service 不创建目录、不写文件、不操作 UI
- panel 不再手写 monitor record 字段和 manifest markdown 内容
- 测试通过模拟 artifact result 验证 record builder，不依赖真实文件系统

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

新增覆盖：

- status fields 能推导 `ready` / `ready_to_resume`
- monitor items 能继承 monitor id/signature
- artifact id 稳定生成
- artifact payload 固化 monitor status 和 item count
- artifact markdown 包含 batch id 和 monitor status
- record builder 能用注入 artifact result 生成完整 monitor record
- manifest 写入失败时 record 转入 `manifest_write_failed`
- record lookup、items_from_record、entries recorded 状态保持兼容
- 聚合导出和旧私有 alias 指向同一服务实现

## 下一步建议

第 45 步建议进入下游 file recovery center / DOCX media relationship recovery 链路：

- 先迁移纯解析 helper 和 docx target 投影
- 再迁移 artifact payload/markdown/record builder
- 面板继续只保留文件扫描、manifest 写入和 UI 编排
