# 第 38 步：订阅漂移批量失败恢复 Word Media Rewrite Helper 服务化记录

日期：2026-07-06

## 目标

继续拆 batch failure recovery 链路，把 word media rewrite 中不触碰文件系统的 helper 下沉到 `src/services/material_assets/question_library.py`。

本步只移动纯 helper，不移动 DOCX 扫描、文件哈希、DOCX 复制、manifest 写入和完整 record builder。

## 新增服务 API

- `question_figure_master_subscription_drift_batch_failure_recovery_word_media_rewrite_signature`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_media_rewrite_record_id`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_word_media_rewrite_record_for`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_media_rewrite_actions`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_media_rewrite_items_from_record`

同时保留旧私有 alias，供现有面板调用和历史测试兼容。

## 职责变化

service 现在负责：

- 基于 archive、batch、auto execution、trace repair artifact 和 historical output targets 生成 word media rewrite signature。
- 生成 `qfig-master-batch-recovery-word-media-rewrite-*` record id。
- 按 batch id + signature 查找已有 word media rewrite record。
- 根据是否已记录生成 actions。
- 从 word media rewrite record 中解析固化 items。

`AssetsPanel` 继续保留：

- `_question_figure_master_subscription_drift_word_media_rewrite_output_dir`
- `_question_figure_master_subscription_drift_word_media_file_sha1`
- `_question_figure_master_subscription_drift_word_media_local_path`
- `_question_figure_master_subscription_drift_word_media_docx_targets`
- `_question_figure_library_master_subscription_drift_batch_failure_recovery_word_media_rewrite_entries`
- `_question_figure_master_subscription_drift_batch_failure_recovery_word_media_rewrite_artifact`
- `_question_figure_library_master_subscription_drift_batch_failure_recovery_word_media_rewrite_record`

这些函数会访问本地路径、扫描 DOCX、复制文件或写 JSON/Markdown manifest，后续需要按副作用边界单独拆。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- signature 生成非空。
- record id 以 `qfig-master-batch-recovery-word-media-rewrite-` 开头。
- 未记录 actions 为 `execute_word_media_rewrite` / `locate_trace`。
- 已记录 actions 为 `locate_manifest`。
- record lookup 能按 batch id + signature 命中。
- items_from_record 能解析固化 items。
- `material_assets` 聚合导出和 `question_library` 私有 alias 指向同一实现。

## 下一步建议

第 39 步建议拆 word media rewrite entries：

- 先把 DOCX target discovery 变成可注入参数，避免 entries 函数直接扫描文件系统。
- service 负责 rows/status labels/recorded lookup。
- 面板负责从 historical output targets 扫描本地 DOCX，并把扫描结果传给 service。
