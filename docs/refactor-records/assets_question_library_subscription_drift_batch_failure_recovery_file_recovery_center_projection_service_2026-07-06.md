# 第 45 步：订阅漂移批量失败恢复 File Recovery Center 投影服务化记录
日期：2026-07-06

## 目标

在第 43、44 步完成 durable worker monitor 投影、artifact、record 服务化之后，本步继续向下游推进到 file recovery center。

本步只迁移“可纯计算”的投影部分：
- 从 worker queue / monitor 记录解析 DOCX target
- 生成 file recovery center signature 和 record id
- 查找已写入的 file recovery center history record
- 生成面板行的 pending / recorded 状态
- 生成行级 actions
- 从已写入记录解析 recovery items

暂不迁移带副作用的逻辑：
- 本地 DOCX 解包和 XML / relationship / media 扫描
- JSON / Markdown manifest 写入
- history append
- archive save
- profile metadata 回填
- UI 定位、刷新、弹窗

## 新增服务 API

- `question_figure_master_subscription_drift_word_media_docx_targets_from_record`
- `question_figure_master_subscription_drift_batch_failure_recovery_file_recovery_center_signature`
- `question_figure_master_subscription_drift_batch_failure_recovery_file_recovery_center_record_id`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_file_recovery_center_record_for`
- `question_figure_library_master_subscription_drift_batch_failure_recovery_file_recovery_center_entries`
- `question_figure_master_subscription_drift_batch_failure_recovery_file_recovery_center_actions`
- `question_figure_master_subscription_drift_batch_failure_recovery_file_recovery_center_items_from_record`

同步补齐：
- `src/services/material_assets/__init__.py` 聚合导出
- `question_library.py` 旧私有 alias
- `AssetsPanel` 本地兼容 wrapper
- `tests/test_material_asset_services.py` 服务链路断言和 alias 断言

## 职责边界

service 现在负责：
- 基于 durable worker monitor 结果决定 file recovery center 行是否可进入分析
- 基于 worker queue 中的 DOCX targets 推导待扫描文件清单
- 生成稳定 signature / record id
- 在历史记录中查找最新 file recovery center 记录
- 将 pending 状态投影为 `pending_analysis` / `blocked_missing_docx_targets`
- 将 recorded 状态投影为已分析的关系状态、媒体一致性状态、DOCX 计数
- 生成面板所需 actions

`AssetsPanel` 继续负责：
- 触发真实 DOCX 扫描
- 写入 file recovery center manifest
- 构造包含扫描结果的最终 history record
- 将记录追加到 profile history
- 回填 profile metadata
- 保存 archive 并刷新 UI

## 为什么这样拆

file recovery center 处在 durable worker monitor 的下游，既依赖上游治理状态，又会触碰本地 DOCX 文件。为了避免 service 过早承担文件系统副作用，本步先把“面板应该展示哪一行、这行是不是已处理、下一步按钮是什么”抽出来。

这个拆法能让结构先健康起来：
- 面板不再手写 file recovery center 行投影
- service 测试可以不依赖真实 DOCX 文件
- 后续迁移 artifact / record builder 时已有稳定入口
- 真实扫描仍留在面板边界内，不扩大本步风险

## 测试覆盖

扩展 `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`：
- pending file recovery center entry
- recorded file recovery center entry
- DOCX target parser
- signature / record id
- record lookup
- actions
- items parser

扩展公共 API 暴露测试：
- `material_assets` 聚合导出
- `question_library` public function
- `question_library` 旧私有 alias

## 后续建议

第 46 步建议继续处理 file recovery center 的 artifact / record builder：
- 抽出 artifact id / payload / markdown 构造
- 抽出 history record builder
- 保持真实 DOCX 扫描与 manifest 写入仍在 panel

第 47 步再评估 DOCX 扫描函数是否适合移动到独立 `word_docx_recovery` 服务；这一步需要更细的文件系统测试和 fixture。
