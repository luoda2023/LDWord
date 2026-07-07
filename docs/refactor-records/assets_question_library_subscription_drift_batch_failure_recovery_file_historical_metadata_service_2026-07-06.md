# 题图订阅漂移失败恢复：文件恢复中心与历史 DOCX 修复 metadata 服务化记录

## 本步目标

继续收束第五步的结构健康问题：把 `AssetsPanel` 中仍然直接维护的 file recovery center 与 historical DOCX repair metadata 回填规则下沉到 `src/services/material_assets/question_library.py`。

本步不改变真实执行链路：DOCX 扫描、文件写入、history append、archive 保存、UI 刷新仍由面板编排。服务层只负责可测试的纯数据逻辑：

- 从 history record 解析受影响素材项。
- 生成可回填到 `AssetItem.metadata` 的 patch。
- 按 `source` + `asset_id` 匹配本地 asset payload。
- 返回更新后的 payload 列表与是否发生更新。

## 新增服务边界

### File recovery center

新增服务 API：

- `question_figure_master_subscription_drift_batch_failure_recovery_file_recovery_center_source_asset_pairs`
- `question_figure_master_subscription_drift_batch_failure_recovery_file_recovery_center_metadata_patch`
- `question_figure_master_subscription_drift_batch_failure_recovery_file_recovery_center_payloads_with_metadata`

它们承接原面板内的回填规则，包括：

- file recovery center 状态与记录 id。
- Word XML relationship 与 word/media consistency 状态。
- DOCX target / checked / missing relationship / unreferenced relationship / missing media / orphan media 计数。
- manifest JSON / Markdown 路径。
- archive id / name。
- `master_subscription_drift_next_step`。

### Historical DOCX repair

新增服务 API：

- `question_figure_master_subscription_drift_batch_failure_recovery_historical_docx_repair_items_from_record`
- `question_figure_master_subscription_drift_batch_failure_recovery_historical_docx_repair_source_asset_pairs`
- `question_figure_master_subscription_drift_batch_failure_recovery_historical_docx_repair_metadata_patch`
- `question_figure_master_subscription_drift_batch_failure_recovery_historical_docx_repair_payloads_with_metadata`

它们承接原面板内的历史 DOCX 修复回填规则，包括：

- historical DOCX repair 状态、记录 id、signature。
- intake 状态与 word media rewrite repair 状态。
- generated / repaired DOCX 计数。
- asset image / missing asset image 计数。
- generated DOCX、rewrite repaired DOCX、manifest JSON / Markdown 路径。
- archive id / name。
- `master_subscription_drift_next_step`。

## 面板收束

`src/ui/panels/assets_panel.py` 保留原私有 wrapper 名称以兼容现有调用点，但函数体变为薄转发：

- 调用服务层 `payloads_with_metadata`。
- 如果 `updated=True`，再把结果写回 `profile.asset_items`。
- 不再在面板内维护两套长字段映射表。

这样 UI 层仍负责 profile mutation 的边界动作，服务层负责字段规则与匹配规则。

## 导出与兼容

本步同步补齐：

- `src/services/material_assets/question_library.py` 的公开函数。
- `_question_...` 私有兼容 alias。
- `src/services/material_assets/__init__.py` 聚合导出。

新增测试覆盖聚合入口与私有 alias，避免后续重构时出现“函数存在但入口不可用”的断裂。

## 验收口径

本步完成后需要通过：

- `py_compile` 覆盖 `question_library.py`、`__init__.py`、`assets_panel.py` 与相关测试。
- `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`
- `tests/test_assets_panel_architecture.py` 中 file recovery / historical DOCX / deep repair 相关架构守门。
- material asset / question library / subscription drift 聚焦测试。
- `scripts/engineering_gate.py`

## 下一步建议

继续沿同一原则推进：只把纯数据、纯投影、纯 record/payload 构造下沉到 service；真实文件写入、外部 IO、用户交互和 archive 保存留在面板或更明确的 orchestrator 边界。下一批优先看仍在面板内维护大量 metadata 回填字段的 subscription drift recovery 后续链路，尤其是已经具备稳定 record schema 的部分。
