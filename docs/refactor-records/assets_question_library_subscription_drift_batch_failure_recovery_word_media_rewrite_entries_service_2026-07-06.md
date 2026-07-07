# 第 39 步：订阅漂移批量失败恢复 Word Media Rewrite Entries 服务化记录
日期：2026-07-06

## 目标

继续拆分 batch failure recovery 链路中的 Word media rewrite 功能，把 entries 行投影、已有记录查找、状态标签和统计字段下沉到 `src/services/material_assets/question_library.py`。

本步不把本地 DOCX 扫描搬进 service。service 通过 `docx_target_count` 参数接收面板已经发现的 DOCX 数量，避免服务层直接访问文件系统。

## 新增服务 API

- `question_figure_library_master_subscription_drift_batch_failure_recovery_word_media_rewrite_entries`

同时保留旧私有 alias：

- `_question_figure_library_master_subscription_drift_batch_failure_recovery_word_media_rewrite_entries`

## 职责变化

service 现在负责：

- 基于 auto execution entries 生成 Word media rewrite 待处理行。
- 只处理 trace repair 已写入的 auto execution 记录。
- 生成 `word_media_rewrite_signature`。
- 按 batch id + signature 查找已有 Word media rewrite record。
- 投影 `word_media_rewrite_recorded`、`latest_word_media_rewrite_record`、`docx_target_count`、`rewritten_docx_count`。
- 根据 record status/rewrite status 生成状态标签和 tooltip。

`AssetsPanel` 现在负责：

- 从 `historical_output_targets` 扫描本地 DOCX。
- 将 `len(docx_targets)` 注入 service entries helper。
- 继续负责真实 Word media rewrite artifact 写入、manifest 写入、history 追加、archive 保存和 UI 刷新。

## 边界原则

这一步刻意让 service 不知道 DOCX 文件在哪里，也不打开本地文件。这样可以保持三层边界：

- service：纯数据投影、record lookup、状态归一化。
- panel：本地路径发现、文件系统副作用、UI 调用编排。
- tests：用可注入 `docx_target_count` 验证投影逻辑，不依赖真实 DOCX 文件。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- 未记录 Word media rewrite 时，entries 能继承 latest auto execution id。
- service 使用注入的 `docx_target_count` 生成 `docx_target_count`。
- entries 生成的 signature 与 helper 生成结果一致。
- 已有 Word media rewrite record 时，entries 能识别 recorded 状态。
- 已有记录中的 DOCX 目标数量和已改写数量会覆盖投影字段。
- `material_assets` 聚合导出和 `question_library` 私有 alias 指向同一实现。

## 下一步建议

第 40 步建议继续拆 Word media rewrite artifact/record builder：

- 先把不写文件的 artifact payload、manifest markdown、record builder 下沉到 service。
- 面板只负责扫描 DOCX、复制或写入实际文件、保存 JSON/Markdown。
- record builder 通过 artifact result 参数接收写入结果，保持 service 无文件副作用。
