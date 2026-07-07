# 高层场景能力矩阵 N2.325 考试题目图片素材库跨包主数据订阅漂移冲突批量失败恢复报告 Drilldown Artifact 闭环

日期：2026-06-22

## 1. 本轮目标

N2.325 承接 N2.324 后的明确缺口：恢复报告 UI 已经可以汇总批次级失败、恢复、跳过和未处理数量，也能固化恢复报告审计记录，但用户仍缺少逐项 drilldown artifact 来复盘“哪一个主数据键、哪一个 source/asset id、原始失败原因是什么、恢复动作是什么、是否能从报告明细回到素材行”。

本轮完成的是恢复报告 Drilldown Artifact 首片：在恢复报告已生成后，前台可以生成 JSON/Markdown 明细产物，明细表按失败项展开，并支持定位素材或打开产物。

本轮不声明后台 worker、自动重试调度、并发限流、取消/暂停、失败 SLA、跨 archive 失败中心、批量回滚、二次补偿、历史 Word 输出追溯修复或非题图素材族同类治理完成。

## 2. 已闭合能力

- 新增 `question_figure_asset_library_master_subscription_drift_batch_failure_recovery_report_drilldown_table`。
- 恢复报告表在报告已生成后提供“生成明细”，生成后切换为“定位明细”。
- 新增审计动作 `question_figure_library_cross_package_master_subscription_drift_conflict_batch_failure_recovery_report_drilldown_artifact`。
- Drilldown artifact 写出 JSON 与 Markdown，默认目录为 `artifacts/subscription_drift_recovery_reports`。
- artifact payload 保留 report 元数据、batch execution 摘要、drilldown rows 和恢复计数 summary。
- drilldown rows 保留 master key、source、asset id、原始失败原因、恢复状态、处理动作、decision execution id、decision plan id 和 next step。
- 明细表逐项展示批次、主数据键、恢复状态、处理动作、原始错误，并提供“定位素材”“打开明细”。
- 对能匹配到 source/asset id 的题图素材回写 `master_subscription_drift_batch_failure_recovery_report_drilldown_*` metadata。
- readiness/maturity 矩阵把 `batch failure recovery report drilldown artifact UI` 移入 evidence，把下一缺口推进为 `batch failure recovery background task governance UI`。

## 3. 链路视角

N2.325 继续不制造第二套失败事实源：

1. 批量裁决执行记录仍是失败事实源。
2. 失败队列治理记录提供 recovered/skipped/retry_failed/open 状态。
3. 恢复报告记录固化批次级摘要。
4. Drilldown artifact 只从恢复报告记录与批量执行摘要派生，不改变恢复事实。
5. 前台明细表从 artifact payload 反推行级 drilldown，并能回到题图素材行。

因此当前闭合的是“报告 -> 明细产物 -> 明细表 -> 素材定位”的前台可复核链路，而不是后台自动恢复系统。

## 4. 配置与测试落点

- `src/ui/panels/assets_panel.py`
  - 新增 drilldown 明细表、生成/定位产物、打开产物、明细行定位素材、artifact payload 和 metadata 回写。
- `tests/test_assets_panel_architecture.py`
  - 扩展批量失败恢复测试，覆盖恢复报告生成后继续生成 Drilldown 明细、表格行、按钮状态、JSON/Markdown 文件、payload 和 metadata。
- `src/config/scene_product_readiness.py`
  - `pack:exam_education` 与 `family:exam_teaching` 增加恢复报告 drilldown artifact UI evidence。
  - 剩余缺口推进为 background task governance UI。
- `src/config/scene_product_maturity_upgrade_audit.py`
  - maturity gap 映射从 drilldown artifact UI 收敛为 background task governance UI。
  - gap 域移除 `report_artifact`，保留 `ui_control`、`runtime_execution`、`rule_governance`、`boundary_gate`。
- `tests/test_scene_product_maturity_upgrade_audit.py`
  - 锁定 pack 和 family 两个视角都能看到 drilldown artifact UI evidence。
  - 锁定下一缺口为 background task governance UI。

## 5. 仍未闭合边界

N2.325 后，明确剩余缺口不再是恢复报告 drilldown artifact，而是恢复治理后台化：

- 后台 worker 与任务状态持久化；
- 自动重试、指数退避、失败重放和幂等任务锁；
- 并发限流、暂停/取消和批次恢复调度；
- 失败 SLA、提醒、责任人升级；
- 跨 archive 失败恢复报告中心；
- 批量回滚、二次补偿和历史 Word 输出追溯修复；
- 非题图素材族的同类跨包主数据订阅漂移批量失败恢复治理。

## 6. 当前验证

已完成：

- 语法检查：`python -m py_compile src/ui/panels/assets_panel.py src/config/scene_product_readiness.py src/config/scene_product_maturity_upgrade_audit.py tests/test_assets_panel_architecture.py tests/test_scene_product_maturity_upgrade_audit.py` 通过。
- 聚焦 AssetsPanel：`1 passed, 98 deselected`。
- 跨包主数据相邻聚焦：`11 passed, 88 deselected`。
- maturity 审计：`4 passed`。

补充完成：AssetsPanel 全量 `99 passed, 4 warnings`；场景矩阵/钻取/release shell 相邻回归 `24 passed`；场景矩阵 release gate passed 且全部 `0 issues`；全量测试 `1505 passed, 8 warnings`；`artifacts/remote_writeback_manifests` 与 `artifacts/subscription_drift_recovery_reports` 均已清理至 `0` 个文件。warnings 均来自 openpyxl 对 `datetime.utcnow()` 的弃用提示，不影响本轮恢复报告 Drilldown Artifact 链路。
