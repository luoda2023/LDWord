# 第 50 步：Word XML/media Deep Repair Projection/Actions 服务化记录
日期：2026-07-06

## 目标

在第 49 步把 Word XML/media deep repair 的 artifact、Markdown、history record builder 下沉到 `question_library.py` 后，本步骤继续迁移仍留在 `AssetsPanel` 的 deep repair 行投影和动作规则。

本步骤迁移的是无副作用 UI 数据投影：
- 根据 file recovery center entries 生成 deep repair entries
- 查找 latest deep repair record
- 合并未记录/已记录状态字段
- 生成 DOCX、relationship、media、rollback 状态标签
- 生成 tooltip
- 生成行级动作按钮定义

## 新增服务 API

- `question_figure_library_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_entries`
- `question_figure_master_subscription_drift_batch_failure_recovery_word_xml_media_deep_repair_actions`

同步补齐：
- `src/services/material_assets/__init__.py` 聚合导出
- `question_library.py` 旧私有 alias
- `AssetsPanel` 本地 wrapper 兼容
- `tests/test_material_asset_services.py` entries/actions 行为测试和 alias 断言

## 职责变化

`question_library.py` 现在负责：
- 复用 file recovery center entries 作为上游候选
- 只在 file recovery center 进入 `analysis_attention_required` 或已有 deep repair record 时浮出行
- 为未记录项设置 `deep_repair_required`、relationship/media required/not-required、rollback pending 等状态
- 为已记录项读取 latest deep repair record 中的状态、计数、manifest path
- 输出面板可直接消费的 label、tooltip、action tuple

`AssetsPanel` 现在只保留：
- 调用服务函数拿 rows/actions
- 渲染表格
- 响应按钮动作
- 执行真实 DOCX deep repair、manifest 落盘、history append、metadata 回填和 UI 刷新

## 为什么这样拆

deep repair 的行投影原来留在面板里，导致 UI 文件继续承载大量治理状态判断。第 49 步只拆掉了 artifact/record 构造，本步骤继续把“哪些行该显示、显示什么状态、按钮是什么”也变成可测试服务逻辑。

这样拆以后：
- deep repair 治理链路在 service 层更完整
- 面板里不再重复理解 latest record schema
- entries/actions 可以在不启动 Qt 的情况下覆盖未记录、已记录、按钮动作和 label
- 下一步可以继续拆 profile metadata 回填或 action dispatch，而不会再被 row projection 牵住

## 测试覆盖

扩展 `tests/test_material_asset_services.py::test_material_asset_service_builds_subscription_drift_queue_and_triage_records`：
- 未记录 deep repair entry 会在 file recovery center 为 `analysis_attention_required` 时浮出
- 未记录 entry 的状态为 `deep_repair_required`
- media repair required 会映射为 `media_deep_repair_required`
- 未记录且有 DOCX target 时 actions 为 `execute_deep_repair` 与 `locate_file_center`
- 已记录 entry 能合并 latest deep repair record 的 id、状态、计数和 manifest 字段
- 已记录 entry 的状态 label 为 `completed`
- 已记录 actions 为 `locate_manifest`
- `material_assets` 聚合导出与 `question_library` 旧私有 alias 保持兼容

## 当前剩余边界

本步骤没有迁移：
- deep repair 的真实 DOCX 修复执行
- JSON/Markdown manifest 文件写入
- history append
- profile metadata 回填
- archive save
- UI 刷新与按钮事件分发

这些仍属于 `AssetsPanel` 的副作用编排职责。

后续第 51 步可考虑：
- 把 deep repair metadata 回填解析/字段映射继续下沉为服务函数
- 或将 non-question asset family recovery 的 projection/artifact/record 分批迁出，避免 `AssetsPanel` 后半段继续膨胀
