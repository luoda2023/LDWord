# 高层场景能力矩阵 N2.336 考试题目图片素材库跨包主数据订阅漂移冲突批量失败恢复 Word XML 关系媒体深修复回滚 Connector 闭环（2026-06-22）

## 1. 本轮定位

N2.335 已经把“没有历史 DOCX 时只能阻断”的缺口推进为历史 DOCX 生成接入和 Word media rewrite repair execution。本轮 N2.336 承接其后一个更深层缺口：当已有旧 DOCX 存在 `word/document.xml`、`word/_rels/document.xml.rels` 与 `word/media/*` 不一致时，不能只停留在扫描和登记，必须提供可执行的深修复、二次扫描验证、manifest 记录和回滚来源锚点。

本轮闭合的对象是考试题目图片素材库的跨包主数据订阅漂移冲突批量失败恢复链路。它覆盖“已有 DOCX 关系仍在但媒体缺失”“图片 relationship 未被正文引用”“媒体文件成为孤儿文件”等高频 Word XML/media 风险。它不把非题目图片素材族、签章/附件/通用素材族的跨归档治理一并声明完成。

## 2. 新增能力

- 新增 `question_figure_asset_library_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_table`，位置接在文件恢复中心和历史 DOCX 修复之后、远程写回之前。
- 新增 action：`question_figure_library_cross_package_master_subscription_drift_conflict_batch_failure_recovery_word_xml_relationship_media_deep_repair_rollback_connector`。
- 新增 artifact 类型：`question_figure_master_subscription_drift_batch_failure_recovery_word_xml_relationship_media_deep_repair_rollback_connector`。
- 新增 artifact 目录：`artifacts/subscription_drift_word_xml_media_deep_repairs`。
- 新增深修复执行器：先调用 Word XML/media scanner 做 pre-scan，再打开 `.docx` zip 包，按扫描结果修复 `.rels` 和 `word/media/*`，最后 post-scan 验证。
- 新增 rollback connector 信息：manifest 中写入 `rollback_source_path`，保留原始 DOCX 作为回滚锚点，不覆盖源文件。
- 新增 metadata 回写：深修复状态、relationship 状态、media 状态、rollback 状态、DOCX 目标数、修复 DOCX 数、缺失媒体修复数、孤儿媒体移除数、manifest 路径和 next step。

## 3. 深修复边界

本轮深修复执行器覆盖四类问题：

- `missing_media_paths`：relationship 指向的 `word/media/*` 文件缺失时，从当前归档素材库中可用本地图片补写到原目标路径。
- `orphan_media_paths`：`word/media/*` 存在但没有 relationship 引用时，从输出副本中剔除。
- `missing_relationship_ids`：`document.xml` 引用了不存在的 relationship id，且有本地图片可用时，新增 image relationship 并写入对应媒体文件。
- `unreferenced_relationship_ids`：存在 image relationship 但正文未引用时，删除该 relationship，并清理其媒体输出副本。

本轮不直接修改原始 DOCX；所有修复写入 `.deep-repair.docx` 输出副本。无法解析、无本地图片可用于补写、或 post-scan 仍不一致时，状态进入 `deep_repair_attention_required`，由后续人工或二次补偿 connector 接管。

## 4. UI 与控件一致性

新表格纳入 AssetsPanel 既有 `QTableWidget` QSS 选择器，沿用统一边框、字号、选中态、表头、行高和按钮 variant。场景配置后续新增控件也应沿用模板管理和素材管理的控件契约：按钮用既有 variant，输入框和选择器用统一 stylesheet，表格不单独发明视觉语言。

这里的重点不是多一个表格，而是让场景能力矩阵里的“扫描 -> 修复 -> 回滚 -> 记录 -> 再扫描 -> metadata/report 消费”使用同一套 UI 与事实来源。

## 5. 状态与链路

- `deep_repair_required`：文件恢复中心发现 XML/media 需要修复，且存在 DOCX 目标。
- `deep_repair_completed`：输出副本 post-scan 为 `xml_media_consistent`。
- `relationship_deep_repair_verified`：post-scan relationship 状态一致。
- `media_deep_repair_verified`：post-scan media 状态一致。
- `rollback_snapshot_written`：manifest 已记录原始 DOCX 路径和输出副本路径。
- `word_xml_relationship_media_deep_repair_verified`：本轮 deep repair 的 next step，表示该批次可进入后续跨素材族或远程写回治理。

## 6. 代码与测试落点

- `src/ui/panels/assets_panel.py`：新增 deep repair 表格、刷新链、行操作、record/artifact helper、DOCX zip 修复执行器、metadata 回写。
- `tests/test_assets_panel_architecture.py`：新增缺失媒体 DOCX 的真实 zip 破坏与修复测试，验证 pre-scan、post-scan、manifest、rollback source 和 metadata。
- `src/config/scene_product_readiness.py`：新增 deep repair rollback connector evidence，并把剩余缺口推进为非题目图片素材族跨归档恢复治理。
- `src/config/scene_product_maturity_upgrade_audit.py`：同步新 remaining gap 的 domain 映射。
- `tests/test_scene_product_maturity_upgrade_audit.py`：锁定新增 evidence 和新 remaining gap。

## 7. 本轮仍未闭合

N2.336 后，考试题目图片素材库的 Word XML relationship/media 深修复首片已经闭合。剩余缺口上移为：

- pack：`advanced question asset library cross-package asset master data subscription drift conflict batch failure recovery non-question asset family cross-archive recovery governance UI`
- family：`advanced asset library cross-package asset master data subscription drift conflict batch failure recovery non-question asset family cross-archive recovery governance UI`

后续应把同类恢复治理扩展到非题目图片素材族，例如签章、Logo、附件证明、封面图、二维码、资格材料等，并明确它们与题目图片素材库在 source/asset_id、路径候选、替换审计、回滚粒度和跨归档恢复策略上的差异。

## 8. 当前验证

- `python -m py_compile src/ui/panels/assets_panel.py tests/test_assets_panel_architecture.py src/config/scene_product_readiness.py src/config/scene_product_maturity_upgrade_audit.py tests/test_scene_product_maturity_upgrade_audit.py`
- `pytest -q tests/test_assets_panel_architecture.py -k "word_xml_media_deep_repair or historical_docx_repair or file_recovery_center"`：4 passed。
- `pytest -q tests/test_assets_panel_architecture.py -k "batch_failure_queue"`：2 passed。
- `pytest -q tests/test_scene_product_maturity_upgrade_audit.py`：4 passed。
- `pytest -q tests/test_assets_panel_architecture.py -k "cross_package_asset_master"`：11 passed。
- `pytest -q tests/test_scene_matrix_dashboard.py tests/test_scene_matrix_drilldown.py tests/test_release_shell.py`：21 passed。
- `python scripts/verify_scene_matrix_release_gate.py`：passed，全部 0 issues。
- `pytest -q tests/test_assets_panel_architecture.py`：103 passed，4 warnings。
- `pytest -q`：1509 passed，8 warnings。
- 已清理 `artifacts/subscription_drift_historical_docx_repairs`、`artifacts/subscription_drift_word_media_rewrites`、`artifacts/subscription_drift_worker_monitors`、`artifacts/subscription_drift_worker_queues`、`artifacts/subscription_drift_trace_repairs`、`artifacts/subscription_drift_recovery_reports`、`artifacts/remote_writeback_manifests`，最终文件数均为 0。
