# 第 46 步：订阅漂移批量失败恢复 File Recovery Center Artifact/Record 服务化记录
日期：2026-07-06

## 目标

在第 45 步完成 file recovery center 行投影服务化后，本步继续把 file recovery center 的 artifact 构造和 history record 构造下沉到 `src/services/material_assets/question_library.py`。

本步继续保持副作用边界：
- service 只负责生成 artifact id、payload、markdown、status fields、recovery items 和最终 history record
- `AssetsPanel` 继续负责真实 DOCX 扫描、本地 JSON/Markdown 写入、history append、profile metadata 回填、archive 保存和 UI 刷新

## 新增服务 API

- `question_figure_master_subscription_drift_batch_failure_recovery_file_recovery_center_status_fields`
- `question_figure_master_subscription_drift_batch_failure_recovery_file_recovery_center_items`
- `question_figure_master_subscription_drift_batch_failure_recovery_file_recovery_center_artifact_id`
- `question_figure_master_subscription_drift_batch_failure_recovery_file_recovery_center_artifact_payload`
- `question_figure_master_subscription_drift_batch_failure_recovery_file_recovery_center_artifact_markdown`
- `build_question_figure_library_master_subscription_drift_batch_failure_recovery_file_recovery_center_record`

同步补齐：
- `src/services/material_assets/__init__.py` 聚合导出
- `question_library.py` 旧私有 alias
- `AssetsPanel` 本地 wrapper 兼容
- `tests/test_material_asset_services.py` 服务构造测试和 alias 断言

## 职责变化

service 现在负责：
- 根据 DOCX scan rows 计算 file recovery center 状态
- 计算 relationship/media 缺失和 orphan 计数
- 生成 recovery items
- 生成 artifact id
- 生成 artifact payload 和 markdown
- 根据 artifact 写入结果生成最终 history record
- 在 artifact 写入失败时把 record 状态切到 `analysis_manifest_write_failed`

`AssetsPanel` 现在只负责：
- 从 worker queue 记录解析 DOCX 目标
- 调用本地 DOCX XML/media scanner
- 把 service 生成的 payload/markdown 写入本地 manifest 文件
- 调用 service record builder
- 追加 history、回填 profile metadata、保存 archive、刷新 UI

## 为什么这样拆

file recovery center 的 record 原来在面板里同时完成扫描、计数、manifest 内容拼接、文件写入和 history record 拼装，导致 UI 层继续承载大量治理逻辑。

本步把“可测试的纯业务结构”拆到 service：
- service 测试可以不用创建真实 DOCX，也能验证 status、payload、markdown、record 字段
- 面板测试继续覆盖真实 DOCX 扫描和 manifest 写入
- 后续如果要迁移 DOCX scanner，可以单独拆成文件系统服务，不会和 record schema 混在一起

## 测试覆盖

扩展 `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`：
- `status_fields` 对 consistent / repair-required scan rows 的状态推导
- recovery items 继承 durable worker monitor item
- artifact id 稳定生成
- artifact payload summary 计数
- artifact markdown 包含 batch/status
- record builder 写入 artifact 字段和 scan/items JSON
- manifest 写入失败时 record 进入 `analysis_manifest_write_failed`

保留 `tests/test_assets_panel_architecture.py` 中的真实 DOCX manifest 写入覆盖，用来验证面板副作用链路没有丢。

## 后续建议

第 47 步建议开始评估 DOCX XML/media scanner 的边界：
- 如果继续迁出，优先放入独立文件系统服务，而不是继续塞进 `question_library.py`
- scanner 应有 fixture 覆盖 missing relationship、missing media、orphan media、invalid docx、missing docx
- 面板最终只保留 UI 编排、用户动作处理、history append 和 archive save
