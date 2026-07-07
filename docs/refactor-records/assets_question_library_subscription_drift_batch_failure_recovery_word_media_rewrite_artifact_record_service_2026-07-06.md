# 第 40 步：订阅漂移批量失败恢复 Word Media Rewrite Artifact/Record 服务化记录
日期：2026-07-06

## 目标

继续拆分 Word media rewrite 链路，把不触碰文件系统的 artifact payload、manifest markdown、execution items、状态推导和最终 history record builder 下沉到 `src/services/material_assets/question_library.py`。

本步仍然不把本地 DOCX 扫描、ZIP 检查、文件复制、JSON/Markdown 写入搬进 service。

## 新增服务 API

- `question_figure_master_subscription_drift_batch_failure_recovery_word_media_rewrite_execution_items`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_media_rewrite_artifact_id`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_media_rewrite_status`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_media_rewrite_artifact_payload`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_media_rewrite_artifact_markdown`
- `build_question_figure_library_master_subscription_drift_batch_failure_recovery_word_media_rewrite_record`

同时保留旧私有 alias，避免面板和历史测试大范围重命名。

## 职责变化

service 现在负责：

- 生成 Word media rewrite execution items。
- 生成稳定 artifact id。
- 根据 DOCX 目标数和已改写数推导 rewrite status。
- 组装 Word media rewrite artifact payload。
- 生成 manifest markdown。
- 通过注入的 artifact result 组装最终 history record。
- 固化 record 中的执行状态、DOCX 计数、manifest 路径、next step 和 policy 字段。

`AssetsPanel` 现在负责：

- 从历史输出目标中发现本地 DOCX。
- 判断 DOCX/ZIP 是否可读。
- 扫描 `word/media/` 条目。
- 复制 DOCX 到 rewrite artifact 目录。
- 写入 JSON/Markdown manifest。
- 将写入结果注入 service record builder。
- 追加 history、保存 archive、刷新 UI。

## 边界原则

这一步继续维持三层边界：

- service：纯数据构造、状态归一化、record 固化。
- panel：文件系统副作用和 UI 编排。
- tests：用模拟 artifact result 验证 record builder，不依赖真实 DOCX 文件。

这样后续可以继续拆文件副作用，而不会让 service 在测试中依赖本地路径、ZIP 文件或桌面环境。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- execution items 继承 auto execution id、signature 和 worker scope。
- artifact id 稳定生成。
- status helper 能推导 `partial_rewrite`。
- artifact payload 固化 DOCX 目标数和已改写数。
- artifact markdown 包含 batch id 和 rewrite status。
- record builder 使用注入 artifact result 生成完整 history record。
- record lookup、items_from_record、entries recorded 状态仍兼容。
- `material_assets` 聚合导出和 `question_library` 私有 alias 指向同一实现。

## 下一步建议

第 41 步建议继续拆 persistent worker queue：

- 先审计 worker queue signature、entries、actions、record builder、manifest helper。
- 优先下沉不触碰文件系统和 UI 的 queue row/status/record projection。
- 面板继续保留实际任务调度、写 history、保存 archive 和刷新 UI。
