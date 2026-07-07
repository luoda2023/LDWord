# 高层场景能力矩阵 N2.352 考试题目图片素材库跨包主数据订阅漂移冲突批量失败恢复非题图素材族修复历史 Word 输出远端冲突裁决重放失败补偿授权快照后续 Connector 闭环

日期：2026-06-23

## 1. 定位

N2.351 已经把 retry/replay failure compensation execution 推进到 Dead Letter/final audit 首片：执行结果能够被前台 `Audit` 消费，并把无法自动补偿的项归档为 dead-letter、authorization refresh follow-up 或 remote snapshot follow-up。

N2.352 继续闭合 final audit 之后的两个可继续治理入口：授权刷新与远端快照复核。当前不声明真实 OAuth/SSO 登录、外部授权刷新服务、远端快照重新拉取、后台 worker 或最终二次补偿自动归档已经完成；本轮只承诺 final audit 中的 `authorization_refresh` 与 `remote_snapshot_review` 项可以从前台进入可审计的后续 Connector 交接记录，并把该事实写入 manifest、metadata、表格状态与成熟度矩阵。

## 2. 本轮闭环

- final audit 记录存在且包含 authorization/snapshot 后续项时，非题图素材族恢复表格显示 `Connector` 与 `Manifest`。
- `Connector` 消费最新 final audit record，不新建第二套事实源。
- authorization refresh 项写入 `authorization_refresh_connector_pending`，路由为 `authorization_refresh_connector`，动作标记为 `open_authorization_refresh_connector_and_retry_replay`。
- remote snapshot review 项写入 `remote_snapshot_governance_pending`，路由为 `remote_snapshot_governance`，动作标记为 `refresh_remote_snapshot_and_reopen_conflict_governance`。
- 纯 dead-letter final audit 不显示 Connector，继续只保留 `Manifest`，避免把人工归档项误算成可自动后续治理项。
- follow-up connector manifest 独立写入 `artifacts/subscription_drift_non_question_asset_family_word_output_remote_conflict_decision_retry_replay_failure_compensation_followup_connectors`。
- profile metadata 回写 follow-up connector status、id、item count、authorization count、remote snapshot count 与 manifest path。
- follow-up connector 记录后，表格状态变为 `followup`，动作收敛为 `Manifest`，并阻止重复 Connector、重复 Audit、重复 Execute 和重复 Queue。

## 3. 链路变化

N2.352 后链路变为：

```text
... -> Failure Queue -> Execute -> Handoff -> Final Audit
                                                |
                                                v
                              Authorization/Snapshot Follow-up Connector -> Manifest
```

这一步把 final audit 中“仍需继续治理”的授权和远端快照项转成可审计 handoff，不再让 audited 状态成为新的悬空终点。它也保持边界诚实：dead-letter 人工归档项不会被误推进为 connector；authorization/snapshot follow-up 只承诺交接、路由、manifest 和 metadata 已经闭合，真实后台自动处理仍属于下一阶段。

## 4. 矩阵口径

新增 evidence：

- `question asset per-question asset library cross-package master subscription drift conflict batch failure recovery non-question asset family repaired historical Word output remote conflict decision retry replay failure compensation authorization snapshot followup connector UI bridge`

剩余 gap 推进为：

- pack：`advanced question asset library cross-package asset master data subscription drift conflict batch failure recovery non-question asset family repaired historical Word output remote conflict decision retry replay failure compensation terminal archive worker UI`
- family：`advanced asset library cross-package asset master data subscription drift conflict batch failure recovery non-question asset family repaired historical Word output remote conflict decision retry replay failure compensation terminal archive worker UI`

这个口径表示 authorization/snapshot follow-up connector UI 已从 L5 blocker 中退场；后续优先级应转向 terminal archive worker，即把 dead-letter、授权刷新、远端快照治理后的最终状态统一归档、跨 archive 持久化、可调度、可恢复，并与非题图素材族远端补偿终态审计合流。

## 5. 控件样式约束

场景配置中的后续控件仍必须保持与模板管理/素材管理规定的样式一致：

- 表格、状态列、动作按钮继续复用既有 AssetsPanel QSS、按钮 variant 与紧凑表格布局。
- `Connector`、`Manifest` 这类动作按钮只表达明确命令，不引入新的视觉语言或解释型大卡片。
- manifest path、metadata path、counts、status 等只进入已有表格行、状态 label 与 artifact，不在场景配置页另造一套控件语义。
- 后续 terminal archive worker UI 也应沿用相同控件体系：队列/归档表、状态标签、动作按钮、只读 manifest drilldown、必要的 confirmation guard，而不是独立做一套不兼容的场景面板样式。

## 6. 落点

- `src/ui/panels/assets_panel.py`：新增 follow-up connector 输出目录、record finder、items 派生、artifact/record 构造、metadata 回写、append 入口、handler action、状态标签、按钮策略、manifest 优先级和表格投影。
- `tests/test_assets_panel_architecture.py`：新增 final audit -> authorization/snapshot follow-up connector 的专项覆盖，验证 Connector 动作、manifest、metadata、状态推进、重复保护和纯 dead-letter 边界。
- `src/config/scene_product_readiness.py`：将 authorization/snapshot follow-up connector UI bridge 移入 evidence，并把剩余 gap 推进为 terminal archive worker UI。
- `src/config/scene_product_maturity_upgrade_audit.py`：同步 terminal archive worker gap 的 domain 映射。
- `tests/test_scene_product_maturity_upgrade_audit.py`：同步 evidence 和 gap 断言。

## 7. 当前验证

- `python -m py_compile src/ui/panels/assets_panel.py`：通过。
- `python -m py_compile src/ui/panels/assets_panel.py tests/test_assets_panel_architecture.py`：通过。
- `pytest -q tests/test_assets_panel_architecture.py -k "non_question_asset_family_compensation"`：`1 passed, 104 deselected`。
- `pytest -q tests/test_assets_panel_architecture.py -k "non_question_asset_family_recovery_governance or non_question_asset_family_compensation"`：`2 passed, 103 deselected`。
- `python -m py_compile src/config/scene_product_readiness.py src/config/scene_product_maturity_upgrade_audit.py tests/test_scene_product_maturity_upgrade_audit.py`：通过。
- `pytest -q tests/test_scene_product_maturity_upgrade_audit.py`：`4 passed`。
- `python scripts/verify_scene_matrix_release_gate.py`：通过，全部 `0 issues`。
- `pytest -q tests/test_assets_panel_architecture.py`：`105 passed, 4 warnings`。
- `pytest -q`：`1511 passed, 8 warnings`。

验证后结论：N2.352 已经把 authorization/snapshot follow-up connector UI 从剩余 L5 blocker 中移出。当前仍保留的明确非本轮缺口是 terminal archive worker：需要把 dead-letter、authorization refresh、remote snapshot governance 后的最终状态统一归档、跨 archive 持久化，并与非题图素材族远端补偿终态审计合流。warnings 均来自 openpyxl 对 `datetime.utcnow()` 的弃用提示，不影响本轮 follow-up connector 链路。
