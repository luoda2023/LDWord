# 高层场景能力矩阵 N2.333 考试题目图片素材库跨包主数据订阅漂移冲突批量失败恢复 Durable Worker 执行监控续跑死信闭环

日期：2026-06-22

## 1. 本轮目标

N2.332 已经把 Word media rewrite 后的恢复批次推进到跨归档持久 worker 队列，能写入 queue manifest、幂等 lock key、retry policy、审计历史和题图 metadata。N2.333 承接的明确缺口是：队列登记后仍缺少执行监控、续跑判断和死信登记视角。

本轮不声明真实后台线程、跨进程 worker、定时调度器、自动续跑执行器或 Word XML relationship 深层修复已经完成。当前只闭合前台治理首片：已登记的持久 worker 队列可以进入 durable worker 监控表，生成监控快照；当上游 Word media rewrite 没有历史 DOCX 目标时，系统会诚实标记为续跑受阻，并允许登记死信记录。

## 2. 已闭合能力

- 新增 `question_figure_asset_library_master_subscription_drift_batch_failure_recovery_durable_worker_monitor_table`。
- 监控表从最新持久 worker 队列记录派生，不新增第二套事实源。
- 表格展示批次、队列状态、监控状态、续跑状态、死信状态和行级处理动作。
- 未登记监控时提供“记录监控”和“定位队列”。
- 监控快照记录 action 为 `question_figure_library_cross_package_master_subscription_drift_conflict_batch_failure_recovery_durable_worker_execution_monitor_resume_dead_letter`。
- 监控/死信 artifact 写入 `artifacts/subscription_drift_worker_monitors`。
- 无历史 DOCX 目标时写入：
  - `monitor_status=blocked_waiting_for_docx`
  - `resume_status=resume_blocked_missing_docx`
  - `dead_letter_status=candidate_no_docx_targets`
  - `dead_letter_reason=no_docx_targets`
- 死信登记后写入：
  - `record_kind=dead_letter_registration`
  - `execution_status=dead_lettered`
  - `dead_letter_status=dead_lettered_no_docx_targets`
- metadata 回写 durable worker monitor id、record kind、execution status、monitor status、resume status、dead letter status/reason、heartbeat status、queue id/status、retry scheduler status、manifest paths 和 archive 信息。
- readiness/maturity 同步把 durable worker execution monitor/resume/dead-letter UI 移入 evidence。

## 3. 链路边界

当前链路是：

1. 批量失败恢复报告、Drilldown、SLA、followup 和自动 trace repair 已闭合。
2. Word media rewrite 可生成执行记录和 manifest。
3. 持久 worker 队列表从 Word media rewrite 记录派生。
4. 用户登记持久 worker 队列，生成 queue manifest、lock key 和 retry policy。
5. Durable worker 监控表从最新持久队列记录派生。
6. 用户点击“记录监控”，系统生成 monitor snapshot、JSON/Markdown artifact 和 metadata 回写。
7. 如果历史 DOCX 目标数为 0，监控状态为受阻，续跑状态为等待 DOCX，死信状态为候选。
8. 用户点击“登记死信”，系统生成 dead letter registration 记录和 artifact，并把最终状态回写到 metadata。
9. readiness/maturity 把 durable worker execution monitor/resume/dead-letter UI 移入 evidence。
10. 剩余缺口推进为 cross archive file recovery center Word XML relationship media consistency UI。

这仍然是 durable worker 治理前台首片，不是后台调度执行器。它不会启动真实后台线程，不会跨进程抢锁，不会恢复中断进程，也不会改写 `.docx` 内的 `word/document.xml`、`word/_rels/document.xml.rels` 或 `word/media/*`。本轮保持边界清晰，避免把死信登记误读为 Word 文件级修复已经完成。

## 4. Word XML 视角复核

对照 Word 本身的 Open XML 结构，本轮仍没有完成以下文件级能力：

- 未读取并修改 `word/document.xml` 中的 `a:blip/@r:embed` 或相关图片引用。
- 未重写 `word/_rels/document.xml.rels` 中的 image relationship。
- 未校验 `word/media/*` 是否存在孤儿媒体、重复媒体或 relationship 断链。
- 未把题图替换候选、替换审计、回滚审计与真实 `.docx` media rewrite 合并为一个跨归档文件级恢复中心。
- 未处理历史 DOCX 缺失时的生成、定位或用户补交策略。
- 未把非题图素材族纳入同类跨包主数据订阅漂移批量失败恢复。

因此本轮后更准确的下一层缺口不是“durable worker 监控/死信”，而是“跨归档文件恢复中心 + Word XML relationship/media 一致性”。这个缺口同时属于 UI control、runtime execution、report artifact、rule governance 和 boundary gate。

## 5. 当前验证

已完成：

- `python -m py_compile src/ui/panels/assets_panel.py tests/test_assets_panel_architecture.py src/config/scene_product_readiness.py src/config/scene_product_maturity_upgrade_audit.py tests/test_scene_product_maturity_upgrade_audit.py`
- `python -m pytest tests/test_assets_panel_architecture.py -k subscription_drift_batch_failure_queue -q`
- `python -m pytest tests/test_scene_product_maturity_upgrade_audit.py -q`
- `python -m pytest tests/test_assets_panel_architecture.py -k cross_package_asset_master -q`
- `python -m pytest tests/test_scene_product_maturity_upgrade_audit.py tests/test_scene_matrix_dashboard.py tests/test_scene_matrix_drilldown.py tests/test_release_shell.py -q`
- `python scripts/verify_scene_matrix_release_gate.py`
- `python -m pytest tests/test_assets_panel_architecture.py -q`
- `python -m pytest -q`

当前结果：

- 订阅漂移批量失败恢复聚焦链路：`1 passed, 98 deselected`。
- 跨包主数据相邻聚焦：`11 passed, 88 deselected`。
- maturity 审计：`4 passed`。
- maturity/dashboard/drilldown/release shell：`25 passed`。
- release gate：passed，全部 `0 issues`。
- AssetsPanel 全量：`99 passed, 4 warnings`。
- 全量 pytest：`1505 passed, 8 warnings`。
- `artifacts/remote_writeback_manifests`、`artifacts/subscription_drift_recovery_reports`、`artifacts/subscription_drift_trace_repairs`、`artifacts/subscription_drift_word_media_rewrites`、`artifacts/subscription_drift_worker_queues`、`artifacts/subscription_drift_worker_monitors` 均已清理为 `0`。

warnings 均来自 openpyxl 对 `datetime.utcnow()` 的弃用提示，不影响本轮 durable worker 监控、续跑、死信、manifest、metadata 和 maturity 链路。
