# 第 37 步：订阅漂移批量失败恢复 Auto Execution Record 服务化记录

日期：2026-07-06

## 目标

继续拆第 35、36 步留下的 auto execution record builder，把执行状态决策、execution items 构造和最终 history record 构造下沉到 `src/services/material_assets/question_library.py`。

本步不让 service 隐式写文件。trace repair artifact 仍由面板写入，写入结果通过 `artifact` 参数注入 record builder。

## 新增服务 API

- `question_figure_master_subscription_drift_batch_failure_recovery_auto_execution_status_fields`
- `question_figure_master_subscription_drift_batch_failure_recovery_auto_execution_items`
- `build_question_figure_library_master_subscription_drift_batch_failure_recovery_auto_execution_record`
- `question_figure_master_subscription_drift_batch_failure_recovery_auto_execution_items_from_record`

同时保留旧私有 alias，兼容现有调用和测试。

## 职责变化

service 现在负责：

- 根据 follow-up 治理结果判断 rollback execution status。
- 判断 compensation execution status。
- 判断 historical output trace repair status。
- 推导 auto execution 总状态和下一步。
- 构造 trace repair execution items。
- 构造完整 auto execution history record。
- 从 record 中解析固化的 execution items。

`AssetsPanel` 现在负责：

- 为 record builder 准备 row 和 execution id。
- 调用 service status/items helper。
- 写入 trace repair JSON/Markdown artifact。
- 把 artifact result 注入 service record builder。
- 追加 history、写回 profile metadata、保存 archive 和刷新 UI。

## 验证

扩展测试：

- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`

覆盖内容：

- status fields 能推导 `executed`、`guarded_review_recorded`、`not_required`、`trace_index_written`。
- execution items 能继承 historical output targets。
- record builder 能接收 artifact result 并写入 artifact id/path/status 字段。
- items_from_record 能解析固化的 execution items。
- record lookup 能按 batch id + signature 命中 service builder 生成的 record。
- `material_assets` 聚合导出和 `question_library` 私有 alias 指向同一实现。

## 下一步建议

第 38 步建议继续拆 word media rewrite 链路：

- 先审计 word media rewrite 的 signature、record id、docx target discovery、entries、actions、record builder。
- 把不触碰本地 docx 文件的 projection/record helper 下沉到 service。
- 文件哈希、docx target discovery、真实 rewrite artifact 写入可单独分步处理，避免把文件副作用和状态投影混在一起。
