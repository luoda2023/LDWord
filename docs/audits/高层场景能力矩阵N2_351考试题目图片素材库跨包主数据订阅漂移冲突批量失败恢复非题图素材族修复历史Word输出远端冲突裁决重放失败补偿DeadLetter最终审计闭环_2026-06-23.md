# 高层场景能力矩阵 N2.351 考试题目图片素材库跨包主数据订阅漂移冲突批量失败恢复非题图素材族修复历史 Word 输出远端冲突裁决重放失败补偿 Dead Letter 最终审计闭环

日期：2026-06-23

## 1. 定位

N2.350 已经把 retry/replay failure compensation queue 推进为可执行 handoff：前台可以从补偿队列生成 execution record，并将失败补偿项分发到授权刷新、远端快照复核或 dead-letter 复核。N2.351 继续补齐 execution 之后的最终审计首片，让 `handoff` 状态不再停留为“有执行结果但没有终态证据”。

本轮不声明后台 worker、自动重试调度、真实授权刷新外呼、真实远端快照重新拉取或二次补偿自动归档已经完成。当前只承诺：补偿执行结果可以被前台 `Audit` 消费，生成 dead-letter/final audit record、manifest、items 和 metadata，并在 UI 上收束为 `audited`。

## 2. 本轮闭环

- execution record 已存在时，非题图素材族恢复表格从 `handoff` 显示 `Audit` 与 `Manifest`。
- `Audit` 消费最新 compensation execution record，不新增第二套事实源。
- final audit items 按 execution item 分类：
  - `dead_letter_review_required` -> `dead_letter_final_audit_recorded`，终态为 `dead_lettered_for_manual_followup`。
  - `authorization_refresh_required` -> `authorization_refresh_final_audit_recorded`，后续路由到 authorization refresh connector。
  - `remote_snapshot_review_required` -> `remote_snapshot_final_audit_recorded`，后续路由到 remote snapshot governance。
- final audit manifest 独立写入 `artifacts/subscription_drift_non_question_asset_family_word_output_remote_conflict_decision_retry_replay_failure_compensation_final_audits`。
- profile metadata 回写 `master_subscription_drift_non_question_asset_family_remote_conflict_decision_retry_replay_failure_compensation_final_audit_*` 字段。
- final audit 记录后，表格状态变为 `audited`，动作收束为 `Manifest`，并阻止重复 Audit、重复 Execute、重复 Queue。

## 3. 链路变化

N2.351 后链路变为：

```text
... -> Review -> Replay
                  |
                  v
             Failure Queue -> Execute -> Handoff -> Final Audit -> Manifest
```

这不是把失败补偿伪装成远端修复完成，而是给每个无法自动补偿的 execution item 留下明确终态：dead-letter 人工归档、授权刷新后续连接器、远端快照治理后续连接器。这样前台链路从“执行后只剩一个 handoff manifest”推进为“执行结果可审计、最终处置可追踪、后续连接器缺口可命名”。

## 4. 矩阵口径

新增 evidence：

- `question asset per-question asset library cross-package master subscription drift conflict batch failure recovery non-question asset family repaired historical Word output remote conflict decision retry replay failure compensation dead letter final audit UI bridge`

剩余 gap 推进为：

- pack：`advanced question asset library cross-package asset master data subscription drift conflict batch failure recovery non-question asset family repaired historical Word output remote conflict decision retry replay failure compensation authorization snapshot followup connector UI`
- family：`advanced asset library cross-package asset master data subscription drift conflict batch failure recovery non-question asset family repaired historical Word output remote conflict decision retry replay failure compensation authorization snapshot followup connector UI`

这个口径表示 final audit 已经从剩余缺口中退出；下一优先级应处理 authorization refresh 与 remote snapshot follow-up connector，而不是继续把 dead-letter final audit UI 列为未打通。

## 5. 落点

- `src/ui/panels/assets_panel.py`：新增 final audit 输出目录、record finder、item 派生、artifact、record、metadata 回写、append 入口、handler action、列表投影、状态标签、按钮策略和 manifest 优先级。
- `tests/test_assets_panel_architecture.py`：扩展 409 -> 500 -> 500 失败路径，覆盖 Queue -> Execute -> Audit -> Manifest 的完整 UI 链路、final audit manifest、items、metadata 与重复动作保护。
- `src/config/scene_product_readiness.py`：将 final audit UI bridge 移入 evidence，并把剩余 gap 推进为 authorization/snapshot follow-up connector UI。
- `src/config/scene_product_maturity_upgrade_audit.py`：同步新 gap 的 domain 映射。
- `tests/test_scene_product_maturity_upgrade_audit.py`：同步 evidence 与 gap 断言。

## 6. 当前验证

- `python -m py_compile src/ui/panels/assets_panel.py tests/test_assets_panel_architecture.py`：通过。
- `pytest -q tests/test_assets_panel_architecture.py -k "non_question_asset_family_recovery_governance"`：`1 passed, 103 deselected`。
- `python -m py_compile src/config/scene_product_readiness.py src/config/scene_product_maturity_upgrade_audit.py tests/test_scene_product_maturity_upgrade_audit.py`：通过。
- `pytest -q tests/test_scene_product_maturity_upgrade_audit.py`：`4 passed`。
- `python scripts/verify_scene_matrix_release_gate.py`：通过，全部 `0 issues`。
- `pytest -q tests/test_assets_panel_architecture.py`：`104 passed, 4 warnings`。
- `pytest -q`：`1510 passed, 8 warnings`。

验证后结论：N2.351 已经把 retry/replay failure compensation execution handoff 推进到 Dead Letter/final audit 首片闭环。当前仍保留明确非本轮缺口：authorization refresh connector、remote snapshot follow-up connector、后台 worker/调度、跨 archive 持久化、最终二次补偿自动归档和非题图素材族远端补偿终态归档。warnings 均来自 openpyxl 对 `datetime.utcnow()` 的弃用提示，不影响本轮 final audit 链路。
