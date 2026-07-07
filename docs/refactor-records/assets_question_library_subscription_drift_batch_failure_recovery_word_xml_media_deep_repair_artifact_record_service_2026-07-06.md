# 第 49 步：Word XML/media Deep Repair Artifact/Record 服务化记录
日期：2026-07-06

## 目标

在第 47 步把 DOCX XML/media scanner 拆入 `word_docx_recovery.py`、第 48 步把真实 DOCX deep repair 写回器拆入同一文件后，本步骤继续把 deep repair 的治理结构构造逻辑从 `AssetsPanel` 下沉到 `src/services/material_assets/question_library.py`。

本步骤迁移的是可测试的纯业务结构：
- deep repair signature
- deep repair record id
- history record 查找
- artifact id
- status/count 汇总
- artifact payload
- artifact markdown
- record items 反解析
- 最终 history record builder

## 新增服务 API

- `question_figure_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_signature`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_record_id`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_record_for`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_artifact_id`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_status_fields`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_artifact_payload`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_artifact_markdown`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_items_from_record`
- `build_question_figure_library_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_record`

同步补齐：
- `src/services/material_assets/__init__.py` 聚合导出
- `question_library.py` 旧私有 alias
- `AssetsPanel` 本地 wrapper 兼容
- `tests/test_material_asset_services.py` 服务构造测试与 alias 断言

## 职责变化

`question_library.py` 现在负责：
- 根据 file recovery center、historical DOCX repair、worker queue 生成 deep repair signature
- 生成稳定 repair id 和 artifact id
- 汇总 repaired DOCX、relationship、media、rollback 状态
- 汇总 missing relationship/media 与 orphan/unreferenced 计数
- 生成 JSON manifest payload 和 Markdown manifest 文本
- 构造最终治理 history record
- 在 manifest 写入失败时把状态切换为 `deep_repair_manifest_write_failed`

`AssetsPanel` 现在只保留编排和副作用：
- 从 worker queue 解析 DOCX target
- 调用 `word_docx_recovery.py` 执行真实 DOCX deep repair
- 把 service 生成的 payload/markdown 写入本地 manifest
- 调用 service record builder
- append history、回填 profile metadata、保存 archive、刷新 UI

## 为什么这样拆

deep repair 原来在面板里同时做三类事情：真实 DOCX 文件修复、manifest 内容拼装、治理 history record 拼装。第 47、48 步已经把文件扫描/写回能力移出 UI，本步骤把剩下的治理结构也移出 UI。

这样拆以后：
- 文件系统能力归 `word_docx_recovery.py`
- record schema、artifact schema、状态汇总归 `question_library.py`
- `AssetsPanel` 只做用户动作编排和持久化副作用

这个边界比之前健康：服务测试不用启动 Qt，也不用真实写 DOCX，就能验证治理字段、状态、计数和兼容导出；面板测试继续负责真实副作用链路。

## 测试覆盖

扩展 `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`：
- deep repair signature 与 record id 稳定生成
- deep repair status fields 对 completed rows 的状态和计数汇总
- artifact id 稳定生成
- artifact payload 写入 archive、summary、asset rows、docx rows
- artifact markdown 包含状态和 repaired DOCX 路径
- record builder 写入 manifest path、计数字段和 items JSON
- `record_for` 能按 batch/signature 找回记录
- `items_from_record` 能反解析记录中的 repair items
- manifest 写入失败时进入 `deep_repair_manifest_write_failed`
- `material_assets` 聚合导出和 `question_library` 私有 alias 仍然兼容

## 当前剩余边界

本步骤没有迁移 deep repair entries/actions 行投影逻辑。它仍留在 `AssetsPanel`，因为这部分强依赖 UI 文案、状态标签和按钮动作。

后续如果继续拆，第 50 步可以考虑：
- 将 `word_xml_media_deep_repair_entries` 行投影下沉到 `question_library.py`
- 将 deep repair actions 下沉为服务函数
- 让 `AssetsPanel` 的 deep repair 区域进一步变成 presenter 调用和 action dispatch
