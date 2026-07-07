# 高层场景能力矩阵 N2.343 考试题目图片素材库跨包主数据订阅漂移冲突批量失败恢复非题图素材族修复历史 Word 输出远端 Connector 冲突治理闭环

## 1. 本轮定位

N2.342 已把 adopted repaired DOCX 打包为正式输出/远端写回 handoff，但仍停在 pending connector 状态。本轮 N2.343 补上 remote connector conflict governance：handoff 后前台提供 `Connector`，真实执行 HTTP JSON POST，上传 repaired DOCX 内容、sha256、文件名、大小和幂等键；对 401/403、409/412 和其他失败做明确归类；当远端返回冲突时，前台提供 `Govern` 并记录冲突治理计划。

## 2. 新增能力

- 新增 remote connector execution action：`asset_library_cross_package_master_subscription_drift_conflict_batch_failure_recovery_non_question_asset_family_repaired_historical_word_output_remote_connector_execution`。
- 新增 conflict governance action：`asset_library_cross_package_master_subscription_drift_conflict_batch_failure_recovery_non_question_asset_family_repaired_historical_word_output_remote_connector_conflict_governance`。
- 非题图素材族链路推进为：`Record -> Execute -> Verify -> Rewrite -> Adopt -> Writeback -> Connector -> Govern -> Manifest`。
- Connector 从当前素材 metadata 读取 `writeback_url/remote_writeback_url/...`，因此远端地址可在配置侧更新后被重试消费。
- Connector payload 包含 formal DOCX 的 base64 内容、sha256、文件名、大小、row idempotency key 和整体 connector idempotency key。
- HTTP 结果归类：
  - 2xx：`connector_success`
  - 401/403：`connector_permission_required`
  - 409/412：`connector_remote_conflict`
  - 缺 endpoint、缺正式输出 DOCX、网络/其他 HTTP 错误：阻断或失败状态
- Connector 生成 JSON/Markdown manifest，记录 endpoint、HTTP status、attempted/uploaded/blocked docx count、响应预览与错误摘要。
- Connector metadata 回写 status、endpoint、HTTP status、manifest path、idempotency key 和 uploaded count。
- 冲突治理记录写入 manual-review 计划，声明可选方向为 `overwrite_remote`、`keep_remote_upload_new_version`、`abandon_local`。

## 3. 当前边界

本轮完成真实 connector 执行与冲突治理入口，不声明完成最终冲突裁决：

- 尚未执行 overwrite remote / keep remote upload new version / abandon local 的具体裁决动作。
- 尚未拉取非题图素材族远端当前 DOCX 快照并做内容级 diff。
- 尚未接入非题图素材族远端失败队列、批量事务、回滚和二次补偿。
- 权限失败已归类，可通过更新授权后重试；但企业级审批/续期 callback 的非题图专项流尚未展开。

下一缺口推进为：

- pack：`advanced question asset library cross-package asset master data subscription drift conflict batch failure recovery non-question asset family repaired historical Word output remote conflict decision execution UI`
- family：`advanced asset library cross-package asset master data subscription drift conflict batch failure recovery non-question asset family repaired historical Word output remote conflict decision execution UI`

## 4. 代码与测试落点

- `src/ui/panels/assets_panel.py`：新增非题图素材族 remote connector execution、manifest、metadata 回写、冲突治理记录和 UI actions。
- `tests/test_assets_panel_architecture.py`：扩展非题图素材族链路测试，覆盖 connector 成功上传、base64 DOCX payload、409 冲突、`Govern` 动作和冲突治理 metadata。
- `src/config/scene_product_readiness.py`：新增 remote connector conflict governance evidence，并把剩余 gap 推进到 remote conflict decision execution。
- `src/config/scene_product_maturity_upgrade_audit.py` 与 `tests/test_scene_product_maturity_upgrade_audit.py`：同步新 gap 域映射和断言。

## 5. 当前验证

- `python -m py_compile src/ui/panels/assets_panel.py tests/test_assets_panel_architecture.py src/config/scene_product_readiness.py src/config/scene_product_maturity_upgrade_audit.py tests/test_scene_product_maturity_upgrade_audit.py`：通过。
- `pytest -q tests/test_assets_panel_architecture.py -k "non_question_asset_family_recovery_governance"`：1 passed，103 deselected。
- `pytest -q tests/test_scene_product_maturity_upgrade_audit.py`：4 passed。
- `python scripts/verify_scene_matrix_release_gate.py`：通过，0 issues。
- `pytest -q tests/test_assets_panel_architecture.py -k "cross_package_asset_master or non_question_asset_family_recovery_governance or docx_xml_media_scan or word_xml_media_deep_repair"`：13 passed，91 deselected。
- `pytest -q tests/test_assets_panel_architecture.py`：104 passed，4 warnings。
- `pytest -q`：1510 passed，8 warnings。

本轮已完成语法、成熟度、release gate、素材面板重点/全量回归和全量测试验证。当前明确保留的下一缺口是 `non-question asset family repaired historical Word output remote conflict decision execution UI`。
